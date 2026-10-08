"""SF-10: provider metadata is the fixture boundary, not a painted green URL."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from sf import ci_evidence as ev
from sf.cli import main as cli

REPO = "spsoftwarefc/s-f"
SHA = "a" * 40
BASE = "b" * 40
QUEUE = "c" * 40
PREFIX = f"/repos/{REPO}"
JOBS = ["linux / test", "windows / test", "acceptance"]


def request(**changes):
    r = {"schemaVersion": 1, "repository": REPO, "runId": 301, "attempt": 2,
         "workflowId": 70, "workflowPath": ".github/workflows/ci.yml",
         "event": "pull_request", "candidateSha": SHA, "baseSha": BASE, "pullRequest": 19,
         "requiredJobs": list(JOBS), "requiredArtifacts": []}
    return {**r, **changes}


def fixture(r=None):
    r = r or request()
    def side(sha):
        return {"sha": sha, "repo": {"full_name": REPO, "url": "https://api.github.com/repos/" + REPO}}
    run = {"id": r["runId"], "repository": {"full_name": REPO},
           "head_repository": {"full_name": REPO},
           "workflow_id": r["workflowId"], "path": r["workflowPath"], "event": r["event"],
           "run_attempt": r["attempt"], "head_sha": r["candidateSha"], "head_branch": "feature",
           "html_url": f"https://github.com/{REPO}/actions/runs/{r['runId']}",
           "status": "completed", "conclusion": "success", "pull_requests": []}
    pr = {"number": 19, "head": {**side(SHA), "ref": "feature"},
          "base": {**side(BASE), "ref": "main"}}
    if r["event"] == "pull_request":
        run["pull_requests"] = [{"number": 19, "head": {**side(SHA), "repo": {"url": "https://api.github.com/repos/" + REPO}},
                                  "base": {**side(BASE), "repo": {"url": "https://api.github.com/repos/" + REPO}}}]
    jobs = []
    for i, name in enumerate(JOBS):
        jid = 101 + i
        jobs.append({"id": jid, "name": name, "run_id": r["runId"], "run_attempt": r["attempt"],
                     "head_sha": r["candidateSha"], "status": "completed", "conclusion": "success",
                     "html_url": f"https://github.com/{REPO}/actions/runs/{r['runId']}/job/{jid}",
                     "check_run_url": f"https://api.github.com/repos/{REPO}/check-runs/{jid}"})
    artifact = {"id": 777, "name": "test-report", "workflow_run": {"id": r["runId"]},
                "digest": "sha256:" + "d" * 64, "expired": False, "size_in_bytes": 180,
                "archive_download_url": f"https://api.github.com/repos/{REPO}/actions/artifacts/777/zip"}
    return {"run": run, "pr": pr, "jobs": jobs, "artifacts": [artifact]}


def fake_fetch(f, *, calls=None):
    def fetch(path):
        if calls is not None:
            calls.append(path)
        if path == f"{PREFIX}/actions/runs/301":
            return f["run"]
        if path == f"{PREFIX}/pulls/19":
            return f["pr"]
        if path.startswith(f"{PREFIX}/actions/runs/301/jobs?"):
            page = int(path.split("page=")[-1])
            items = f["jobs"] if page == 1 else []
            return {"total_count": len(f["jobs"]), "jobs": items}
        if path.startswith(f"{PREFIX}/actions/runs/301/artifacts?"):
            page = int(path.split("page=")[-1])
            items = f["artifacts"] if page == 1 else []
            return {"total_count": len(f["artifacts"]), "artifacts": items}
        raise AssertionError("unexpected endpoint: " + path)
    return fetch


class CiEvidenceTests(unittest.TestCase):
    def good(self, *, r=None, f=None):
        r = r or request()
        return ev.verify_github(r, fetcher=fake_fetch(f or fixture(r)))

    def blocked(self, fn):
        with self.assertRaises(ev.EvidenceBlocked):
            fn()

    def unavailable(self, fn):
        with self.assertRaises(ev.ProviderUnavailable):
            fn()

    def test_valid_PR_provider_observation_without_false_checkout_or_acceptance(self):
        value = self.good()
        self.assertEqual(value["status"], "provider-metadata-verified")
        self.assertTrue(value["boundary"]["headAndBaseProviderBound"])
        self.assertEqual(value["checkoutSha"], "unknown")
        self.assertFalse(value["independentPolicyVerified"])
        self.assertFalse(value["accepted"])
        self.assertEqual(len(value["requiredJobs"]), 3)

    def test_verified_real_provider_shapes_never_execute_commands(self):
        paths = []
        self.good(f=fixture(), r=request())
        ev.verify_github(request(), fetcher=fake_fetch(fixture(), calls=paths))
        self.assertTrue(all(path.startswith(PREFIX + "/") for path in paths))
        self.assertEqual(len(paths), 4)

    def test_forged_run_url(self):
        f = fixture(); f["run"]["html_url"] = "https://evil.example/runs/301"
        self.blocked(lambda: self.good(f=f))

    def test_wrong_repository_and_head_repo(self):
        for name in ("repository", "head_repository"):
            with self.subTest(name=name):
                f = fixture(); f["run"][name]["full_name"] = "other/repo"
                self.blocked(lambda: self.good(f=f))

    def test_mismatched_workflow_id_or_path(self):
        for name, value in (("workflow_id", 71), ("path", ".github/workflows/other.yml")):
            with self.subTest(name=name):
                f = fixture(); f["run"][name] = value
                self.blocked(lambda: self.good(f=f))

    def test_run_attempt_substitution(self):
        for value in (1, 3):
            f = fixture(); f["run"]["run_attempt"] = value
            self.blocked(lambda: self.good(f=f))

    def test_wrong_sha_and_event(self):
        for name, value in (("head_sha", BASE), ("event", "push"), ("id", 302)):
            with self.subTest(name=name):
                f = fixture(); f["run"][name] = value
                self.blocked(lambda: self.good(f=f))

    def test_incomplete_failed_cancelled_run(self):
        for status, conclusion in (("in_progress", None), ("completed", "failure"),
                                   ("completed", "cancelled"), ("completed", "neutral")):
            f = fixture(); f["run"].update(status=status, conclusion=conclusion)
            self.blocked(lambda: self.good(f=f))

    def test_run_pr_head_base_correlation_required(self):
        for mutation in (lambda f: f["run"]["pull_requests"].clear(),
                         lambda f: f["run"]["pull_requests"][0]["base"].update(sha=SHA),
                         lambda f: f["run"]["pull_requests"][0]["head"]["repo"].update(url="https://evil.example/repo")):
            f = fixture(); mutation(f)
            self.blocked(lambda: self.good(f=f))

    def test_stale_current_pr_head_or_base(self):
        for part in ("head", "base"):
            f = fixture(); f["pr"][part]["sha"] = QUEUE
            self.blocked(lambda: self.good(f=f))

    def test_wrong_pr_head_repo_and_branch(self):
        f = fixture(); f["pr"]["head"]["repo"]["full_name"] = "other/thing"
        self.blocked(lambda: self.good(f=f))
        f = fixture(); f["run"]["head_branch"] = "unrelated"
        self.blocked(lambda: self.good(f=f))

    def test_required_missing_and_duplicate_job(self):
        f = fixture(); f["jobs"] = f["jobs"][:-1]
        self.blocked(lambda: self.good(f=f))
        f = fixture(); duplicated = copy.deepcopy(f["jobs"][0]); duplicated["id"] = 666
        duplicated["html_url"] = f"https://github.com/{REPO}/actions/runs/301/job/666"
        duplicated["check_run_url"] = f"https://api.github.com/repos/{REPO}/check-runs/666"
        f["jobs"].append(duplicated)
        self.blocked(lambda: self.good(f=f))

    def test_job_skipped_cancelled_failure_and_incomplete(self):
        for status, conclusion in (("completed", "skipped"), ("completed", "cancelled"),
                                   ("completed", "failure"), ("queued", None)):
            f = fixture(); f["jobs"][0].update(status=status, conclusion=conclusion)
            self.blocked(lambda: self.good(f=f))

    def test_wrong_job_attempt_or_sha(self):
        for field, value in (("run_attempt", 1), ("run_id", 2), ("head_sha", BASE)):
            f = fixture(); f["jobs"][1][field] = value
            self.blocked(lambda: self.good(f=f))

    def test_forged_job_and_check_run_url(self):
        for field in ("html_url", "check_run_url"):
            f = fixture(); f["jobs"][0][field] = "https://example.com/fake"
            self.blocked(lambda: self.good(f=f))

    def test_page_count_mismatch_rejected(self):
        f = fixture(); orig = fake_fetch(f)
        def fetch(path):
            value = orig(path)
            if "/jobs?" in path:
                return {**value, "total_count": 400}
            return value
        self.unavailable(lambda: ev.verify_github(request(), fetcher=fetch))

    def test_duplicate_job_id(self):
        f = fixture(); f["jobs"][1]["id"] = 101
        self.unavailable(lambda: self.good(f=f))

    def test_required_artifact_pass_metadata_only(self):
        r = request(requiredArtifacts=[{"name": "test-report", "digest": "sha256:" + "d" * 64}])
        value = self.good(r=r)
        self.assertEqual(len(value["requiredArtifacts"]), 1)
        self.assertFalse(value["requiredArtifacts"][0]["bytesIndependentlyHashed"])

    def test_required_artifact_missing_expired_wrong_digest(self):
        r = request(requiredArtifacts=[{"name": "test-report", "digest": "sha256:" + "d" * 64}])
        variations = [lambda f: f["artifacts"].clear(),
                      lambda f: f["artifacts"][0].update(expired=True),
                      lambda f: f["artifacts"][0].update(digest="sha256:"+"f"*64),
                      lambda f: f["artifacts"][0].update(size_in_bytes=0),
                      lambda f: f["artifacts"][0]["workflow_run"].update(id=1),
                      lambda f: f["artifacts"][0].update(archive_download_url="https://evil.example/zip")]
        for change in variations:
            f = fixture(r); change(f)
            self.blocked(lambda: self.good(r=r, f=f))

    def test_queue_identity_is_only_provider_observed_run_sha(self):
        r = request(event="merge_group", candidateSha=QUEUE, baseSha=None, pullRequest=None)
        f = fixture(r)
        value = self.good(r=r, f=f)
        self.assertEqual(value["boundary"]["mergeGroupSha"], QUEUE)
        self.assertFalse(value["boundary"]["headAndBaseProviderBound"])
        self.assertEqual(value["checkoutSha"], "unknown")

    def test_queue_with_unverifiable_base_is_rejected(self):
        for r in (request(event="merge_group", candidateSha=QUEUE, pullRequest=None),
                  request(event="merge_group", candidateSha=QUEUE, baseSha=None)):
            with self.assertRaises(ev.EvidenceError):
                self.good(r=r)

    def test_malformed_request_unknown_fields_and_types(self):
        for update in ({"schemaVersion": 2}, {"runId": True}, {"attempt": 0},
                       {"candidateSha": "ab"}, {"requiredJobs": ["linux", "linux"]},
                       {"workflowPath": "../a.yml"}, {"repository": "../evil"},
                       {"requiredArtifacts": [{"name": "x", "digest": "bad"}]},
                       {"extra": 123}):
            with self.subTest(update=update):
                with self.assertRaises(ev.EvidenceError):
                    ev.validate_request(request(**update))

    def test_duplicate_keys_malformed_oversized_json(self):
        for data in (b'{"a":1,"a":2}', b'garbage', b'x' * (1024*1024+1)):
            with self.assertRaises(ev.EvidenceError):
                ev._json_bytes(data, "test")

    def test_offline_snapshot_never_passes_ci(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); req = root / "request.json"; snapshot = root / "observation.json"
            req.write_text(json.dumps(request()))
            snapshot.write_text(json.dumps({"conclusion": "success"}))
            result = ev.inspect_offline(ev.read_request(req), snapshot)
            self.assertEqual(result["status"], "present-unverified")
            self.assertFalse(result["providerMetadataVerified"])
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = cli(["evidence", "verify", "--request", str(req), "--source", "offline", "--snapshot", str(snapshot)])
            self.assertEqual(code, 1)
            self.assertFalse(json.loads(output.getvalue())["accepted"])

    def test_no_implicit_network_from_request_parser(self):
        with tempfile.TemporaryDirectory() as folder:
            req = Path(folder) / "request.json"; req.write_text(json.dumps(request()))
            self.assertEqual(ev.read_request(req)["runId"], 301)
            with self.assertRaises(ev.EvidenceError):
                ev._https_api(request(), "/repos/evil/not-repo/actions/runs/301")

    def test_reject_snapshot_in_github_mode_before_http_request(self):
        with tempfile.TemporaryDirectory() as folder:
            req = Path(folder) / "request.json"; req.write_text(json.dumps(request()))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli(["evidence", "verify", "--request", str(req),
                                      "--source", "github", "--snapshot", "unused.json"]), 2)


if __name__ == "__main__":
    unittest.main()
