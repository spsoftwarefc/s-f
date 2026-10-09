"""PQ-03 reference-local retention tests."""
import hashlib
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sf.retained_artifact import RetentionError, read_retained, stage_retained


class RetainedTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.directory = root / "store"
        self.directory.mkdir()
        self.artifact = root / "a.zip"
        self.artifact.write_bytes(b"reference retained bytes")
        self.digest = hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.manifest = {
            "schemaVersion": 1, "kind": "sf-reference-retained-build",
            "releaseId": "v1", "artifactSha256": self.digest,
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "toolchainSha256": "c" * 64, "sbomSha256": "d" * 64,
            "provenanceSha256": "e" * 64, "retainUntil": "2099-01-01",
        }

    def test_stage_reuse_and_unchanged_bytes(self):
        first = stage_retained(self.artifact, self.directory, self.manifest,
                               today=date(2026, 10, 9))
        second = stage_retained(self.artifact, self.directory, self.manifest,
                                today=date(2026, 10, 9))
        _, data = read_retained(self.directory, self.digest, today=date(2026, 10, 9))
        self.assertEqual(first["status"], "retained-locally")
        self.assertEqual(second["status"], "already-retained")
        self.assertEqual(data, self.artifact.read_bytes())
        self.assertFalse(first["signedProvenanceVerified"])

    def test_changed_source_denied(self):
        with self.assertRaises(RetentionError):
            stage_retained(self.artifact, self.directory,
                           {**self.manifest, "artifactSha256": "f" * 64})

    def test_corrupt_retained_file_denied(self):
        stage_retained(self.artifact, self.directory, self.manifest)
        (self.directory / (self.digest + ".zip")).write_bytes(b"tampered")
        with self.assertRaises(RetentionError):
            read_retained(self.directory, self.digest)

    def test_conflicting_record_and_expiry_denied(self):
        stage_retained(self.artifact, self.directory, self.manifest)
        with self.assertRaises(RetentionError):
            stage_retained(self.artifact, self.directory,
                           {**self.manifest, "toolchainSha256": "f" * 64})
        with self.assertRaises(RetentionError):
            read_retained(self.directory, self.digest, today=date(2100, 1, 1))

    def test_symlinked_store_rejected(self):
        link = self.directory.parent / "linked"
        try:
            link.symlink_to(self.directory, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(RetentionError):
            stage_retained(self.artifact, link, self.manifest)


if __name__ == "__main__":
    unittest.main()
