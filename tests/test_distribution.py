"""SF-13 independently constructed archive fixture and tamper/replay tests."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from sf.cli import main
from sf.lifecycle import JOURNAL, execute_plan, plan_lifecycle, recover
from unittest.mock import patch
from sf.distribution import (COMPAT, MANDATORY, DistributionError, _canonical,
                             _read_json, build_bundle, build_bytes, verify_bundle, verify_bytes, verify_installation_lock)


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.folder = Path(self.t.name)
        self.root = self.folder / 'repo'
        self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Release Fixture')
        self.git('config', 'user.email', 'release@example.invalid')
        for name in sorted(MANDATORY):
            self.write(name, ('portable:' + name + '\n').encode())
        self.write('src/sf/module.py', b'x = 42\n')
        self.write('docs/factory/PROJECT.md', b'project-specific, NOT portable\n')
        self.write('secret.env', b'THIS_MUST_NOT_BE_PACKAGED\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'clean baseline')
        self.release = 'preview-20261008'
        self.publisher = 'test-publisher'
        self.archive = build_bytes(self.root, publisher=self.publisher, release_id=self.release)
        self.trust = self.make_trust(self.archive)

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.root), *args], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=True)
        return result.stdout.decode().strip()

    def write(self, name, data):
        file = self.root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
        return file

    def make_trust(self, archive):
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            m = json.loads(z.read('manifest.json'))
        return {'schemaVersion': 1, 'kind': 'sf-out-of-band-release-pin',
                'publisher': m['publisher'], 'releaseId': m['releaseId'],
                'factoryVersion': m['factoryVersion'], 'sourceCommit': m['sourceCommit'],
                'sourceTree': m['sourceTree'], 'bundleSha256': hashlib.sha256(archive).hexdigest(),
                'expiresOn': '2099-01-01', 'compatibility': copy.deepcopy(COMPAT)}

    def verify(self, archive=None, trust=None):
        return verify_bytes(self.archive if archive is None else archive,
                            self.trust if trust is None else trust, today=date(2026, 10, 8))

    def patch_archive(self, files, *, manifest=None, sort=True, dup=None, symlink=None):
        with zipfile.ZipFile(io.BytesIO(self.archive)) as z:
            raw = {f.filename: z.read(f) for f in z.infolist()}
        if manifest is not None:
            raw['manifest.json'] = _canonical(manifest)
        raw.update(files)
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as z:
            names = ['manifest.json'] + (sorted(n for n in raw if n != 'manifest.json') if sort
                                          else list(reversed([n for n in raw if n != 'manifest.json'])))
            for name in names:
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = ((0o120777 if name == symlink else 0o100644) << 16)
                z.writestr(info, raw[name])
            if dup:
                info = zipfile.ZipInfo(dup, (1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                z.writestr(info, raw[dup])
        return output.getvalue()

    def test_build_is_reproducible(self):
        self.assertEqual(self.archive, build_bytes(self.root, publisher=self.publisher, release_id=self.release))
        self.assertEqual(self.verify()['status'], 'matched-external-release-pin')
        self.assertFalse(self.verify()['accepted'])

    def test_portable_selection_excludes_project_and_secrets(self):
        with zipfile.ZipFile(io.BytesIO(self.archive)) as z:
            self.assertNotIn('docs/factory/PROJECT.md', z.namelist())
            self.assertNotIn('secret.env', z.namelist())
            self.assertIn('src/sf/module.py', z.namelist())
            self.assertIn('.agents/skills/factory-review/SKILL.md', z.namelist())

    def test_different_archive_bytes_rejected(self):
        with self.assertRaises(DistributionError):
            self.verify(self.archive[:-1] + b'X')

    def test_no_self_authentication(self):
        tampered = self.patch_archive({'src/sf/module.py': b'forged\n'})
        self.assertNotEqual(self.trust['bundleSha256'], hashlib.sha256(tampered).hexdigest())
        with self.assertRaisesRegex(DistributionError, 'external trust anchor'):
            self.verify(tampered)

    def test_internal_digest_wrong_even_if_caller_pin_matches(self):
        bad = self.patch_archive({'src/sf/module.py': b'forged\n'})
        with self.assertRaisesRegex(DistributionError, 'corrupt bundle member'):
            self.verify(bad, self.make_trust(bad))

    def test_wrong_publisher(self):
        bad = dict(self.trust, publisher='another-publisher')
        with self.assertRaisesRegex(DistributionError, 'publisher'):
            self.verify(trust=bad)

    def test_wrong_release(self):
        with self.assertRaises(DistributionError):
            self.verify(trust=dict(self.trust, releaseId='another-release'))

    def test_wrong_tree(self):
        with self.assertRaises(DistributionError):
            self.verify(trust=dict(self.trust, sourceTree='a' * 40))

    def test_wrong_commit(self):
        with self.assertRaises(DistributionError):
            self.verify(trust=dict(self.trust, sourceCommit='a' * 40))

    def test_trust_expired(self):
        with self.assertRaisesRegex(DistributionError, 'expired'):
            self.verify(trust=dict(self.trust, expiresOn='2026-01-01'))

    def test_trust_malformed_compatibility(self):
        with self.assertRaisesRegex(DistributionError, 'compatibility'):
            self.verify(trust=dict(self.trust, compatibility={'profileSchema': 4}))

    def test_trust_unknown_version(self):
        with self.assertRaisesRegex(DistributionError, 'fields'):
            self.verify(trust=dict(self.trust, schemaVersion=1, attacker=True))

    def test_source_dirty_refused(self):
        self.write('src/sf/module.py', b'modified\n')
        with self.assertRaisesRegex(DistributionError, 'dirty source'):
            build_bytes(self.root, publisher=self.publisher, release_id=self.release)

    def test_untracked_source_dirty_refused(self):
        self.write('src/sf/extra.py', b'x=5\n')
        with self.assertRaisesRegex(DistributionError, 'dirty source'):
            build_bytes(self.root, publisher=self.publisher, release_id=self.release)

    def test_symlink_factory_file_rejected(self):
        file = self.root / 'src/sf/module.py'
        file.unlink()
        try:
            file.symlink_to(self.root / 'secret.env')
        except (NotImplementedError, OSError):
            # Windows can deny symlink creation; safety property is tested via ZIP metadata below.
            return
        self.git('add', 'src/sf/module.py')
        self.git('commit', '-qm', 'symlink candidate')
        with self.assertRaises(DistributionError):
            build_bytes(self.root, publisher=self.publisher, release_id=self.release)

    def test_zip_symlink_entry_rejected(self):
        modified = self.patch_archive({}, symlink='src/sf/module.py')
        with self.assertRaisesRegex(DistributionError, 'unsafe or noncanonical'):
            self.verify(modified, self.make_trust(modified))

    def test_duplicate_zip_entries_rejected(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            bad = self.patch_archive({}, dup='src/sf/module.py')
        with self.assertRaisesRegex(DistributionError, 'duplicate'):
            self.verify(bad, self.make_trust(bad))

    def test_zip_traversal_rejected(self):
        bad = self.patch_archive({'../outside': b'evil'})
        with self.assertRaisesRegex(DistributionError, 'unsafe archive path'):
            self.verify(bad, self.make_trust(bad))

    def test_zip_windows_reserved_rejected(self):
        bad = self.patch_archive({'CON': b'evil'})
        with self.assertRaisesRegex(DistributionError, 'Windows reserved'):
            self.verify(bad, self.make_trust(bad))

    def test_extra_zip_member_rejected(self):
        bad = self.patch_archive({'extra.txt': b'evil'})
        with self.assertRaisesRegex(DistributionError, 'ZIP contents disagree'):
            self.verify(bad, self.make_trust(bad))

    def test_zip_wrong_order_rejected(self):
        bad = self.patch_archive({}, sort=False)
        with self.assertRaisesRegex(DistributionError, 'ordering'):
            self.verify(bad, self.make_trust(bad))

    def test_missing_manifest_rejected(self):
        with self.assertRaises(DistributionError):
            self.verify(b'bad', dict(self.trust, bundleSha256=hashlib.sha256(b'bad').hexdigest()))

    def test_noncanonical_manifest_rejected(self):
        with zipfile.ZipFile(io.BytesIO(self.archive)) as z:
            m=json.loads(z.read('manifest.json'))
        mutated=self.patch_archive({}, manifest=dict(m, extra=True))
        with self.assertRaisesRegex(DistributionError, 'fields'):
            self.verify(mutated, self.make_trust(mutated))

    def test_unlisted_manifest_file_rejected(self):
        with zipfile.ZipFile(io.BytesIO(self.archive)) as z:
            m=json.loads(z.read('manifest.json'))
        m['files']=m['files'][:-1]
        bad=self.patch_archive({}, manifest=m)
        with self.assertRaises(DistributionError):
            self.verify(bad, self.make_trust(bad))

    def test_modified_manifest_identity_not_accepted(self):
        with zipfile.ZipFile(io.BytesIO(self.archive)) as z:
            m=json.loads(z.read('manifest.json'))
        m['sourceTree']='b'*40
        bad=self.patch_archive({}, manifest=m)
        with self.assertRaises(DistributionError):
            self.verify(bad, self.trust)

    def test_write_bundle_and_lock_opt_in_exclusive(self):
        dest=self.folder/'bundle.zip'
        result=build_bundle(self.root,dest,publisher=self.publisher,release_id=self.release)
        self.assertEqual(result['status'],'built-not-authenticated')
        self.assertEqual(dest.read_bytes(),self.archive)
        with self.assertRaises(DistributionError):
            build_bundle(self.root,dest,publisher=self.publisher,release_id=self.release)
        trust=self.folder/'trust.json'
        trust.write_bytes(_canonical(self.trust))
        lock=self.folder/'lock.json'
        v=verify_bundle(dest,trust,lock_out=lock)
        self.assertEqual(v['filesVerified'],len(MANDATORY)+1)
        self.assertEqual(json.loads(lock.read_bytes())['bundleSha256'],hashlib.sha256(self.archive).hexdigest())
        with self.assertRaises(DistributionError):
            verify_bundle(dest,trust,lock_out=lock)

    def test_trust_symlink_rejected(self):
        trust=self.folder/'real-trust.json'
        trust.write_bytes(_canonical(self.trust))
        alias=self.folder/'alias.json'
        try:
            alias.symlink_to(trust)
        except (NotImplementedError,OSError):
            return
        bundle=self.folder/'bundle.zip'
        bundle.write_bytes(self.archive)
        with self.assertRaisesRegex(DistributionError, 'symlinked'):
            verify_bundle(bundle,alias)

    def test_cli_offline_no_auth_promotion(self):
        dest=self.folder/'bundle.zip'
        trust=self.folder/'trust.json'
        trust.write_bytes(_canonical(self.trust))
        self.assertEqual(main(['distribution','build','--root',str(self.root),'--output',str(dest),
                               '--publisher',self.publisher,'--release-id',self.release]),0)
        self.assertEqual(main(['distribution','verify','--bundle',str(dest),'--trust',str(trust)]),0)

    def test_cli_invalid_missing_trust(self):
        bundle=self.folder/'bundle.zip'
        bundle.write_bytes(self.archive)
        self.assertEqual(main(['distribution','verify','--bundle',str(bundle),'--trust',str(self.folder/'missing.json')]),2)

    def test_json_duplicate_member_rejected(self):
        with self.assertRaisesRegex(DistributionError, 'duplicate JSON'):
            _read_json(b'{"a":1,"a":2}', 'trust')

    def test_no_script_autoexecution_during_archive(self):
        self.write('src/sf/module.py', b'import sys\nraise RuntimeError("do not execute")\n')
        self.git('add','src/sf/module.py')
        self.git('commit','-qm','unsafe module data')
        bundle=build_bytes(self.root,publisher=self.publisher,release_id=self.release)
        self.assertTrue(bundle)


    def test_installation_lock_requires_same_verified_archive(self):
        archive_path = self.folder / "release.zip"
        trust_path = self.folder / "approved.json"
        lock_path = self.folder / "factory-lock.json"
        archive_path.write_bytes(self.archive)
        trust_path.write_bytes(_canonical(self.trust))
        result = verify_bundle(archive_path, trust_path, lock_out=lock_path)
        binding = verify_installation_lock(archive_path, trust_path, lock_path)
        self.assertEqual(binding["bundleSha256"], self.trust["bundleSha256"])
        self.assertEqual(binding["lock"], result["lock"])
        self.assertFalse(binding["releaseQualified"])
        self.assertFalse(binding["independentTrustProvisioningVerified"])

    def test_missing_or_mutated_installation_lock_blocks(self):
        archive_path = self.folder / "release.zip"
        trust_path = self.folder / "approved.json"
        lock_path = self.folder / "factory-lock.json"
        archive_path.write_bytes(self.archive)
        trust_path.write_bytes(_canonical(self.trust))
        with self.assertRaisesRegex(DistributionError, "installation lock"):
            verify_installation_lock(archive_path, trust_path, lock_path)
        lock = verify_bundle(archive_path, trust_path)["lock"]
        for mutated in (dict(lock, bundleSha256="0" * 64),
                        dict(lock, releaseId="other-release"),
                        dict(lock, compatibility=dict(lock["compatibility"], profileSchema=99)),
                        dict(lock, attacker=True)):
            lock_path.write_bytes(_canonical(mutated))
            with self.assertRaisesRegex(DistributionError, "installation lock"):
                verify_installation_lock(archive_path, trust_path, lock_path)

    def test_lock_noncanonical_and_expired_trust_block(self):
        archive_path = self.folder / "release.zip"
        trust_path = self.folder / "approved.json"
        lock_path = self.folder / "factory-lock.json"
        archive_path.write_bytes(self.archive)
        trust_path.write_bytes(_canonical(self.trust))
        lock = verify_bundle(archive_path, trust_path)["lock"]
        lock_path.write_text(json.dumps(lock, sort_keys=True, indent=2))
        with self.assertRaisesRegex(DistributionError, "noncanonical"):
            verify_installation_lock(archive_path, trust_path, lock_path)
        lock_path.write_bytes(_canonical(lock))
        trust_path.write_bytes(_canonical(dict(self.trust, expiresOn="2020-01-01")))
        with self.assertRaisesRegex(DistributionError, "expired"):
            verify_installation_lock(archive_path, trust_path, lock_path)

    def test_separately_tampered_bundle_rejected_against_lock(self):
        archive_path = self.folder / "release.zip"
        trust_path = self.folder / "approved.json"
        lock_path = self.folder / "factory-lock.json"
        archive_path.write_bytes(self.archive)
        trust_path.write_bytes(_canonical(self.trust))
        lock_path.write_bytes(_canonical(verify_bundle(archive_path, trust_path)["lock"]))
        archive_path.write_bytes(self.archive[:-1] + b"X")
        with self.assertRaisesRegex(DistributionError, "external trust anchor"):
            verify_installation_lock(archive_path, trust_path, lock_path)



    def _lifecycle_proof_fixture(self):
        target = self.folder / "destination"
        target.mkdir()
        profile = target / "profile.json"
        profile.write_text(json.dumps({
            "schemaVersion": 1, "project": {"id": "sandbox"},
            "commands": {"check": {"argv": ["make", "verify"], "cwd": "."}},
            "components": [{"id": "svc", "path": ".", "stack": "custom",
                            "checks": ["check"]}]
        }))
        archive_path = self.folder / "release.zip"
        trust_path = self.folder / "approved.json"
        lock_path = self.folder / "factory-lock.json"
        archive_path.write_bytes(self.archive)
        trust_path.write_bytes(_canonical(self.trust))
        verify_bundle(archive_path, trust_path, lock_out=lock_path)
        return target, profile, archive_path, trust_path, lock_path

    def test_verified_distribution_bound_into_lifecycle_plan_and_apply(self):
        target, profile, archive, trust, lock = self._lifecycle_proof_fixture()
        kwargs = {"bundle": archive, "trust": trust, "lock": lock}
        plan = plan_lifecycle("integrate", target, profile, **kwargs)
        self.assertEqual(plan["schemaVersion"], 2)
        self.assertEqual(plan["verifiedLock"]["bundleSha256"], self.trust["bundleSha256"])
        self.assertFalse(plan["installedDistributionBytesVerified"])
        doc = self.folder / "plan.json"
        doc.write_text(json.dumps(plan))
        receipt = execute_plan(target, profile, doc, mode="integrate", **kwargs)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["distributionVerified"])
        self.assertTrue((target / ".s-f/OWNERSHIP.json").is_file())
        self.assertFalse((target / JOURNAL).exists())

    def test_verified_plan_rejects_missing_or_replaced_proof_before_mutation(self):
        target, profile, archive, trust, lock = self._lifecycle_proof_fixture()
        kwargs = {"bundle": archive, "trust": trust, "lock": lock}
        doc = self.folder / "plan.json"
        doc.write_text(json.dumps(plan_lifecycle("integrate", target, profile, **kwargs)))
        with self.assertRaisesRegex(Exception, "stale or altered"):
            execute_plan(target, profile, doc, mode="integrate")
        self.assertFalse((target / ".s-f").exists())
        self.assertFalse((target / JOURNAL).exists())
        payload = json.loads(lock.read_text())
        lock.write_bytes(_canonical(dict(payload, sourceTree="0" * 40)))
        with self.assertRaises(DistributionError):
            execute_plan(target, profile, doc, mode="integrate", **kwargs)
        self.assertFalse((target / ".s-f").exists())
        self.assertFalse((target / JOURNAL).exists())

    def test_verification_failure_on_recovery_preserves_incomplete_journal(self):
        target, profile, archive, trust, lock = self._lifecycle_proof_fixture()
        kwargs = {"bundle": archive, "trust": trust, "lock": lock}
        doc = self.folder / "plan.json"
        doc.write_text(json.dumps(plan_lifecycle("integrate", target, profile, **kwargs)))
        from sf import lifecycle
        actual = lifecycle._checked_effect
        count = []
        def interrupted(root, step):
            if count:
                raise OSError("interruption")
            count.append(step["path"])
            return actual(root, step)
        with patch("sf.lifecycle._checked_effect", side_effect=interrupted):
            with self.assertRaises(OSError):
                execute_plan(target, profile, doc, mode="integrate", **kwargs)
        self.assertTrue((target / JOURNAL).is_file())
        with self.assertRaises(Exception):
            recover(target)
        self.assertTrue((target / JOURNAL).is_file())
        self.assertEqual(recover(target, **kwargs)["status"], "completed")
        self.assertFalse((target / JOURNAL).exists())


if __name__ == '__main__':
    unittest.main()
