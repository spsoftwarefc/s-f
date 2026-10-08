"""SF-09 isolated execution boundary and receipt tests, no network or secrets."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from sf.execution import ExecutionError, execute_check, OUTPUT_LIMIT
from sf.profile import ProfileError


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError((args, result.stderr))
    return result.stdout.strip()


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, 'init', '-q')
        git(self.root, 'config', 'user.email', 'test@example.invalid')
        git(self.root, 'config', 'user.name', 'Local')
        (self.root / 'README.md').write_text('base', encoding='utf8')
        git(self.root, 'add', 'README.md')
        git(self.root, 'commit', '-qm', 'base')
        self.profile = {'schemaVersion':1, 'project':{'id':'local-project'},
                        'commands':{'check':{'argv':[sys.executable,'-c','print("ok")'],
                                             'cwd':'.','risk':'build','timeoutSeconds':5,'network':False}}}
        (self.root / 'records').mkdir()
        self.save()

    def save(self):
        (self.root / 'profile.json').write_text(json.dumps(self.profile),encoding='utf8')

    def run_check(self, **options):
        return execute_check(self.root, 'profile.json', 'check', **options)

    def test_success_receipt_is_observation_not_approval(self):
        r=self.run_check(receipt_out='records/first.json')
        self.assertEqual(r['result']['outcome'],'success')
        self.assertEqual(r['result']['exitCode'],0)
        self.assertEqual(r['stdout']['text'],'ok\n')
        self.assertEqual(r['schemaVersion'],1)
        self.assertFalse(r['ciVerified'])
        self.assertFalse(r['evidenceVerified'])
        self.assertFalse(r['accepted'])
        self.assertEqual(r['repository']['before']['commit'],git(self.root,'rev-parse','HEAD'))
        self.assertEqual(r['environment']['networkIsolation'],'not-enforced')
        self.assertEqual(r['profileSha256'],hashlib.sha256((self.root/'profile.json').read_bytes()).hexdigest())
        self.assertEqual(json.loads((self.root/'records/first.json').read_text()),r)

    def test_execution_is_not_implicit_in_profile_validation(self):
        self.profile['commands']['check']['argv']=[sys.executable,'-c','open("effect", "w").write("side")']
        self.save()
        from sf.profile import read_profile
        read_profile(self.root/'profile.json',root=self.root)
        self.assertFalse((self.root/'effect').exists())
        self.run_check()
        self.assertEqual((self.root/'effect').read_text(),'side')

    def test_explicit_argument_vector_never_shell_interpolated(self):
        self.profile['commands']['check']['argv']=[sys.executable,'-c','import sys;print(sys.argv[1])','$(touch injected); $HOME']
        self.save()
        r=self.run_check()
        self.assertEqual(r['stdout']['text'],'$(touch injected); $HOME\n')
        self.assertFalse((self.root/'injected').exists())

    def test_nonzero_exit_retained_without_success(self):
        self.profile['commands']['check']['argv']=[sys.executable,'-c','import sys;print("bad",file=sys.stderr);sys.exit(13)']
        self.save()
        r=self.run_check(receipt_out='records/fail.json')
        self.assertEqual(r['result']['outcome'],'failed')
        self.assertEqual(r['result']['exitCode'],13)
        self.assertEqual(r['stderr']['text'],'bad\n')
        self.assertTrue((self.root/'records/fail.json').exists())

    def test_timeout_is_recorded_and_stops_process(self):
        self.profile['commands']['check']['argv']=[sys.executable,'-c','import time;time.sleep(30)']
        self.profile['commands']['check']['timeoutSeconds']=1
        self.save()
        start=time.monotonic()
        r=self.run_check()
        self.assertEqual(r['result']['outcome'],'timeout')
        self.assertLess(time.monotonic()-start,5)

    def test_cancellation_records_explicit_outcome(self):
        self.profile['commands']['check']['argv']=[sys.executable,'-c','import time;time.sleep(30)']
        self.save()
        cancel=threading.Event()
        timer=threading.Timer(0.25,cancel.set)
        timer.start()
        try:
            r=self.run_check(cancel_event=cancel)
        finally:
            timer.join()
        self.assertEqual(r['result']['outcome'],'cancelled')

    def test_bounded_output_and_truncation_not_silently_complete(self):
        self.profile['commands']['check']['argv']=[sys.executable,'-c','import sys;sys.stdout.write("x"*120000);sys.stderr.write("y"*120000)']
        self.save()
        r=self.run_check()
        self.assertEqual(r['result']['outcome'],'success')
        for stream in ('stdout','stderr'):
            self.assertEqual(r[stream]['bytesObserved'],120000)
            self.assertEqual(r[stream]['bytesRetained'],OUTPUT_LIMIT)
            self.assertTrue(r[stream]['truncated'])

    def test_redaction_and_environment_filter(self):
        self.profile['commands']['check']['argv']=[sys.executable,'-c',
            'import os; print(os.getenv("SF09_PRIVATE_SENTINEL", "absent")); print("SECRET_TEST_123456")']
        self.save()
        with patch.dict(os.environ,{'SF09_PRIVATE_SENTINEL':'SECRET_TEST_123456'}):
            r=self.run_check(redact_env=['SF09_PRIVATE_SENTINEL'])
        self.assertEqual(r['stdout']['text'],'absent\n[REDACTED]\n')
        self.assertNotIn('SECRET_TEST_123456',json.dumps(r))
        self.assertEqual(r['environment']['redactedNames'],['SF09_PRIVATE_SENTINEL'])

    def test_known_token_pattern_redacted(self):
        token='ghp_'+'A'*28
        self.profile['commands']['check']['argv']=[sys.executable,'-c',f'print("{token}")']
        self.save()
        r=self.run_check()
        self.assertEqual(r['stdout']['text'],'[REDACTED]\n')
        self.assertEqual(r['argv'][-1],'print("[REDACTED]")')

    def test_undeclared_check_blocks_without_executing(self):
        with self.assertRaisesRegex(ExecutionError,'not declared'):
            execute_check(self.root,'profile.json','missing')
        self.assertFalse((self.root/'effect').exists())

    def test_risk_categories_block_unauthorized_effects(self):
        for risk in ('external','mutating'):
            with self.subTest(risk=risk):
                self.profile['commands']['check']['risk']=risk
                self.profile['commands']['check']['argv']=[sys.executable,'-c','open("effect","w").write("bad")']
                self.save()
                with self.assertRaisesRegex(ExecutionError,'unsupported risk'):
                    self.run_check()
                self.assertFalse((self.root/'effect').exists())

    def test_network_declared_requires_explicit_acknowledgement(self):
        self.profile['commands']['check']['network']=True
        self.save()
        with self.assertRaisesRegex(ExecutionError,'allow-network'):
            self.run_check()
        r=self.run_check(allow_network=True)
        self.assertTrue(r['environment']['networkDeclared'])
        self.assertEqual(r['environment']['networkIsolation'],'not-enforced')

    def test_invalid_profile_and_unsafe_cwd(self):
        self.profile['commands']['check']['cwd']='../outside'
        self.save()
        with self.assertRaises(ProfileError):
            self.run_check()
        self.profile['commands']['check']['cwd']='linked'
        self.save()
        with tempfile.TemporaryDirectory() as other:
            try:
                (self.root/'linked').symlink_to(other,target_is_directory=True)
            except OSError:
                # The platform lacks symlink privileges: still exercise absent cwd.
                pass
            with self.assertRaises(ProfileError):
                self.run_check()

    def test_bad_profile_path_and_outside_receipt(self):
        for path in ('../secret.json','/tmp/out.json','evil\\path'):
            with self.subTest(path=path):
                with self.assertRaises(ExecutionError):
                    execute_check(self.root,path,'check')
                with self.assertRaises(ExecutionError):
                    self.run_check(receipt_out=path)

    def test_receipt_is_exclusive_and_non_overwriting(self):
        r=self.run_check(receipt_out='records/out.json')
        content=(self.root/'records/out.json').read_bytes()
        self.profile['commands']['check']['argv']=[sys.executable,'-c','open("effect","w").write("bad")']
        self.save()
        with self.assertRaises(ExecutionError):
            self.run_check(receipt_out='records/out.json')
        self.assertFalse((self.root/'effect').exists())
        self.assertEqual(content,(self.root/'records/out.json').read_bytes())

    def test_does_not_execute_missing_command_binary(self):
        self.profile['commands']['check']['argv']=['sf09-absent-program-6cf801']
        self.save()
        r=self.run_check()
        self.assertEqual(r['result']['outcome'],'spawn-error')
        self.assertFalse(r['ciVerified'])

    def test_dirty_repo_state_survives(self):
        (self.root/'unrelated.dat').write_bytes(b'keep')
        self.run_check()
        self.assertEqual((self.root/'unrelated.dat').read_bytes(),b'keep')

    def test_redaction_name_validation(self):
        with self.assertRaises(ExecutionError):
            self.run_check(redact_env=['-danger'])

    def test_profile_file_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            foreign=Path(other)/'foreign.json'
            foreign.write_text(json.dumps(self.profile))
            target=self.root/'linked.json'
            try:
                target.symlink_to(foreign)
            except OSError:
                target.write_text('{"schemaVersion":999}')
            with self.assertRaises((ExecutionError,ProfileError)):
                execute_check(self.root,'linked.json','check')

    def test_source_dirt_is_detected_even_when_head_is_identical(self):
        self.profile['commands']['check']['argv']=[sys.executable,'-c',
            'open("README.md","w").write("changed without commit")']
        self.save()
        r=self.run_check()
        self.assertTrue(r['repository']['sourceChangedDuringExecution'])
        self.assertFalse(r['repository']['postExecutionIdentityUnavailable'])
        self.assertEqual(r['repository']['before']['commit'],r['repository']['after']['commit'])

    def test_pre_cancel_is_nonexecuting(self):
        self.profile['commands']['check']['argv']=[sys.executable,'-c',
            'open("unexpected", "w").write("wrong")']
        self.save()
        stopped=threading.Event()
        stopped.set()
        with self.assertRaisesRegex(ExecutionError,'before dispatch'):
            self.run_check(cancel_event=stopped)
        self.assertFalse((self.root/'unexpected').exists())

    def test_git_identity_loss_keeps_failure_receipt(self):
        self.profile['commands']['check']['argv']=[sys.executable,'-c',
            'import os; os.rename(".git", ".git.broken")']
        self.save()
        r=self.run_check()
        self.assertEqual(r['result']['outcome'],'indeterminate')
        self.assertTrue(r['repository']['postExecutionIdentityUnavailable'])
        self.assertTrue(r['repository']['sourceChangedDuringExecution'])
        self.assertFalse(r['accepted'])

    def test_child_process_is_killed_on_timeout(self):
        if os.name == 'nt':
            # Windows Job Object behavior is qualified by the native PR matrix.
            self.test_timeout_is_recorded_and_stops_process()
            return
        self.profile['commands']['check']['argv']=[sys.executable,'-c',
            'import subprocess,sys,time;'
            'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);'
            'open("child.pid","w").write(str(p.pid));'
            'time.sleep(30)']
        self.profile['commands']['check']['timeoutSeconds']=1
        self.save()
        r=self.run_check()
        self.assertEqual(r['result']['outcome'],'timeout')
        pid_file=self.root/'child.pid'
        self.assertTrue(pid_file.exists())
        child=int(pid_file.read_text())
        # A reaped dead child's /proc entry disappears; a zombie may still be
        # present temporarily but cannot run or survive as an active process.
        state=Path(f'/proc/{child}/stat')
        if state.exists():
            self.assertEqual(state.read_text().split(') ')[1][0], 'Z')


if __name__ == '__main__':
    unittest.main()
