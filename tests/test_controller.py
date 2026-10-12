import importlib.util
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import time
import uuid
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('controller',Path(__file__).resolve().parents[1]/'hypr-ccv/scripts/controller.py')
ccv=importlib.util.module_from_spec(spec); spec.loader.exec_module(ccv)

class IsolationTests(unittest.TestCase):
    def test_environment_has_private_profiles_and_bus(self):
        state={'id':'run1','directory':'/private/run1','signature':'sandbox','display':'wayland-1','bus':'unix:path=/private/bus'}
        with patch.dict(os.environ,{'HOME':'/real/home','DISPLAY':':0','SSH_AUTH_SOCK':'/real/auth','DBUS_SESSION_BUS_ADDRESS':'unix:path=/real/bus'}):
            env=ccv.session_env(state)
        self.assertEqual(env['HOME'],'/private/run1/home')
        self.assertEqual(env['HYPRLAND_INSTANCE_SIGNATURE'],'sandbox')
        self.assertEqual(env['DBUS_SESSION_BUS_ADDRESS'],state['bus'])
        self.assertNotIn('DISPLAY',env); self.assertNotIn('SSH_AUTH_SOCK',env)

    def test_pid_reuse_is_not_alive(self):
        with patch.object(ccv,'identity',return_value='new'):
            self.assertFalse(ccv.alive({'pid':123,'start':'old'}))

    def test_missing_state_fails_without_host_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError): ccv.load(Path(tmp))

    def test_instance_override_rejected(self):
        for args in [('-i','parent'),('-iparent',),('--instance=parent',)]:
            with self.assertRaises(RuntimeError): ccv.hypr({'signature':'sandbox'},*args)

    def test_pid_selection_not_newest_directory(self):
        instances=[{'instance':'wrong','wl_socket':'wayland-3','pid':2}, {'instance':'right','wl_socket':'wayland-1','pid':1}]
        with patch.dict(os.environ,{'CC_PARENT_SIG':'right'}), patch.object(ccv,'run',return_value=json.dumps(instances)), patch.object(Path,'is_socket',return_value=True):
            self.assertEqual(ccv.parent_instance()['pid'],1)

    def test_ambiguous_parent_rejected(self):
        with patch.dict(os.environ,{},clear=True), patch.object(ccv,'run',return_value='[{"instance":"a"},{"instance":"b"}]'):
            with self.assertRaises(RuntimeError): ccv.parent_instance()

    def test_stop_does_not_signal_reused_or_unowned_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            state={'id':'ours','directory':tmp,'phase':'ready','processes':{'hyprland':{'pid':12345,'start':'old'}}}
            (root/'state.json').write_text(json.dumps(state))
            with patch.object(ccv,'scoped_processes',return_value={}), patch.object(ccv,'identity',return_value='new'), patch.object(ccv.os,'kill') as kill:
                ccv.stop(root); kill.assert_not_called()
            self.assertFalse((root/'state.json').exists())
            self.assertTrue((root/'last-session.json').exists())

    def test_stop_collects_child_spawned_by_shutdown_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); runtime=root/'runtime'; runtime.mkdir()
            ready=root/'ready'; childfile=root/'child'
            state={'id':uuid.uuid4().hex,'directory':tmp,'phase':'ready','processes':{}}
            code="""import os,signal,subprocess,sys,time
from pathlib import Path
def shutdown(*args):
    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    Path(sys.argv[2]).write_text(str(child.pid))
    sys.exit(0)
signal.signal(signal.SIGTERM,shutdown)
Path(sys.argv[1]).touch()
time.sleep(60)
"""
            env={**os.environ,'CCV_SESSION_ID':state['id'],'XDG_RUNTIME_DIR':str(runtime)}
            process=subprocess.Popen([sys.executable,'-c',code,str(ready),str(childfile)],env=env)
            try:
                deadline=time.monotonic()+3
                while not ready.exists() and time.monotonic()<deadline: time.sleep(.02)
                self.assertTrue(ready.exists())
                state['processes']['app']={'pid':process.pid,'start':ccv.identity(process.pid)}
                (root/'state.json').write_text(json.dumps(state))
                ccv.stop(root)
                self.assertTrue(childfile.exists())
                self.assertIsNone(ccv.identity(int(childfile.read_text())))
                self.assertFalse((root/'state.json').exists())
            finally:
                if process.poll() is None: process.kill()
                process.wait(timeout=3)

    def test_installer_preserves_foreign_dangling_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp); registry=home/'.agents/skills'; registry.mkdir(parents=True)
            destination=registry/'hypr-ccv'; destination.symlink_to('/missing/foreign-checkout/hypr-ccv')
            env={**os.environ,'HOME':tmp,'CODEX_HOME':str(home/'.codex')}
            setup=Path(__file__).resolve().parents[1]/'setup.sh'
            result=subprocess.run([str(setup),'--sandbox-only'],env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(os.readlink(destination),'/missing/foreign-checkout/hypr-ccv')

    def test_installer_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp); env={**os.environ,'HOME':tmp,'CODEX_HOME':str(home/'.codex')}
            setup=Path(__file__).resolve().parents[1]/'setup.sh'
            subprocess.run([str(setup),'--sandbox-only'],env=env,check=True,capture_output=True)
            skill=home/'.agents/skills/hypr-ccv'; inode=skill.lstat().st_ino
            subprocess.run([str(setup),'--sandbox-only'],env=env,check=True,capture_output=True)
            self.assertEqual(skill.lstat().st_ino,inode)
            self.assertTrue((home/'.local/bin/hypr-ccv').resolve().is_file())

    def test_pointer_coordinates_do_not_wrap(self):
        module=ccv.pointer_module(); client=module.RFBClient.__new__(module.RFBClient)
        client.width=640; client.height=480
        from unittest.mock import Mock
        client.sock=Mock()
        for x,y in [(-1,0),(65536,1),(640,0),(0,480)]:
            with self.assertRaises(ValueError): client.pointer(1,x,y)
        client.sock.sendall.assert_not_called()

if __name__=='__main__': unittest.main()
