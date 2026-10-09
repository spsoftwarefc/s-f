"""PQ-07N workflow declaration must not silently acquire release triggers."""
from pathlib import Path
import re
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/pq07-preview-attestation.yml"
REQUIRED_ACTIONS = {
    "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/attest": "1e69f48acb82d1966a394da916b4c1698aa569d6",
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
}

class ManualAttestationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.source = WORKFLOW.read_text(encoding="utf-8")

    def test_only_manual_dispatch_and_protected_ref(self):
        self.assertIn("on:\n  workflow_dispatch:", self.source)
        self.assertNotRegex(self.source, r"(?m)^\s+(push|pull_request|merge_group|schedule|workflow_run):")
        self.assertIn("github.ref == 'refs/heads/main'", self.source)
        self.assertIn("inputs.intent == 'preview-provenance-only'", self.source)

    def test_narrow_permissions_and_pinned_actions(self):
        self.assertIn("permissions:\n  contents: read\n", self.source)
        for action, digest in REQUIRED_ACTIONS.items():
            with self.subTest(action=action):
                self.assertIn(f"uses: {action}@{digest}", self.source)
        self.assertIn("      id-token: write", self.source)
        self.assertIn("      attestations: write", self.source)
        self.assertIn("      artifact-metadata: write", self.source)
        self.assertIn("persist-credentials: false", self.source)

    def test_preview_not_public_release(self):
        self.assertIn("subject-path: dist/*.whl", self.source)
        self.assertIn("retention-days: 7", self.source)
        self.assertIn("--no-build-isolation", self.source)
        self.assertNotIn("gh release create", self.source)
        self.assertNotIn("pypa/gh-action-pypi-publish", self.source)
        self.assertNotIn("deploy-pages", self.source)

if __name__ == "__main__":
    unittest.main()
