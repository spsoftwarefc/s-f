"""SF-08: independently initialized, offline Git history fixtures."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from sf.work import WorkError, inspect_work, validate_order

ORDER_PATH = 'docs/factory/work-orders/DEMO.json'


def git(root, *args):
    cp = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
    if cp.returncode:
        raise AssertionError((args, cp.stderr))
    return cp.stdout.strip()


def write(root, path, content):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf8')


def commit(root, msg):
    git(root, 'add', '-A')
    git(root, 'commit', '-qm', msg)
    return git(root, 'rev-parse', 'HEAD')


def declaration(base, tree):
    return {'schemaVersion':1,'id':'DEMO','baseline':{'commit':base,'tree':tree},
            'objective':'Build deterministic assessment','nonGoals':['No external effect'],
            'allowedPaths':[ORDER_PATH,'src/demo.py','docs/guide.md','docs/proof.md'],
            'requirements':['R1'],'decisions':['D1'],
            'obligations':[{'id':'core','description':'source correctness','proofKinds':['independent-output']},
                           {'id':'docs','description':'docs preservation','proofKinds':['preservation-review','diff-review']}],
            'dependencies':[{'id':'baseline','kind':'git-ancestor','revision':base,'scope':'development'}],
            'structure':['src'], 'impact':['demo'],
            'budget':{'hostedRuns':1,'repairDiagnosticAfter':2,'network':'none','execution':'offline'},
            'externalEffects':['No deployment'],'proofs':{},'amendments':[]}


class WorkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, 'init', '-q', '-b', 'main')
        git(self.root, 'config', 'user.name', 'Local Test')
        git(self.root, 'config', 'user.email', 'local@example.invalid')
        write(self.root, 'README.md', 'base\n')
        self.base = commit(self.root, 'baseline')
        self.tree = git(self.root, 'rev-parse', 'HEAD^{tree}')
        git(self.root, 'checkout', '-qb', 'work')
        self.order = declaration(self.base, self.tree)

    def declare(self):
        write(self.root, ORDER_PATH, json.dumps(self.order, indent=2)+'\n')
        return commit(self.root, 'declare before implementation')

    def test_start_and_resume_are_read_only_and_do_not_run_commands(self):
        declare = self.declare()
        before = git(self.root, 'status', '--porcelain')
        result = inspect_work(self.root, ORDER_PATH, mode='start', base_ref='main')
        self.assertEqual(result['declarationCommit'], declare)
        self.assertTrue(result['developmentReady'])
        self.assertEqual(result['state'], 'specified')
        self.assertEqual(result['providerCI'], 'unknown')
        self.assertEqual(result['accepted'], 'unknown')
        self.assertFalse(result['externalEffectsAuthorized'])
        self.assertTrue(all(p['missing'] for p in result['obligations']))
        write(self.root, 'src/demo.py', 'print(1)\n')
        commit(self.root, 'implementation')
        write(self.root, 'unrelated.txt', 'keep this intact')
        resumed = inspect_work(self.root, ORDER_PATH, mode='resume', base_ref='main')
        self.assertIn('unrelated.txt', resumed['dirtyPaths'])
        self.assertIn('unrelated.txt', resumed['outOfScopePaths'])
        self.assertIn('OUT_OF_SCOPE_PATHS', resumed['blockers'])
        self.assertEqual((self.root/'unrelated.txt').read_text(), 'keep this intact')
        self.assertEqual(git(self.root, 'status','--porcelain').splitlines(), ['?? unrelated.txt'])
        self.assertEqual(before, '')

    def test_detect_implementation_preceding_declaration(self):
        write(self.root, 'src/demo.py', 'before order\n')
        commit(self.root, 'implementation first')
        self.declare()
        r = inspect_work(self.root, ORDER_PATH, mode='resume')
        self.assertIn('IMPLEMENTATION_PRECEDES_DECLARATION', r['blockers'])

    def test_reject_mixed_declaration_commit(self):
        write(self.root, 'src/demo.py', 'wrong\n')
        self.declare()
        r = inspect_work(self.root, ORDER_PATH, mode='start')
        self.assertIn('DECLARATION_NOT_ISOLATED', r['blockers'])

    def test_out_of_scope_commits_and_baseline_drift(self):
        self.declare()
        write(self.root, 'outside.py', 'bad\n')
        commit(self.root, 'out of scope')
        r = inspect_work(self.root, ORDER_PATH, mode='resume')
        self.assertIn('UNDECLARED_COMMIT_PATH:outside.py', r['blockers'])
        write(self.root, 'README.md', 'advance main\n')
        git(self.root, 'checkout', 'main')
        commit(self.root, 'advance base')
        git(self.root, 'checkout', 'work')
        r = inspect_work(self.root, ORDER_PATH, mode='resume', base_ref='main')
        self.assertIn('BASE_REF_DRIFT', r['blockers'])

    def test_dependency_unresolved_dev_blocks_external_does_not(self):
        future = 'f'*40
        self.order['dependencies'].append({'id':'future','kind':'git-ancestor','revision':future,'scope':'development'})
        self.order['dependencies'].append({'id':'external','kind':'external','revision':None,'scope':'external-effect'})
        self.declare()
        r = inspect_work(self.root, ORDER_PATH, mode='start')
        self.assertIn('DEVELOPMENT_DEPENDENCY_UNRESOLVED:future', r['blockers'])
        self.assertEqual(r['dependencyChecks'][-1]['status'],'unknown')
        self.assertNotIn('DEVELOPMENT_DEPENDENCY_UNRESOLVED:external', r['blockers'])

    def test_documentation_only_requires_explicit_proof_kinds(self):
        self.order['obligations']=[self.order['obligations'][0]]
        self.declare()
        write(self.root,'docs/guide.md','new doc')
        commit(self.root, 'documentation')
        self.assertIn('DOC_PROOF_KINDS_UNDECLARED',
                      inspect_work(self.root,ORDER_PATH,mode='resume')['blockers'])

    def test_amendment_requires_append_only_reason_and_isolation(self):
        self.declare()
        self.order['allowedPaths'].append('src/extra.py')
        self.order['amendments']=[{'reason':'needed an extra module'}]
        write(self.root,ORDER_PATH,json.dumps(self.order))
        amend = commit(self.root,'bounded amendment')
        write(self.root,'src/extra.py','ok')
        commit(self.root,'within amended scope')
        r=inspect_work(self.root,ORDER_PATH,mode='resume')
        self.assertEqual(r['amendmentCommits'],[amend])
        self.assertFalse(r['blockers'])
        self.order['allowedPaths'].append('src/later.py')
        write(self.root,ORDER_PATH,json.dumps(self.order))
        commit(self.root,'silent amendment')
        self.assertIn('AMENDMENT_REASON_MISSING_OR_REWRITTEN',
                      inspect_work(self.root,ORDER_PATH,mode='resume')['blockers'])

    def test_malformed_and_unsupported(self):
        self.assertRaises(WorkError, validate_order, {'schemaVersion':2})
        self.order['schemaVersion']=2
        self.assertRaisesRegex(WorkError,'unsupported', validate_order,self.order)
        self.order['schemaVersion']=1
        self.order['allowedPaths'].append('../escape')
        self.assertRaises(WorkError,validate_order,self.order)
        self.order['allowedPaths'].pop()
        self.order['accepted']='true'
        self.assertRaises(WorkError,validate_order,self.order)

    def test_uncommitted_order_cannot_start(self):
        write(self.root,ORDER_PATH,json.dumps(self.order))
        with self.assertRaisesRegex(WorkError,'not committed'):
            inspect_work(self.root,ORDER_PATH,mode='start')

    def test_dirty_order_blocks_but_preserves_edit(self):
        self.declare()
        path=self.root/ORDER_PATH
        path.write_text(path.read_text()+'\n', encoding='utf8')
        r=inspect_work(self.root,ORDER_PATH,mode='resume')
        self.assertIn('DIRTY_DECLARATION',r['blockers'])
        self.assertTrue(path.read_text().endswith('\n\n'))

    def test_proof_paths_only_prove_presence_not_verification(self):
        self.order['proofs']={'core':[{'kind':'independent-output','path':'docs/proof.md'}]}
        self.declare()
        write(self.root,'docs/proof.md','someone claims success')
        commit(self.root,'claim proof without external verification')
        result=inspect_work(self.root,ORDER_PATH,mode='resume')
        self.assertEqual(result['obligations'][0]['presentUnverified'],['independent-output'])
        self.assertEqual(result['obligations'][0]['verification'],'unknown')
        self.assertEqual(result['accepted'],'unknown')


if __name__=='__main__':
    unittest.main()
