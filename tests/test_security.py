"""SF-12 independently chosen negative cases for offline security observations."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sf.security import SecurityError, assess_security, read_policy, validate_policy
from sf.cli import main


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.git('init', '-q')
        self.git('config', 'user.email', 'security@example.invalid')
        self.git('config', 'user.name', 'Security Fixture')
        self.write('src/module.py', 'print("not a secret")\n')
        self.write('.github/workflows/check.yml', 'jobs:\n  check:\n    steps:\n      - uses: actions/checkout@'+('a'*40)+'\n')
        self.write('requirements.txt', 'package==1.2.3 --hash=sha256:'+('b'*64)+'\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'baseline')
        self.policy = {'schemaVersion': 1, 'owner': 'Security owner',
                       'candidateSha': self.git('rev-parse', 'HEAD'),
                       'secretPaths': ['src/**'], 'workflowPaths': ['.github/workflows/**'],
                       'requirementFiles': ['requirements.txt'], 'scannerEvidence': [], 'exceptions': []}

    def git(self, *args):
        p = subprocess.run(['git','-C',str(self.root),*args], capture_output=True, text=True, check=True)
        return p.stdout.strip()

    def write(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def scan(self, policy=None):
        return assess_security(self.root, policy or self.policy, today=date(2026, 10, 8))

    def test_clean_builtin_checks_do_not_imply_external_security(self):
        o = self.scan()
        self.assertEqual(o['status'], 'incomplete')
        self.assertEqual(o['coverage']['secrets'], 'locally-scanned')
        self.assertEqual(o['coverage']['actionPins'], 'locally-scanned')
        self.assertEqual(o['coverage']['pythonPins'], 'locally-scanned')
        self.assertIn('vulnerability:scanner-unavailable', o['unknowns'])
        self.assertFalse(o['securityQualified'])
        self.assertFalse(o['accepted'])

    def test_seeded_fake_github_secret_without_exposing_value(self):
        secret = 'ghp_'+'T'*32
        self.write('src/module.py', 'key='+secret+'\n')
        o = self.scan()
        self.assertEqual(o['status'], 'blocked')
        self.assertTrue(any(f['rule']=='github-token' for f in o['findings']))
        self.assertNotIn(secret, json.dumps(o))

    def test_seeded_fake_private_key(self):
        self.write('src/module.py','-----BEGIN PRIVATE KEY-----\n')
        self.assertEqual(self.scan()['status'], 'blocked')

    def test_seeded_fake_aws_key(self):
        self.write('src/module.py','AKIA'+'A'*16)
        self.assertIn('aws-access-id',[f['rule'] for f in self.scan()['findings']])

    def test_seeded_hardcoded_password(self):
        self.write('src/module.py', 'password = "ABCDEFGHIJKLMNOPQRST"')
        self.assertIn('credential-assignment',[f['rule'] for f in self.scan()['findings']])

    def test_unpinned_action_tag_detected(self):
        self.write('.github/workflows/check.yml','jobs:\n - uses: actions/checkout@v4\n')
        self.assertIn('action-missing-full-sha',[f['rule'] for f in self.scan()['findings']])

    def test_unpinned_action_dynamic_expression_detected(self):
        self.write('.github/workflows/check.yml','- uses: ${{ matrix.action }}\n')
        self.assertEqual(self.scan()['status'], 'blocked')

    def test_action_without_scalar_fails_closed(self):
        self.write('.github/workflows/check.yml','- uses: # unresolved expression\n')
        self.assertIn('action-missing-full-sha',[f['rule'] for f in self.scan()['findings']])

    def test_commented_requirement_hash_does_not_count(self):
        self.write('requirements.txt','package==1.2.3 # --hash=sha256:'+('b'*64)+'\n')
        self.assertEqual(self.scan()['status'], 'blocked')

    def test_local_action_allowed(self):
        self.write('.github/workflows/check.yml','- uses: ./my-local-action\n')
        self.assertNotIn('action-missing-full-sha',[f['rule'] for f in self.scan()['findings']])

    def test_requirement_without_hash(self):
        self.write('requirements.txt','requests==2.31.0\n')
        self.assertIn('requirement-missing-version-or-sha256',[f['rule'] for f in self.scan()['findings']])

    def test_unpinned_requirement(self):
        self.write('requirements.txt','requests>=2\n')
        self.assertIn('requirement-missing-version-or-sha256',[f['rule'] for f in self.scan()['findings']])

    def test_missing_configuration_is_not_clean(self):
        self.policy['secretPaths']=[]
        self.assertIn('secrets:not-configured',self.scan()['unknowns'])

    def test_no_matching_tracked_files_unknown(self):
        self.policy['secretPaths']=['absent/**']
        self.assertIn('secrets:no-matching-tracked-files',self.scan()['unknowns'])

    def test_symlink_scan_does_not_escape(self):
        outside = self.write('outside.txt','ghp_'+'Z'*32)
        self.write('src/link.py','example')
        self.git('add', '.')
        self.git('commit','-qm','add path')
        self.policy['candidateSha']=self.git('rev-parse','HEAD')
        (self.root/'src/link.py').unlink()
        try:
            (self.root/'src/link.py').symlink_to(outside)
        except (NotImplementedError, OSError):
            # A host without symlink privilege must not invent successful native
            # symlink coverage. Exercise the common path-rejection invariant.
            bad=copy.deepcopy(self.policy)
            bad['secretPaths']=['../outside']
            with self.assertRaises(SecurityError):
                validate_policy(bad)
            return
        o=self.scan()
        self.assertIn('secrets:unreadable-or-unsupported-file',o['unknowns'])

    def test_too_large_file_unknown(self):
        self.write('src/module.py','A'*(512*1024+1))
        self.assertIn('secrets:unreadable-or-unsupported-file',self.scan()['unknowns'])

    def test_dirty_worktree_is_reported(self):
        self.write('src/module.py','print("changed")')
        self.assertTrue(any(x.startswith('dirty-worktree:') for x in self.scan()['unknowns']))

    def test_candidate_drift_rejected(self):
        self.policy['candidateSha']='0'*40
        with self.assertRaisesRegex(SecurityError,'stale'):
            self.scan()

    def test_duplicate_json_key_rejected(self):
        path=self.write('policy.json','{"schemaVersion":1,"schemaVersion":1}')
        with self.assertRaisesRegex(SecurityError,'duplicate'):
            read_policy(path)

    def test_unsafe_glob_and_path_rejected(self):
        for value in ('../repo', 'src/*/file', 'src/../../foo', '/abs'):
            p=copy.deepcopy(self.policy)
            p['secretPaths']=[value]
            with self.subTest(value=value),self.assertRaises(SecurityError):
                validate_policy(p)

    def test_unknown_policy_field_rejected(self):
        self.policy['trustMe']=True
        with self.assertRaises(SecurityError):
            validate_policy(self.policy)

    def test_bool_version_rejected(self):
        self.policy['schemaVersion']=True
        with self.assertRaises(SecurityError):
            validate_policy(self.policy)

    def test_external_report_missing_unknown(self):
        self.policy['scannerEvidence']=[{'kind':'vulnerability','path':'evidence/vuln.json',
               'sha256':'0'*64,'maxAgeDays':14}]
        self.assertIn('vulnerability:evidence-unavailable',self.scan()['unknowns'])

    def report(self, kind, findings, days='2026-10-07T00:00:00Z', db=None):
        if db is None and kind=='vulnerability':
            db={'name':'fixture-db','revision':'fixture-2026-10-07'}
        d={'schemaVersion':1,'kind':kind,'candidateSha':self.policy['candidateSha'],
           'generatedAt':days,'tool':{'name':'synthetic-scanner','version':'1.0'},'database':db,
           'findings':findings}
        raw=(json.dumps(d,sort_keys=True)+'\n').encode()
        self.write('evidence/'+kind+'.json',raw.decode())
        self.policy['scannerEvidence'].append({'kind':kind,'path':'evidence/'+kind+'.json',
                    'sha256':hashlib.sha256(raw).hexdigest(),'maxAgeDays':30})

    def test_vulnerable_dependency_seed_fixture_blocks(self):
        self.report('vulnerability',[{'id':'OSV-FIXTURE-1','severity':'critical','path':'requirements.txt','rule':'vulnerable-version'}])
        o=self.scan()
        self.assertEqual(o['status'],'blocked')
        self.assertTrue(any(f['id']=='OSV-FIXTURE-1' for f in o['findings']))
        self.assertEqual(o['coverage']['vulnerability'],'present-unverified')

    def test_empty_vulnerability_report_not_authenticated(self):
        self.report('vulnerability',[])
        o=self.scan()
        self.assertFalse(o['externalScannerResultsAuthenticated'])
        self.assertFalse(o['securityQualified'])

    def test_expired_report_does_not_qualify(self):
        self.report('vulnerability',[{'id':'OSV-OLD','severity':'high','path':'requirements.txt','rule':'expired'}],days='2020-01-01T00:00:00Z')
        o=self.scan()
        self.assertEqual(o['coverage']['vulnerability'],'stale')
        self.assertIn('vulnerability:stale-report',o['unknowns'])

    def test_digest_tampered_unverified(self):
        self.report('static',[])
        self.write('evidence/static.json','{}')
        self.assertEqual(self.scan()['coverage']['static'],'mismatched')

    def test_license_report_violation_detected(self):
        self.report('license',[{'id':'LICENSE-ISSUE','severity':'high','path':'requirements.txt','rule':'unapproved-license'}])
        self.assertEqual(self.scan()['status'],'blocked')

    def test_static_report_violation_detected(self):
        self.report('static',[{'id':'STATIC-FAIL','severity':'medium','path':'src/module.py','rule':'unsafe-call'}])
        self.assertTrue(any(x['id']=='STATIC-FAIL' for x in self.scan()['findings']))

    def test_scanner_candidate_mismatch_rejected(self):
        self.report('static',[])
        path=self.root/'evidence/static.json'
        data=json.loads(path.read_text())
        data['candidateSha']='0'*40
        content=(json.dumps(data,sort_keys=True)+'\n')
        path.write_text(content)
        self.policy['scannerEvidence'][0]['sha256']=hashlib.sha256(content.encode()).hexdigest()
        self.assertEqual(self.scan()['coverage']['static'],'invalid')

    def test_exception_unverified_does_not_hide_finding(self):
        self.write('.github/workflows/check.yml','- uses: actions/checkout@v4')
        violation=self.scan()['findings'][0]
        self.policy['exceptions']=[{'findingId':violation['id'],'path':violation['path'],
                                  'owner':'security-lead','approvedBy':'team-lead',
                                  'reason':'temporary local test','expiresOn':'2026-10-09'}]
        o=self.scan()
        self.assertEqual(o['status'],'blocked')
        self.assertEqual(o['findings'][0]['exception'],'declared-unverified')
        self.assertFalse(o['exceptionsApproved'])

    def test_expired_exception_cannot_suppress(self):
        self.write('.github/workflows/check.yml','- uses: actions/checkout@v4')
        f=self.scan()['findings'][0]
        self.policy['exceptions']=[{'findingId':f['id'],'path':f['path'],'owner':'x',
                                  'approvedBy':'y','reason':'old','expiresOn':'2026-10-01'}]
        self.assertEqual(self.scan()['findings'][0]['exception'],'expired')

    def test_unmatched_exception_detected(self):
        self.policy['exceptions']=[{'findingId':'FAKE-123','path':'src/module.py','owner':'x',
                                  'approvedBy':'y','reason':'old','expiresOn':'2026-10-09'}]
        self.assertIn('exception:unmatched',self.scan()['unknowns'])

    def test_duplicate_exception_rejected(self):
        e={'findingId':'FAKE-123','path':'src/module.py','owner':'x','approvedBy':'y',
           'reason':'old','expiresOn':'2026-10-09'}
        self.policy['exceptions']=[e,copy.deepcopy(e)]
        with self.assertRaises(SecurityError):
            validate_policy(self.policy)

    def test_command_explicit_and_help_keeps_prior_commands(self):
        import contextlib
        import io
        tmp=io.StringIO()
        with contextlib.redirect_stdout(tmp):
            self.assertEqual(main(['security','assess','--root',str(self.root),'--policy',str(self.root/'missing.json')]),2)
        # A failed command does not run scanner or modify source.
        self.assertIn('src/module.py',self.git('ls-files'))


if __name__=='__main__':
    unittest.main()
