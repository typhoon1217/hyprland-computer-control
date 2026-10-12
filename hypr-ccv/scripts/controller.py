#!/usr/bin/env python3
"""Isolated Hyprland GUI sessions. Python stdlib; no main-session input."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid

SCRIPTS = Path(__file__).resolve().parent


def run(argv, env=None, timeout=10):
    return subprocess.check_output(argv, env=env, text=True, stderr=subprocess.PIPE, timeout=timeout).strip()


def identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()
        return None if fields[0] == 'Z' else fields[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def alive(process):
    return identity(process['pid']) == process['start'] and process['start'] is not None


def save(path, data):
    staged = path.with_suffix('.new')
    staged.write_text(json.dumps(data, indent=2) + '\n')
    staged.replace(path)


def root_path():
    control = os.environ.get('CCV_CONTROL_ROOT')
    if control:
        root = Path(control)
        if not root.is_absolute() or root.parent.name != 'cc-vdisplay' or root.is_symlink() or root.stat().st_uid != os.getuid():
            raise RuntimeError('Invalid session control root')
        return root
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    if not runtime.is_dir() or runtime.stat().st_uid != os.getuid():
        raise RuntimeError('XDG_RUNTIME_DIR must be a live runtime directory owned by this user')
    name = os.environ.get('CC_SESSION', 'default')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', name):
        raise RuntimeError('CC_SESSION must contain 1–48 letters, digits, underscores or hyphens')
    root = runtime / 'cc-vdisplay' / name
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or root.stat().st_uid != os.getuid():
        raise RuntimeError('Session directory must be owned by this user, not a symlink')
    root.chmod(0o700)
    return root


def parent_instance():
    env = os.environ.copy()
    env.setdefault('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
    instances = json.loads(run(['hyprctl', 'instances', '-j'], env))
    sig = os.environ.get('CC_PARENT_SIG', os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'))
    display = os.environ.get('WAYLAND_DISPLAY')
    if sig:
        instances = [i for i in instances if i['instance'] == sig]
    elif display:
        instances = [i for i in instances if i['wl_socket'] == Path(display).name]
    if len(instances) != 1:
        raise RuntimeError('Select one parent using CC_PARENT_SIG or WAYLAND_DISPLAY; refusing to guess')
    parent = instances[0]
    path = Path(parent['wl_socket'])
    if not path.is_absolute():
        path = Path(env['XDG_RUNTIME_DIR']) / path
    if not path.is_socket():
        raise RuntimeError('Parent Wayland socket is unavailable')
    return {**parent, 'socket': str(path)}


def session_env(state):
    env = os.environ.copy()
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE', 'DBUS_SESSION_BUS_ADDRESS',
                'SSH_AUTH_SOCK', 'GNUPGHOME', 'SESSION_MANAGER', 'QT_QPA_PLATFORMTHEME'):
        env.pop(key, None)
    base = Path(state['directory'])
    env.update(HOME=str(base / 'home'), XDG_CONFIG_HOME=str(base / 'home/.config'),
               XDG_STATE_HOME=str(base / 'home/.local/state'), XDG_CACHE_HOME=str(base / 'home/.cache'),
               XDG_DATA_HOME=str(base / 'home/.local/share'), XDG_RUNTIME_DIR=str(base / 'runtime'),
               CCV_SESSION_ID=state['id'], CCV_CONTROL_ROOT=str(base.parent), QT_QPA_PLATFORM='wayland', GDK_BACKEND='wayland',
               MOZ_ENABLE_WAYLAND='1')
    if state.get('signature'):
        env['HYPRLAND_INSTANCE_SIGNATURE'] = state['signature']
        env['WAYLAND_DISPLAY'] = state['display']
    if state.get('bus'):
        env['DBUS_SESSION_BUS_ADDRESS'] = state['bus']
    return env


def load(root, require_ready=True):
    path = root / 'state.json'
    if not path.exists():
        raise RuntimeError('Sandbox is not running; use hypr-ccv start')
    state = json.loads(path.read_text())
    if require_ready:
        if state['phase'] != 'ready' or not alive(state['processes']['hyprland']):
            raise RuntimeError('Sandbox is stale or initializing; inspect status/doctor, then restart')
        matches = json.loads(run(['hyprctl', 'instances', '-j'], session_env(state)))
        if not any(i['pid'] == state['processes']['hyprland']['pid'] and
                   i['instance'] == state['signature'] and i['wl_socket'] == state['display'] for i in matches):
            raise RuntimeError('PID, instance signature and Wayland socket do not agree')
        if not (Path(state['directory']) / 'runtime' / state['display']).is_socket():
            raise RuntimeError('Sandbox Wayland socket is missing')
    return state


def hypr(state, *args):
    # Always inject the session selector. Prevent caller overrides.
    if any(a.startswith('-i') or a.startswith('--instance') for a in args):
        raise RuntimeError('Instance overrides are not accepted by sandbox IPC')
    return run(['hyprctl', '-i', state['signature'], *args], session_env(state))


def spawn(state, key, argv, env, root):
    log = Path(state['directory']) / 'logs' / f'{key}.log'
    with log.open('a') as output:
        process = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=output, start_new_session=True)
    state['processes'][key] = {'pid': process.pid, 'start': identity(process.pid)}
    save(root / 'state.json', state)
    return process


def scoped_processes(state):
    """Only current-UID processes with the exact run marker and private runtime."""
    expected_runtime = str(Path(state['directory']) / 'runtime')
    result = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            env = dict(item.split(b'=', 1) for item in (entry / 'environ').read_bytes().split(b'\0') if b'=' in item)
            if env.get(b'CCV_SESSION_ID') == state['id'].encode() and env.get(b'XDG_RUNTIME_DIR') == expected_runtime.encode():
                result[int(entry.name)] = identity(int(entry.name))
        except (OSError, ValueError):
            continue
    return result


def stop(root):
    if not (root / 'state.json').exists():
        print('Not running.')
        return
    state = load(root, require_ready=False)
    # Recheck within a deadline: termination handlers may spawn descendants.
    signaled=set()
    deadline=time.monotonic()+3
    while True:
        targets=scoped_processes(state)
        for pid,tick in targets.items():
            if tick is not None and identity(pid)==tick and (pid,tick) not in signaled:
                try: os.kill(pid,signal.SIGTERM)
                except ProcessLookupError: pass
                signaled.add((pid,tick))
        if not any(tick is not None and identity(pid)==tick for pid,tick in targets.items()):
            break
        if time.monotonic()>=deadline:
            break
        time.sleep(.05)
    for pid,tick in scoped_processes(state).items():
        if tick is not None and identity(pid)==tick:
            try: os.kill(pid,signal.SIGKILL)
            except ProcessLookupError: pass
    time.sleep(.1)
    if any(tick is not None and identity(pid)==tick for pid,tick in scoped_processes(state).items()):
        raise RuntimeError('Owned processes remain; state retained for doctor/retry')
    state['phase'] = 'stopped'
    save(root / 'last-session.json', state)
    (root / 'state.json').unlink()
    print(f"Stopped owned session; profiles, logs and captures retained at {state['directory']}")


def wait_for(check, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.1)
    raise RuntimeError('Readiness deadline exceeded')


def pointer_module():
    spec = importlib.util.spec_from_file_location('cc_pointer', SCRIPTS / 'cc-click.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def start(root, resolution, count):
    if (root / 'state.json').exists():
        load(root)
        print('Already running; stop before changing outputs or config.')
        return
    match = re.fullmatch(r'(\d{3,4})x(\d{3,4})', resolution)
    if not match or not all(320 <= int(v) <= 8192 for v in match.groups()) or not 1 <= count <= 4:
        raise RuntimeError('Use a 320–8192 pixel resolution and 1–4 outputs')
    for tool in ('Hyprland', 'hyprctl', 'wtype', 'grim', 'dbus-daemon'):
        if not shutil.which(tool):
            raise RuntimeError(f'Missing {tool}; install documented dependencies first')
    version = run(['Hyprland', '--version-json'], {**os.environ, 'XDG_RUNTIME_DIR':str(root.parents[1])})
    if not re.search(r'0\.(?:5[6-9]|[6-9][0-9])\.', version):
        raise RuntimeError('Lua sandbox config requires Hyprland 0.56+; see version output: ' + version)
    parent = parent_instance()
    directory = Path(tempfile.mkdtemp(prefix='run-', dir=root))
    for name in ('home/.config/hypr', 'home/.local/state', 'home/.cache', 'home/.local/share', 'runtime', 'logs', 'captures'):
        (directory / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    state = {'id': uuid.uuid4().hex, 'directory': str(directory), 'phase':'initializing', 'parent':parent,
             'processes':{}, 'resolution':resolution, 'outputs':[], 'hyprlandVersion':json.loads(version)}
    save(root / 'state.json', state)
    try:
        env = session_env(state)
        bus = f"unix:path={directory}/runtime/bus"
        spawn(state, 'dbus', ['dbus-daemon','--session','--nofork',f'--address={bus}'], env, root)
        wait_for(lambda:(directory / 'runtime/bus').is_socket(), 5)
        state['bus'] = bus
        env = session_env(state)
        config = directory / 'home/.config/hypr/hyprland.lua'
        config.write_text((SCRIPTS / 'headless.lua').read_text())
        env.update(WAYLAND_DISPLAY=parent['socket'], AQ_DRM_DEVICES='/dev/null')
        child = spawn(state, 'hyprland', ['Hyprland','--config',str(config)], env, root)
        def find_instance():
            if child.poll() is not None:
                raise RuntimeError('Hyprland exited; inspect ' + str(directory / 'logs/hyprland.log'))
            try:
                return next((i for i in json.loads(run(['hyprctl','instances','-j'],env)) if i['pid']==child.pid), None)
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                return None
        instance = wait_for(find_instance)
        state.update(signature=instance['instance'], display=instance['wl_socket'])
        if Path(state['display']).name != state['display'] or not state['display'].startswith('wayland-'):
            raise RuntimeError('Unexpected Wayland socket name')
        save(root / 'state.json', state)
        env = session_env(state)
        wait_for(lambda:(directory / 'runtime' / state['display']).is_socket())
        width, height = map(int, match.groups())
        bootstrap = json.loads(hypr(state, '-j','monitors'))
        for index in range(count):
            before = {m['name'] for m in json.loads(hypr(state, '-j','monitors'))}
            hypr(state,'output','create','headless')
            output = wait_for(lambda:next((m['name'] for m in json.loads(hypr(state,'-j','monitors')) if m['name'] not in before),None))
            state['outputs'].append(output)
        lines = [f'hl.monitor({{ output = {json.dumps(output)}, mode = "{resolution}@60.00", position = "{index*width}x0", scale = 1 }})' for index,output in enumerate(state['outputs'])]
        lines += [f'hl.monitor({{ output = {json.dumps(m["name"])}, disabled = true }})' for m in bootstrap]
        (directory / 'home/.config/hypr/monitors.lua').write_text('\n'.join(lines)+'\n')
        hypr(state, 'reload')
        def outputs_ready():
            monitors = json.loads(hypr(state, '-j','monitors'))
            return len(monitors)==count and all(m['name'] in state['outputs'] and m['width']==width and m['height']==height for m in monitors)
        wait_for(outputs_ready)
        if hypr(state,'configerrors').strip():
            raise RuntimeError('Sandbox config has errors: '+hypr(state,'configerrors'))
        if os.environ.get('CC_VNC','1')!='0':
            if not shutil.which('wayvnc'):
                raise RuntimeError('Missing wayvnc; use CC_VNC=0 for keyboard-only testing')
            state['vncSocket'] = str(directory / 'runtime/vnc.sock')
            spawn(state,'wayvnc',['wayvnc','-u','-o',state['outputs'][0],state['vncSocket']],env,root)
            wait_for(lambda:Path(state['vncSocket']).is_socket(),5)
            client = pointer_module().RFBClient(unix_socket=state['vncSocket'])
            client.close()
        # A real bounded screenshot proves that frame delivery works.
        run(['grim','-o',state['outputs'][0],str(directory/'captures/ready.png')],env,timeout=5)
        state['phase']='ready'
        save(root / 'state.json',state)
        print(json.dumps(state,indent=2))
    except BaseException:
        stop(root)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',nargs='?',default='help')
    parser.add_argument('args',nargs=argparse.REMAINDER)
    options=parser.parse_args()
    command,args=options.command,options.args
    if command in ('help','--help','-h'):
        print('hypr-ccv start [WIDTHxHEIGHT] [OUTPUTS] | status | stop | doctor\n'
              'run CMD... (detached) | exec CMD... (wait) | hypr ARGS... | env | sig | wl\n'
              'click X Y [--button right] | dblclick X Y | move X Y | drag SX SY DX DY | scroll X Y N\n'
              'type TEXT | key KEY | keys WTYPE-ARGS... | shot [PATH] [OUTPUT] | copy TEXT | paste\n'
              'vnc (private Unix socket) | snapshot [PATH] | record PATH SECONDS [OUTPUT]\n'
              'CC_SESSION selects an isolated session; HOME/XDG/D-Bus are private. No ydotool.')
        return 0
    root=root_path()
    if command in ('start','stop','doctor'):
        with (root/'lifecycle.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if command=='start':
                start(root,args[0] if args else os.environ.get('CC_RESOLUTION','1920x1080'),int(args[1]) if len(args)>1 else int(os.environ.get('CC_OUTPUTS','1')))
            else:
                stop(root)
        return 0
    state=load(root)
    env=session_env(state)
    if command=='status':
        print(json.dumps(state,indent=2))
    elif command in ('env','sig','wl','vnc'):
        if command=='env':
            for key,value in env.items():
                if key in ('HOME','XDG_CONFIG_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','XDG_DATA_HOME','XDG_RUNTIME_DIR','WAYLAND_DISPLAY','HYPRLAND_INSTANCE_SIGNATURE','DBUS_SESSION_BUS_ADDRESS','CCV_SESSION_ID','CCV_CONTROL_ROOT'):
                    print(f'export {key}={shlex.quote(value)}')
            print('unset DISPLAY SSH_AUTH_SOCK GNUPGHOME SESSION_MANAGER')
        else:
            print(state[{'sig':'signature','wl':'display','vnc':'vncSocket'}[command]])
    elif command in ('run','exec'):
        if not args: raise RuntimeError('Provide a command')
        if command=='run':
            with (root/'lifecycle.lock').open('w') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                state=load(root)
                process=spawn(state,'app-'+uuid.uuid4().hex[:10],args,session_env(state),root)
                print(process.pid)
        else:
            return subprocess.run(args,env=env).returncode
    elif command=='hypr':
        print(hypr(state,*args))
    elif command in ('focus','spawn','cursor'):
        print(hypr(state,'dispatch',{'focus':'focuswindow','spawn':'exec','cursor':'movecursor'}[command],*args))
    elif command in ('type','key','keys'):
        run(['wtype',*(['-k'] if command=='key' else []),*args],env)
    elif command=='shot':
        path=Path(args[0]) if args else Path(state['directory'])/'captures'/f'{time.time_ns()}.png'
        output=args[1] if len(args)>1 else state['outputs'][0]
        run(['grim','-o',output,str(path)],env,timeout=5)
        print(path)
    elif command=='record':
        if len(args)<2 or not 1<=int(args[1])<=60:
            raise RuntimeError('record requires PATH and duration 1–60 seconds')
        output=args[2] if len(args)>2 else state['outputs'][0]
        frames=Path(tempfile.mkdtemp(prefix='record-',dir=Path(state['directory'])/'captures'))
        begin=time.monotonic()
        for frame in range(int(args[1])*2):
            run(['grim','-o',output,str(frames/f'{frame:03}.png')],env,timeout=5)
            time.sleep(max(0,begin+(frame+1)/2-time.monotonic()))
        run(['ffmpeg','-v','error','-y','-framerate','2','-i',str(frames/'%03d.png'),
             '-c:v','libx264','-pix_fmt','yuv420p',args[0]],env,timeout=30)
        print(args[0])
    elif command=='snapshot':
        data={'monitors':json.loads(hypr(state,'-j','monitors','all')),'clients':json.loads(hypr(state,'-j','clients')),'workspaces':json.loads(hypr(state,'-j','workspaces')),'configErrors':hypr(state,'configerrors')}
        text=json.dumps(data,indent=2)
        if args: Path(args[0]).write_text(text+'\n')
        else: print(text)
    elif command=='copy':
        subprocess.run(['wl-copy'],env=env,input=args[0] if args else sys.stdin.read(),text=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=5)
    elif command=='paste':
        print(run(['wl-paste',*args],env))
    elif command in ('click','dblclick','move','scroll','drag'):
        if not state.get('vncSocket'): raise RuntimeError('Pointer input requires CC_VNC=1 at startup')
        run([sys.executable,str(SCRIPTS/'cc-click.py'),'--unix-socket',state['vncSocket'],'double' if command=='dblclick' else command,*args],env)
    else:
        raise RuntimeError('Unknown command: '+command)
    return 0


if __name__=='__main__':
    os.umask(0o077)
    try:
        sys.exit(main())
    except (RuntimeError,OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        print(f'ERROR: {error}',file=sys.stderr)
        if isinstance(error,subprocess.CalledProcessError) and error.stderr:
            print(error.stderr.strip(),file=sys.stderr)
        sys.exit(1)
