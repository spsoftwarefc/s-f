"""Check factory routing, preserved instructions, required CI gates, work orders and evidence (PF-2).

These controls are committed alongside the change they police, so they make removals visible and
require a recorded justification; they do not prevent removal. A present heading does not prove
that an instruction's meaning was preserved, and a matching execution fingerprint does not prove
that a command still enforces the same requirement. Hosted CI run facts and approvals in records
are format-checked attestations, not verified results. See docs/factory/PF2_WORK_ORDER.md.

Stages: candidate runs (draft pull requests, pushes to non-default branches, local runs by default)
report missing, stale or incomplete evidence as pending; acceptance runs (ready pull requests,
pushes to the default branch, or --stage acceptance) fail on it. Malformed records, work orders,
labels and references fail at every stage.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import posixpath
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Any

EVIDENCE_DIR = "docs/factory/evidence"
GATES_PATH = f"{EVIDENCE_DIR}/REQUIRED_GATES.json"
PRESERVED_PATH = f"{EVIDENCE_DIR}/PRESERVED_INSTRUCTIONS.json"
CHANGES_PATH = f"{EVIDENCE_DIR}/CONTROL_CHANGES.json"
RECORDS_DIR = f"{EVIDENCE_DIR}/records"
WORK_ORDERS_DIR = f"{EVIDENCE_DIR}/work-orders"
EVIDENCE_SUBDIRS = (RECORDS_DIR + "/", WORK_ORDERS_DIR + "/")
CHECKER_PATH = "tools/check_factory_evidence.py"
SELF_STEP = "Factory routing, preservation and evidence checks"
DEFAULT_BRANCH = "main"
CANDIDATE = "candidate"
ACCEPTANCE = "acceptance"

INVENTORY_PATH = "docs/NORMATIVE_INVENTORY.json"
MANIFEST_PATH = "docs/CONTRACT_MANIFEST_v2.json"
INTEGRITY_PATH = "docs/MANIFEST_INTEGRITY.txt"
# Rewritten when an evidence record or work order is registered. Changes to them after a candidate are
# exempt from staleness only when they are exactly that registration; see bookkeeping_problem().
INTEGRITY_BOOKKEEPING = {INVENTORY_PATH, MANIFEST_PATH, INTEGRITY_PATH}

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
TICK_RE = re.compile(r"`([^`\s]+)`")
FILE_SUFFIXES = (".md", ".py", ".json", ".jsonl", ".yml", ".yaml", ".ts", ".toml", ".lock")

RUN_LABELS = {"CI verified", "review-ready", "accepted", "released", "operationally qualified"}
PASSING_LABELS = RUN_LABELS | {"locally verified", "fixed"}
NON_VERIFYING_LABELS = {"specified", "implemented", "proposed policy", "not verified"}
RESULT_LABELS = PASSING_LABELS | NON_VERIFYING_LABELS | {"deferred with blocked claim", "failed"}

RECORD_FIELDS_V1 = {
    "schemaVersion",
    "workPackage",
    "candidateSha",
    "baseSha",
    "scope",
    "commands",
    "runs",
    "expectedOutputBasis",
    "resultLabel",
    "exclusions",
}
RECORD_FIELDS_V2 = RECORD_FIELDS_V1 | {"workOrder", "supersedes", "results", "structureReview"}
RECORD_FIELDS_V3 = RECORD_FIELDS_V2 | {"impactReview"}
IMPACT_REVIEW_FIELDS = {"invariantsRechecked", "unexpectedImpact", "unaffectedBoundaries", "declarationGapReasons"}
DECLARED_IMPACT_FIELDS = {"mapNodes", "interfaces", "evidenceBindings", "invariants", "discovery"}
STRUCTURE_REVIEW_FIELDS = {
    "conventionsFollowed",
    "departures",
    "migratedCallersVerified",
    "authorityCheck",
    "duplicationHiddenStateErrorsCheck",
}
WORK_ORDER_FIELDS_V1 = {
    "schemaVersion",
    "workPackage",
    "objective",
    "baselineSha",
    "scope",
    "obligations",
    "baseline",
    "structure",
    "amendments",
}
WORK_ORDER_FIELDS_V2 = WORK_ORDER_FIELDS_V1 | {"declaredImpact"}
WORK_ORDER_OPTIONAL_FIELDS = {"boundary"}
BOUNDARY_FIELDS = {"nonGoals", "trustBoundary", "budget"}
PRESERVED_KEYS = {
    "schemaVersion",
    "requiredFiles",
    "routingFiles",
    "requiredHeadings",
    "requiredLines",
    "requiredReferences",
    "hostAdapters",
    "canonicalSkillRoot",
    "forbiddenText",
}
PROOF_KINDS = {
    "regression-reproducer",
    "independent-output",
    "event-trace",
    "ui-before-after",
    "performance-measurement",
    "preservation-review",
}
BASELINE_KINDS = {"reproducer", "observation", "limitation"}
OUTCOMES = {"pass", "fail", "deferred"}
REF_KINDS = {"baseline", "path", "command", "run"}

TOP_KEYS = {"name", "on", "permissions", "jobs"}
TRIGGER_OPTIONS = {"push": set(), "pull_request": {"types"}}
JOB_KEYS = {"runs-on", "steps"}
STEP_KEYS = {"name", "uses", "run", "with", "env", "working-directory"}


class CheckError(Exception):
    """Raised when required repository history or context is unavailable."""


# --- git helpers -------------------------------------------------------------------------------

def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def git_out(root: Path, *args: str) -> str:
    result = git(root, *args)
    if result.returncode != 0:
        raise CheckError(f"git {' '.join(args)} failed: {result.stderr.strip() or result.returncode}")
    return result.stdout


def is_commit(root: Path, rev: str) -> bool:
    return git(root, "cat-file", "-e", f"{rev}^{{commit}}").returncode == 0


def is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    result = git(root, "merge-base", "--is-ancestor", ancestor, descendant)
    if result.returncode in (0, 1):
        return result.returncode == 0
    raise CheckError(f"cannot compare ancestry of {ancestor} and {descendant}: {result.stderr.strip()}")


def show(root: Path, rev: str, rel: str) -> str | None:
    result = git(root, "show", f"{rev}:{rel}")
    return result.stdout if result.returncode == 0 else None


def exists_at(root: Path, rev: str, rel: str) -> bool:
    return git(root, "cat-file", "-e", f"{rev}:{rel.rstrip('/')}").returncode == 0


def tracked(root: Path, rel: str) -> bool:
    return git(root, "ls-files", "--error-unmatch", rel).returncode == 0


def changed_paths(root: Path, old: str, new: str, *paths: str) -> list[str]:
    args = ["diff", "--name-only", old, new]
    if paths:
        args += ["--", *paths]
    return [p for p in git_out(root, *args).split("\n") if p]


def merge_base(root: Path, ref: str) -> str:
    if not is_commit(root, ref):
        raise CheckError(f"comparison ref {ref} is unavailable (shallow or incomplete history?)")
    result = git(root, "merge-base", "HEAD", ref)
    if result.returncode != 0 or not result.stdout.strip():
        raise CheckError(f"no merge base between HEAD and {ref} (shallow or incomplete history?)")
    return result.stdout.strip()


def resolve_base(root: Path, env: dict[str, str], default_branch: str = DEFAULT_BRANCH) -> str:
    """Select the comparison base from CI context; the candidate does not choose it."""
    event = env.get("GITHUB_EVENT_NAME")
    if event == "pull_request":
        base_ref = env.get("GITHUB_BASE_REF")
        if not base_ref:
            raise CheckError("pull_request run without GITHUB_BASE_REF")
        return merge_base(root, f"origin/{base_ref}")
    if event == "push":
        if env.get("GITHUB_REF_NAME") == default_branch:
            if not is_commit(root, "HEAD^1"):
                raise CheckError("push to the default branch has no parent commit to compare against")
            return git_out(root, "rev-parse", "HEAD^1").strip()
        return merge_base(root, f"origin/{default_branch}")
    if event:
        raise CheckError(f"unsupported GitHub event for comparison base: {event}")
    for ref in (f"origin/{default_branch}", default_branch):
        if is_commit(root, ref):
            return merge_base(root, ref)
    raise CheckError(f"no {default_branch} or origin/{default_branch} ref available for a comparison base")


def load_event(env: dict[str, str]) -> dict[str, Any] | None:
    path = env.get("GITHUB_EVENT_PATH")
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise CheckError(f"cannot read GitHub event payload: {err}")


def resolve_stage(env: dict[str, str], event: dict[str, Any] | None, default_branch: str = DEFAULT_BRANCH) -> str:
    """Acceptance for ready pull requests and default-branch pushes; candidate otherwise."""
    name = env.get("GITHUB_EVENT_NAME")
    if name == "pull_request":
        draft = (event or {}).get("pull_request", {}).get("draft")
        if not isinstance(draft, bool):
            raise CheckError("pull_request run without a boolean pull_request.draft in the event payload")
        return CANDIDATE if draft else ACCEPTANCE
    if name == "push":
        return ACCEPTANCE if env.get("GITHUB_REF_NAME") == default_branch else CANDIDATE
    if name:
        raise CheckError(f"unsupported GitHub event for stage selection: {name}")
    return CANDIDATE


# --- small validators ----------------------------------------------------------------------------

def safe_rel(value: Any) -> str | None:
    """Return a normalized repository-relative path (optionally ending in /), else None."""
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        return None
    stripped = value[:-1] if value.endswith("/") else value
    if any(part in ("", ".", "..") for part in stripped.split("/")):
        return None
    return value


def nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def str_list(value: Any, allow_empty: bool = False) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(nonempty_str(x) for x in value)


def load_json(root: Path, rel: str, errors: list[str]) -> Any:
    path = root / rel
    if not path.is_file():
        errors.append(f"{rel}: required file is missing")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        errors.append(f"{rel}: unreadable JSON ({err})")
        return None


def in_scope(path: str, scope: list[str]) -> bool:
    for entry in scope:
        prefix = entry if entry.endswith("/") else entry + "/"
        if path == entry.rstrip("/") or path.startswith(prefix):
            return True
    return False


def is_evidence_path(path: str) -> bool:
    return path.startswith(EVIDENCE_SUBDIRS)


# --- workflow parsing ----------------------------------------------------------------------------

def normalize_run(text: str) -> str:
    lines = [line.rstrip() for line in textwrap.dedent(text).splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def execution_sha256(step: dict[str, Any]) -> str:
    """Fingerprint everything the supported step keys contribute to how a command executes."""
    payload = {
        "run": normalize_run(step.get("run") or ""),
        "env": dict(sorted(step.get("env", {}).items())),
        "working-directory": step.get("working-directory"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _flow_list(value: str, context: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        raise ValueError(f"{context} must be a flow list such as [a, b]")
    items = [_unquote(item) for item in value[1:-1].split(",") if item.strip()]
    if not items:
        raise ValueError(f"{context} must not be empty")
    return items


def _key_error(kind: str, key: str, where: str) -> ValueError:
    return ValueError(
        f"unsupported {kind} key '{key}' in {where}; execution-affecting or unrecognized keys "
        "(for example if, continue-on-error, timeout-minutes) fail closed"
    )


def parse_workflow(text: str) -> dict[str, Any]:
    """Parse the block-style subset of GitHub Actions YAML used by verify.yml.

    Every key outside the supported set raises ValueError so the check fails closed.
    Returns {"triggers": {name: {"types": [...]}}, "permissions": {...}, "jobs": {job: [steps]}}.
    """
    lines = text.splitlines()
    if any("\t" in line for line in lines):
        raise ValueError("workflow contains tab characters")
    workflow: dict[str, Any] = {"triggers": {}, "permissions": {}, "jobs": {}}
    seen_top: set[str] = set()
    section: str | None = None
    trigger: str | None = None
    job: str | None = None
    steps: list[dict[str, Any]] | None = None
    step: dict[str, Any] | None = None
    in_steps = False
    nested: str | None = None
    run_block: list[str] | None = None

    for raw in lines:
        if run_block is not None:
            if not raw.strip() or _indent(raw) > 8:
                run_block.append(raw)
                continue
            assert step is not None
            step["run"] = normalize_run("\n".join(run_block))
            run_block = None
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        ind = _indent(raw)
        if ind == 0:
            match = re.match(r"^([A-Za-z_-]+):\s*(.*)$", raw)
            if not match or match.group(1) not in TOP_KEYS:
                key = match.group(1) if match else raw.strip()
                raise _key_error("top-level", key, "workflow")
            section, value = match.group(1), match.group(2).strip()
            if section in seen_top:
                raise ValueError(f"duplicate top-level key: {section}")
            seen_top.add(section)
            if section != "name" and value:
                raise ValueError(f"top-level {section} must be a block mapping")
            continue
        if section == "on":
            if ind == 2:
                match = re.match(r"^  ([A-Za-z_]+):\s*$", raw)
                if not match or match.group(1) not in TRIGGER_OPTIONS:
                    raise _key_error("trigger", raw.strip().rstrip(":"), "on")
                trigger = match.group(1)
                workflow["triggers"][trigger] = {}
                continue
            if ind == 4 and trigger is not None:
                match = re.match(r"^    ([A-Za-z_-]+):\s*(.*)$", raw)
                if not match or match.group(1) not in TRIGGER_OPTIONS[trigger]:
                    raise _key_error("trigger option", raw.strip().split(":")[0], f"on.{trigger}")
                workflow["triggers"][trigger][match.group(1)] = _flow_list(match.group(2), f"on.{trigger}.{match.group(1)}")
                continue
            raise ValueError(f"unexpected line under on: {raw.strip()}")
        if section == "permissions":
            match = re.match(r"^  ([A-Za-z_-]+):\s*(\S+)\s*$", raw)
            if ind != 2 or not match:
                raise ValueError(f"unexpected line under permissions: {raw.strip()}")
            workflow["permissions"][match.group(1)] = _unquote(match.group(2))
            continue
        if section != "jobs":
            raise ValueError(f"unexpected nested line under {section}: {raw.strip()}")
        if ind == 2:
            match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", raw)
            if not match:
                raise ValueError(f"unexpected job line: {raw.strip()}")
            job = match.group(1)
            if job in workflow["jobs"]:
                raise ValueError(f"duplicate job: {job}")
            steps = []
            workflow["jobs"][job] = steps
            step, in_steps, nested = None, False, None
            continue
        if steps is None or job is None:
            raise ValueError(f"line outside any job: {raw.strip()}")
        if ind == 4:
            match = re.match(r"^    ([A-Za-z_-]+):\s*(.*)$", raw)
            if not match or match.group(1) not in JOB_KEYS:
                raise _key_error("job", match.group(1) if match else raw.strip(), f"job {job}")
            in_steps = match.group(1) == "steps"
            step, nested = None, None
            continue
        if not in_steps:
            raise ValueError(f"unexpected line in job {job}: {raw.strip()}")
        if ind == 6:
            match = re.match(r"^      - ([A-Za-z_-]+):\s*(.*)$", raw)
            if not match:
                raise ValueError(f"unexpected step line in job {job}: {raw.strip()}")
            step = {"name": None, "uses": None, "run": None, "with": {}, "env": {}, "working-directory": None, "_keys": set()}
            steps.append(step)
            key, value = match.groups()
        elif ind == 8:
            match = re.match(r"^        ([A-Za-z_-]+):\s*(.*)$", raw)
            if step is None or not match:
                raise ValueError(f"unexpected step key line in job {job}: {raw.strip()}")
            key, value = match.groups()
        elif ind >= 10:
            match = re.match(r"^\s+([A-Za-z0-9_-]+):\s*(.*)$", raw)
            if step is None or nested is None or not match:
                raise ValueError(f"unexpected nested line in job {job}: {raw.strip()}")
            step[nested][match.group(1)] = _unquote(match.group(2))
            continue
        else:
            raise ValueError(f"unexpected indentation in job {job}: {raw.strip()}")
        if key not in STEP_KEYS:
            raise _key_error("step", key, f"job {job}")
        if key in step["_keys"]:
            raise ValueError(f"duplicate step key '{key}' in job {job}")
        step["_keys"].add(key)
        nested = None
        if key in ("with", "env"):
            if value.strip():
                raise ValueError(f"step {key} in job {job} must be a block mapping")
            nested = key
        elif key == "run" and value.strip() in ("|", "|-"):
            run_block = []
        elif key == "run" and value.strip().startswith(">"):
            raise ValueError("folded run blocks are not supported")
        elif key == "run":
            step["run"] = normalize_run(_unquote(value))
        else:
            if not value.strip():
                raise ValueError(f"step {key} in job {job} needs a value")
            step[key] = _unquote(value)
    if run_block is not None and step is not None:
        step["run"] = normalize_run("\n".join(run_block))
    if not workflow["jobs"]:
        raise ValueError("workflow defines no jobs")
    for job_steps in workflow["jobs"].values():
        for item in job_steps:
            item.pop("_keys", None)
    return workflow


# --- control-list schemas ------------------------------------------------------------------------

def gates_schema_errors(gates: Any) -> list[str]:
    p = GATES_PATH
    if not isinstance(gates, dict) or gates.get("schemaVersion") != 2:
        return [f"{p}: schemaVersion must be 2"]
    errors: list[str] = []
    if safe_rel(gates.get("workflow")) is None:
        errors.append(f"{p}: workflow must be a repository-relative path")
    triggers = gates.get("triggers")
    if not isinstance(triggers, dict) or not triggers or not all(
        k in TRIGGER_OPTIONS and str_list(v, allow_empty=True) for k, v in triggers.items()
    ):
        errors.append(f"{p}: triggers must map push/pull_request to lists of event types")
    permissions = gates.get("permissions")
    if not isinstance(permissions, dict) or not permissions or not all(nonempty_str(v) for v in permissions.values()):
        errors.append(f"{p}: permissions must be a non-empty object of strings")
    jobs = gates.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return errors + [f"{p}: jobs must be a non-empty object"]
    for job, entries in jobs.items():
        if not isinstance(entries, list) or not entries:
            errors.append(f"{p}: jobs.{job} must be a non-empty list")
            continue
        names = [e.get("name") for e in entries if isinstance(e, dict)]
        if len(names) != len(entries) or not all(nonempty_str(n) for n in names):
            errors.append(f"{p}: jobs.{job} entries need a non-empty name")
        if len(set(names)) != len(names):
            errors.append(f"{p}: jobs.{job} has duplicate step names")
        for entry in entries:
            if isinstance(entry, dict) and not HASH_RE.match(str(entry.get("executionSha256", ""))):
                errors.append(f"{p}: jobs.{job}/{entry.get('name')} needs a 64-hex executionSha256")
    depth = gates.get("checkoutFetchDepth", {})
    if not isinstance(depth, dict) or not all(nonempty_str(v) for v in depth.values()):
        errors.append(f"{p}: checkoutFetchDepth must map job names to strings")
    return errors


def preserved_schema_errors(preserved: Any) -> list[str]:
    p = PRESERVED_PATH
    if not isinstance(preserved, dict) or preserved.get("schemaVersion") != 1:
        return [f"{p}: schemaVersion must be 1"]
    errors: list[str] = []
    for key in ("requiredFiles", "routingFiles"):
        value = preserved.get(key)
        if not str_list(value) or any(safe_rel(v) is None for v in value):
            errors.append(f"{p}: {key} must be a non-empty list of repository-relative paths")
    for key in ("requiredHeadings", "requiredLines"):
        value = preserved.get(key)
        if not isinstance(value, dict) or not all(
            safe_rel(k) is not None and str_list(v) for k, v in value.items()
        ):
            errors.append(f"{p}: {key} must map repository-relative paths to non-empty string lists")
    unknown = set(preserved) - PRESERVED_KEYS
    if unknown:
        errors.append(f"{p}: unknown keys {sorted(unknown)}")
    for key in ("requiredReferences", "forbiddenText"):
        value = preserved.get(key, {})
        if not isinstance(value, dict) or not all(safe_rel(k) is not None and str_list(v) for k, v in value.items()):
            errors.append(f"{p}: {key} must map repository-relative paths to non-empty string lists")
    adapters = preserved.get("hostAdapters", {})
    if not isinstance(adapters, dict) or not all(
        safe_rel(k) is not None
        and isinstance(v, dict)
        and set(v) <= {"requires", "forbidHeadingsFrom"}
        and str_list(v.get("requires"))
        and (v.get("forbidHeadingsFrom") is None or safe_rel(v.get("forbidHeadingsFrom")) is not None)
        for k, v in adapters.items()
    ):
        errors.append(f"{p}: hostAdapters must map adapter paths to requires (non-empty list) and optional forbidHeadingsFrom")
    skill_root = preserved.get("canonicalSkillRoot")
    if skill_root is not None and (safe_rel(skill_root) is None or not str(skill_root).endswith("/")):
        errors.append(f"{p}: canonicalSkillRoot must be a repository-relative directory ending in /")
    return errors


def changes_schema_errors(changes: Any) -> list[str]:
    p = CHANGES_PATH
    if not isinstance(changes, dict) or changes.get("schemaVersion") != 1:
        return [f"{p}: schemaVersion must be 1"]
    entries = changes.get("changes")
    if not isinstance(entries, list):
        return [f"{p}: changes must be a list"]
    errors: list[str] = []
    ids = []
    for entry in entries:
        if not isinstance(entry, dict) or not all(nonempty_str(entry.get(k)) for k in ("id", "reason", "acceptedBy")):
            errors.append(f"{p}: each change needs non-empty id, reason and acceptedBy")
            continue
        if not str_list(entry.get("removed")):
            errors.append(f"{p}: change {entry['id']} must list removed control items")
        ids.append(entry["id"])
    if len(set(ids)) != len(ids):
        errors.append(f"{p}: change ids must be unique")
    return errors


def gate_items(gates: dict[str, Any]) -> set[str]:
    items = {f"gate:{job}/{entry['name']}" for job, entries in gates["jobs"].items() for entry in entries}
    items |= {f"fetch-depth:{job}" for job in gates.get("checkoutFetchDepth", {})}
    items |= {f"trigger:{name}" for name in gates.get("triggers", {})}
    items |= {f"permission:{name}" for name in gates.get("permissions", {})}
    return items


def preserved_items(preserved: dict[str, Any]) -> set[str]:
    items = {f"file:{path}" for path in preserved["requiredFiles"]}
    items |= {f"routing:{path}" for path in preserved["routingFiles"]}
    items |= {f"heading:{path}#{h}" for path, hs in preserved["requiredHeadings"].items() for h in hs}
    items |= {f"line:{path}#{line}" for path, ls in preserved["requiredLines"].items() for line in ls}
    items |= {f"reference:{path}#{t}" for path, ts in preserved.get("requiredReferences", {}).items() for t in ts}
    for path, rule in preserved.get("hostAdapters", {}).items():
        items.add(f"adapter:{path}")
        items |= {f"adapter-requires:{path}#{t}" for t in rule.get("requires", [])}
        if rule.get("forbidHeadingsFrom"):
            items.add(f"adapter-headings:{path}#{rule['forbidHeadingsFrom']}")
    if preserved.get("canonicalSkillRoot"):
        items.add(f"canonical-skill-root:{preserved['canonicalSkillRoot']}")
    items |= {f"forbidden:{path}#{phrase}" for path, ps in preserved.get("forbiddenText", {}).items() for phrase in ps}
    return items


# --- checks on the current tree ----------------------------------------------------------------

def routing_errors(root: Path, routing_files: list[str]) -> list[str]:
    errors: list[str] = []
    for rel in routing_files:
        path = root / rel
        if not path.is_file():
            errors.append(f"routing file missing: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            target = target.split("#", 1)[0]
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(rel), target))
            if resolved.startswith("..") or not (root / resolved).exists():
                errors.append(f"routing link in {rel} does not resolve: {target}")
        for token in TICK_RE.findall(text):
            if "/" not in token or not token.endswith(FILE_SUFFIXES) or any(c in token for c in "<>*{}$|"):
                continue
            if safe_rel(token) is None or not (root / token).is_file():
                errors.append(f"routing path in {rel} does not exist: {token}")
    return errors


def preservation_errors(root: Path, preserved: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for rel in preserved["requiredFiles"]:
        if not (root / rel).is_file():
            errors.append(f"preserved file missing: {rel}")
    for key, label in (("requiredHeadings", "heading"), ("requiredLines", "line")):
        for rel, wanted in preserved[key].items():
            path = root / rel
            if not path.is_file():
                errors.append(f"preserved {label} file missing: {rel}")
                continue
            present = {line.strip() for line in path.read_text(encoding="utf-8").splitlines()}
            for item in wanted:
                if item.strip() not in present:
                    errors.append(f"preserved {label} missing from {rel}: {item}")
    return errors


def _read_text(root: Path, rel: str) -> str | None:
    path = root / rel
    return path.read_text(encoding="utf-8") if path.is_file() else None


def routing_consistency_errors(root: Path, preserved: dict[str, Any]) -> list[str]:
    """Required references, canonical skill location, host-adapter thinness and forbidden text.

    These are routing guardrails: a present reference does not prove the linked instruction is still
    correct, and a phrase list only catches the contradictions it names.
    """
    errors: list[str] = []
    for rel, tokens in preserved.get("requiredReferences", {}).items():
        text = _read_text(root, rel)
        if text is None:
            errors.append(f"routing reference file missing: {rel}")
            continue
        for token in tokens:
            if token not in text:
                errors.append(f"required routing reference missing from {rel}: {token}")
    for rel, rule in preserved.get("hostAdapters", {}).items():
        text = _read_text(root, rel)
        if text is None:
            errors.append(f"host adapter missing: {rel}")
            continue
        for token in rule["requires"]:
            if token not in text:
                errors.append(f"host adapter {rel} must reference its entry point: {token}")
        source = rule.get("forbidHeadingsFrom")
        if source:
            source_text = _read_text(root, source)
            if source_text is None:
                errors.append(f"host adapter {rel} checklist source missing: {source}")
                continue
            headings = {line.strip() for line in source_text.splitlines() if line.startswith("## ")}
            for line in text.splitlines():
                if line.strip() in headings:
                    errors.append(f"host adapter {rel} copies a heading from {source}: {line.strip()}")
    skill_root = preserved.get("canonicalSkillRoot")
    if skill_root:
        for tracked_path in git_out(root, "ls-files").splitlines():
            if posixpath.basename(tracked_path) == "SKILL.md" and not tracked_path.startswith(skill_root):
                errors.append(f"skill body outside the canonical location {skill_root}: {tracked_path}")
    for rel, phrases in preserved.get("forbiddenText", {}).items():
        text = _read_text(root, rel)
        if text is None:
            continue
        lowered = text.lower()
        for phrase in phrases:
            if phrase.lower() in lowered:
                errors.append(f"forbidden contradiction text in {rel}: {phrase}")
    return errors


def gate_errors(root: Path, gates: dict[str, Any]) -> list[str]:
    workflow_rel = gates["workflow"]
    path = root / workflow_rel
    if not path.is_file():
        return [f"required workflow missing: {workflow_rel}"]
    try:
        workflow = parse_workflow(path.read_text(encoding="utf-8"))
    except ValueError as err:
        return [f"{workflow_rel}: cannot parse ({err})"]
    jobs = workflow["jobs"]
    errors: list[str] = []
    for name, types in gates["triggers"].items():
        if name not in workflow["triggers"]:
            errors.append(f"{workflow_rel}: required trigger missing: {name}")
        elif sorted(workflow["triggers"][name].get("types", [])) != sorted(types):
            errors.append(f"{workflow_rel}: trigger {name} event types differ from {GATES_PATH}: expected {sorted(types)}")
    if workflow["permissions"] != gates["permissions"]:
        errors.append(f"{workflow_rel}: permissions must be exactly {gates['permissions']}")
    for job, entries in gates["jobs"].items():
        if job not in jobs:
            errors.append(f"required job missing from {workflow_rel}: {job}")
            continue
        named = [s for s in jobs[job] if s["name"]]
        by_name = {s["name"]: s for s in named}
        if len(by_name) != len(named):
            errors.append(f"{workflow_rel}: job {job} has duplicate step names")
        for entry in entries:
            step = by_name.get(entry["name"])
            if step is None:
                errors.append(f"required gate step missing: {job}/{entry['name']}")
            elif not step["run"]:
                errors.append(f"required gate step has an empty run command: {job}/{entry['name']}")
            elif execution_sha256(step) != entry["executionSha256"]:
                errors.append(
                    f"required gate step execution changed: {job}/{entry['name']} "
                    f"(command, env or working-directory; update {GATES_PATH} so the change is reviewed)"
                )
    if SELF_STEP not in {e["name"] for entries in gates["jobs"].values() for e in entries}:
        errors.append(f"{GATES_PATH} must include the factory check step itself: {SELF_STEP}")
    for job, depth in gates.get("checkoutFetchDepth", {}).items():
        checkout = next(
            (s for s in jobs.get(job, []) if str(s.get("uses") or "").startswith("actions/checkout@")), None
        )
        if checkout is None or checkout["with"].get("fetch-depth") != depth:
            errors.append(f"{workflow_rel}: job {job} checkout must set fetch-depth: {depth}")
    return errors


# --- comparison against the base -----------------------------------------------------------------

def removal_errors(
    root: Path, base: str, head_gates: dict[str, Any], head_preserved: dict[str, Any], head_changes: dict[str, Any]
) -> tuple[list[str], bool]:
    """Return (errors, bootstrap). Bootstrap applies only to the change introducing the controls."""
    if not is_commit(root, base):
        return [f"comparison base {base} is unavailable (shallow or incomplete history?)"], False
    base_gates_text = show(root, base, GATES_PATH)
    base_preserved_text = show(root, base, PRESERVED_PATH)
    if base_gates_text is None and base_preserved_text is None:
        if show(root, base, CHECKER_PATH) is None:
            return [], True
        return [f"comparison base contains {CHECKER_PATH} but no control lists; bootstrap does not apply"], False
    if base_gates_text is None or base_preserved_text is None:
        return ["comparison base has only one of the control lists; bootstrap does not apply"], False
    try:
        base_gates = json.loads(base_gates_text)
        base_preserved = json.loads(base_preserved_text)
    except ValueError as err:
        return [f"comparison base control lists are not valid JSON ({err})"], False
    schema = gates_schema_errors(base_gates) + preserved_schema_errors(base_preserved)
    if schema:
        return [f"comparison base: {e}" for e in schema], False

    base_changes: list[dict[str, Any]] = []
    base_changes_text = show(root, base, CHANGES_PATH)
    if base_changes_text is not None:
        try:
            parsed = json.loads(base_changes_text)
            base_changes = parsed.get("changes", []) if isinstance(parsed, dict) else []
        except ValueError:
            return ["comparison base change ledger is not valid JSON"], False

    errors: list[str] = []
    head_entries = {c["id"]: c for c in head_changes["changes"]}
    for old in base_changes:
        if isinstance(old, dict) and head_entries.get(old.get("id")) != old:
            errors.append(f"{CHANGES_PATH} is append-only; change {old.get('id')!r} was altered or removed")
    base_ids = {c.get("id") for c in base_changes if isinstance(c, dict)}
    allowed = {item for c in head_changes["changes"] if c["id"] not in base_ids for item in c["removed"]}
    removed = (gate_items(base_gates) - gate_items(head_gates)) | (
        preserved_items(base_preserved) - preserved_items(head_preserved)
    )
    for item in sorted(removed - allowed):
        errors.append(f"control removed without a change record added in this change: {item}")
    return errors, False


# --- work orders -----------------------------------------------------------------------------------

def work_order_schema_errors(rel: str, data: Any) -> list[str]:
    p = f"{rel}:"
    if not isinstance(data, dict):
        return [f"{p} work order must be a JSON object"]
    version = data.get("schemaVersion")
    fields = WORK_ORDER_FIELDS_V2 if version == 2 else WORK_ORDER_FIELDS_V1
    missing = fields - set(data)
    extra = set(data) - fields - WORK_ORDER_OPTIONAL_FIELDS
    errors: list[str] = []
    if version not in (1, 2):
        errors.append(f"{p} schemaVersion must be 1 or 2")
    if missing:
        errors.append(f"{p} missing fields {sorted(missing)}")
    if extra:
        errors.append(f"{p} unknown fields {sorted(extra)}")
    if missing:
        return errors
    for key in ("workPackage", "objective"):
        if not nonempty_str(data[key]):
            errors.append(f"{p} {key} must be non-empty")
    if not isinstance(data["baselineSha"], str) or not SHA_RE.match(data["baselineSha"]):
        errors.append(f"{p} baselineSha must be a full 40-hex commit SHA")
    if not str_list(data["scope"]) or any(safe_rel(s) is None for s in data["scope"]):
        errors.append(f"{p} scope must be a non-empty list of normalized repository-relative paths")

    obligations = data["obligations"]
    ids: list[str] = []
    if not isinstance(obligations, list) or not obligations:
        errors.append(f"{p} obligations must be a non-empty list")
        obligations = []
    for item in obligations:
        if not isinstance(item, dict) or not all(
            nonempty_str(item.get(k)) for k in ("id", "requirement", "expectedResult", "expectedBasis")
        ):
            errors.append(f"{p} each obligation needs id, requirement, expectedResult and expectedBasis")
            continue
        if item.get("proofKind") not in PROOF_KINDS:
            errors.append(f"{p} obligation {item['id']} proofKind must be one of {sorted(PROOF_KINDS)}")
        ids.append(item["id"])
    if len(set(ids)) != len(ids):
        errors.append(f"{p} obligation ids must be unique")

    baseline = data["baseline"]
    if not isinstance(baseline, list):
        errors.append(f"{p} baseline must be a list")
        baseline = []
    covered: list[str] = []
    for entry in baseline:
        if not isinstance(entry, dict) or entry.get("obligation") not in ids:
            errors.append(f"{p} baseline entries must name a declared obligation")
            continue
        kind = entry.get("kind")
        if kind not in BASELINE_KINDS:
            errors.append(f"{p} baseline for {entry['obligation']} kind must be one of {sorted(BASELINE_KINDS)}")
        detail = "reason" if kind == "limitation" else "observed"
        if not nonempty_str(entry.get(detail)) or not nonempty_str(entry.get("method")):
            errors.append(f"{p} baseline for {entry['obligation']} needs {detail} and method")
        covered.append(entry["obligation"])
    for obligation in ids:
        if covered.count(obligation) != 1:
            errors.append(f"{p} obligation {obligation} needs exactly one baseline entry (observation, reproducer or limitation)")

    structure = data["structure"]
    if not isinstance(structure, dict):
        errors.append(f"{p} structure must be an object")
    else:
        if not str_list(structure.get("layers")):
            errors.append(f"{p} structure.layers must list affected layers")
        modules = structure.get("representativeModules")
        if not str_list(modules) or any(safe_rel(m) is None for m in modules):
            errors.append(f"{p} structure.representativeModules must list existing module paths to follow")
        if not nonempty_str(structure.get("conventions")):
            errors.append(f"{p} structure.conventions must describe the conventions to follow")
        mechanics = structure.get("reusableMechanics")
        if not isinstance(mechanics, list) or not all(
            isinstance(m, dict) and nonempty_str(m.get("mechanic")) and str_list(m.get("callers")) for m in mechanics
        ):
            errors.append(f"{p} structure.reusableMechanics must list mechanics with their callers (may be empty)")
        owners = structure.get("policyOwners")
        if not isinstance(owners, list) or not owners or not all(
            isinstance(o, dict) and nonempty_str(o.get("policy")) and nonempty_str(o.get("owner")) for o in owners
        ):
            errors.append(f"{p} structure.policyOwners must name policy/authority owners")
        interfaces = structure.get("interfaces")
        if not isinstance(interfaces, list) or not interfaces or not all(
            isinstance(i, dict) and all(nonempty_str(i.get(k)) for k in ("name", "inputs", "outputs", "sideEffects"))
            for i in interfaces
        ):
            errors.append(f"{p} structure.interfaces must declare name, inputs, outputs and sideEffects")

    amendments = data["amendments"]
    if not isinstance(amendments, list) or not all(
        isinstance(a, dict) and nonempty_str(a.get("obligation")) and nonempty_str(a.get("reason")) for a in amendments
    ):
        errors.append(f"{p} amendments must be a list of obligation and reason")
    if "boundary" in data:
        boundary = data["boundary"]
        if (
            not isinstance(boundary, dict)
            or set(boundary) != BOUNDARY_FIELDS
            or not str_list(boundary.get("nonGoals"), allow_empty=True)
            or not nonempty_str(boundary.get("trustBoundary"))
            or not nonempty_str(boundary.get("budget"))
        ):
            errors.append(f"{p} boundary needs exactly nonGoals (list), trustBoundary and budget")
    if version == 2:
        impact = data["declaredImpact"]
        if not isinstance(impact, dict) or set(impact) != DECLARED_IMPACT_FIELDS:
            errors.append(f"{p} declaredImpact needs exactly {sorted(DECLARED_IMPACT_FIELDS)}")
        else:
            for key in ("mapNodes", "interfaces", "evidenceBindings"):
                if not str_list(impact.get(key), allow_empty=True):
                    errors.append(f"{p} declaredImpact.{key} must be a list of strings")
            invariants = impact.get("invariants")
            if not isinstance(invariants, list) or not all(
                isinstance(item, dict) and set(item) == {"id", "source", "tests"}
                and nonempty_str(item.get("id")) and nonempty_str(item.get("source"))
                and str_list(item.get("tests")) for item in invariants
            ):
                errors.append(f"{p} declaredImpact.invariants must list id, source and non-empty tests")
            elif len({item["id"] for item in invariants}) != len(invariants):
                errors.append(f"{p} declaredImpact invariant ids must be unique")
            discovery = impact.get("discovery")
            if not isinstance(discovery, dict) or set(discovery) != {"command", "workingTreeFingerprint", "limitation"}:
                errors.append(f"{p} declaredImpact.discovery needs exactly command, workingTreeFingerprint and limitation")
            else:
                if not nonempty_str(discovery.get("command")):
                    errors.append(f"{p} declaredImpact.discovery.command must be non-empty")
                fingerprint = discovery.get("workingTreeFingerprint")
                if fingerprint is not None and (not isinstance(fingerprint, str) or not HASH_RE.match(fingerprint)):
                    errors.append(f"{p} declaredImpact.discovery.workingTreeFingerprint must be null or a 64-hex SHA-256")
                if fingerprint is None and not nonempty_str(discovery.get("limitation")):
                    errors.append(f"{p} declaredImpact.discovery needs a limitation when no fingerprint is available")
    return errors


def work_order_history_errors(root: Path, rel: str, data: dict[str, Any]) -> tuple[list[str], str | None]:
    """Validate that the work order was declared before implementation and kept its expectations."""
    errors: list[str] = []
    if not tracked(root, rel):
        return [f"{rel}: work order is not committed; declare it in history before implementation"], None
    baseline = data["baselineSha"]
    if not is_commit(root, baseline) or not is_ancestor(root, baseline, "HEAD"):
        return [f"{rel}: baselineSha is not an ancestor of HEAD"], None
    added = git_out(root, "log", "--format=%H", "--diff-filter=A", "HEAD", "--", rel).split()
    if not added:
        return [f"{rel}: cannot find the commit that declared the work order"], None
    declared = added[-1]
    if declared == baseline or not is_ancestor(root, baseline, declared):
        return [f"{rel}: baselineSha must precede the commit that declares the work order"], declared
    for path in changed_paths(root, baseline, declared):
        if path != rel and path not in INTEGRITY_BOOKKEEPING and not path.startswith(WORK_ORDERS_DIR + "/"):
            errors.append(
                f"{rel}: work order was declared after implementation began; {path} changed between "
                f"baselineSha and the declaring commit {declared[:12]}"
            )
    for module in data["structure"]["representativeModules"]:
        if not exists_at(root, baseline, module):
            errors.append(f"{rel}: representative module does not exist at baselineSha: {module}")
    declared_text = show(root, declared, rel)
    try:
        original = json.loads(declared_text or "")
    except ValueError:
        return errors + [f"{rel}: declared version is not valid JSON"], declared
    if not isinstance(original, dict):
        return errors + [f"{rel}: declared version is not a JSON object"], declared
    before = {o.get("id"): o for o in original.get("obligations", []) if isinstance(o, dict)}
    after = {o["id"]: o for o in data["obligations"] if isinstance(o, dict) and "id" in o}
    changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
    amended = {a["obligation"] for a in data["amendments"]}
    for obligation in sorted(changed - amended):
        errors.append(f"{rel}: obligation {obligation} changed after declaration without an amendment")
    if original.get("baseline") != data["baseline"]:
        errors.append(f"{rel}: baseline entries are immutable after declaration")
    if original.get("baselineSha") != data["baselineSha"]:
        errors.append(f"{rel}: baselineSha is immutable after declaration")
    if original.get("declaredImpact") != data.get("declaredImpact"):
        amended = {a["obligation"] for a in data["amendments"]}
        if "declaredImpact" not in amended:
            errors.append(f"{rel}: declaredImpact changed after declaration without a declaredImpact amendment")
    return errors, declared


# --- evidence records ----------------------------------------------------------------------------

def _ref_errors(p: str, label: str, ref: Any, obligation: str, commands: list[Any], runs: list[Any]) -> list[str]:
    if ref is None:
        return []
    if not isinstance(ref, dict) or ref.get("kind") not in REF_KINDS or not nonempty_str(ref.get("reference")):
        return [f"{p} result {obligation} {label} must be null or a reference with kind {sorted(REF_KINDS)}"]
    kind, reference = ref["kind"], ref["reference"]
    if kind == "baseline" and reference != obligation:
        return [f"{p} result {obligation} {label} baseline reference must name its own obligation"]
    if kind == "command" and not (reference.isdigit() and int(reference) < len(commands)):
        return [f"{p} result {obligation} {label} references a missing command index {reference}"]
    if kind == "run" and reference not in {r.get("id") for r in runs if isinstance(r, dict)}:
        return [f"{p} result {obligation} {label} references run {reference} not listed in runs"]
    if kind == "path" and safe_rel(reference) is None:
        return [f"{p} result {obligation} {label} path reference must be repository-relative"]
    return []


def record_schema_errors(rel: str, data: Any) -> list[str]:
    p = f"{rel}:"
    if not isinstance(data, dict):
        return [f"{p} record must be a JSON object"]
    version = data.get("schemaVersion")
    fields = RECORD_FIELDS_V3 if version == 3 else (RECORD_FIELDS_V2 if version == 2 else RECORD_FIELDS_V1)
    errors: list[str] = []
    if version not in (1, 2, 3):
        return [f"{p} schemaVersion must be 2 or 3 (1 is legacy, validated but never acceptance evidence)"]
    missing = fields - set(data)
    extra = set(data) - fields
    if missing:
        errors.append(f"{p} missing fields {sorted(missing)}")
    if extra:
        errors.append(f"{p} unknown fields {sorted(extra)}")
    if missing:
        return errors
    if not nonempty_str(data["workPackage"]):
        errors.append(f"{p} workPackage must be non-empty")
    for key in ("candidateSha", "baseSha"):
        if not isinstance(data[key], str) or not SHA_RE.match(data[key]):
            errors.append(f"{p} {key} must be a full 40-hex commit SHA")
    scope = data["scope"]
    if not str_list(scope) or any(safe_rel(s) is None for s in scope):
        errors.append(f"{p} scope must be a non-empty list of normalized repository-relative paths")
    commands = data["commands"]
    if not isinstance(commands, list) or not commands:
        errors.append(f"{p} commands must be a non-empty list")
        commands = []
    for cmd in commands:
        if (
            not isinstance(cmd, dict)
            or not nonempty_str(cmd.get("command"))
            or not nonempty_str(cmd.get("environment"))
            or not isinstance(cmd.get("exitCode"), int)
            or isinstance(cmd.get("exitCode"), bool)
        ):
            errors.append(f"{p} each command needs command, integer exitCode and environment")
    runs = data["runs"]
    if not isinstance(runs, list):
        errors.append(f"{p} runs must be a list")
        runs = []
    candidate = data["candidateSha"]
    for run in runs:
        errors.extend(run_errors(p, run, candidate))
    if not nonempty_str(data["expectedOutputBasis"]):
        errors.append(f"{p} expectedOutputBasis must be non-empty")
    if data["resultLabel"] not in RESULT_LABELS:
        errors.append(f"{p} resultLabel {data['resultLabel']!r} is not a recognized label")
    if not str_list(data["exclusions"], allow_empty=True):
        errors.append(f"{p} exclusions must be a list of strings")

    results: list[Any] = []
    if version in (2, 3):
        work_order = data["workOrder"]
        if safe_rel(work_order) is None or not work_order.startswith(WORK_ORDERS_DIR + "/") or not work_order.endswith(".json"):
            errors.append(f"{p} workOrder must be a .json path under {WORK_ORDERS_DIR}/")
        if not str_list(data["supersedes"], allow_empty=True) or not all(
            s.startswith(RECORDS_DIR + "/") and s != rel for s in data["supersedes"]
        ):
            errors.append(f"{p} supersedes must list other record paths under {RECORDS_DIR}/")
        results = data["results"] if isinstance(data["results"], list) else []
        if not isinstance(data["results"], list):
            errors.append(f"{p} results must be a list")
        seen: list[str] = []
        for result in results:
            if not isinstance(result, dict) or not nonempty_str(result.get("obligation")):
                errors.append(f"{p} each result needs an obligation")
                continue
            obligation, outcome = result["obligation"], result.get("outcome")
            seen.append(obligation)
            if set(result) != {"obligation", "outcome", "before", "after", "baselineLimitation", "blockedClaim"}:
                errors.append(f"{p} result {obligation} needs exactly obligation, outcome, before, after, baselineLimitation, blockedClaim")
                continue
            if outcome not in OUTCOMES:
                errors.append(f"{p} result {obligation} outcome must be one of {sorted(OUTCOMES)}")
            for key in ("baselineLimitation", "blockedClaim"):
                if result[key] is not None and not nonempty_str(result[key]):
                    errors.append(f"{p} result {obligation} {key} must be null or non-empty")
            errors.extend(_ref_errors(p, "before", result["before"], obligation, commands, runs))
            errors.extend(_ref_errors(p, "after", result["after"], obligation, commands, runs))
            if outcome in ("pass", "fail") and result["after"] is None:
                errors.append(f"{p} result {obligation} outcome {outcome} needs after evidence")
            if outcome == "pass" and result["before"] is None and result["baselineLimitation"] is None:
                errors.append(f"{p} result {obligation} pass needs a before reference or a recorded baselineLimitation")
            if outcome == "deferred" and result["blockedClaim"] is None:
                errors.append(f"{p} result {obligation} deferred needs a blockedClaim")
        if len(set(seen)) != len(seen):
            errors.append(f"{p} each obligation may have only one result")
        review = data["structureReview"]
        if not isinstance(review, dict) or set(review) != STRUCTURE_REVIEW_FIELDS:
            errors.append(f"{p} structureReview needs exactly {sorted(STRUCTURE_REVIEW_FIELDS)}")
        else:
            for key in ("conventionsFollowed", "authorityCheck", "duplicationHiddenStateErrorsCheck"):
                if not nonempty_str(review[key]):
                    errors.append(f"{p} structureReview.{key} must be non-empty")
            for key in ("departures", "migratedCallersVerified"):
                if not str_list(review[key], allow_empty=True):
                    errors.append(f"{p} structureReview.{key} must be a list of strings")
        if version == 3:
            impact_review = data["impactReview"]
            if not isinstance(impact_review, dict) or set(impact_review) != IMPACT_REVIEW_FIELDS:
                errors.append(f"{p} impactReview needs exactly {sorted(IMPACT_REVIEW_FIELDS)}")
            else:
                checks = impact_review.get("invariantsRechecked")
                if not isinstance(checks, list) or not all(
                    isinstance(item, dict) and set(item) == {"id", "testsRun", "result"}
                    and nonempty_str(item.get("id")) and str_list(item.get("testsRun")) and nonempty_str(item.get("result"))
                    for item in checks
                ):
                    errors.append(f"{p} impactReview.invariantsRechecked must list id, non-empty testsRun and result")
                elif len({item["id"] for item in checks}) != len(checks):
                    errors.append(f"{p} impactReview invariant ids must be unique")
                if not str_list(impact_review.get("unexpectedImpact"), allow_empty=True):
                    errors.append(f"{p} impactReview.unexpectedImpact must be a list of strings")
                boundaries = impact_review.get("unaffectedBoundaries")
                if not isinstance(boundaries, list) or not all(
                    isinstance(item, dict) and set(item) == {"boundary", "method"}
                    and nonempty_str(item.get("boundary")) and nonempty_str(item.get("method")) for item in boundaries
                ):
                    errors.append(f"{p} impactReview.unaffectedBoundaries must list boundary and method")
                gaps = impact_review.get("declarationGapReasons")
                if not isinstance(gaps, list) or not all(
                    isinstance(item, dict) and set(item) == {"node", "reason"}
                    and nonempty_str(item.get("node")) and nonempty_str(item.get("reason")) for item in gaps
                ):
                    errors.append(f"{p} impactReview.declarationGapReasons must list node and reason")
    errors.extend(label_errors(p, data, commands, runs, results, version))
    return errors


def label_errors(p: str, data: dict[str, Any], commands: list[Any], runs: list[Any], results: list[Any], version: int) -> list[str]:
    """Label-specific evidence: the claimed result level must be backed by matching evidence."""
    label = data["resultLabel"]
    errors: list[str] = []
    exit_codes = [c.get("exitCode") for c in commands if isinstance(c, dict)]
    outcomes = [r.get("outcome") for r in results if isinstance(r, dict)]
    candidate_push = [
        r for r in runs
        if isinstance(r, dict) and r.get("kind") == "push" and r.get("testedSha") == data["candidateSha"]
        and r.get("conclusion") == "success"
    ]
    if label in PASSING_LABELS:
        if any(code != 0 for code in exit_codes):
            errors.append(f"{p} passing label {label!r} with a non-zero command exit code")
        if any(isinstance(r, dict) and r.get("conclusion") != "success" for r in runs):
            errors.append(f"{p} passing label {label!r} with a non-successful run")
        if "fail" in outcomes:
            errors.append(f"{p} passing label {label!r} with a failed obligation result")
        if "deferred" in outcomes and not data["exclusions"]:
            errors.append(f"{p} passing label {label!r} with deferred results needs exclusions naming them")
    if label in RUN_LABELS and not candidate_push:
        errors.append(f"{p} label {label!r} requires a successful push run whose testedSha is candidateSha")
    if label == "fixed":
        if version != 2:
            errors.append(f"{p} label 'fixed' requires schemaVersion 2 results with before evidence")
        elif any(isinstance(r, dict) and r.get("outcome") == "pass" and r.get("before") is None for r in results):
            errors.append(f"{p} label 'fixed' requires a before reference for every passing result")
    if label == "failed" and not (
        any(code != 0 for code in exit_codes)
        or any(isinstance(r, dict) and r.get("conclusion") != "success" for r in runs)
        or "fail" in outcomes
    ):
        errors.append(f"{p} label 'failed' requires a failing command, run or obligation result")
    if label == "deferred with blocked claim" and "deferred" not in outcomes:
        errors.append(f"{p} label 'deferred with blocked claim' requires a deferred obligation result")
    if label in NON_VERIFYING_LABELS and "pass" in outcomes:
        errors.append(f"{p} label {label!r} cannot carry passing obligation results")
    return errors


def run_errors(p: str, run: Any, candidate: str) -> list[str]:
    if not isinstance(run, dict):
        return [f"{p} each run must be an object"]
    errors: list[str] = []
    if not (isinstance(run.get("id"), str) and run["id"].isdigit()):
        errors.append(f"{p} run id must be a numeric string")
    if not nonempty_str(run.get("conclusion")):
        errors.append(f"{p} run {run.get('id')} needs a conclusion")
    kind = run.get("kind")
    tested, head, base = run.get("testedSha"), run.get("headSha"), run.get("baseSha")
    for key, value in (("testedSha", tested), ("headSha", head)):
        if not isinstance(value, str) or not SHA_RE.match(value):
            errors.append(f"{p} run {run.get('id')} {key} must be a full 40-hex SHA")
    if head != candidate:
        errors.append(f"{p} run {run.get('id')} headSha must equal candidateSha")
    if kind == "push":
        if tested != candidate:
            errors.append(f"{p} push run {run.get('id')} must test candidateSha exactly")
        if base is not None and (not isinstance(base, str) or not SHA_RE.match(base)):
            errors.append(f"{p} push run {run.get('id')} baseSha must be null or a full SHA")
    elif kind == "pull_request":
        if tested == head:
            errors.append(f"{p} pull_request run {run.get('id')} tests a merge commit, not the head itself")
        if not isinstance(base, str) or not SHA_RE.match(base):
            errors.append(f"{p} pull_request run {run.get('id')} must name baseSha")
    else:
        errors.append(f"{p} run kind must be push or pull_request")
    return errors


def _json_at(root: Path, rev: str, rel: str) -> Any:
    text = show(root, rev, rel)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def bookkeeping_problem(root: Path, candidate: str, path: str) -> str | None:
    """None when a post-candidate change to an integrity file is exactly record registration."""
    if path == INVENTORY_PATH:
        before, after = _json_at(root, candidate, path), _json_at(root, "HEAD", path)
        if not isinstance(before, dict) or not isinstance(after, dict):
            return f"{path} is unreadable at candidateSha or HEAD"
        before_entries, after_entries = before.get("entries"), after.get("entries")
        if not isinstance(before_entries, list) or not isinstance(after_entries, list):
            return f"{path} entries are not lists"
        if {k: v for k, v in before.items() if k != "entries"} != {k: v for k, v in after.items() if k != "entries"}:
            return f"{path} metadata changed after candidateSha"
        known = {e.get("path") for e in before_entries if isinstance(e, dict)}
        kept = [e for e in after_entries if isinstance(e, dict) and e.get("path") in known]
        added = [e for e in after_entries if not (isinstance(e, dict) and e.get("path") in known)]
        if kept != before_entries:
            return f"{path} membership or classification changed after candidateSha"
        for entry in added:
            if (
                not isinstance(entry, dict)
                or not str(entry.get("path", "")).startswith(EVIDENCE_SUBDIRS)
                or entry.get("status") != "INFORMATIVE"
            ):
                return f"{path} added an entry that is not an INFORMATIVE evidence record or work order after candidateSha: {entry}"
        return None
    if path in (MANIFEST_PATH, INTEGRITY_PATH):
        before, after = _json_at(root, candidate, MANIFEST_PATH), _json_at(root, "HEAD", MANIFEST_PATH)
        if not isinstance(before, dict) or not isinstance(after, dict):
            return f"{MANIFEST_PATH} is unreadable at candidateSha or HEAD"
        strip = lambda m: {k: v for k, v in m.items() if k != "inventory"}  # noqa: E731
        if strip(before) != strip(after) or (before.get("inventory") or {}).get("path") != (after.get("inventory") or {}).get("path"):
            return f"{MANIFEST_PATH} changed beyond the inventory digest after candidateSha"
        return None
    return f"{path} is not integrity bookkeeping"


def resolve_record_scope(
    rel: str, loaded: dict[str, dict[str, Any]]
) -> tuple[list[str], list[str] | None, str | None]:
    """Return transitive scope, a closed cycle, or an unavailable record path."""

    def walk(node: str, path: list[str]) -> tuple[list[str], list[str] | None, str | None]:
        if node in path:
            start = path.index(node)
            return [], path[start:] + [node], None
        data = loaded.get(node)
        if data is None:
            return [], None, node
        scope = list(data.get("scope", []))
        for old in data.get("supersedes", []) or []:
            inherited, cycle, unavailable = walk(old, path + [node])
            if cycle is not None:
                return scope, cycle, None
            if unavailable is not None:
                return scope, None, unavailable
            scope.extend(inherited)
        return scope, None, None

    scope, cycle, unavailable = walk(rel, [])
    return list(dict.fromkeys(scope)), cycle, unavailable


def compute_project_impact(root: Path, base: str, candidate: str) -> dict[str, list[str]]:
    """Derive actual map impact from the real package diff without author self-attestation."""
    map_path = root / "tools/project_map.py"
    if not map_path.is_file():
        raise CheckError("tools/project_map.py is required for schemaVersion 2 semantic-impact work orders")
    spec = importlib.util.spec_from_file_location("_factory_project_map", map_path)
    if spec is None or spec.loader is None:
        raise CheckError("cannot load tools/project_map.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    graph = module.build(root)
    if graph.get("errors"):
        raise CheckError("project map is invalid: " + "; ".join(graph["errors"]))
    paths = [p for p in changed_paths(root, base, candidate) if not is_evidence_path(p)]
    result = module.impact(graph, paths)
    changed = set(result.get("changedNodes", []))
    stale = {item.get("node") for item in result.get("evidenceBecomingStale", []) if isinstance(item, dict)}
    affected = set(result.get("affectedNodes", []))
    nodes = sorted((changed | stale | affected) - {None})
    interfaces = sorted(n for n in nodes if graph["nodes"].get(n, {}).get("type") == "INTERFACE")
    evidence = sorted(n for n in nodes if graph["nodes"].get(n, {}).get("type") == "EVIDENCE")
    return {"mapNodes": nodes, "interfaces": interfaces, "evidenceBindings": evidence}


def evaluate_evidence(root: Path, base: str) -> dict[str, Any]:
    """Validate work orders and records.

    Returns errors (fail at every stage), pending (fail only at acceptance), and summary data.
    Records and work orders added or modified since the base are current; others are historical.
    """
    errors: list[str] = []
    pending: list[str] = []
    info: dict[str, Any] = {"records": 0, "currentRecords": 0, "coveringScopes": [], "results": {}}
    if not is_commit(root, base):
        errors.append(f"comparison base {base} is unavailable (shallow or incomplete history?)")
        return {"errors": errors, "pending": pending, **info}

    impact_schema_active = "New work orders use `schemaVersion` 2" in (show(root, base, "docs/factory/WORK_ORDER.md") or "")
    current: set[str] = set()
    for line in git_out(root, "diff", "--name-status", base, "HEAD", "--", RECORDS_DIR, WORK_ORDERS_DIR).splitlines():
        parts = line.split("\t")
        if parts[0].startswith("D"):
            errors.append(f"evidence files are preserved, not deleted: {parts[1]}")
        elif parts[0].startswith("R"):
            errors.append(f"evidence files are preserved, not renamed: {parts[1]}")
            current.add(parts[2])
        else:
            current.add(parts[-1])

    def listed(directory: str) -> list[str]:
        folder = root / directory
        rels = []
        for path in sorted(folder.rglob("*")) if folder.is_dir() else []:
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                if not rel.endswith(".json"):
                    errors.append(f"{directory} accepts only .json files: {rel}")
                else:
                    rels.append(rel)
        return rels

    record_rels = listed(RECORDS_DIR)
    info["records"] = len(record_rels)
    work_orders: dict[str, dict[str, Any]] = {}
    work_order_declared: dict[str, str | None] = {}
    for rel in listed(WORK_ORDERS_DIR):
        if not tracked(root, rel):
            errors.append(f"{rel}: work order is not committed; declare it in history before implementation")
            continue
        try:
            data = json.loads((root / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            errors.append(f"{rel}: unreadable JSON ({err})")
            continue
        schema = work_order_schema_errors(rel, data)
        if schema:
            errors.extend(schema)
            continue
        history, declared = work_order_history_errors(root, rel, data)
        if rel in current:
            errors.extend(history)
            if data["schemaVersion"] == 1 and impact_schema_active:
                pending.append(f"{rel}: new work orders use schemaVersion 2 with declaredImpact; legacy schemaVersion 1 is historical only")
        work_orders[rel] = data
        work_order_declared[rel] = declared

    loaded: dict[str, dict[str, Any]] = {}
    for rel in record_rels:
        if not tracked(root, rel):
            errors.append(f"{rel}: record is not committed; evidence must be bound to history")
            continue
        try:
            data = json.loads((root / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            errors.append(f"{rel}: unreadable JSON ({err})")
            continue
        schema = record_schema_errors(rel, data)
        if schema:
            errors.extend(schema)
            continue
        if not is_commit(root, data["candidateSha"]) or not is_commit(root, data["baseSha"]):
            errors.append(f"{rel}: candidateSha or baseSha is not available in history")
            continue
        if not is_ancestor(root, data["candidateSha"], "HEAD"):
            errors.append(f"{rel}: candidateSha is not an ancestor of HEAD")
            continue
        loaded[rel] = data

    superseded: dict[str, str] = {}
    for rel, data in loaded.items():
        if rel in current and data["schemaVersion"] in (2, 3):
            for old in data["supersedes"]:
                superseded[old] = rel

    resolved_scopes: dict[str, list[str]] = {}
    invalid_chain_records: set[str] = set()
    for rel, data in loaded.items():
        if rel not in current or data["schemaVersion"] not in (2, 3):
            continue
        resolved_scope, cycle, unavailable = resolve_record_scope(rel, loaded)
        if cycle is not None:
            errors.append(f"{rel}: supersession chain has a cycle: {' -> '.join(cycle)}")
            invalid_chain_records.add(rel)
            continue
        if unavailable is not None:
            errors.append(f"{rel}: supersedes a record that is not present: {unavailable}")
            invalid_chain_records.add(rel)
            continue
        resolved_scopes[rel] = resolved_scope

    for rel, data in loaded.items():
        if rel not in current:
            continue
        info["currentRecords"] += 1
        own_errors, own_pending = current_record_checks(
            root,
            rel,
            data,
            work_orders,
            work_order_declared,
            resolved_scopes.get(rel, data["scope"]),
            rel in superseded,
        )
        errors.extend(own_errors)
        pending.extend(own_pending)
        if data["schemaVersion"] == 1:
            if rel not in superseded:
                pending.append(f"{rel}: legacy schemaVersion 1 record is not acceptance evidence; supersede it with a schemaVersion 2 or 3 record")
        elif not own_errors and rel not in superseded and rel not in invalid_chain_records:
            info["coveringScopes"].append(resolved_scopes[rel])
            info["results"][rel] = data
    return {"errors": errors, "pending": pending, **info}


def current_record_checks(
    root: Path,
    rel: str,
    data: dict[str, Any],
    work_orders: dict[str, dict[str, Any]],
    declared: dict[str, str | None],
    resolved_scope: list[str],
    is_superseded: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    pending: list[str] = []
    candidate, record_base, scope = data["candidateSha"], data["baseSha"], data["scope"]
    if not is_ancestor(root, record_base, candidate):
        return [f"{rel}: baseSha is not an ancestor of candidateSha"], pending
    # The record's current content was committed by the last commit touching it; a commit cannot
    # name its own SHA, so the candidate must strictly precede that commit.
    touched = git_out(root, "log", "-1", "--format=%H", "HEAD", "--", rel).strip()
    if not touched or touched == candidate or not is_ancestor(root, candidate, touched):
        errors.append(f"{rel}: candidateSha must precede the commit that records it (no self-reference)")
    for entry in scope:
        if not exists_at(root, candidate, entry):
            errors.append(f"{rel}: scope entry does not exist at candidateSha: {entry}")
    for path in changed_paths(root, record_base, candidate):
        if not is_evidence_path(path) and not in_scope(path, scope):
            errors.append(f"{rel}: scope does not cover changed path {path}")

    if data["schemaVersion"] in (2, 3):
        wo_rel = data["workOrder"]
        work_order = work_orders.get(wo_rel)
        if work_order is None:
            errors.append(f"{rel}: work order {wo_rel} is missing or invalid")
        else:
            wo_declared = declared.get(wo_rel)
            if work_order["workPackage"] != data["workPackage"]:
                errors.append(f"{rel}: workPackage differs from its work order")
            if work_order["baselineSha"] != record_base:
                errors.append(f"{rel}: baseSha must equal the work order baselineSha")
            if wo_declared is None or wo_declared == candidate or not is_ancestor(root, wo_declared, candidate):
                errors.append(f"{rel}: work order must be declared in a commit before candidateSha")
            obligations = {o["id"]: o for o in work_order["obligations"]}
            baselines = {b["obligation"]: b for b in work_order["baseline"]}
            results = {r["obligation"]: r for r in data["results"]}
            for obligation in sorted(set(results) - set(obligations)):
                errors.append(f"{rel}: result for an obligation not in the work order: {obligation}")
            for obligation in sorted(set(obligations) - set(results)):
                pending.append(f"{rel}: no result recorded for work-order obligation {obligation}")
            for obligation, result in results.items():
                if obligation not in obligations:
                    continue
                before, after = result["before"], result["after"]
                if isinstance(before, dict) and before.get("kind") == "baseline" and baselines.get(obligation, {}).get("kind") == "limitation":
                    errors.append(f"{rel}: result {obligation} cites a baseline that is a limitation; record baselineLimitation instead")
                if obligations[obligation]["proofKind"] == "ui-before-after" and result["outcome"] == "pass":
                    if not (isinstance(before, dict) and before.get("kind") == "path" and isinstance(after, dict) and after.get("kind") == "path"):
                        errors.append(f"{rel}: result {obligation} ui-before-after proof needs before and after artifact paths")
                for label, ref in (("before", before), ("after", after)):
                    if isinstance(ref, dict) and ref.get("kind") == "path" and not exists_at(root, candidate, ref["reference"]):
                        errors.append(f"{rel}: result {obligation} {label} path does not exist at candidateSha: {ref['reference']}")
            if work_order["schemaVersion"] == 2:
                if data["schemaVersion"] != 3:
                    pending.append(f"{rel}: schemaVersion 2 work order requires a schemaVersion 3 evidence record with impactReview")
                else:
                    try:
                        computed = compute_project_impact(root, record_base, candidate)
                    except CheckError as err:
                        errors.append(f"{rel}: cannot derive project impact: {err}")
                    else:
                        declared_impact = work_order["declaredImpact"]
                        for key in ("mapNodes", "interfaces", "evidenceBindings"):
                            missing = sorted(set(computed[key]) - set(declared_impact[key]))
                            for node in missing:
                                pending.append(f"{rel}: computed {key} impact is undeclared: {node}; amend declaredImpact before acceptance")
                        declared_invariants = {item["id"]: item for item in declared_impact["invariants"]}
                        reviewed = {item["id"]: item for item in data["impactReview"]["invariantsRechecked"]}
                        for invariant, declaration in declared_invariants.items():
                            item = reviewed.get(invariant)
                            if item is None:
                                pending.append(f"{rel}: declared invariant not rechecked: {invariant}")
                                continue
                            missing_tests = sorted(set(declaration["tests"]) - set(item["testsRun"]))
                            if missing_tests:
                                pending.append(f"{rel}: invariant {invariant} did not recheck declared tests: {missing_tests}")
                        extra_invariants = sorted(set(reviewed) - set(declared_invariants))
                        if extra_invariants:
                            errors.append(f"{rel}: impactReview rechecks undeclared invariants: {extra_invariants}")
                        if data["impactReview"]["declarationGapReasons"] and data["resultLabel"] in PASSING_LABELS:
                            pending.append(f"{rel}: passing label cannot retain declarationGapReasons; amend declaredImpact or use a non-passing label")
    if is_superseded:
        return errors, pending
    for path in changed_paths(root, candidate, "HEAD", *[s.rstrip("/") for s in resolved_scope]):
        if path in INTEGRITY_BOOKKEEPING:
            problem = bookkeeping_problem(root, candidate, path)
            if problem is None:
                continue
            pending.append(f"{rel}: stale evidence; {problem}")
            continue
        pending.append(f"{rel}: stale evidence; {path} changed after candidateSha")
    return errors, pending


# --- resume / handoff ------------------------------------------------------------------------------

def describe_ref(ref: Any, record: dict[str, Any]) -> str:
    """Human-readable form of a result reference; command references show the command text."""
    if not isinstance(ref, dict):
        return "none"
    kind, reference = ref.get("kind"), str(ref.get("reference"))
    commands = record.get("commands", [])
    if kind == "command" and reference.isdigit() and int(reference) < len(commands):
        return f"command[{reference}] {str(commands[int(reference)].get('command', ''))[:120]}"
    return f"{kind} {reference}"


def resume_report(root: Path, work_order_rel: str) -> tuple[list[str], list[str]]:
    """Read-only handoff checkpoint for a receiving agent."""
    lines: list[str] = []
    errors: list[str] = []
    path = root / work_order_rel
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        return lines, [f"{work_order_rel}: unreadable work order ({err})"]
    schema = work_order_schema_errors(work_order_rel, data)
    if schema:
        return lines, schema
    history, declared = work_order_history_errors(root, work_order_rel, data)
    errors.extend(history)
    head = git_out(root, "rev-parse", "HEAD").strip()
    branch = git_out(root, "branch", "--show-current").strip() or "(detached)"
    lines.append(f"work order: {work_order_rel} ({data['workPackage']})")
    lines.append(f"HEAD: {head} branch: {branch}")
    lines.append(f"baselineSha: {data['baselineSha']} declared in: {declared or 'unknown'}")
    boundary = data.get("boundary")
    if boundary:
        lines.append("non-goals: " + ("; ".join(boundary["nonGoals"]) or "none"))
        lines.append(f"trust boundary: {boundary['trustBoundary']}")
        lines.append(f"budget: {boundary['budget']}")
    dirty = [line for line in git_out(root, "status", "--porcelain", "--untracked-files=all").splitlines() if line]
    lines.append("dirty paths: " + ("none" if not dirty else "; ".join(dirty)))
    if errors:
        return lines, errors
    changed = changed_paths(root, data["baselineSha"], "HEAD")
    dirty_paths = [line[3:].split(" -> ")[-1] for line in dirty]
    outside = sorted(
        {p for p in changed + dirty_paths if not is_evidence_path(p) and p not in INTEGRITY_BOOKKEEPING and not in_scope(p, data["scope"])}
    )
    lines.append("changes outside declared scope: " + ("none" if not outside else "; ".join(outside)))
    evidence = evaluate_evidence(root, data["baselineSha"])
    results: dict[str, str] = {}
    for rel, record in evidence["results"].items():
        if record.get("workOrder") == work_order_rel:
            for result in record["results"]:
                results[result["obligation"]] = (
                    f"{result['outcome']} in {rel} (candidate {record['candidateSha'][:12]}); "
                    f"after: {describe_ref(result['after'], record)}"
                )
    remaining = []
    for obligation in data["obligations"]:
        status = results.get(obligation["id"])
        lines.append(f"obligation {obligation['id']}: {status or 'no current result'}")
        if not status or not status.startswith("pass"):
            remaining.append(obligation["id"])
    lines.append("remaining obligations: " + ("none" if not remaining else ", ".join(remaining)))
    for item in evidence["pending"]:
        lines.append(f"pending: {item}")
    errors.extend(evidence["errors"])
    return lines, errors


# --- entry point ---------------------------------------------------------------------------------

def check(root: Path, base: str, stage: str = CANDIDATE) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    gates = load_json(root, GATES_PATH, errors)
    preserved = load_json(root, PRESERVED_PATH, errors)
    changes = load_json(root, CHANGES_PATH, errors)
    if errors:
        return errors, {}
    schema = gates_schema_errors(gates) + preserved_schema_errors(preserved) + changes_schema_errors(changes)
    if schema:
        return schema, {}
    errors += routing_errors(root, preserved["routingFiles"])
    errors += preservation_errors(root, preserved)
    errors += gate_errors(root, gates)
    try:
        errors += routing_consistency_errors(root, preserved)
        removal, bootstrap = removal_errors(root, base, gates, preserved, changes)
        errors += removal
        evidence = evaluate_evidence(root, base)
        errors += evidence["errors"]
        pending = list(evidence["pending"])
        changed = [p for p in changed_paths(root, base, "HEAD") if not is_evidence_path(p)] if is_commit(root, base) else []
    except CheckError as err:
        errors.append(str(err))
        return errors, {}
    scopes = evidence["coveringScopes"]
    if changed and not scopes:
        pending.append(
            f"no valid current evidence record covers this change ({len(changed)} changed paths since base)"
        )
    elif scopes:
        for path in changed:
            if not any(in_scope(path, scope) for scope in scopes):
                pending.append(f"changed path not covered by current evidence: {path}")
    if stage == ACCEPTANCE:
        errors += [f"acceptance: {item}" for item in pending]
        pending = []
    summary = {
        "base": base,
        "stage": stage,
        "bootstrap": bootstrap,
        "routingFiles": len(preserved["routingFiles"]),
        "preservedItems": len(preserved_items(preserved)),
        "requiredGates": len(gate_items(gates)),
        "records": evidence["records"],
        "currentRecords": evidence["currentRecords"],
        "pending": pending,
    }
    return errors, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="repository root")
    parser.add_argument("--base", default="auto", help="comparison base commit, or 'auto' to derive it from CI context")
    parser.add_argument(
        "--stage", default="auto", choices=("auto", CANDIDATE, ACCEPTANCE), help="evidence stage; auto derives it from CI context"
    )
    parser.add_argument("--resume", metavar="WORK_ORDER", help="print the handoff checkpoint for a work order and exit")
    args = parser.parse_args()
    root = Path(args.root)
    env = dict(os.environ)
    if args.resume:
        try:
            lines, errors = resume_report(root, args.resume)
        except CheckError as err:
            lines, errors = [], [str(err)]
        for line in lines:
            print(line)
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1 if errors else 0)
    try:
        base = resolve_base(root, env) if args.base == "auto" else args.base
        stage = resolve_stage(env, load_event(env)) if args.stage == "auto" else args.stage
    except CheckError as err:
        print(f"ERROR: {err}")
        raise SystemExit(1)
    errors, summary = check(root, base, stage)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    for item in summary["pending"]:
        print(f"PENDING (candidate stage; fails at acceptance): {item}")
    print(
        "Factory checks valid: "
        f"stage={summary['stage']} base={summary['base'][:12]}{' (bootstrap)' if summary['bootstrap'] else ''} "
        f"routingFiles={summary['routingFiles']} preservedItems={summary['preservedItems']} "
        f"requiredGates={summary['requiredGates']} records={summary['records']} "
        f"currentRecords={summary['currentRecords']} pending={len(summary['pending'])}"
    )


if __name__ == "__main__":
    main()
