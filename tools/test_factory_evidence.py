import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from check_factory_evidence import (
    ACCEPTANCE,
    CANDIDATE,
    CHANGES_PATH,
    CHECKER_PATH,
    GATES_PATH,
    PRESERVED_PATH,
    RECORDS_DIR,
    SELF_STEP,
    WORK_ORDERS_DIR,
    CheckError,
    check,
    evaluate_evidence,
    gate_errors,
    parse_workflow,
    preservation_errors,
    preserved_schema_errors,
    record_schema_errors,
    removal_errors,
    resolve_base,
    resolve_stage,
    resume_report,
    routing_consistency_errors,
    routing_errors,
    work_order_history_errors,
    work_order_schema_errors,
)

WORKFLOW = """name: verify
on:
  push:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
permissions:
  contents: read
jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: pytest
        run: uv run pytest
      - name: Factory routing, preservation and evidence checks
        env:
          PYTHONPATH: "tools"
        run: |
          uv run python -m unittest
          uv run python tools/check_factory_evidence.py --base auto
  hygiene:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: scan
        run: |
          set -e
          echo ok
"""

# Expected normalized commands, written by hand from WORKFLOW above (independent of the parser).
PYTEST_RUN = "uv run pytest"
SELF_RUN = "uv run python -m unittest\nuv run python tools/check_factory_evidence.py --base auto"
SCAN_RUN = "set -e\necho ok"
PR_TYPES = ["opened", "synchronize", "reopened", "ready_for_review"]


def execution(run: str, env=None, working_directory=None) -> str:
    payload = {"env": env or {}, "run": run, "working-directory": working_directory}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


GATES = {
    "schemaVersion": 2,
    "workflow": ".github/workflows/verify.yml",
    "triggers": {"push": [], "pull_request": PR_TYPES},
    "permissions": {"contents": "read"},
    "jobs": {
        "python": [
            {"name": "pytest", "executionSha256": execution(PYTEST_RUN)},
            {"name": SELF_STEP, "executionSha256": execution(SELF_RUN, {"PYTHONPATH": "tools"})},
        ],
        "hygiene": [{"name": "scan", "executionSha256": execution(SCAN_RUN)}],
    },
    "checkoutFetchDepth": {"python": "0"},
}

PRESERVED = {
    "schemaVersion": 1,
    "requiredFiles": ["AGENTS.md", "CLAUDE.md", "SKILLS.md", ".agents/skills/x/SKILL.md"],
    "requiredHeadings": {"AGENTS.md": ["## Purpose", "## Rules"]},
    "requiredLines": {"CLAUDE.md": ["@AGENTS.md"]},
    "routingFiles": ["AGENTS.md", "CLAUDE.md", "SKILLS.md"],
}

CHANGES = {"schemaVersion": 1, "changes": []}

FILES = {
    "AGENTS.md": "# AGENTS\n\n## Purpose\n\nRead `docs/guide.md`.\n\n## Rules\n\nKeep rules.\n",
    "CLAUDE.md": "# CLAUDE\n\n@AGENTS.md\n\nSee [skills](SKILLS.md).\n",
    "SKILLS.md": "# Skills\n\n[x](.agents/skills/x/SKILL.md) and `SKILL.md` placeholder.\n",
    "docs/guide.md": "guide\n",
    ".agents/skills/x/SKILL.md": "skill\n",
    ".github/workflows/verify.yml": WORKFLOW,
    CHECKER_PATH: "# checker placeholder\n",
    "src/a.py": "a = 1\n",
    "docs/b.md": "b\n",
}

WO_PATH = f"{WORK_ORDERS_DIR}/wp.json"
REC_PATH = f"{RECORDS_DIR}/wp.json"
INVENTORY = "docs/NORMATIVE_INVENTORY.json"


class Repo:
    def __init__(self, case: unittest.TestCase):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        case.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout.strip()

    def write(self, rel: str, content: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))

    def write_json(self, rel: str, value) -> None:
        self.write(rel, json.dumps(value, indent=2) + "\n")

    def delete(self, rel: str) -> None:
        (self.root / rel).unlink()

    def commit(self, message: str = "commit") -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def seed(self, with_controls: bool = True, with_checker: bool = True) -> str:
        for rel, content in FILES.items():
            if rel == CHECKER_PATH and not with_checker:
                continue
            self.write(rel, content)
        if with_controls:
            self.write_json(GATES_PATH, GATES)
            self.write_json(PRESERVED_PATH, PRESERVED)
            self.write_json(CHANGES_PATH, CHANGES)
        return self.commit("seed")


def record(candidate: str, base: str, scope=None, **overrides) -> dict:
    """Legacy schemaVersion 1 record."""
    data = {
        "schemaVersion": 1,
        "workPackage": "PF-2-test",
        "candidateSha": candidate,
        "baseSha": base,
        "scope": scope if scope is not None else ["src/"],
        "commands": [{"command": "uv run pytest", "exitCode": 0, "environment": "test"}],
        "runs": [],
        "expectedOutputBasis": "independently written expectations",
        "resultLabel": "locally verified",
        "exclusions": [],
    }
    data.update(overrides)
    return data


def declared_impact(map_nodes=("COMP-X",), invariants=("INV-1",)) -> dict:
    return {"mapNodes": list(map_nodes), "interfaces": [], "evidenceBindings": [], "invariants": [{"id": item, "source": "AGENTS.md#Rules", "tests": ["tools/test_factory_evidence.py::ImpactBindingTests"]} for item in invariants], "discovery": {"command": "python tools/context_map.py --find x --format json", "workingTreeFingerprint": None, "limitation": "fixture repository has no meaningful context-map baseline"}}


def work_order(baseline: str, obligations=("O1",), scope=("src/",), proof="regression-reproducer", **overrides) -> dict:
    data = {
        "schemaVersion": 1,
        "workPackage": "WP",
        "objective": "objective",
        "baselineSha": baseline,
        "scope": list(scope),
        "obligations": [
            {"id": o, "requirement": "r", "expectedResult": "e", "expectedBasis": "b", "proofKind": proof}
            for o in obligations
        ],
        "baseline": [
            {"obligation": o, "kind": "reproducer", "observed": "fails before", "method": "probe"} for o in obligations
        ],
        "structure": {
            "layers": ["src"],
            "representativeModules": ["src/a.py"],
            "conventions": "c",
            "reusableMechanics": [],
            "policyOwners": [{"policy": "p", "owner": "o"}],
            "interfaces": [{"name": "f", "inputs": "i", "outputs": "o", "sideEffects": "none"}],
        },
        "amendments": [],
    }
    data.update(overrides)
    return data


def work_order_v2(baseline: str, obligations=("O1",), scope=("src/",), **overrides) -> dict:
    data = work_order(baseline, obligations=obligations, scope=scope)
    data["schemaVersion"] = 2
    data["declaredImpact"] = declared_impact()
    data.update(overrides)
    return data


def result(obligation: str, **overrides) -> dict:
    data = {
        "obligation": obligation,
        "outcome": "pass",
        "before": {"kind": "baseline", "reference": obligation},
        "after": {"kind": "command", "reference": "0"},
        "baselineLimitation": None,
        "blockedClaim": None,
    }
    data.update(overrides)
    return data


def record_v2(candidate: str, base: str, obligations=("O1",), scope=("src/",), **overrides) -> dict:
    data = record(candidate, base, scope=list(scope))
    data.update(
        schemaVersion=2,
        workPackage="WP",
        workOrder=WO_PATH,
        supersedes=[],
        results=[result(o) for o in obligations],
        structureReview={
            "conventionsFollowed": "followed module conventions",
            "departures": [],
            "migratedCallersVerified": [],
            "authorityCheck": "no helper gained authority",
            "duplicationHiddenStateErrorsCheck": "none found",
        },
    )
    data.update(overrides)
    return data


def record_v3(candidate: str, base: str, obligations=("O1",), scope=("src/",), **overrides) -> dict:
    data = record_v2(candidate, base, obligations=obligations, scope=scope)
    data["schemaVersion"] = 3
    data["impactReview"] = {"invariantsRechecked": [{"id": "INV-1", "testsRun": ["tools/test_factory_evidence.py::ImpactBindingTests"], "result": "pass"}], "unexpectedImpact": [], "unaffectedBoundaries": [{"boundary": "live trading", "method": "no runtime paths changed"}], "declarationGapReasons": []}
    data.update(overrides)
    return data


