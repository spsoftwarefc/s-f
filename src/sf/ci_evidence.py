"""SF-10: explicit GitHub Actions provider-metadata verifier.

Trusted observations come exclusively from requested HTTPS API responses, never
from a URL, local snapshot, candidate-supplied check labels, or untrusted logs.
The request describes what to check; it is NOT a baseline-controlled policy.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


class EvidenceError(ValueError):
    """Invalid evidence request, incompatible schema or malformed response."""


class EvidenceBlocked(Exception):
    """Provider evidence contradicts a required binding."""


class ProviderUnavailable(Exception):
    """Provider metadata unavailable, incomplete or unverifiable."""


_REPO = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_WORKFLOW = re.compile(r"\.github/workflows/[A-Za-z0-9_.-]+\.(?:yml|yaml)\Z")
_MAX_JSON = 1024 * 1024
_MAX_PAGE = 15
_PAGE_SIZE = 100
_MAX_REQUIRED = 80
_REQ_KEYS = {"schemaVersion", "repository", "runId", "attempt", "workflowId",
             "workflowPath", "event", "candidateSha", "baseSha", "pullRequest",
             "requiredJobs", "requiredArtifacts"}


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for k, v in pairs:
        if k in result:
            raise EvidenceError("duplicate JSON key")
        result[k] = v
    return result


def _json_bytes(data: bytes, label: str) -> dict:
    if len(data) > _MAX_JSON:
        raise EvidenceError(f"{label}: oversized JSON")
    try:
        parsed = json.loads(data.decode('utf-8'), object_pairs_hook=_unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise EvidenceError(f"{label}: invalid JSON/UTF-8") from exc
    if type(parsed) is not dict:
        raise EvidenceError(f"{label}: expected object")
    return parsed


def read_request(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_JSON:
        raise EvidenceError("request must be a bounded regular non-symlink file")
    return validate_request(_json_bytes(path.read_bytes(), "request"))


def _positive(value: object) -> bool:
    return type(value) is int and value > 0


def _string(value: Any) -> bool:
    return type(value) is str and bool(value)


def validate_request(request: object) -> dict:
    if type(request) is not dict or set(request) != _REQ_KEYS:
        raise EvidenceError("incorrect CI evidence request fields")
    r = request
    if type(r["schemaVersion"]) is not int or r["schemaVersion"] != 1:
        raise EvidenceError("unsupported evidence request schemaVersion")
    if (not _string(r["repository"]) or not _REPO.fullmatch(r["repository"])
            or any(part in (".", "..") for part in r["repository"].split("/"))):
        raise EvidenceError("invalid repository owner/name")
    if not all(_positive(r[k]) for k in ("runId", "attempt", "workflowId")):
        raise EvidenceError("invalid run/attempt/workflow identity")
    if not _string(r["workflowPath"]) or not _WORKFLOW.fullmatch(r["workflowPath"]):
        raise EvidenceError("workflowPath must be a canonical workflow file path")
    if not _string(r["candidateSha"]) or not _SHA.fullmatch(r["candidateSha"]):
        raise EvidenceError("candidateSha must be full lowercase SHA-1")
    if (r["baseSha"] is not None and
            (not _string(r["baseSha"]) or not _SHA.fullmatch(r["baseSha"]))):
        raise EvidenceError("baseSha must be null or full lowercase SHA-1")
    if r["event"] == "pull_request":
        if not _positive(r["pullRequest"]) or r["baseSha"] is None:
            raise EvidenceError("PR evidence requires pullRequest and baseSha")
    elif r["event"] == "merge_group":
        # GitHub workflow run metadata does not independently authenticate the
        # queue's base/head composition or members. Do not pretend otherwise.
        if r["pullRequest"] is not None or r["baseSha"] is not None:
            raise EvidenceError("merge-group run cannot independently verify PR/baseSha")
    else:
        raise EvidenceError("unsupported provider event")
    jobs = r["requiredJobs"]
    if (type(jobs) is not list or not 1 <= len(jobs) <= _MAX_REQUIRED
            or any(not _string(x) or len(x) > 200 or x != x.strip() for x in jobs)
            or len(set(jobs)) != len(jobs)):
        raise EvidenceError("invalid requiredJobs")
    artifacts = r["requiredArtifacts"]
    if type(artifacts) is not list or len(artifacts) > _MAX_REQUIRED:
        raise EvidenceError("invalid requiredArtifacts")
    names = set()
    for entry in artifacts:
        if (type(entry) is not dict or set(entry) != {"name", "digest"}
                or not _string(entry["name"]) or len(entry["name"]) > 200
                or not _string(entry["digest"]) or not _DIGEST.fullmatch(entry["digest"]) 
                or entry["name"] in names):
            raise EvidenceError("invalid or duplicate required artifact/digest")
        names.add(entry["name"])
    return r


def _need(ok: bool, why: str) -> None:
    if not ok:
        raise EvidenceBlocked(why)


def _obj(value: object, what: str) -> dict:
    if type(value) is not dict:
        raise ProviderUnavailable(f"missing/malformed {what} provider metadata")
    return value


def _array(value: object, what: str) -> list:
    if type(value) is not list:
        raise ProviderUnavailable(f"missing/malformed {what} provider metadata")
    return value


def _repo_identity(value: object, expected: str) -> bool:
    return type(value) is dict and value.get("full_name") == expected


def _https_api(request: dict, path: str) -> dict:
    """Provider read only: no caller-supplied URL, no redirects or cross-host auth."""
    if not path.startswith('/repos/' + request["repository"] + '/'):
        raise EvidenceError("GitHub API path escaped the selected repository")
    if not re.fullmatch(r"/[A-Za-z0-9_./?=&-]+", path):
        raise EvidenceError("invalid GitHub API path")
    url = "https://api.github.com" + path
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "s-f-evidence-v1",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers, method="GET")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req: object, fp: object, code: int, msg: str,
                             hdrs: object, newurl: str) -> None:
            return None

    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=12) as response:
            size = response.headers.get("Content-Length")
            if size is not None and (not size.isdecimal() or int(size) > _MAX_JSON):
                raise ProviderUnavailable("GitHub API response size unavailable/too large")
            chunk = response.read(_MAX_JSON + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # Do not leak tokens, arbitrary echoed URLs or provider response bodies.
        raise ProviderUnavailable("GitHub API unavailable, unauthorized or redirected") from None
    try:
        return _json_bytes(chunk, "GitHub API")
    except EvidenceError as exc:
        raise ProviderUnavailable("GitHub API returned invalid/oversized JSON") from exc


def _list_pages(fetch: Callable[[str], dict], prefix: str, key: str) -> list[dict]:
    accumulated: list[dict] = []
    total: int | None = None
    for page in range(1, _MAX_PAGE + 1):
        data = _obj(fetch(f"{prefix}?per_page={_PAGE_SIZE}&page={page}"), key)
        count = data.get("total_count")
        if type(count) is not int or not 0 <= count <= _MAX_PAGE * _PAGE_SIZE:
            raise ProviderUnavailable(f"{key}: missing/invalid total_count")
        if total is None:
            total = count
        elif count != total:
            raise ProviderUnavailable(f"{key}: changed count while paginating")
        items = _array(data.get(key), key)
        if len(items) > _PAGE_SIZE:
            raise ProviderUnavailable(f"{key}: oversized page")
        accumulated.extend(_obj(x, key) for x in items)
        if len(accumulated) >= total:
            if len(accumulated) != total:
                raise ProviderUnavailable(f"{key}: duplicate/overflow page")
            return accumulated
        if len(items) != _PAGE_SIZE:
            raise ProviderUnavailable(f"{key}: incomplete page")
    raise ProviderUnavailable(f"{key}: page cap hit")


def _verify_pr(r: dict, run: dict, fetch: Callable[[str], dict], prefix: str) -> dict:
    n = r["pullRequest"]
    linked = _array(run.get("pull_requests"), "pull_requests")
    matching = [x for x in linked if type(x) is dict and x.get("number") == n]
    _need(len(matching) == 1, "workflow run missing or ambiguous PR correlation")
    observed = matching[0]
    _need((_obj(observed.get("head"), "run PR head").get("sha") == r["candidateSha"]
           and _obj(observed.get("base"), "run PR base").get("sha") == r["baseSha"]),
          "workflow PR head/base identity mismatch")
    for side in ("head", "base"):
        repo = _obj(observed[side].get("repo"), "run PR repository")
        _need(repo.get("url") == "https://api.github.com/repos/" + r["repository"],
              "workflow PR repository mismatch")
    current = _obj(fetch(f"{prefix}/pulls/{n}"), "PR")
    _need(current.get("number") == n, "provider PR number mismatch")
    for side, sha in (("head", r["candidateSha"]), ("base", r["baseSha"])):
        source = _obj(current.get(side), f"PR {side}")
        _need(source.get("sha") == sha and _repo_identity(source.get("repo"), r["repository"]),
              f"current PR {side} drifted since recorded run")
    _need(run.get("head_branch") == current["head"].get("ref"),
          "run branch does not match current PR head")
    return {"pullRequest": n, "headSha": r["candidateSha"], "baseSha": r["baseSha"],
            "headAndBaseProviderBound": True, "checkoutShaProviderAttested": False}


def verify_github(request: dict, *, fetcher: Callable[[str], dict] | None = None) -> dict:
    """Verify one candidate against direct GitHub API run/job/artifact observations.

    Tests may pass an injected fetcher; CLI never accepts one or arbitrary URLs.
    """
    r = validate_request(request)
    prefix = "/repos/" + r["repository"]
    fetch = fetcher if fetcher is not None else (lambda path: _https_api(r, path))
    run = _obj(fetch(f"{prefix}/actions/runs/{r['runId']}"), "workflow run")
    _need(run.get("id") == r["runId"], "workflow run ID mismatch")
    _need(_repo_identity(run.get("repository"), r["repository"]), "workflow repository mismatch")
    _need(_repo_identity(run.get("head_repository"), r["repository"]), "head repository mismatch")
    _need(run.get("workflow_id") == r["workflowId"] and run.get("path") == r["workflowPath"],
          "workflow identity mismatch")
    _need(run.get("event") == r["event"], "workflow event mismatch")
    _need(run.get("run_attempt") == r["attempt"], "workflow run attempt mismatch")
    _need(run.get("head_sha") == r["candidateSha"], "run candidate SHA mismatch")
    _need(run.get("html_url") ==
          f"https://github.com/{r['repository']}/actions/runs/{r['runId']}",
          "forged workflow run URL")
    _need(run.get("status") == "completed" and run.get("conclusion") == "success",
          "workflow run is not completed/successful")
    if r["event"] == "pull_request":
        boundary = _verify_pr(r, run, fetch, prefix)
    else:
        # The API run's head_sha binds one merge-group commit, not group members,
        # independently checked-out tree or baseline composition.
        boundary = {"pullRequest": None, "mergeGroupSha": r["candidateSha"],
                    "baseSha": None, "headAndBaseProviderBound": False,
                    "checkoutShaProviderAttested": False}
    jobs = _list_pages(fetch, f"{prefix}/actions/runs/{r['runId']}/jobs", "jobs")
    names: dict[str, list[dict]] = {}
    ids: set[int] = set()
    for job in jobs:
        ident = job.get("id")
        if not _positive(ident) or ident in ids:
            raise ProviderUnavailable("missing/duplicate job ID")
        ids.add(ident)
        _need(job.get("run_id") == r["runId"] and job.get("run_attempt") == r["attempt"],
              "job run/attempt mismatch")
        _need(job.get("head_sha") == r["candidateSha"], "job source SHA mismatch")
        _need(job.get("html_url") ==
              f"https://github.com/{r['repository']}/actions/runs/{r['runId']}/job/{ident}",
              "forged job URL")
        _need(job.get("check_run_url") ==
              f"https://api.github.com/repos/{r['repository']}/check-runs/{ident}",
              "forged check-run URL")
        _need(job.get("status") == "completed" and job.get("conclusion") == "success",
              "incomplete/skipped/failing workflow job")
        name = job.get("name")
        if not _string(name):
            raise ProviderUnavailable("job has no name")
        names.setdefault(name, []).append(job)
    matched = []
    for name in r["requiredJobs"]:
        _need(len(names.get(name, [])) == 1, f"missing or duplicate required job: {name}")
        matched.append({"name": name, "id": names[name][0]["id"], "conclusion": "success"})
    artifacts = _list_pages(fetch, f"{prefix}/actions/runs/{r['runId']}/artifacts", "artifacts")
    present: dict[str, list[dict]] = {}
    seen_artifact_ids: set[int] = set()
    for artifact in artifacts:
        ident = artifact.get("id")
        if not _positive(ident) or ident in seen_artifact_ids:
            raise ProviderUnavailable("missing/duplicate artifact ID")
        seen_artifact_ids.add(ident)
        name = artifact.get("name")
        if not _string(name):
            raise ProviderUnavailable("artifact missing name")
        present.setdefault(name, []).append(artifact)
    artifact_proofs = []
    for required in r["requiredArtifacts"]:
        named = present.get(required["name"], [])
        _need(len(named) == 1, "missing or duplicate required artifact")
        artifact = named[0]
        ident = artifact["id"]
        _need(artifact.get("expired") is False and type(artifact.get("size_in_bytes")) is int
              and artifact["size_in_bytes"] > 0, "required artifact expired/empty")
        _need(artifact.get("digest") == required["digest"], "required artifact digest mismatch")
        _need(artifact.get("archive_download_url") ==
              f"https://api.github.com/repos/{r['repository']}/actions/artifacts/{ident}/zip",
              "forged artifact URL")
        linked = _obj(artifact.get("workflow_run"), "artifact workflow binding")
        _need(linked.get("id") == r["runId"], "required artifact wrong run")
        artifact_proofs.append({"name": required["name"], "id": ident,
                                "providerDigest": required["digest"], "bytesIndependentlyHashed": False})
    return {"schemaVersion": 1, "kind": "sf-ci-provider-metadata-observation",
            "source": "github", "status": "provider-metadata-verified", "providerMetadataVerified": True,
            "independentPolicyVerified": False, "accepted": False,
            "repository": r["repository"], "runId": r["runId"], "attempt": r["attempt"],
            "workflowId": r["workflowId"], "workflowPath": r["workflowPath"],
            "event": r["event"], "candidateSha": r["candidateSha"],
            "boundary": boundary, "requiredJobs": matched, "requiredArtifacts": artifact_proofs,
            "checkoutSha": "unknown", "artifactBytesVerified": False,
            "limitations": ["Required job and artifact policy supplied by request, not independently authenticated",
                            "Checkout identity not independently attested by run/job metadata",
                            "No artifact download or byte-level verification"]}


def inspect_offline(request: dict, snapshot: Path) -> dict:
    """Manual/saved metadata is inherently not provider authenticated."""
    r = validate_request(request)
    if snapshot.is_symlink() or not snapshot.is_file() or snapshot.stat().st_size > _MAX_JSON:
        raise EvidenceError("offline snapshot must be a bounded regular non-symlink file")
    _json_bytes(snapshot.read_bytes(), "offline snapshot")
    return {"schemaVersion": 1, "kind": "sf-ci-local-snapshot",
            "source": "offline", "status": "present-unverified", "providerMetadataVerified": False,
            "independentPolicyVerified": False, "accepted": False,
            "repository": r["repository"], "runId": r["runId"],
            "candidateSha": r["candidateSha"], "checkoutSha": "unknown",
            "limitations": ["Saved or manual metadata is not a trusted provider response",
                            "No offline snapshot can satisfy provider CI qualification"]}
