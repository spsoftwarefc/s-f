"""PQ-02 deterministic tests: no provider/network or real grants."""
import hashlib
import hmac
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sf.release_authority import (
    AuthorityError, canonical, observe_pinned_ci, observe_reference_grant,
)


class ReferenceGrantTests(unittest.TestCase):
    def setUp(self):
        self.secret = b"trusted operator secret (not an actual production key!)"
        self.grant = {
            "schemaVersion": 1, "kind": "sf-reference-effect-grant",
            "issuer": "operator1", "grantId": "g1", "operationId": "o1",
            "destination": "disposable", "environment": "test",
            "effect": "deploy", "artifactSha256": "a" * 64,
            "policySha256": "b" * 64, "expiresAt": "2099-01-01T00:00:00Z",
            "revocationEpoch": 2,
        }
        self.kw = dict(effect="deploy", destination="disposable",
                       environment="test", artifact_sha256="a" * 64,
                       policy_sha256="b" * 64, minimum_revocation_epoch=2,
                       now=datetime(2026, 10, 9, tzinfo=timezone.utc))

    def observe(self, grant=None, mac=None, **kwargs):
        body = self.grant if grant is None else grant
        tag = mac if mac is not None else hmac.new(
            self.secret, canonical(body), hashlib.sha256).hexdigest()
        return observe_reference_grant(body, tag, self.secret, **{**self.kw, **kwargs})

    def test_good_reference_mac_is_not_release_permission(self):
        result = self.observe()
        self.assertTrue(result["hmacVerified"])
        self.assertFalse(result["effectAuthorized"])
        self.assertFalse(result["accepted"])

    def test_mutation_and_wrong_scope_denied(self):
        good_tag = hmac.new(self.secret, canonical(self.grant), hashlib.sha256).hexdigest()
        with self.assertRaises(AuthorityError):
            self.observe({**self.grant, "destination": "other"}, mac=good_tag)
        for override in ({"effect": "migrate"}, {"environment": "prod"},
                         {"policy_sha256": "c" * 64}, {"minimum_revocation_epoch": 3}):
            with self.subTest(override=override):
                with self.assertRaises(AuthorityError):
                    self.observe(**override)

    def test_expiry_and_invalid_fields(self):
        with self.assertRaises(AuthorityError):
            self.observe(now=datetime(2100, 1, 1, tzinfo=timezone.utc))
        with self.assertRaises(AuthorityError):
            self.observe({**self.grant, "secretField": "x"})

    def test_wrong_key_and_weak_key_denied(self):
        with self.assertRaises(AuthorityError):
            observe_reference_grant(self.grant, "f" * 64, self.secret, **self.kw)
        with self.assertRaises(AuthorityError):
            observe_reference_grant(self.grant, "f" * 64, b"weak", **self.kw)


class CIPolicyTests(unittest.TestCase):
    def test_policy_digest_blocks_candidate_changes_before_provider(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "policy.json"
            path.write_bytes(canonical({"schemaVersion": 1}))
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            with patch("sf.release_authority.verify_github") as verify:
                with self.assertRaises(AuthorityError):
                    observe_pinned_ci(path, "0" * 64)
                verify.assert_not_called()
                with patch("sf.release_authority.validate_request",
                           return_value={"schemaVersion": 1}):
                    verify.return_value = {"status": "provider-metadata-verified",
                                           "accepted": False}
                    out = observe_pinned_ci(path, expected)
                self.assertTrue(out["independentPolicyDigestMatched"])
                self.assertFalse(out["effectAuthorized"])
                self.assertFalse(out["accepted"])


if __name__ == "__main__":
    unittest.main()