def push_run(candidate: str, **overrides) -> dict:
    data = {"id": "2", "kind": "push", "testedSha": candidate, "headSha": candidate, "baseSha": None, "conclusion": "success"}
    data.update(overrides)
    return data


class WorkflowParserTests(unittest.TestCase):
    def test_parser_extracts_triggers_permissions_steps_and_commands(self):
        workflow = parse_workflow(WORKFLOW)
        self.assertEqual(workflow["triggers"], {"push": {}, "pull_request": {"types": PR_TYPES}})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        jobs = workflow["jobs"]
        self.assertEqual(sorted(jobs), ["hygiene", "python"])
        python = jobs["python"]
        self.assertEqual(python[0]["uses"], "actions/checkout@v4")
        self.assertEqual(python[0]["with"], {"fetch-depth": "0"})
        self.assertEqual([s["name"] for s in python[1:]], ["pytest", SELF_STEP])
        self.assertEqual(python[1]["run"], PYTEST_RUN)
        self.assertEqual(python[2]["run"], SELF_RUN)
        self.assertEqual(python[2]["env"], {"PYTHONPATH": "tools"})
        self.assertEqual(jobs["hygiene"][1]["run"], SCAN_RUN)

    def test_unsupported_structure_fails_closed(self):
        with self.assertRaises(ValueError):
            parse_workflow(WORKFLOW.replace("  python:", "\tpython:"))
        with self.assertRaises(ValueError):
            parse_workflow(WORKFLOW.replace("run: uv run pytest", "run: >\n          uv run pytest"))
        with self.assertRaises(ValueError):
            parse_workflow("name: x\non:\n  push:\n")

    def test_execution_affecting_keys_fail_closed(self):
        cases = {
            "step key 'if'": WORKFLOW.replace("      - name: pytest\n", "      - name: pytest\n        if: false\n"),
            "step key 'continue-on-error'": WORKFLOW.replace("      - name: pytest\n", "      - name: pytest\n        continue-on-error: true\n"),
            "step key 'timeout-minutes'": WORKFLOW.replace("      - name: pytest\n", "      - name: pytest\n        timeout-minutes: 1\n"),
            "job key 'if'": WORKFLOW.replace("  python:\n    runs-on", "  python:\n    if: false\n    runs-on"),
            "job key 'continue-on-error'": WORKFLOW.replace("  hygiene:\n    runs-on", "  hygiene:\n    continue-on-error: true\n    runs-on"),
            "top-level key 'concurrency'": WORKFLOW.replace("jobs:\n", "concurrency:\n  group: x\njobs:\n"),
            "trigger option key 'branches'": WORKFLOW.replace("  push:\n", "  push:\n    branches: [main]\n"),
        }
        for expected, text in cases.items():
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ValueError, f"unsupported {expected}"):
                    parse_workflow(text)


class TreeCheckTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(self)
        self.repo.seed()
        self.root = self.repo.root

    def test_valid_tree_passes(self):
        self.assertEqual(routing_errors(self.root, PRESERVED["routingFiles"]), [])
        self.assertEqual(preservation_errors(self.root, PRESERVED), [])
        self.assertEqual(gate_errors(self.root, GATES), [])

    def test_missing_link_target_and_backtick_path_are_errors(self):
        self.repo.delete("docs/guide.md")
        self.repo.delete(".agents/skills/x/SKILL.md")
        errors = routing_errors(self.root, PRESERVED["routingFiles"])
        self.assertTrue(any("does not exist: docs/guide.md" in e for e in errors))
        self.assertTrue(any("does not resolve: .agents/skills/x/SKILL.md" in e for e in errors))

    def test_deleted_heading_skill_and_import_are_errors_but_additions_pass(self):
        self.repo.write("AGENTS.md", FILES["AGENTS.md"] + "\n## New section\n")
        self.assertEqual(preservation_errors(self.root, PRESERVED), [])
        self.repo.write("AGENTS.md", FILES["AGENTS.md"].replace("## Rules", "## Renamed"))
        self.repo.delete(".agents/skills/x/SKILL.md")
        self.repo.write("CLAUDE.md", FILES["CLAUDE.md"].replace("@AGENTS.md", "AGENTS.md"))
        errors = preservation_errors(self.root, PRESERVED)
        self.assertTrue(any("heading missing from AGENTS.md: ## Rules" in e for e in errors))
        self.assertTrue(any("file missing: .agents/skills/x/SKILL.md" in e for e in errors))
        self.assertTrue(any("line missing from CLAUDE.md: @AGENTS.md" in e for e in errors))

    def test_removed_emptied_changed_disabled_and_renamed_gates_are_errors(self):
        wf = ".github/workflows/verify.yml"
        cases = {
            "required gate step missing: python/pytest": WORKFLOW.replace("      - name: pytest\n        run: uv run pytest\n", ""),
            "empty run command: hygiene/scan": WORKFLOW.replace("          set -e\n          echo ok\n", ""),
            "execution changed: python/pytest": WORKFLOW.replace("run: uv run pytest", "run: echo skipped"),
            f"execution changed: python/{SELF_STEP}": WORKFLOW.replace('PYTHONPATH: "tools"', 'PYTHONPATH: "elsewhere"'),
            "required job missing from .github/workflows/verify.yml: hygiene": WORKFLOW.replace("  hygiene:", "  lint:"),
            "checkout must set fetch-depth: 0": WORKFLOW.replace("        with:\n          fetch-depth: 0\n", ""),
            "unsupported step key 'if'": WORKFLOW.replace("      - name: pytest\n", "      - name: pytest\n        if: false\n"),
            "unsupported step key 'continue-on-error'": WORKFLOW.replace("      - name: pytest\n", "      - name: pytest\n        continue-on-error: true\n"),
            "trigger pull_request event types differ": WORKFLOW.replace(", ready_for_review]", "]"),
            "required trigger missing: push": WORKFLOW.replace("  push:\n", ""),
            "permissions must be exactly": WORKFLOW.replace("contents: read", "contents: write"),
        }
        for expected, text in cases.items():
            with self.subTest(expected=expected):
                self.repo.write(wf, text)
                errors = gate_errors(self.root, GATES)
                self.assertTrue(any(expected in e for e in errors), errors)
        self.repo.write(wf, WORKFLOW + "      - name: extra\n        run: echo extra\n")
        self.assertEqual(gate_errors(self.root, GATES), [])

    def test_gate_list_must_include_its_own_step(self):
        gates = copy.deepcopy(GATES)
        gates["jobs"]["python"] = [e for e in gates["jobs"]["python"] if e["name"] != SELF_STEP]
        self.assertTrue(any("must include the factory check step itself" in e for e in gate_errors(self.root, gates)))


class RemovalTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(self)
        self.base = self.repo.seed()
        self.root = self.repo.root

    def shrink(self):
        gates = copy.deepcopy(GATES)
        gates["jobs"]["python"] = [e for e in gates["jobs"]["python"] if e["name"] != "pytest"]
        self.repo.write(".github/workflows/verify.yml", WORKFLOW.replace("      - name: pytest\n        run: uv run pytest\n", ""))
        self.repo.write_json(GATES_PATH, gates)
        return gates

    def test_unrecorded_gate_removal_fails(self):
        gates = self.shrink()
        self.repo.commit()
        errors, bootstrap = removal_errors(self.root, self.base, gates, PRESERVED, CHANGES)
        self.assertFalse(bootstrap)
        self.assertEqual(errors, ["control removed without a change record added in this change: gate:python/pytest"])

    def test_unrecorded_trigger_removal_fails(self):
        gates = copy.deepcopy(GATES)
        del gates["triggers"]["pull_request"]
        errors, _ = removal_errors(self.root, self.base, gates, PRESERVED, CHANGES)
        self.assertEqual(errors, ["control removed without a change record added in this change: trigger:pull_request"])

    def test_removal_recorded_in_this_change_passes(self):
        gates = self.shrink()
        changes = {"schemaVersion": 1, "changes": [{"id": "C1", "removed": ["gate:python/pytest"], "reason": "r", "acceptedBy": "operator"}]}
        self.repo.write_json(CHANGES_PATH, changes)
        self.repo.commit()
        self.assertEqual(removal_errors(self.root, self.base, gates, PRESERVED, changes), ([], False))

    def test_change_record_already_at_base_does_not_license_new_removal(self):
        changes = {"schemaVersion": 1, "changes": [{"id": "C1", "removed": ["gate:python/pytest"], "reason": "r", "acceptedBy": "operator"}]}
        self.repo.write_json(CHANGES_PATH, changes)
        base = self.repo.commit()
        gates = self.shrink()
        self.repo.commit()
        errors, _ = removal_errors(self.root, base, gates, PRESERVED, changes)
        self.assertTrue(any("gate:python/pytest" in e for e in errors))

    def test_change_ledger_is_append_only(self):
        changes = {"schemaVersion": 1, "changes": [{"id": "C1", "removed": ["x"], "reason": "r", "acceptedBy": "o"}]}
        self.repo.write_json(CHANGES_PATH, changes)
        base = self.repo.commit()
        errors, _ = removal_errors(self.root, base, GATES, PRESERVED, CHANGES)
        self.assertTrue(any("append-only" in e for e in errors))

    def test_removed_preserved_heading_fails(self):
        preserved = copy.deepcopy(PRESERVED)
        preserved["requiredHeadings"]["AGENTS.md"] = ["## Purpose"]
        errors, _ = removal_errors(self.root, self.base, GATES, preserved, CHANGES)
        self.assertEqual(errors, ["control removed without a change record added in this change: heading:AGENTS.md### Rules"])

    def test_bootstrap_only_when_base_lacks_controls_and_checker(self):
        fresh = Repo(self)
        base = fresh.seed(with_controls=False, with_checker=False)
        self.assertEqual(removal_errors(fresh.root, base, GATES, PRESERVED, CHANGES), ([], True))

        with_checker = Repo(self)
        base = with_checker.seed(with_controls=False, with_checker=True)
        errors, bootstrap = removal_errors(with_checker.root, base, GATES, PRESERVED, CHANGES)
        self.assertFalse(bootstrap)
        self.assertTrue(any("bootstrap does not apply" in e for e in errors))

        partial = Repo(self)
        partial.seed(with_controls=False, with_checker=False)
        partial.write_json(GATES_PATH, GATES)
        base = partial.commit()
        errors, _ = removal_errors(partial.root, base, GATES, PRESERVED, CHANGES)
        self.assertTrue(any("only one of the control lists" in e for e in errors))

    def test_unavailable_base_fails_closed(self):
        errors, bootstrap = removal_errors(self.root, "0" * 40, GATES, PRESERVED, CHANGES)
        self.assertFalse(bootstrap)
        self.assertTrue(any("unavailable" in e for e in errors))


class StageTests(unittest.TestCase):
    def test_stage_is_derived_from_ci_context(self):
        self.assertEqual(resolve_stage({"GITHUB_EVENT_NAME": "pull_request"}, {"pull_request": {"draft": True}}), CANDIDATE)
        self.assertEqual(resolve_stage({"GITHUB_EVENT_NAME": "pull_request"}, {"pull_request": {"draft": False}}), ACCEPTANCE)
        self.assertEqual(resolve_stage({"GITHUB_EVENT_NAME": "push", "GITHUB_REF_NAME": "main"}, None), ACCEPTANCE)
        self.assertEqual(resolve_stage({"GITHUB_EVENT_NAME": "push", "GITHUB_REF_NAME": "feature"}, None), CANDIDATE)
        self.assertEqual(resolve_stage({}, None), CANDIDATE)

    def test_stage_without_required_context_fails_closed(self):
        with self.assertRaises(CheckError):
            resolve_stage({"GITHUB_EVENT_NAME": "pull_request"}, None)
        with self.assertRaises(CheckError):
            resolve_stage({"GITHUB_EVENT_NAME": "pull_request"}, {"pull_request": {}})
        with self.assertRaises(CheckError):
            resolve_stage({"GITHUB_EVENT_NAME": "schedule"}, None)


class RecordSchemaTests(unittest.TestCase):
    CAND = "a" * 40
    BASE = "b" * 40

    def errors(self, **overrides):
        return record_schema_errors("r.json", record(self.CAND, self.BASE, **overrides))

    def v2_errors(self, **overrides):
        return record_schema_errors("r.json", record_v2(self.CAND, self.BASE, **overrides))

    def assert_error(self, errors, expected):
        self.assertTrue(any(expected in e for e in errors), errors)

    def test_valid_record_schemas(self):
        self.assertEqual(self.errors(), [])
        self.assertEqual(self.v2_errors(), [])

    def test_schema_negative_cases(self):
        cases = [
            ({"candidateSha": "abc123"}, "candidateSha must be a full 40-hex"),
            ({"resultLabel": "done"}, "not a recognized label"),
            ({"commands": [{"command": "x", "exitCode": 1, "environment": "e"}]}, "non-zero command exit code"),
            ({"scope": ["../outside"]}, "scope must be a non-empty list"),
            ({"scope": []}, "scope must be a non-empty list"),
            ({"extra": 1}, "unknown fields"),
            ({"schemaVersion": 3}, "missing fields"),
        ]
        for overrides, expected in cases:
            with self.subTest(expected=expected):
                self.assert_error(self.errors(**overrides), expected)
        data = record(self.CAND, self.BASE)
        del data["expectedOutputBasis"]
        self.assert_error(record_schema_errors("r.json", data), "missing fields")

    def test_run_binding_negative_cases(self):
        good_pr = {"id": "1", "kind": "pull_request", "testedSha": "c" * 40, "headSha": self.CAND, "baseSha": self.BASE, "conclusion": "success"}
        good_push = push_run(self.CAND)
        self.assertEqual(self.errors(runs=[good_pr, good_push]), [])
        cases = [
            (dict(good_pr, testedSha=self.CAND), "tests a merge commit, not the head itself"),
            (dict(good_pr, baseSha=None), "must name baseSha"),
            (dict(good_push, testedSha="d" * 40), "must test candidateSha exactly"),
            (dict(good_push, headSha="d" * 40, testedSha="d" * 40), "headSha must equal candidateSha"),
            (dict(good_push, conclusion="failure"), "non-successful run"),
            (dict(good_push, kind="schedule"), "run kind must be push or pull_request"),
        ]
        for run, expected in cases:
            with self.subTest(expected=expected):
                self.assert_error(self.errors(runs=[run]), expected)

    def test_label_specific_evidence_requirements(self):
        self.assert_error(self.errors(resultLabel="CI verified", runs=[]), "requires a successful push run")
        self.assertEqual(self.errors(resultLabel="CI verified", runs=[push_run(self.CAND)]), [])
        self.assert_error(
            self.errors(resultLabel="accepted", runs=[{"id": "1", "kind": "pull_request", "testedSha": "c" * 40, "headSha": self.CAND, "baseSha": self.BASE, "conclusion": "success"}]),
            "requires a successful push run",
        )
        self.assert_error(self.errors(resultLabel="failed"), "label 'failed' requires a failing")
        self.assertEqual(self.errors(resultLabel="failed", commands=[{"command": "x", "exitCode": 1, "environment": "e"}]), [])
        self.assert_error(self.errors(resultLabel="fixed"), "requires schemaVersion 2 results")
        self.assert_error(self.errors(resultLabel="deferred with blocked claim"), "requires a deferred obligation result")
        self.assert_error(self.v2_errors(resultLabel="not verified"), "cannot carry passing obligation results")
        self.assert_error(
            self.v2_errors(resultLabel="fixed", results=[result("O1", before=None, baselineLimitation="no baseline")]),
            "requires a before reference for every passing result",
        )
        self.assert_error(
            self.v2_errors(results=[result("O1", outcome="fail")]), "passing label 'locally verified' with a failed obligation result"
        )
        self.assert_error(
            self.v2_errors(results=[result("O1", outcome="deferred", blockedClaim="waiting")]), "deferred results needs exclusions"
        )

    def test_v2_result_negative_cases(self):
        cases = [
            ([result("O1", after=None)], "outcome pass needs after evidence"),
            ([result("O1", before=None)], "needs a before reference or a recorded baselineLimitation"),
            ([result("O1", outcome="deferred", before=None, after=None)], "deferred needs a blockedClaim"),
            ([result("O1", after={"kind": "run", "reference": "999"})], "references run 999 not listed"),
            ([result("O1", after={"kind": "command", "reference": "5"})], "missing command index 5"),
            ([result("O1", before={"kind": "baseline", "reference": "O2"})], "must name its own obligation"),
            ([result("O1"), result("O1")], "only one result"),
        ]
        for results, expected in cases:
            with self.subTest(expected=expected):
                self.assert_error(self.v2_errors(results=results, exclusions=["x"]), expected)
        data = record_v2(self.CAND, self.BASE)
        del data["structureReview"]["authorityCheck"]
        self.assert_error(record_schema_errors("r.json", data), "structureReview needs exactly")


class WorkOrderTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(self)
        self.base = self.repo.seed()
        self.root = self.repo.root

    def declare(self, data) -> str:
        self.repo.write_json(WO_PATH, data)
        return self.repo.commit("declare work order")

    def history(self):
        data = json.loads((self.root / WO_PATH).read_text(encoding="utf-8"))
        return work_order_history_errors(self.root, WO_PATH, data)

    def test_schema_requires_baseline_and_structure(self):
        self.assertEqual(work_order_schema_errors(WO_PATH, work_order(self.base)), [])
        data = work_order(self.base)
        data["baseline"] = []
        self.assertTrue(any("needs exactly one baseline entry" in e for e in work_order_schema_errors(WO_PATH, data)))
        data = work_order(self.base)
        data["structure"]["policyOwners"] = []
        self.assertTrue(any("policyOwners" in e for e in work_order_schema_errors(WO_PATH, data)))
        data = work_order(self.base, proof="screenshot")
        self.assertTrue(any("proofKind must be one of" in e for e in work_order_schema_errors(WO_PATH, data)))

    def test_declared_before_implementation_passes(self):
        declared = self.declare(work_order(self.base))
        self.assertEqual(self.history(), ([], declared))

    def test_declared_after_implementation_fails(self):
        self.repo.write("src/a.py", "a = 2\n")
        self.repo.commit("implementation first")
        self.declare(work_order(self.base))
        errors, _ = self.history()
        self.assertTrue(any("declared after implementation began; src/a.py changed" in e for e in errors), errors)

    def test_expectations_and_baseline_are_immutable_unless_amended(self):
        self.declare(work_order(self.base))
        changed = work_order(self.base)
        changed["obligations"][0]["expectedResult"] = "moved goalposts"
        self.repo.write_json(WO_PATH, changed)
        self.repo.commit("change expectation")
        errors, _ = self.history()
        self.assertTrue(any("obligation O1 changed after declaration without an amendment" in e for e in errors), errors)
        changed["amendments"] = [{"obligation": "O1", "reason": "clarified with operator"}]
        self.repo.write_json(WO_PATH, changed)
        self.repo.commit("amend")
        self.assertEqual(self.history()[0], [])
        changed["baseline"][0]["observed"] = "rewritten"
        self.repo.write_json(WO_PATH, changed)
        self.repo.commit("rewrite baseline")
        self.assertTrue(any("baseline entries are immutable" in e for e in self.history()[0]))

    def test_missing_representative_module_and_uncommitted_work_order_fail(self):
        data = work_order(self.base)
        data["structure"]["representativeModules"] = ["src/missing.py"]
        self.repo.write_json(WO_PATH, data)
        errors, _ = self.history()
        self.assertTrue(any("not committed" in e for e in errors), errors)
        self.repo.commit("declare")
        errors, _ = self.history()
        self.assertTrue(any("representative module does not exist at baselineSha: src/missing.py" in e for e in errors), errors)


