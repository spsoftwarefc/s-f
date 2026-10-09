"""PQ-07D local archive, manifest, SBOM and build-input byte audit."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from sf.artifact_audit import ArtifactAuditError, audit_retained_inputs
from sf.retained_artifact import stage_retained


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class ArtifactAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = self.root / "store"
        self.store.mkdir()
        self.src = self.root / "bundle.zip"
        self.src.write_bytes(b"local retained archive (not a signed release)")
        self.files = {
            "sbom": self.root / "sbom.json", "provenance": self.root / "provenance.json",
            "toolchain": self.root / "python.lock",
        }
        for role, path in self.files.items():
            path.write_bytes(("test-" + role).encode())
        self.digest = sha(self.src.read_bytes())
        manifest = {
            "schemaVersion": 1, "kind": "sf-reference-retained-build",
            "releaseId": "v1", "sourceCommit": "a" * 40,
            "sourceTree": "b" * 40, "artifactSha256": self.digest,
            "sbomSha256": sha(self.files["sbom"].read_bytes()),
            "provenanceSha256": sha(self.files["provenance"].read_bytes()),
            "toolchainSha256": sha(self.files["toolchain"].read_bytes()),
            "retainUntil": "2099-01-01",
        }
        stage_retained(self.src, self.store, manifest)
        manifest_path = self.store / (self.digest + ".manifest.json")
        self.manifest_digest = sha(manifest_path.read_bytes())
        self.kw = dict(sbom_path=self.files["sbom"],
                       provenance_path=self.files["provenance"],
                       toolchain_lock_path=self.files["toolchain"])

    def call(self, **kwargs):
        return audit_retained_inputs(self.store,self.digest,self.manifest_digest,
                                     **{**self.kw,**kwargs})

    def test_all_exact_bytes_do_not_qualify_signature(self):
        r = self.call()
        self.assertTrue(r["bytesRechecked"])
        self.assertFalse(r["signedProvenanceVerified"])
        self.assertFalse(r["releaseQualified"])

    def test_substituted_sbom_and_provenance_denied(self):
        for role in ("sbom", "provenance", "toolchain"):
            with self.subTest(role=role):
                file = self.files[role]
                original = file.read_bytes()
                file.write_bytes(b"substituted")
                with self.assertRaises(ArtifactAuditError):
                    self.call()
                file.write_bytes(original)

    def test_replaced_manifest_pin_denied(self):
        with self.assertRaises(ArtifactAuditError):
            audit_retained_inputs(self.store,self.digest,"0" * 64,**self.kw)

    def test_conflicting_role_paths_denied(self):
        with self.assertRaises(ArtifactAuditError):
            self.call(sbom_path=self.files["provenance"])

    def test_missing_proof_denied(self):
        self.files["sbom"].unlink()
        with self.assertRaises(ArtifactAuditError):
            self.call()


if __name__ == "__main__":
    unittest.main()
