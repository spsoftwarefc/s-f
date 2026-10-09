"""PQ-07O operator CLI cannot silently turn provider observations into grants."""
import contextlib
import importlib.util
import io
import json
import pathlib
import unittest
from unittest.mock import patch

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "tools/pq07_provider.py"
spec = importlib.util.spec_from_file_location("pq07_provider_tool", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class ProviderCliTests(unittest.TestCase):
    def invoke(self, result=None, exception=None):
        stdout = io.StringIO()
        def fake(*args):
            if exception is not None:
                raise exception
            return result
        with patch.object(tool, "observe_pinned_ci", side_effect=fake):
            with contextlib.redirect_stdout(stdout):
                code = tool.main(["--policy", "/tmp/absent.json", "--policy-sha256", "a" * 64])
        return code, json.loads(stdout.getvalue())

    def test_provider_success_still_cannot_authorize_effect(self):
        result = {"providerMetadataVerified": True,
                  "independentPolicyDigestMatched": True,
                  "independentPolicyCustodyVerified": False,
                  "effectAuthorized": False, "accepted": False,
                  "candidateSha": "b" * 40}
        code, value = self.invoke(result=result)
        self.assertEqual(code, 0)
        self.assertFalse(value["effectAuthorized"])
        self.assertFalse(value["productionQualified"])
        self.assertFalse(value["accepted"])

    def test_false_authority_is_rejected(self):
        for field in ("accepted", "effectAuthorized", "independentPolicyCustodyVerified"):
            with self.subTest(field=field):
                result = {"providerMetadataVerified": True,
                          "independentPolicyDigestMatched": True,
                          "independentPolicyCustodyVerified": False,
                          "effectAuthorized": False, "accepted": False}
                result[field] = True
                code, value = self.invoke(result=result)
                self.assertEqual(code, 2)
                self.assertFalse(value["accepted"])

    def test_provider_errors_are_distinct(self):
        for error, expected_code, status in (
            (tool.AuthorityError("bad policy"), 2, "BLOCKED"),
            (tool.EvidenceBlocked("wrong jobs"), 2, "BLOCKED"),
            (tool.ProviderUnavailable("offline"), 3, "UNAVAILABLE"),
        ):
            with self.subTest(error=type(error).__name__):
                code, value = self.invoke(exception=error)
                self.assertEqual(code, expected_code)
                self.assertEqual(value["status"], status)


if __name__ == "__main__":
    unittest.main()
