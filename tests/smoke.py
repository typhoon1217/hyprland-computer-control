#!/usr/bin/env python3
"""Opt-in live nested GUI smoke; leaves the parent layout/config untouched."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
import uuid

REPO=Path(__file__).resolve().parents[1]
CLI=REPO/'hypr-ccv/scripts/hypr-ccv'
env={**os.environ,'XDG_RUNTIME_DIR':os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'),'CC_SESSION':'smoke-'+uuid.uuid4().hex[:8]}
env.pop('CCV_CONTROL_ROOT',None)
instances=json.loads(subprocess.check_output(['hyprctl','instances','-j'],env=env,text=True))
if 'HYPRLAND_INSTANCE_SIGNATURE' not in env:
    assert len(instances)==1, 'select an explicit parent signature for live smoke'
    env['HYPRLAND_INSTANCE_SIGNATURE']=instances[0]['instance']

def run(*args):
    try: return subprocess.check_output([str(CLI),*args],env=env,text=True,stderr=subprocess.PIPE,timeout=45).strip()
    except subprocess.CalledProcessError as error: raise RuntimeError(error.stderr.strip()) from error
def parent_monitors():
    return [{key:m[key] for key in ('name','x','y','width','height','scale','transform')} for m in json.loads(subprocess.check_output(['hyprctl','-j','monitors'],env=env,text=True))]
def wait(check,seconds=10):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if check(): return
        time.sleep(.1)
    raise AssertionError('GUI readiness deadline exceeded')
before=parent_monitors()
config=Path.home()/'.config/hypr/monitors.lua'
checksum=hashlib.sha256(config.read_bytes()).hexdigest() if config.exists() else None
state=None
try:
    state=json.loads(run('start','1280x800','2'))
    assert len(state['outputs'])==2
    assert not Path(state['directory']).is_relative_to(Path.home())
    pid=int(run('run','quickshell','-p',str(REPO/'tests/gui-smoke.qml')))
    wait(lambda:any(c['pid']==pid and c['mapped'] for c in json.loads(run('hypr','-j','clients'))))
    logs=Path(state['directory'])/'logs'
    def app_log(): return '\n'.join(p.read_text() for p in logs.glob('app-*.log'))
    def rendered():
        clients=json.loads(run('hypr','-j','clients'))
        item=next((c for c in clients if c['pid']==pid),None)
        return item and ('READY='+'x'.join(map(str,item['size']))) in app_log()
    wait(rendered)
    wait(lambda:'IPC_MONITORS=2' in app_log())
    run('hypr','output','create','headless')
    wait(lambda:'IPC_MONITORS=3' in app_log())
    extra=next(m['name'] for m in json.loads(run('hypr','-j','monitors')) if m['name'] not in state['outputs'])
    run('hypr','output','remove',extra)
    wait(lambda:len(json.loads(run('hypr','-j','monitors')))==2)
    client=next(c for c in json.loads(run('hypr','-j','clients')) if c['pid']==pid)
    x=client['at'][0]+client['size'][0]//2
    y=client['at'][1]+client['size'][1]//2
    run('click',str(x),str(y+10))
    run('click',str(x),str(y-80))
    run('keys','-M','ctrl','-k','a','-m','ctrl')
    run('type','isolated-smoke')
    run('key','Return')
    logs=Path(state['directory'])/'logs'
    def app_log(): return '\n'.join(p.read_text() for p in logs.glob('app-*.log'))
    wait(lambda:'CLICK=1' in app_log() and 'INPUT=isolated-smoke' in app_log())
    run('copy','sandbox-only'); assert run('paste')=='sandbox-only'
    image=Path(state['directory'])/'captures/gui.png'; run('shot',str(image))
    assert image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    video=Path(state['directory'])/'captures/gui.mp4'; run('record',str(video),'3')
    assert video.stat().st_size>1000
    print(json.dumps({'session':env['CC_SESSION'],'inputVerified':True,'image':str(image),'video':str(video),'state':str(Path(state['directory']).parent/'last-session.json')},indent=2))
finally:
    run('stop')
    assert parent_monitors()==before,'parent geometry changed'
    assert checksum==(hashlib.sha256(config.read_bytes()).hexdigest() if config.exists() else None),'parent config changed'
    if state:
        assert not Path(state['runtimeAlias']).is_symlink(), 'private runtime alias remained'
        for process in state['processes'].values():
            stat=Path(f'/proc/{process["pid"]}/stat')
            if stat.exists(): assert stat.read_text().rsplit(') ',1)[1].split()[0]=='Z','owned process remained alive'
