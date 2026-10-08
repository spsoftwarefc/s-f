"""SF-11: read-only, source-bound substantive-review assessment.

Candidate supplied cases/results are claims, not independently authenticated evidence.
This module never grants merge, approval, CI, release or deployment authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


class AssuranceError(ValueError):
    """Unsafe, invalid or unavailable review input."""


_SHA = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,95}\Z")
_SELECTOR = {"positive", "negative", "fault", "temporal", "ui"}
_PROOF = {"independent-output", "regression-reproducer", "event-trace", "ui-before-after", "preservation-review", "diff-review"}
_MAX_BYTES = 1024 * 1024
_PLAN = {"schemaVersion", "requiredSelectors", "cases"}
_CASE = {"id", "selector", "requirement", "expected", "proofKind"}
_PACKET = {"schemaVersion", "packageId", "baselineSha", "candidateSha", "candidateTree", "planPath", "planCommit", "changedPaths", "observations", "findings", "uiAffected"}
_OBS = {"id", "status", "evidencePath", "evidenceSha256"}
_FINDING = {"id", "severity", "status", "rationale", "evidencePath", "evidenceSha256"}
_CONTROL = (".github/", ".agents/", "schemas/", "tools/ci_acceptance.py", "AGENTS.md", "CLAUDE.md", "SKILLS.md", "docs/factory/WORK_ORDER.md", "docs/factory/CI_ENFORCEMENT.md")
_UI_SUFFIX = (".tsx", ".jsx", ".vue", ".svelte", ".html", ".css")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for k, v in pairs:
        if k in result:
            raise AssuranceError("duplicate JSON key")
        result[k] = v
    return result


def _json(raw: bytes, context: str) -> dict:
    if len(raw) > _MAX_BYTES:
        raise AssuranceError(f"{context}: oversized JSON")
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise AssuranceError(f"{context}: invalid JSON/UTF-8") from exc
    if type(data) is not dict:
        raise AssuranceError(f"{context}: expected object")
    return data


def _fields(data: Any, names: set[str], context: str) -> dict:
    if type(data) is not dict or set(data) != names:
        raise AssuranceError(f"{context}: incorrect field set")
    return data


def _sha(value: Any, context: str) -> str:
    if type(value) is not str or not _SHA.fullmatch(value):
        raise AssuranceError(f"{context}: full lowercase git SHA required")
    return value


def _id(value: Any, context: str) -> str:
    if type(value) is not str or not _ID.fullmatch(value):
        raise AssuranceError(f"{context}: invalid id")
    return value


def _text(value: Any, context: str) -> str:
    if type(value) is not str or not value.strip() or '\x00' in value or len(value) > 2048:
        raise AssuranceError(f"{context}: invalid text")
    return value


def _path(value: Any, context: str) -> str:
    if (type(value) is not str or not value or len(value) > 1024
            or value.startswith(('/', '\\')) or '\\' in value or ':' in value
            or any(p in ('', '.', '..', '.git') for p in value.split('/'))
            or value != value.strip()):
        raise AssuranceError(f"{context}: unsafe repository path")
    return value


def _digest_check(value: Any, context: str) -> str:
    if type(value) is not str or not _DIGEST.fullmatch(value):
        raise AssuranceError(f"{context}: invalid sha256")
    return value


def _strings(value: Any, context: str, *, nonempty: bool = False) -> list[str]:
    if type(value) is not list or len(value) > 160 or (nonempty and not value):
        raise AssuranceError(f"{context}: invalid list")
    if any(type(v) is not str for v in value) or len(set(value)) != len(value):
        raise AssuranceError(f"{context}: invalid or duplicate list values")
    return value


def validate_plan(plan: Any) -> dict:
    p = _fields(plan, _PLAN, 'case plan')
    if type(p['schemaVersion']) is not int or p['schemaVersion'] != 1:
        raise AssuranceError('unsupported case plan version')
    selectors = _strings(p['requiredSelectors'], 'requiredSelectors', nonempty=True)
    if not set(selectors) <= _SELECTOR or 'positive' not in selectors:
        raise AssuranceError('plan must require positive and only known selectors')
    cases = p['cases']
    if type(cases) is not list or not 1 <= len(cases) <= 100:
        raise AssuranceError('plan requires bounded cases')
    ids = set()
    for case in cases:
        c = _fields(case, _CASE, 'case')
        ident = _id(c['id'], 'case.id')
        if ident in ids:
            raise AssuranceError('duplicate case id')
        ids.add(ident)
        if c['selector'] not in _SELECTOR or c['proofKind'] not in _PROOF:
            raise AssuranceError('unknown selector/proof kind')
        _text(c['requirement'], 'case.requirement')
        _text(c['expected'], 'case.expected')
    if not set(selectors) <= {c['selector'] for c in cases}:
        raise AssuranceError('required selector has no predeclared case')
    if any(c['selector'] == 'ui' and c['proofKind'] != 'ui-before-after' for c in cases):
        raise AssuranceError('UI cases require ui-before-after proof')
    return p


def validate_packet(raw: Any) -> dict:
    p = _fields(raw, _PACKET, 'review packet')
    if type(p['schemaVersion']) is not int or p['schemaVersion'] != 1:
        raise AssuranceError('unsupported review packet version')
    _id(p['packageId'], 'packageId')
    for key in ('baselineSha', 'candidateSha', 'candidateTree', 'planCommit'):
        _sha(p[key], key)
    _path(p['planPath'], 'planPath')
    if type(p['uiAffected']) is not bool:
        raise AssuranceError('uiAffected must be boolean')
    paths = _strings(p['changedPaths'], 'changedPaths')
    for path in paths:
        _path(path, 'changedPath')
    if type(p['observations']) is not list or len(p['observations']) > 100:
        raise AssuranceError('invalid observations')
    ids = set()
    for entry in p['observations']:
        o = _fields(entry, _OBS, 'observation')
        ident = _id(o['id'], 'observation.id')
        if ident in ids:
            raise AssuranceError('duplicate observation')
        ids.add(ident)
        if o['status'] not in ('pass', 'fail', 'unknown'):
            raise AssuranceError('observation: invalid status')
        _path(o['evidencePath'], 'evidencePath')
        _digest_check(o['evidenceSha256'], 'evidenceSha256')
    if type(p['findings']) is not list or len(p['findings']) > 100:
        raise AssuranceError('invalid findings')
    ids.clear()
    for entry in p['findings']:
        f = _fields(entry, _FINDING, 'finding')
        ident = _id(f['id'], 'finding.id')
        if ident in ids:
            raise AssuranceError('duplicate finding')
        ids.add(ident)
        if f['severity'] not in ('blocker', 'material', 'minor') or f['status'] not in ('open', 'resolved', 'deferred'):
            raise AssuranceError('finding: unsupported severity/disposition')
        _text(f['rationale'], 'finding.rationale')
        _path(f['evidencePath'], 'finding.evidencePath')
        _digest_check(f['evidenceSha256'], 'finding.evidenceSha256')
    return p


def _git(root: Path, *args: str, allow_error: bool = False) -> tuple[int, bytes]:
    try:
        proc = subprocess.run(['git', '-C', str(root), '-c', 'core.fsmonitor=false',
                               '-c', 'core.untrackedCache=false', '--no-pager', *args],
                              env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0'},
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AssuranceError('Git unavailable') from exc
    if proc.returncode and not allow_error:
        raise AssuranceError('Git identity or history unavailable: ' + args[0])
    return proc.returncode, proc.stdout


def _one(root: Path, *args: str) -> str:
    return _git(root, *args)[1].decode('utf-8', 'replace').strip()


def _tracked_file(root: Path, path: str, sha: str) -> bool:
    """Require a regular tracked blob at current candidate and matching local bytes."""
    name = _path(path, 'proof path')
    node = root
    for part in name.split('/'):
        node = node / part
        if node.is_symlink():
            return False
    if not node.is_file() or node.stat().st_size > _MAX_BYTES:
        return False
    rc, out = _git(root, 'ls-tree', 'HEAD', '--', name)
    if rc or not out or not out.startswith(b'100644 blob ') and not out.startswith(b'100755 blob '):
        return False
    return _digest(node.read_bytes()) == sha


def _changed(root: Path, baseline: str, candidate: str) -> dict[str, str]:
    data = _git(root, 'diff', '--name-status', '-z', '--no-renames', baseline, candidate, '--')[1].split(b'\0')
    data = [x for x in data if x]
    if len(data) % 2:
        raise AssuranceError('unrecognized Git diff')
    changed = {}
    for i in range(0, len(data), 2):
        kind = data[i].decode('ascii', 'replace')
        name = data[i + 1].decode('utf-8', 'surrogateescape')
        if kind not in ('M', 'A', 'D', 'T'):
            raise AssuranceError('unsupported diff status')
        changed[name] = kind
    return changed


def read_packet(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BYTES:
        raise AssuranceError('review packet missing, symlinked or oversized')
    return validate_packet(_json(path.read_bytes(), 'review packet'))


def inspect_review(root: Path, packet: dict, *, summary: bool = False) -> dict:
    """Derive blockers and reviewability; never accept self-declared proof as truth."""
    p = validate_packet(packet)
    root = root.resolve(strict=True)
    if not root.is_dir() or Path(_one(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise AssuranceError('root must be the Git worktree root')
    head = _one(root, 'rev-parse', 'HEAD')
    tree = _one(root, 'rev-parse', 'HEAD^{tree}')
    blockers: list[str] = []
    warnings: list[str] = []
    if head != p['candidateSha'] or tree != p['candidateTree']:
        blockers.append('STALE_CANDIDATE_IDENTITY')
    for sha, code in ((p['baselineSha'], 'BASELINE_NOT_ANCESTOR'), (p['planCommit'], 'PLAN_NOT_ANCESTOR')):
        if _git(root, 'merge-base', '--is-ancestor', sha, head, allow_error=True)[0]:
            blockers.append(code)
    # Pre-implementation plan must be a single isolated direct child of baseline.
    parents = _one(root, 'rev-list', '-n', '1', '--parents', p['planCommit']).split()
    if len(parents) != 2 or parents[1] != p['baselineSha']:
        blockers.append('PLAN_NOT_FIRST_AFTER_BASELINE')
    if _one(root, 'rev-parse', 'HEAD') == p['planCommit']:
        blockers.append('NO_IMPLEMENTATION_AFTER_PLAN')
    before = _git(root, 'diff-tree', '--no-commit-id', '--name-only', '-r', p['planCommit'], '--')[1]
    plan_paths = [v.decode('utf-8', 'surrogateescape') for v in before.split(b'\0') if v]
    # diff-tree without -z is newline delimited.
    if b'\0' not in before:
        plan_paths = before.decode('utf-8', 'replace').splitlines()
    if plan_paths != [p['planPath']]:
        blockers.append('PLAN_DECLARATION_NOT_ISOLATED')
    committed = _git(root, 'show', f"{p['planCommit']}:{p['planPath']}", allow_error=True)
    if committed[0]:
        raise AssuranceError('predeclared case plan missing from Git history')
    plan = validate_plan(_json(committed[1], 'committed case plan'))
    # Oracle expectations must not be rewritten (even if restored) after declaration.
    plan_touches = _git(root, 'log', '--format=', '--name-only',
                        f"{p['planCommit']}..{head}", '--', p['planPath'])[1].strip()
    if plan_touches:
        blockers.append('PREDECLARED_ORACLE_MODIFIED')
    # Detect control edits across intermediate commits, not only final net diffs:
    # a test introduced and later weakened is still 'A' against baseline.
    history = _one(root, 'rev-list', '--first-parent', '--reverse',
                   f"{p['planCommit']}..{head}").splitlines()
    history_control_changes: set[str] = set()
    for commit in history:
        parents = _one(root, 'rev-list', '-n', '1', '--parents', commit).split()
        if len(parents) != 2:
            blockers.append('MERGE_HISTORY_NEEDS_REVIEW')
            continue
        for path, kind in _changed(root, parents[1], commit).items():
            if ((path.startswith('tests/') and kind in ('M', 'D', 'T'))
                    or path.startswith(_CONTROL) or path.endswith('/SKILL.md')
                    or path.endswith('.schema.json')):
                history_control_changes.add(path)
    changed = _changed(root, p['baselineSha'], head)
    if set(changed) != set(p['changedPaths']):
        blockers.append('DECLARED_DIFF_MISMATCH')
    dirt = _git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all')[1]
    if dirt:
        blockers.append('DIRTY_WORKTREE_SOURCE')
    if any(path.endswith(_UI_SUFFIX) for path in changed) and not p['uiAffected']:
        blockers.append('UI_IMPACT_UNDECLARED')
    if p['uiAffected'] and 'ui' not in plan['requiredSelectors']:
        blockers.append('UI_PROOF_NOT_PREDECLARED')
    control_changes = sorted(path for path, kind in changed.items()
                             if ((path.startswith('tests/') and kind != 'A') or
                                 path.startswith(_CONTROL) or
                                 path.endswith('/SKILL.md') or path.endswith('.schema.json')))
    test_additions = sorted(path for path, kind in changed.items()
                            if path.startswith('tests/') and kind == 'A')
    control_changes = sorted(set(control_changes) | history_control_changes)
    if control_changes:
        blockers.append('CONTROL_CHANGE_EXTERNAL_ASSESSMENT_REQUIRED')
    if test_additions:
        warnings.append('NEW_TESTS_REQUIRE_SUBSTANTIVE_DIFF_REVIEW')
    case_lookup = {c['id']: c for c in plan['cases']}
    observations = {o['id']: o for o in p['observations']}
    if set(case_lookup) != set(observations):
        blockers.append('INCOMPLETE_CASE_OBSERVATIONS')
    for ident, obs in observations.items():
        if ident not in case_lookup:
            continue
        if obs['status'] != 'pass':
            blockers.append('NONPASS_CASE:' + ident)
        if not _tracked_file(root, obs['evidencePath'], obs['evidenceSha256']):
            blockers.append('STALE_OR_MISSING_CASE_PROOF:' + ident)
    for finding in p['findings']:
        if finding['severity'] in ('blocker', 'material') and finding['status'] != 'resolved':
            blockers.append('UNRESOLVED_MATERIAL_FINDING:' + finding['id'])
        if finding['status'] == 'resolved' and not _tracked_file(root, finding['evidencePath'], finding['evidenceSha256']):
            blockers.append('UNVERIFIED_FINDING_RESOLUTION:' + finding['id'])
        if finding['severity'] == 'minor' and finding['status'] != 'resolved':
            warnings.append('OPEN_MINOR_FINDING:' + finding['id'])
    if not p['findings']:
        warnings.append('NO_RECORDED_FINDINGS_NOT_PROOF_OF_NO_DEFECTS')
    result = {'schemaVersion': 1, 'packageId': p['packageId'], 'baselineSha': p['baselineSha'],
              'candidateSha': head, 'candidateTree': tree, 'planCommit': p['planCommit'],
              'changedPaths': sorted(changed), 'controlChangedPaths': control_changes,
              'testAdditions': test_additions, 'predeclaredSelectors': plan['requiredSelectors'],
              'casesRecorded': len(observations), 'casesPlanned': len(case_lookup),
              'blockers': sorted(set(blockers)), 'warnings': sorted(set(warnings)),
              'reviewReady': not blockers, 'proofStatus': 'candidate-recorded-unverified',
              'providerCIVerified': False, 'independentPolicyVerified': False,
              'accepted': False, 'mergeAuthorized': False, 'releaseQualified': False}
    if summary:
        return {key: result[key] for key in ('schemaVersion', 'packageId', 'candidateSha', 'blockers',
                                             'reviewReady', 'proofStatus', 'providerCIVerified',
                                             'independentPolicyVerified', 'accepted', 'mergeAuthorized',
                                             'releaseQualified')}
    return result