class EvidenceFlowTests(unittest.TestCase):
    """Work order declared at the baseline, implementation, then evidence in a later commit."""

    def setUp(self):
        self.repo = Repo(self)
        self.base = self.repo.seed()
        self.root = self.repo.root
        self.obligations = ("O1",)

    def declare(self, **overrides) -> str:
        self.repo.write_json(WO_PATH, work_order(self.base, obligations=self.obligations, **overrides))
        return self.repo.commit("declare work order")

    def implement(self, content="a = 2\n") -> str:
        self.repo.write("src/a.py", content)
        return self.repo.commit("implementation")

    def add_record(self, data, path=REC_PATH) -> str:
        self.repo.write_json(path, data)
        return self.repo.commit("record")

    def run_check(self, stage):
        errors, summary = check(self.root, self.base, stage)
        return errors, summary.get("pending", [])

    def test_missing_evidence_fails_at_acceptance_and_is_pending_at_candidate(self):
        self.declare()
        self.implement()
        errors, _ = self.run_check(ACCEPTANCE)
        self.assertTrue(any("acceptance: no valid current evidence record covers this change" in e for e in errors), errors)
        errors, pending = self.run_check(CANDIDATE)
        self.assertEqual(errors, [])
        self.assertTrue(any("no valid current evidence record" in p for p in pending), pending)

    def test_complete_evidence_is_accepted(self):
        self.declare()
        candidate = self.implement()
        self.add_record(record_v2(candidate, self.base))
        errors, pending = self.run_check(ACCEPTANCE)
        self.assertEqual((errors, pending), ([], []))

    def test_later_implementation_outside_scope_blocks_acceptance(self):
        self.declare()
        candidate = self.implement()
        self.add_record(record_v2(candidate, self.base, scope=("src/a.py",)))
        self.repo.write("src/new.py", "new = 1\n")
        self.repo.commit("later implementation")
        errors, _ = self.run_check(ACCEPTANCE)
        self.assertEqual(errors, ["acceptance: changed path not covered by current evidence: src/new.py"])
        errors, pending = self.run_check(CANDIDATE)
        self.assertEqual(errors, [])
        self.assertIn("changed path not covered by current evidence: src/new.py", pending)

    def test_later_change_inside_scope_is_stale_at_acceptance(self):
        self.declare()
        candidate = self.implement()
        self.add_record(record_v2(candidate, self.base))
        self.implement("a = 3\n")
        errors, _ = self.run_check(ACCEPTANCE)
        self.assertEqual(errors, [f"acceptance: {REC_PATH}: stale evidence; src/a.py changed after candidateSha"])

    def test_missing_obligation_result_is_pending_then_fails_acceptance(self):
        self.obligations = ("O1", "O2")
        self.declare()
        candidate = self.implement()
        self.add_record(record_v2(candidate, self.base, obligations=("O1",)))
        errors, pending = self.run_check(CANDIDATE)
        self.assertEqual(errors, [])
        self.assertIn(f"{REC_PATH}: no result recorded for work-order obligation O2", pending)
        errors, _ = self.run_check(ACCEPTANCE)
        self.assertIn(f"acceptance: {REC_PATH}: no result recorded for work-order obligation O2", errors)

    def test_record_bindings_to_work_order(self):
        self.declare()
        candidate = self.implement()
        cases = {
            "result for an obligation not in the work order: O9": record_v2(candidate, self.base, results=[result("O1"), result("O9")]),
            "workPackage differs from its work order": record_v2(candidate, self.base, workPackage="OTHER"),
            "work order docs/factory/evidence/work-orders/missing.json is missing or invalid": record_v2(
                candidate, self.base, workOrder=f"{WORK_ORDERS_DIR}/missing.json"
            ),
        }
        for index, (expected, data) in enumerate(cases.items()):
            with self.subTest(expected=expected):
                path = f"{RECORDS_DIR}/case{index}.json"
                self.add_record(data, path)
                errors = evaluate_evidence(self.root, self.base)["errors"]
                self.assertTrue(any(expected in e for e in errors), errors)
                self.repo.delete(path)
                self.repo.commit("remove case")

    def test_record_base_must_equal_work_order_baseline(self):
        self.declare()
        self.repo.write("docs/b.md", "b2\n")
        other_base = self.repo.commit("unrelated")
        self.repo.write("src/a.py", "a = 2\n")
        candidate = self.repo.commit("implementation")
        self.add_record(record_v2(candidate, other_base))
        errors = evaluate_evidence(self.root, self.base)["errors"]
        self.assertTrue(any("baseSha must equal the work order baselineSha" in e for e in errors), errors)

    def test_work_order_declared_after_candidate_fails(self):
        candidate = self.implement()
        self.repo.write_json(WO_PATH, work_order(candidate))
        self.repo.commit("late work order")
        self.add_record(record_v2(candidate, candidate, scope=("src/",)))
        errors = evaluate_evidence(self.root, self.base)["errors"]
        self.assertTrue(any("work order must be declared in a commit before candidateSha" in e for e in errors), errors)

    def test_limitation_baseline_cannot_be_cited_as_before_evidence(self):
        data = work_order(self.base)
        data["baseline"] = [{"obligation": "O1", "kind": "limitation", "reason": "no reproducer", "method": "n/a"}]
        self.repo.write_json(WO_PATH, data)
        self.repo.commit("declare")
        candidate = self.implement()
        self.add_record(record_v2(candidate, self.base))
        errors = evaluate_evidence(self.root, self.base)["errors"]
        self.assertTrue(any("cites a baseline that is a limitation" in e for e in errors), errors)

    def test_ui_proof_requires_before_and_after_artifact_paths(self):
        self.declare(proof="ui-before-after")
        candidate = self.implement()
        self.add_record(record_v2(candidate, self.base))
        errors = evaluate_evidence(self.root, self.base)["errors"]
        self.assertTrue(any("ui-before-after proof needs before and after artifact paths" in e for e in errors), errors)

    def test_superseding_record_replaces_stale_legacy_record(self):
        self.declare()
        first = self.implement()
        self.add_record(record(first, self.base), f"{RECORDS_DIR}/legacy.json")
        candidate = self.implement("a = 3\n")
        self.add_record(record_v2(candidate, self.base, supersedes=[f"{RECORDS_DIR}/legacy.json"]))
        errors, pending = self.run_check(ACCEPTANCE)
        self.assertEqual((errors, pending), ([], []))

    def test_superseding_record_need_not_repeat_superseded_scope(self):
        work_order_a = f"{WORK_ORDERS_DIR}/a.json"
        work_order_b = f"{WORK_ORDERS_DIR}/b.json"
        record_a = f"{RECORDS_DIR}/a.json"
        record_b = f"{RECORDS_DIR}/b.json"
        self.repo.write_json(work_order_a, work_order(self.base))
        self.repo.commit("declare A")
        candidate_a = self.implement()
        tip_a = self.add_record(record_v2(candidate_a, self.base, workOrder=work_order_a), record_a)

        self.repo.write_json(work_order_b, work_order(tip_a))
        self.repo.commit("declare B")
        self.repo.write("docs/b.md", "b = 2\n")
        candidate_b = self.repo.commit("implementation B")
        self.add_record(
            record_v2(
                candidate_b,
                tip_a,
                workOrder=work_order_b,
                scope=("docs/b.md",),
                supersedes=[record_a],
            ),
            record_b,
        )

        errors, pending = self.run_check(ACCEPTANCE)
        self.assertEqual((errors, pending), ([], []))

    def test_separate_current_records_cover_their_own_paths(self):
        work_order_a = f"{WORK_ORDERS_DIR}/a.json"
        work_order_b = f"{WORK_ORDERS_DIR}/b.json"
        record_a = f"{RECORDS_DIR}/a.json"
        record_b = f"{RECORDS_DIR}/b.json"
        self.repo.write_json(work_order_a, work_order(self.base))
        self.repo.commit("declare A")
        candidate_a = self.implement()
        tip_a = self.add_record(record_v2(candidate_a, self.base, workOrder=work_order_a), record_a)

        self.repo.write_json(work_order_b, work_order(tip_a))
        self.repo.commit("declare B")
        self.repo.write("docs/b.md", "b = 2\n")
        candidate_b = self.repo.commit("implementation B")
        self.add_record(
            record_v2(candidate_b, tip_a, workOrder=work_order_b, scope=("docs/b.md",)),
            record_b,
        )

        errors, pending = self.run_check(ACCEPTANCE)
        self.assertEqual((errors, pending), ([], []))

    def test_supersession_chain_scope_is_transitive(self):
        previous_tip = self.base
        previous_record = None
        changes = (("src/a.py", "a = 2\n"), ("docs/b.md", "b = 2\n"), ("docs/c.md", "c = 2\n"))
        for name, (path, content) in zip(("a", "b", "c"), changes):
            work_order_path = f"{WORK_ORDERS_DIR}/{name}.json"
            record_path = f"{RECORDS_DIR}/{name}.json"
            self.repo.write_json(work_order_path, work_order(previous_tip))
            self.repo.commit(f"declare {name}")
            self.repo.write(path, content)
            candidate = self.repo.commit(f"implementation {name}")
            supersedes = [] if previous_record is None else [previous_record]
            previous_tip = self.add_record(
                record_v2(
                    candidate,
                    previous_tip,
                    workOrder=work_order_path,
                    scope=(path,),
                    supersedes=supersedes,
                ),
                record_path,
            )
            previous_record = record_path

        errors, pending = self.run_check(ACCEPTANCE)
        self.assertEqual((errors, pending), ([], []))

    def test_inherited_scope_change_after_candidate_is_stale(self):
        work_order_a = f"{WORK_ORDERS_DIR}/a.json"
        work_order_b = f"{WORK_ORDERS_DIR}/b.json"
        record_a = f"{RECORDS_DIR}/a.json"
        record_b = f"{RECORDS_DIR}/b.json"
        self.repo.write_json(work_order_a, work_order(self.base))
        self.repo.commit("declare A")
        candidate_a = self.implement()
        tip_a = self.add_record(record_v2(candidate_a, self.base, workOrder=work_order_a), record_a)
        self.repo.write_json(work_order_b, work_order(tip_a))
        self.repo.commit("declare B")
        self.repo.write("docs/b.md", "b = 2\n")
        candidate_b = self.repo.commit("implementation B")
        self.add_record(
            record_v2(
                candidate_b,
                tip_a,
                workOrder=work_order_b,
                scope=("docs/b.md",),
                supersedes=[record_a],
            ),
            record_b,
        )
        self.implement("a = 3\n")

        errors, _ = self.run_check(ACCEPTANCE)
        self.assertTrue(any("stale evidence; src/a.py changed after candidateSha" in error for error in errors), errors)

    def test_supersession_cycle_is_an_error(self):
        record_a = f"{RECORDS_DIR}/a.json"
        record_b = f"{RECORDS_DIR}/b.json"
        self.declare()
        candidate = self.implement()
        self.repo.write_json(record_a, record_v2(candidate, self.base, supersedes=[record_b]))
        self.repo.write_json(record_b, record_v2(candidate, self.base, supersedes=[record_a]))
        self.repo.commit("cyclic records")

        errors = evaluate_evidence(self.root, self.base)["errors"]
        self.assertTrue(any("supersession chain has a cycle" in error for error in errors), errors)

    def test_missing_superseded_record_is_an_error(self):
        missing = f"{RECORDS_DIR}/missing.json"
        self.declare()
        candidate = self.implement()
        self.add_record(record_v2(candidate, self.base, supersedes=[missing]))

        evidence = evaluate_evidence(self.root, self.base)
        self.assertTrue(any(f"supersedes a record that is not present: {missing}" in error for error in evidence["errors"]), evidence)
        self.assertEqual(evidence["coveringScopes"], [])
        self.assertEqual(evidence["results"], {})

    def test_transitively_missing_superseded_record_contributes_no_coverage(self):
        record_a = f"{RECORDS_DIR}/a.json"
        missing = f"{RECORDS_DIR}/missing.json"
        self.declare()
        candidate_a = self.implement("a = 2\n")
        self.repo.write_json(record_a, record_v2(candidate_a, self.base, supersedes=[missing]))
        self.repo.commit("record a")
        candidate_b = self.implement("a = 3\n")
        self.add_record(record_v2(candidate_b, candidate_a, supersedes=[record_a]))

        evidence = evaluate_evidence(self.root, self.base)
        self.assertTrue(any(f"supersedes a record that is not present: {missing}" in error for error in evidence["errors"]), evidence)
        self.assertEqual(evidence["coveringScopes"], [])
        self.assertEqual(evidence["results"], {})

    def test_record_own_changed_path_still_must_be_in_own_scope(self):
        self.declare()
        self.repo.write("src/a.py", "a = 2\n")
        self.repo.write("docs/b.md", "b = 2\n")
        candidate = self.repo.commit("implementation")
        self.add_record(record_v2(candidate, self.base, scope=("src/a.py",)))

        errors = evaluate_evidence(self.root, self.base)["errors"]
        self.assertTrue(any("scope does not cover changed path docs/b.md" in error for error in errors), errors)

    def test_record_with_own_scope_error_contributes_no_coverage(self):
        self.declare()
        self.repo.write("src/a.py", "a = 2\n")
        self.repo.write("docs/b.md", "b = 2\n")
        candidate = self.repo.commit("implementation")
        self.add_record(record_v2(candidate, self.base, scope=("src/a.py",)))

        evidence = evaluate_evidence(self.root, self.base)
        self.assertTrue(any("scope does not cover changed path docs/b.md" in error for error in evidence["errors"]), evidence)
        self.assertEqual(evidence["coveringScopes"], [])

    def test_scope_entry_must_exist_at_candidate(self):
        self.declare()
        candidate = self.implement()
        self.add_record(record_v2(candidate, self.base, scope=("src/", "docs/missing.md")))

        errors = evaluate_evidence(self.root, self.base)["errors"]
        self.assertTrue(any("scope entry does not exist at candidateSha: docs/missing.md" in error for error in errors), errors)

    def test_unsuperseded_legacy_record_is_not_acceptance_evidence(self):
        self.declare()
        candidate = self.implement()
        self.add_record(record(candidate, self.base))
        errors, _ = self.run_check(ACCEPTANCE)
        self.assertTrue(any("legacy schemaVersion 1 record is not acceptance evidence" in e for e in errors), errors)

    def test_record_registration_bookkeeping_is_not_stale(self):
        inventory = {"entries": [{"path": "docs/b.md", "status": "NORMATIVE", "version": "1"}]}
        self.repo.write_json(INVENTORY, inventory)
        self.repo.commit("inventory at baseline")
        self.base = self.repo.git("rev-parse", "HEAD")
        self.declare()
        candidate = self.implement()
        registered = copy.deepcopy(inventory)
        registered["entries"].append({"path": REC_PATH, "status": "INFORMATIVE", "version": "1"})
        self.repo.write_json(INVENTORY, registered)
        self.add_record(record_v2(candidate, self.base, scope=("src/", INVENTORY)))
        errors, pending = self.run_check(ACCEPTANCE)
        self.assertEqual((errors, pending), ([], []))

    def registered_package(self):
        inventory = {"entries": [{"path": "docs/b.md", "status": "NORMATIVE", "version": "1"}]}
        self.repo.write_json(INVENTORY, inventory)
        self.repo.commit("inventory at baseline")
        self.base = self.repo.git("rev-parse", "HEAD")
        self.declare()
        candidate = self.implement()
        inventory["entries"].append({"path": REC_PATH, "status": "INFORMATIVE", "version": "1"})
        self.repo.write_json(INVENTORY, inventory)
        self.add_record(record_v2(candidate, self.base, scope=("src/", INVENTORY)))
        return inventory

    def test_later_work_order_registration_is_not_stale(self):
        inventory = self.registered_package()
        second = f"{WORK_ORDERS_DIR}/second.json"
        inventory["entries"].append({"path": second, "status": "INFORMATIVE", "version": "1"})
        self.repo.write_json(INVENTORY, inventory)
        self.repo.write_json(second, work_order(self.repo.git("rev-parse", "HEAD"), workPackage="SECOND"))
        self.repo.commit("declare second package")
        errors, pending = self.run_check(ACCEPTANCE)
        self.assertEqual((errors, pending), ([], []))

    def test_non_evidence_inventory_addition_after_candidate_is_stale(self):
        inventory = self.registered_package()
        inventory["entries"].append({"path": "docs/new.md", "status": "INFORMATIVE", "version": "1"})
        self.repo.write_json(INVENTORY, inventory)
        self.repo.write("docs/new.md", "new\n")
        self.repo.commit("unrelated inventory addition")
        errors, _ = self.run_check(ACCEPTANCE)
        self.assertTrue(
            any("added an entry that is not an INFORMATIVE evidence record or work order after candidateSha" in e for e in errors),
            errors,
        )

    def test_inventory_reclassification_after_candidate_is_stale(self):
        inventory = {"entries": [{"path": "docs/b.md", "status": "NORMATIVE", "version": "1"}]}
        self.repo.write_json(INVENTORY, inventory)
        self.repo.commit("inventory at baseline")
        self.base = self.repo.git("rev-parse", "HEAD")
        self.declare()
        candidate = self.implement()
        changed = {"entries": [{"path": "docs/b.md", "status": "INFORMATIVE", "version": "1"}]}
        self.repo.write_json(INVENTORY, changed)
        self.add_record(record_v2(candidate, self.base, scope=("src/", INVENTORY)))
        errors, _ = self.run_check(ACCEPTANCE)
        self.assertEqual(
            errors,
            [f"acceptance: {REC_PATH}: stale evidence; {INVENTORY} membership or classification changed after candidateSha"],
        )


class LegacyRecordHistoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(self)
        self.base = self.repo.seed()
        self.root = self.repo.root
        self.repo.write("src/a.py", "a = 2\n")
        self.candidate = self.repo.commit("candidate")

    def add_record(self, data, name="pf2.json") -> str:
        self.repo.write_json(f"{RECORDS_DIR}/{name}", data)
        return self.repo.commit("record")

    def evidence(self, base=None):
        return evaluate_evidence(self.root, base or self.base)

    def test_fresh_legacy_record_validates_but_is_not_acceptance_evidence(self):
        self.add_record(record(self.candidate, self.base))
        result = self.evidence()
        self.assertEqual((result["errors"], result["records"], result["currentRecords"]), ([], 1, 1))
        self.assertTrue(any("legacy schemaVersion 1" in p for p in result["pending"]))

    def test_scope_change_after_candidate_is_stale(self):
        self.add_record(record(self.candidate, self.base))
        self.repo.write("src/a.py", "a = 3\n")
        self.repo.commit("later change")
        self.assertIn(f"{RECORDS_DIR}/pf2.json: stale evidence; src/a.py changed after candidateSha", self.evidence()["pending"])

    def test_scope_must_cover_reviewed_change(self):
        self.repo.write("docs/b.md", "b2\n")
        candidate = self.repo.commit("candidate touching docs")
        self.add_record(record(candidate, self.base))
        errors = self.evidence()["errors"]
        self.assertTrue(any("scope does not cover changed path docs/b.md" in e for e in errors), errors)

    def test_candidate_not_preceding_its_recording_commit_is_rejected(self):
        self.repo.git("checkout", "-q", "-b", "side", self.base)
        self.repo.write("src/a.py", "side\n")
        side = self.repo.commit("side candidate")
        self.repo.git("checkout", "-q", "main")
        self.repo.git("reset", "-q", "--hard", self.base)
        self.repo.write_json(f"{RECORDS_DIR}/pf2.json", record(side, self.base))
        self.repo.commit("record names side")
        self.repo.git("merge", "-q", "--no-ff", "-m", "merge side", "side")
        self.assertEqual(
            self.evidence()["errors"],
            [f"{RECORDS_DIR}/pf2.json: candidateSha must precede the commit that records it (no self-reference)"],
        )

    def test_candidate_not_ancestor_of_head_fails(self):
        self.repo.git("checkout", "-q", "-b", "side", self.base)
        self.repo.write("src/a.py", "side\n")
        side = self.repo.commit("side")
        self.repo.git("checkout", "-q", "main")
        self.add_record(record(side, self.base))
        self.assertTrue(any("candidateSha is not an ancestor of HEAD" in e for e in self.evidence()["errors"]))

    def test_historical_record_does_not_block_later_changes(self):
        self.add_record(record(self.candidate, self.base))
        new_base = self.repo.git("rev-parse", "HEAD")
        self.repo.write("src/a.py", "a = 4\n")
        self.repo.commit("legitimate later change")
        result = self.evidence(new_base)
        self.assertEqual((result["errors"], result["pending"], result["currentRecords"]), ([], [], 0))

    def test_deleting_a_record_fails(self):
        self.add_record(record(self.candidate, self.base))
        new_base = self.repo.git("rev-parse", "HEAD")
        self.repo.delete(f"{RECORDS_DIR}/pf2.json")
        self.repo.commit("delete record")
        self.assertTrue(any("preserved, not deleted" in e for e in self.evidence(new_base)["errors"]))

    def test_uncommitted_record_fails(self):
        self.repo.write_json(f"{RECORDS_DIR}/pf2.json", record(self.candidate, self.base))
        self.assertTrue(any("not committed" in e for e in self.evidence()["errors"]))


class BaseResolutionTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(self)
        self.first = self.repo.seed()
        self.repo.write("src/a.py", "main two\n")
        self.second = self.repo.commit("main two")
        self.root = self.repo.root

    def test_push_to_default_branch_uses_first_parent(self):
        self.assertEqual(resolve_base(self.root, {"GITHUB_EVENT_NAME": "push", "GITHUB_REF_NAME": "main"}), self.first)

    def test_push_to_branch_and_pull_request_use_merge_base_with_origin(self):
        self.repo.git("update-ref", "refs/remotes/origin/main", self.first)
        self.repo.git("checkout", "-q", "-b", "feature")
        self.repo.write("src/a.py", "feature\n")
        self.repo.commit("feature")
        self.assertEqual(resolve_base(self.root, {"GITHUB_EVENT_NAME": "push", "GITHUB_REF_NAME": "feature"}), self.first)
        self.assertEqual(resolve_base(self.root, {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_BASE_REF": "main"}), self.first)

    def test_missing_context_or_refs_fail_closed(self):
        with self.assertRaises(CheckError):
            resolve_base(self.root, {"GITHUB_EVENT_NAME": "pull_request"})
        with self.assertRaises(CheckError):
            resolve_base(self.root, {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_BASE_REF": "main"})
        with self.assertRaises(CheckError):
            resolve_base(self.root, {"GITHUB_EVENT_NAME": "schedule"})

    def test_local_run_falls_back_to_local_default_branch(self):
        self.assertEqual(resolve_base(self.root, {}), self.second)


class ResumeReportTests(unittest.TestCase):
    def test_handoff_report_shows_revision_dirty_scope_and_remaining_obligations(self):
        repo = Repo(self)
        base = repo.seed()
        repo.write_json(WO_PATH, work_order(base, obligations=("O1", "O2")))
        repo.commit("declare")
        repo.write("src/a.py", "a = 2\n")
        candidate = repo.commit("implementation")
        repo.write_json(REC_PATH, record_v2(candidate, base, obligations=("O1",)))
        repo.commit("record")
        repo.write("docs/b.md", "outside plan\n")
        repo.commit("out of scope change")
        repo.write("src/wip.py", "wip = True\n")
        lines, errors = resume_report(repo.root, WO_PATH)
        self.assertEqual(errors, [])
        text = "\n".join(lines)
        self.assertIn(f"HEAD: {repo.git('rev-parse', 'HEAD')} branch: main", text)
        self.assertIn("?? src/wip.py", text)
        self.assertIn("changes outside declared scope: docs/b.md", text)
        self.assertIn(f"obligation O1: pass in {REC_PATH}", text)
        self.assertIn("obligation O2: no current result", text)
        self.assertIn("remaining obligations: O2", text)
        self.assertIn(f"pending: {REC_PATH}: no result recorded for work-order obligation O2", text)

    def test_handoff_report_surfaces_work_order_problems(self):
        repo = Repo(self)
        base = repo.seed()
        repo.write("src/a.py", "a = 2\n")
        repo.commit("implementation before declaration")
        repo.write_json(WO_PATH, work_order(base))
        repo.commit("declare late")
        _, errors = resume_report(repo.root, WO_PATH)
        self.assertTrue(any("declared after implementation began" in e for e in errors), errors)


class EndToEndTests(unittest.TestCase):
    def test_check_reports_bootstrap_then_enforces(self):
        repo = Repo(self)
        base = repo.seed(with_controls=False, with_checker=False)
        repo.write(CHECKER_PATH, FILES[CHECKER_PATH])
        repo.write_json(GATES_PATH, GATES)
        repo.write_json(PRESERVED_PATH, PRESERVED)
        repo.write_json(CHANGES_PATH, CHANGES)
        introduced = repo.commit("introduce controls")
        errors, summary = check(repo.root, base, CANDIDATE)
        self.assertEqual(errors, [])
        self.assertTrue(summary["bootstrap"])
        self.assertTrue(summary["pending"])

        repo.delete(PRESERVED_PATH)
        repo.commit("delete list")
        errors, _ = check(repo.root, introduced, CANDIDATE)
        self.assertTrue(any(f"{PRESERVED_PATH}: required file is missing" in e for e in errors), errors)


CHECKLIST = "docs/checklist.md"
ROUTING = dict(
    PRESERVED,
    requiredReferences={"SKILLS.md": [".agents/skills/x/SKILL.md"], "AGENTS.md": ["docs/guide.md"]},
    hostAdapters={"CLAUDE.md": {"requires": ["@AGENTS.md"], "forbidHeadingsFrom": CHECKLIST}},
    canonicalSkillRoot=".agents/skills/",
    forbiddenText={"SKILLS.md": ["is optional when"]},
)


class RoutingConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(self)
        self.repo.write(CHECKLIST, "# Checklist\n\n## 1. Pre-implementation checkpoint\n\nBody.\n")
        self.base = self.repo.seed()
        self.repo.write_json(PRESERVED_PATH, ROUTING)
        self.base = self.repo.commit("routing controls")
        self.root = self.repo.root

    def errors(self):
        return routing_consistency_errors(self.root, ROUTING)

    def test_consistent_routing_passes(self):
        self.assertEqual(preserved_schema_errors(ROUTING), [])
        self.assertEqual(self.errors(), [])
        errors, _ = check(self.root, self.base, CANDIDATE)
        self.assertEqual(errors, [])

    def test_host_adapter_copying_checklist_heading_fails(self):
        self.repo.write("CLAUDE.md", FILES["CLAUDE.md"] + "\n## 1. Pre-implementation checkpoint\n\nCopied body.\n")
        self.assertEqual(self.errors(), [f"host adapter CLAUDE.md copies a heading from {CHECKLIST}: ## 1. Pre-implementation checkpoint"])

    def test_host_adapter_without_entry_reference_fails(self):
        self.repo.write("CLAUDE.md", "# CLAUDE\n\nSee the docs.\n")
        self.assertIn("host adapter CLAUDE.md must reference its entry point: @AGENTS.md", self.errors())

    def test_skill_body_outside_canonical_root_fails(self):
        self.repo.write(".claude/skills/x/SKILL.md", "---\nname: x\n---\nduplicate\n")
        self.repo.commit("duplicate skill body")
        self.assertEqual(self.errors(), ["skill body outside the canonical location .agents/skills/: .claude/skills/x/SKILL.md"])

    def test_missing_required_reference_fails(self):
        self.repo.write("SKILLS.md", "# Skills\n\nNo routes here.\n")
        self.assertIn("required routing reference missing from SKILLS.md: .agents/skills/x/SKILL.md", self.errors())

    def test_reintroduced_contradiction_text_fails_case_insensitively(self):
        self.repo.write("SKILLS.md", FILES["SKILLS.md"] + "\nThe checklist IS OPTIONAL WHEN records exist.\n")
        self.assertEqual(self.errors(), ["forbidden contradiction text in SKILLS.md: is optional when"])

    def test_routing_errors_surface_through_check(self):
        self.repo.write("SKILLS.md", "# Skills\n\nNo routes here.\n")
        self.repo.commit("drop routes")
        errors, _ = check(self.root, self.base, CANDIDATE)
        self.assertIn("required routing reference missing from SKILLS.md: .agents/skills/x/SKILL.md", errors)

    def test_schema_rejects_malformed_and_unknown_routing_keys(self):
        cases = {
            "requiredReferences must map": dict(ROUTING, requiredReferences={"SKILLS.md": []}),
            "hostAdapters must map": dict(ROUTING, hostAdapters={"CLAUDE.md": {"requires": []}}),
            "canonicalSkillRoot must be": dict(ROUTING, canonicalSkillRoot=".agents/skills"),
            "forbiddenText must map": dict(ROUTING, forbiddenText={"../x.md": ["a"]}),
            "unknown keys": dict(ROUTING, extraRule=True),
        }
        for expected, data in cases.items():
            with self.subTest(expected=expected):
                self.assertTrue(any(expected in e for e in preserved_schema_errors(data)), preserved_schema_errors(data))

    def test_removing_a_routing_rule_needs_a_change_record(self):
        weakened = copy.deepcopy(ROUTING)
        weakened["forbiddenText"] = {}
        del weakened["hostAdapters"]
        errors, _ = removal_errors(self.root, self.base, GATES, weakened, CHANGES)
        self.assertEqual(
            errors,
            [
                "control removed without a change record added in this change: adapter-headings:CLAUDE.md#docs/checklist.md",
                "control removed without a change record added in this change: adapter-requires:CLAUDE.md#@AGENTS.md",
                "control removed without a change record added in this change: adapter:CLAUDE.md",
                "control removed without a change record added in this change: forbidden:SKILLS.md#is optional when",
            ],
        )


class WorkOrderBoundaryAndResumeDetailTests(unittest.TestCase):
    BOUNDARY = {"nonGoals": ["no merge"], "trustBoundary": "routing docs", "budget": "one package"}

    def test_boundary_is_optional_but_validated(self):
        base = "b" * 40
        self.assertEqual(work_order_schema_errors(WO_PATH, work_order(base)), [])
        self.assertEqual(work_order_schema_errors(WO_PATH, work_order(base, boundary=self.BOUNDARY)), [])
        bad = work_order(base, boundary={"nonGoals": "no merge", "trustBoundary": "x", "budget": "y"})
        self.assertTrue(any("boundary needs exactly" in e for e in work_order_schema_errors(WO_PATH, bad)))

    def test_resume_report_shows_boundary_and_after_command_text(self):
        repo = Repo(self)
        base = repo.seed()
        repo.write_json(WO_PATH, work_order(base, boundary=self.BOUNDARY))
        repo.commit("declare")
        repo.write("src/a.py", "a = 2\n")
        candidate = repo.commit("implementation")
        repo.write_json(REC_PATH, record_v2(candidate, base))
        repo.commit("record")
        lines, errors = resume_report(repo.root, WO_PATH)
        self.assertEqual(errors, [])
        text = "\n".join(lines)
        self.assertIn("non-goals: no merge", text)
        self.assertIn("trust boundary: routing docs", text)
        self.assertIn("budget: one package", text)
        self.assertIn("after: command[0] uv run pytest", text)


class ImpactBindingTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(self)
        self.base = self.repo.seed()
        self.root = self.repo.root

    def declare_v2(self, impact=None):
        data = work_order_v2(self.base)
        if impact is not None:
            data["declaredImpact"] = impact
        self.repo.write_json(WO_PATH, data)
        return self.repo.commit("declare v2 work order")

    def implement(self):
        self.repo.write("src/a.py", "a = 2\n")
        return self.repo.commit("implementation")

    def add_record(self, data):
        self.repo.write_json(REC_PATH, data)
        return self.repo.commit("record")

    def test_v2_work_order_requires_declared_impact_and_v3_record_requires_impact_review(self):
        good = work_order_v2(self.base)
        self.assertEqual(work_order_schema_errors(WO_PATH, good), [])
        missing = dict(good)
        del missing["declaredImpact"]
        self.assertTrue(any("missing fields" in e for e in work_order_schema_errors(WO_PATH, missing)))
        candidate = "a" * 40
        rec = record_v3(candidate, self.base)
        self.assertEqual(record_schema_errors("r.json", rec), [])
        bad = dict(rec)
        del bad["impactReview"]
        self.assertTrue(any("missing fields" in e for e in record_schema_errors("r.json", bad)))

    def test_declared_impact_is_immutable_without_explicit_amendment(self):
        self.declare_v2()
        data = json.loads((self.root / WO_PATH).read_text(encoding="utf-8"))
        data["declaredImpact"]["mapNodes"].append("COMP-Y")
        self.repo.write_json(WO_PATH, data)
        self.repo.commit("expand impact")
        errors, _ = work_order_history_errors(self.root, WO_PATH, data)
        self.assertTrue(any("declaredImpact changed after declaration" in e for e in errors), errors)
        data["amendments"] = [{"obligation": "declaredImpact", "reason": "computed impact exposed COMP-Y"}]
        self.repo.write_json(WO_PATH, data)
        self.repo.commit("record impact amendment")
        self.assertEqual(work_order_history_errors(self.root, WO_PATH, data)[0], [])

    def test_computed_impact_gap_is_pending_then_fails_acceptance(self):
        self.declare_v2(impact=declared_impact(map_nodes=("COMP-X",)))
        candidate = self.implement()
        self.add_record(record_v3(candidate, self.base))
        computed = {"mapNodes": ["COMP-X", "COMP-Y"], "interfaces": [], "evidenceBindings": []}
        with patch("check_factory_evidence.compute_project_impact", return_value=computed):
            errors, summary = check(self.root, self.base, CANDIDATE)
            self.assertEqual(errors, [])
            self.assertTrue(any("computed mapNodes impact is undeclared: COMP-Y" in p for p in summary["pending"]))
            errors, _ = check(self.root, self.base, ACCEPTANCE)
            self.assertTrue(any("acceptance:" in e and "COMP-Y" in e for e in errors), errors)

    def test_amended_declaration_and_invariant_recheck_allow_acceptance(self):
        self.declare_v2(impact=declared_impact(map_nodes=("COMP-X",)))
        data = json.loads((self.root / WO_PATH).read_text(encoding="utf-8"))
        data["declaredImpact"]["mapNodes"].append("COMP-Y")
        data["amendments"] = [{"obligation": "declaredImpact", "reason": "computed impact exposed COMP-Y"}]
        self.repo.write_json(WO_PATH, data)
        self.repo.commit("amend impact")
        candidate = self.implement()
        self.add_record(record_v3(candidate, self.base))
        computed = {"mapNodes": ["COMP-X", "COMP-Y"], "interfaces": [], "evidenceBindings": []}
        with patch("check_factory_evidence.compute_project_impact", return_value=computed):
            errors, summary = check(self.root, self.base, ACCEPTANCE)
            self.assertEqual(errors, [])
            self.assertEqual(summary["pending"], [])

    def test_missing_declared_invariant_recheck_is_not_acceptance_evidence(self):
        self.declare_v2()
        candidate = self.implement()
        rec = record_v3(candidate, self.base)
        rec["impactReview"]["invariantsRechecked"] = []
        self.add_record(rec)
        computed = {"mapNodes": ["COMP-X"], "interfaces": [], "evidenceBindings": []}
        with patch("check_factory_evidence.compute_project_impact", return_value=computed):
            errors, summary = check(self.root, self.base, CANDIDATE)
            self.assertEqual(errors, [])
            self.assertTrue(any("declared invariant not rechecked: INV-1" in p for p in summary["pending"]))
            errors, _ = check(self.root, self.base, ACCEPTANCE)
            self.assertTrue(any("INV-1" in e for e in errors), errors)

    def test_new_legacy_work_order_is_pending_then_fails_acceptance_after_activation(self):
        self.repo.write("docs/factory/WORK_ORDER.md", "New work orders use `schemaVersion` 2; schemaVersion 1 is historical compatibility only.\\n")
        self.base = self.repo.commit("activate semantic-impact schema")
        self.repo.write_json(WO_PATH, work_order(self.base))
        self.repo.commit("legacy declaration")
        errors, summary = check(self.root, self.base, CANDIDATE)
        self.assertEqual(errors, [])
        self.assertTrue(any("new work orders use schemaVersion 2" in p for p in summary["pending"]))
        errors, _ = check(self.root, self.base, ACCEPTANCE)
        self.assertTrue(any("new work orders use schemaVersion 2" in e for e in errors), errors)

if __name__ == "__main__":
    unittest.main()
