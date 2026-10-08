"""SF-11: synthetic, isolated Git histories and independently predeclared oracles."""
import copy
import hashlib
import json
from unittest.mock import patch
import subprocess
import tempfile
import unittest
from pathlib import Path

from sf.assurance import AssuranceError, inspect_review, validate_packet, validate_plan, read_packet


def sha(data):
    return hashlib.sha256(data).hexdigest()


class AssuranceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'repo'; self.root.mkdir()
        self.git('init','-q')
        self.git('config','user.name','Fixture')
        self.git('config','user.email','fixture@example.test')
        self.write('README.md','baseline\n'); self.commit('baseline')
        self.baseline = self.git('rev-parse','HEAD')
        self.plan = {'schemaVersion':1,'requiredSelectors':['positive','negative','fault','temporal'],
            'cases':[
                {'id':'ok','selector':'positive','requirement':'R1','expected':'3','proofKind':'independent-output'},
                {'id':'reject','selector':'negative','requirement':'R1','expected':'invalid rejected','proofKind':'regression-reproducer'},
                {'id':'fault','selector':'fault','requirement':'R2','expected':'timeout terminates owned children','proofKind':'event-trace'},
                {'id':'restart','selector':'temporal','requirement':'R2','expected':'idempotent replay','proofKind':'event-trace'}]}
        self.write('plans/cases.json',json.dumps(self.plan,sort_keys=True)+'\n');self.commit('predeclare acceptance cases')
        self.plan_commit=self.git('rev-parse','HEAD')
        self.write('src/module.py','def total(x,y): return x+y\n')
        self.write('tests/test_feature.py','def test_product(): assert 1 + 2 == 3\n')
        for case in self.plan['cases']:
            self.write('proofs/'+case['id']+'.txt',case['expected']+'\n')
        self.commit('implementation evidence')
        self.head=self.git('rev-parse','HEAD');self.tree=self.git('rev-parse','HEAD^{tree}')
        self.packet = {
          'schemaVersion':1,'packageId':'F-1','baselineSha':self.baseline,
          'candidateSha':self.head,'candidateTree':self.tree,
          'planPath':'plans/cases.json','planCommit':self.plan_commit,
          'changedPaths':['plans/cases.json','src/module.py','tests/test_feature.py']+[f'proofs/{c["id"]}.txt' for c in self.plan['cases']],
          'observations':[{'id':c['id'],'status':'pass','evidencePath':f'proofs/{c["id"]}.txt',
                           'evidenceSha256':sha((self.root/f'proofs/{c["id"]}.txt').read_bytes())} for c in self.plan['cases']],
          'findings':[], 'uiAffected':False}

    def git(self,*args):
        p=subprocess.run(['git','-C',str(self.root),*args],capture_output=True,text=True,check=True)
        return p.stdout.strip()

    def write(self,path,value):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)

    def commit(self,msg):
        self.git('add','-A');self.git('commit','-q','-m',msg)

    def assess(self, packet=None):
        return inspect_review(self.root, self.packet if packet is None else packet)

    def test_complete_review_ready_but_not_acceptance(self):
        r=self.assess()
        self.assertTrue(r['reviewReady']);self.assertEqual(r['blockers'],[])
        self.assertFalse(r['accepted']);self.assertFalse(r['providerCIVerified'])
        self.assertEqual(r['proofStatus'],'candidate-recorded-unverified')
        self.assertEqual(len(r['testAdditions']),1)

    def test_readiness_restricted(self):
        r=inspect_review(self.root,self.packet,summary=True)
        self.assertNotIn('changedPaths',r)
        self.assertFalse(r['releaseQualified'])

    def test_malformed_packet_extra_fields(self):
        packet={**self.packet,'accepted':True}
        with self.assertRaises(AssuranceError): validate_packet(packet)

    def test_noncanonical_sha(self):
        packet={**self.packet,'candidateSha':'f'*39}
        with self.assertRaises(AssuranceError): validate_packet(packet)

    def test_duplicate_oracle_cases(self):
        plan=copy.deepcopy(self.plan);plan['cases'].append(plan['cases'][0])
        with self.assertRaises(AssuranceError): validate_plan(plan)

    def test_required_selector_missing(self):
        plan=copy.deepcopy(self.plan);plan['cases']=[plan['cases'][0]]
        with self.assertRaises(AssuranceError): validate_plan(plan)

    def test_wrong_head(self):
        packet={**self.packet,'candidateSha':'f'*40}
        self.assertIn('STALE_CANDIDATE_IDENTITY',self.assess(packet)['blockers'])

    def test_wrong_tree(self):
        packet={**self.packet,'candidateTree':'f'*40}
        self.assertIn('STALE_CANDIDATE_IDENTITY',self.assess(packet)['blockers'])

    def test_actual_diff_not_manifest(self):
        packet={**self.packet,'changedPaths':['plans/cases.json']}
        self.assertIn('DECLARED_DIFF_MISMATCH',self.assess(packet)['blockers'])

    def test_uncommitted_dirty_blocks(self):
        self.write('src/module.py','tampered')
        self.assertIn('DIRTY_WORKTREE_SOURCE',self.assess()['blockers'])

    def test_missing_case_blocks(self):
        packet=copy.deepcopy(self.packet);packet['observations'].pop()
        self.assertIn('INCOMPLETE_CASE_OBSERVATIONS',self.assess(packet)['blockers'])

    def test_missing_evidence_digest_blocks(self):
        packet=copy.deepcopy(self.packet);packet['observations'][0]['evidenceSha256']='a'*64
        self.assertIn('STALE_OR_MISSING_CASE_PROOF:ok',self.assess(packet)['blockers'])

    def test_failed_case_blocks(self):
        packet=copy.deepcopy(self.packet);packet['observations'][1]['status']='fail'
        self.assertIn('NONPASS_CASE:reject',self.assess(packet)['blockers'])

    def test_unknown_case_blocks(self):
        packet=copy.deepcopy(self.packet);packet['observations'][1]['status']='unknown'
        self.assertIn('NONPASS_CASE:reject',self.assess(packet)['blockers'])

    def test_unresolved_material_finding_blocks(self):
        packet=copy.deepcopy(self.packet)
        packet['findings']=[{'id':'BUG1','severity':'material','status':'open','rationale':'unhandled failure',
                             'evidencePath':'proofs/ok.txt','evidenceSha256':sha((self.root/'proofs/ok.txt').read_bytes())}]
        self.assertIn('UNRESOLVED_MATERIAL_FINDING:BUG1',self.assess(packet)['blockers'])

    def test_accepted_risk_is_not_self_approval(self):
        packet=copy.deepcopy(self.packet)
        packet['findings']=[{'id':'BUG1','severity':'blocker','status':'deferred','rationale':'operator not consulted',
                             'evidencePath':'proofs/ok.txt','evidenceSha256':sha((self.root/'proofs/ok.txt').read_bytes())}]
        self.assertIn('UNRESOLVED_MATERIAL_FINDING:BUG1',self.assess(packet)['blockers'])

    def test_resolved_finding_requires_matching_proof(self):
        packet=copy.deepcopy(self.packet)
        packet['findings']=[{'id':'BUG1','severity':'material','status':'resolved','rationale':'fixed in source',
                             'evidencePath':'proofs/ok.txt','evidenceSha256':'a'*64}]
        self.assertIn('UNVERIFIED_FINDING_RESOLUTION:BUG1',self.assess(packet)['blockers'])

    def test_ui_change_not_declared(self):
        self.write('app/page.tsx','export default () => <div>hi</div>\n');self.commit('visual change')
        p=copy.deepcopy(self.packet);p['candidateSha']=self.git('rev-parse','HEAD');p['candidateTree']=self.git('rev-parse','HEAD^{tree}');p['changedPaths'].append('app/page.tsx')
        self.assertIn('UI_IMPACT_UNDECLARED',self.assess(p)['blockers'])

    def test_ui_change_without_predeclared_ui_proof(self):
        self.write('app/page.tsx','export default () => <div>hi</div>\n');self.commit('visual change')
        p=copy.deepcopy(self.packet);p['candidateSha']=self.git('rev-parse','HEAD');p['candidateTree']=self.git('rev-parse','HEAD^{tree}');p['changedPaths'].append('app/page.tsx');p['uiAffected']=True
        self.assertIn('UI_PROOF_NOT_PREDECLARED',self.assess(p)['blockers'])

    def test_changed_test_oracle_is_control_change(self):
        self.write('tests/test_feature.py','def test_product(): assert True\n');self.commit('weaken expectation')
        p=copy.deepcopy(self.packet);p['candidateSha']=self.git('rev-parse','HEAD');p['candidateTree']=self.git('rev-parse','HEAD^{tree}')
        self.assertIn('CONTROL_CHANGE_EXTERNAL_ASSESSMENT_REQUIRED',self.assess(p)['blockers'])

    def test_changed_ci_gate_is_control_change(self):
        self.write('.github/workflows/check.yml','name: weakened\n');self.commit('add controlled workflow')
        p=copy.deepcopy(self.packet);p['candidateSha']=self.git('rev-parse','HEAD');p['candidateTree']=self.git('rev-parse','HEAD^{tree}');p['changedPaths'].append('.github/workflows/check.yml')
        self.assertIn('CONTROL_CHANGE_EXTERNAL_ASSESSMENT_REQUIRED',self.assess(p)['blockers'])

    def test_oracle_modified_after_predeclaration_fails(self):
        self.write('plans/cases.json',json.dumps({'schemaVersion':1,'requiredSelectors':['positive'],'cases':[self.plan['cases'][0]]})+'\n')
        self.commit('posthoc change to plan file')
        p=copy.deepcopy(self.packet);p['candidateSha']=self.git('rev-parse','HEAD');p['candidateTree']=self.git('rev-parse','HEAD^{tree}')
        self.assertIn('PREDECLARED_ORACLE_MODIFIED',self.assess(p)['blockers'])

    def test_plan_commit_later_than_implementation_blocks(self):
        p=copy.deepcopy(self.packet);p['planCommit']=self.head
        self.assertIn('PLAN_NOT_FIRST_AFTER_BASELINE',self.assess(p)['blockers'])

    def test_plan_path_cannot_leave_repo(self):
        p=copy.deepcopy(self.packet);p['planPath']='../cases.json'
        with self.assertRaises(AssuranceError):validate_packet(p)

    def test_untrusted_packet_duplicate_json_key(self):
        path=self.base/'bad.json';path.write_text('{"schemaVersion":1,"schemaVersion":1}')
        with self.assertRaises(AssuranceError):read_packet(path)

    def test_untrusted_symlinked_proof_rejected(self):
        # Symlinks are unsupported for evidence bytes even if the digest matches.
        self.write('proofs/new.txt','value\n');self.commit('other proof')
        p=copy.deepcopy(self.packet);p['candidateSha']=self.git('rev-parse','HEAD');p['candidateTree']=self.git('rev-parse','HEAD^{tree}');p['changedPaths'].append('proofs/new.txt')
        p['observations'][0]['evidencePath']='proofs/link.txt'
        self.write('proofs/link.txt','3\n')
        original = Path.is_symlink
        def pretend_link(path):
            return str(path).replace('\\', '/').endswith('/proofs/link.txt') or original(path)
        with patch.object(Path, 'is_symlink', pretend_link):
            self.assertIn('STALE_OR_MISSING_CASE_PROOF:ok',self.assess(p)['blockers'])

    def test_review_cli_returns_status_without_acceptance(self):
        from sf.cli import main
        path=self.base/'packet.json';path.write_text(json.dumps(self.packet))
        self.assertEqual(main(['review','--root',str(self.root),'--packet',str(path)]), 0)
        self.assertEqual(main(['readiness','--root',str(self.root),'--packet',str(path)]), 0)
        bad=copy.deepcopy(self.packet);bad['observations'][0]['status']='fail'
        path.write_text(json.dumps(bad))
        self.assertEqual(main(['review','--root',str(self.root),'--packet',str(path)]), 1)

    def test_case_evidence_untracked_cannot_promote(self):
        # Record has correct bytes but is untracked: source-boundness must fail.
        self.write('proofs/extra.txt','3\n')
        p=copy.deepcopy(self.packet);p['observations'][0]['evidencePath']='proofs/extra.txt'
        self.assertIn('STALE_OR_MISSING_CASE_PROOF:ok',self.assess(p)['blockers'])

    def test_path_traversal_refused(self):
        p=copy.deepcopy(self.packet);p['observations'][0]['evidencePath']='proofs/../../secret'
        with self.assertRaises(AssuranceError):validate_packet(p)

    def test_valid_json_packet_round_trip(self):
        path=self.base/'packet.json';path.write_text(json.dumps(self.packet))
        self.assertEqual(read_packet(path),self.packet)

    def test_manual_packet_is_not_evidence_of_provider_ci(self):
        r=self.assess()
        self.assertFalse(r['independentPolicyVerified']);self.assertFalse(r['mergeAuthorized'])


if __name__=='__main__':unittest.main()
