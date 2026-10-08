"""SF-08: offline, read-only work-order and Git-history assessment.

This module does not execute project commands, verify hosted receipts, or grant
acceptance. Project-owned state remains the authority for those dispositions.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


class WorkError(ValueError):
    """Malformed declaration, unsafe path, or unavailable Git evidence."""


_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,95}\Z")
_PROOFS = frozenset({"regression-reproducer", "independent-output", "event-trace",
                     "ui-before-after", "performance-measurement", "preservation-review",
                     "diff-review"})
_TOP = frozenset({"schemaVersion", "id", "baseline", "objective", "nonGoals",
                  "allowedPaths", "requirements", "decisions", "obligations",
                  "dependencies", "structure", "impact", "budget", "externalEffects",
                  "proofs", "amendments"})


def _fields(obj: Any, keys: set[str] | frozenset[str], where: str) -> dict:
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise WorkError(f"{where}: expected exactly {', '.join(sorted(keys))}")
    return obj


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise WorkError(f"{where}: expected non-empty text")
    return value


def _relative(value: Any, where: str, *, pattern: bool = False) -> str:
    value = _text(value, where)
    if (value.startswith('/') or '\\' in value or value.endswith('/') or
        any(x in ('.', '..', '') for x in value.split('/')) or
        any(x == '.git' for x in value.split('/')) or
        (value != value.strip())):
        raise WorkError(f"{where}: expected canonical repository-relative POSIX path")
    parts = value.split('/')
    if any('*' in p or '?' in p or '[' in p or ']' in p for p in parts):
        if not (pattern and len(parts) > 1 and parts[-1] == '**' and
                all(not any(c in p for c in '*?[]') for p in parts[:-1])):
            raise WorkError(f"{where}: only suffix /** prefix patterns are permitted")
    return value


def _strings(value: Any, where: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise WorkError(f"{where}: expected {'non-empty ' if nonempty else ''}list")
    result = [_text(s, where) for s in value]
    if len(set(result)) != len(result):
        raise WorkError(f"{where}: duplicate entries")
    return result


def validate_order(raw: Any, *, path: str | None = None) -> dict:
    """Closed v1 schema; no mutable 'accepted' or provider-status fields."""
    data = _fields(raw, _TOP, 'work order')
    if type(data['schemaVersion']) is not int or data['schemaVersion'] != 1:
        raise WorkError('unsupported work-order schemaVersion (supported: 1)')
    if not _ID.fullmatch(_text(data['id'], 'id')):
        raise WorkError('id: invalid package identifier')
    if path is not None and Path(path).name != data['id'] + '.json':
        raise WorkError('work-order filename must match id.json')
    baseline = _fields(data['baseline'], {'commit', 'tree'}, 'baseline')
    for key in ('commit', 'tree'):
        if not isinstance(baseline[key], str) or not _HEX40.fullmatch(baseline[key]):
            raise WorkError(f'baseline.{key}: expected full lowercase Git SHA')
    _text(data['objective'], 'objective')
    for key in ('nonGoals', 'requirements', 'decisions', 'structure', 'impact', 'externalEffects'):
        _strings(data[key], key, nonempty=key in ('nonGoals', 'requirements', 'structure', 'impact'))
    allowed = _strings(data['allowedPaths'], 'allowedPaths', nonempty=True)
    for p in allowed:
        _relative(p, 'allowedPaths', pattern=True)
    if path is not None and not _allowed(path, allowed):
        raise WorkError('work-order path must itself be in allowedPaths')
    if not isinstance(data['obligations'], list) or not data['obligations']:
        raise WorkError('obligations: expected non-empty list')
    ids = set()
    for i, item in enumerate(data['obligations']):
        o = _fields(item, {'id', 'description', 'proofKinds'}, f'obligations[{i}]')
        ident = _text(o['id'], f'obligations[{i}].id')
        if not _ID.fullmatch(ident) or ident in ids:
            raise WorkError(f'obligations[{i}].id: duplicate/invalid')
        ids.add(ident)
        _text(o['description'], f'obligations[{i}].description')
        kinds = _strings(o['proofKinds'], f'obligations[{i}].proofKinds', nonempty=True)
        if not set(kinds) <= _PROOFS:
            raise WorkError(f'obligations[{i}]: unknown proof kind')
    if not isinstance(data['dependencies'], list):
        raise WorkError('dependencies: expected list')
    dep_ids = set()
    for i, dependency in enumerate(data['dependencies']):
        dep = _fields(dependency, {'id', 'kind', 'revision', 'scope'}, f'dependencies[{i}]')
        name = _text(dep['id'], f'dependencies[{i}].id')
        if name in dep_ids:
            raise WorkError('dependencies: duplicate id')
        dep_ids.add(name)
        if dep['kind'] not in ('git-ancestor', 'external') or dep['scope'] not in ('development', 'external-effect'):
            raise WorkError('dependencies: unsupported kind/scope')
        if dep['kind'] == 'git-ancestor':
            if not isinstance(dep['revision'], str) or not _HEX40.fullmatch(dep['revision']):
                raise WorkError('dependencies: git-ancestor requires full revision')
        elif dep['revision'] is not None:
            raise WorkError('dependencies: external revision must be null')
    budget = _fields(data['budget'], {'hostedRuns', 'repairDiagnosticAfter', 'network', 'execution'}, 'budget')
    for key in ('hostedRuns', 'repairDiagnosticAfter'):
        if type(budget[key]) is not int or budget[key] < 0:
            raise WorkError(f'budget.{key}: expected nonnegative integer')
    _text(budget['network'], 'budget.network')
    _text(budget['execution'], 'budget.execution')
    if not isinstance(data['proofs'], dict) or not set(data['proofs']) <= ids:
        raise WorkError('proofs: entries must reference declared obligations')
    for ident, proof_entries in data['proofs'].items():
        if not isinstance(proof_entries, list):
            raise WorkError(f'proofs.{ident}: expected list')
        kinds = {kind for ob in data['obligations'] if ob['id'] == ident for kind in ob['proofKinds']}
        for item in proof_entries:
            entry = _fields(item, {'kind', 'path'}, f'proofs.{ident}')
            if not isinstance(entry['kind'], str) or entry['kind'] not in kinds:
                raise WorkError(f'proofs.{ident}: kind not required by obligation')
            _relative(entry['path'], f'proofs.{ident}.path')
    if not isinstance(data['amendments'], list):
        raise WorkError('amendments: expected list')
    for amendment in data['amendments']:
        _fields(amendment, {'reason'}, 'amendment')
        _text(amendment['reason'], 'amendment.reason')
    return data


def _allowed(path: str, patterns: list[str]) -> bool:
    return any(path.startswith(p[:-3] + '/') if p.endswith('/**') else path == p
               for p in patterns)


def _git(root: Path, *args: str, allow_failure: bool = False) -> tuple[int, bytes]:
    env = {**os.environ, 'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0'}
    try:
        run = subprocess.run(['git', '-C', str(root), '-c', 'core.fsmonitor=false',
                              '-c', 'core.untrackedCache=false', '--no-pager', *args],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                             timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkError(f'Git unavailable: {exc}') from exc
    if run.returncode and not allow_failure:
        msg = run.stderr.decode('utf-8', 'replace').strip()[:300]
        raise WorkError(f'git {args[0]}: {msg or "failed"}')
    return run.returncode, run.stdout


def _one(root: Path, *args: str) -> str:
    return _git(root, *args)[1].decode('utf-8', 'replace').strip()


def _paths(raw: bytes) -> list[str]:
    return [p.decode('utf-8', 'surrogateescape') for p in raw.split(b'\0') if p]


def _dirty(root: Path) -> list[str]:
    raw = _git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all')[1].split(b'\0')
    result = []
    i = 0
    while i < len(raw):
        item = raw[i]
        if not item:
            i += 1
            continue
        if len(item) < 4 or item[2:3] != b' ':
            raise WorkError('unrecognized Git status record')
        result.append(item[3:].decode('utf-8', 'surrogateescape'))
        if b'R' in item[:2] or b'C' in item[:2]:
            i += 1
            if i >= len(raw) or not raw[i]:
                raise WorkError('incomplete Git rename/copy record')
            result.append(raw[i].decode('utf-8', 'surrogateescape'))
        i += 1
    return sorted(set(result))


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def _as_commit_order(root: Path, sha: str, path: str) -> dict:
    raw = _git(root, 'show', f'{sha}:{path}')[1]
    try:
        return validate_order(json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs), path=path)
    except (ValueError, UnicodeDecodeError) as exc:
        raise WorkError(f'invalid committed work order at {sha[:12]}: {exc}') from exc


def inspect_work(root: Path, order: str, *, mode: str, base_ref: str | None = None) -> dict:
    """Determine what source history supports, preserving all worktree contents."""
    if mode not in ('start', 'resume'):
        raise WorkError('unsupported work operation')
    order = _relative(order, 'work-order path')
    root = root.resolve(strict=True)
    if not root.is_dir() or Path(_one(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise WorkError('root must be the Git worktree top-level directory')
    head = _one(root, 'rev-parse', 'HEAD')
    head_tree = _one(root, 'rev-parse', 'HEAD^{tree}')
    branch = _one(root, 'symbolic-ref', '--quiet', '--short', 'HEAD') if _git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', allow_failure=True)[0] == 0 else None
    dirt = _dirty(root)
    if _git(root, 'cat-file', '-e', f'HEAD:{order}', allow_failure=True)[0] != 0:
        raise WorkError('work order not committed at HEAD; commit declaration before implementation')
    current = _as_commit_order(root, head, order)
    base = current['baseline']['commit']
    blockers: list[str] = []
    warnings: list[str] = []
    if _git(root, 'cat-file', '-e', f'{base}^{{commit}}', allow_failure=True)[0]:
        blockers.append('BASELINE_MISSING')
    elif _one(root, 'rev-parse', f'{base}^{{tree}}') != current['baseline']['tree']:
        blockers.append('BASELINE_TREE_MISMATCH')
    if not blockers and _git(root, 'merge-base', '--is-ancestor', base, head, allow_failure=True)[0]:
        blockers.append('BASELINE_NOT_ANCESTOR')
    if base_ref:
        if base_ref.startswith('-') or '\x00' in base_ref:
            raise WorkError('unsafe base-ref')
        code, _ = _git(root, 'show-ref', '--verify', '--quiet', f'refs/heads/{base_ref}', allow_failure=True)
        if code:
            warnings.append('BASE_REF_UNAVAILABLE')
        elif _one(root, 'rev-parse', f'refs/heads/{base_ref}') != base:
            blockers.append('BASE_REF_DRIFT')
    commit_order: list[str] = []
    declaration = None
    history_change_paths: set[str] = set()
    if 'BASELINE_MISSING' not in blockers and 'BASELINE_NOT_ANCESTOR' not in blockers:
        commits = _one(root, 'rev-list', '--first-parent', '--reverse', f'{base}..{head}').splitlines()
        previous_order = None
        for sha in commits:
            parent_text = _one(root, 'rev-list', '-n', '1', '--parents', sha).split()
            if len(parent_text) != 2:
                blockers.append('MERGE_HISTORY_NEEDS_REVIEW')
                continue
            changes = _paths(_git(root, 'diff', '--name-only', '-z', '--no-ext-diff', parent_text[1], sha)[1])
            history_change_paths.update(changes)
            if order in changes:
                next_order = _as_commit_order(root, sha, order)
                if previous_order is None:
                    declaration = sha
                    if set(changes) != {order}:
                        blockers.append('DECLARATION_NOT_ISOLATED')
                    if next_order['baseline'] != current['baseline'] or next_order['id'] != current['id']:
                        blockers.append('DECLARATION_IDENTITY_CHANGED')
                    if next_order['amendments']:
                        blockers.append('DECLARATION_HAS_AMENDMENTS')
                else:
                    old_amend = previous_order['amendments']
                    new_amend = next_order['amendments']
                    if new_amend[:len(old_amend)] != old_amend or len(new_amend) <= len(old_amend):
                        blockers.append('AMENDMENT_REASON_MISSING_OR_REWRITTEN')
                    if changes != [order]:
                        blockers.append('AMENDMENT_NOT_ISOLATED')
                    if next_order['id'] != previous_order['id'] or next_order['baseline'] != previous_order['baseline']:
                        blockers.append('AMENDMENT_IDENTITY_CHANGED')
                previous_order = next_order
                commit_order.append(sha)
                continue
            if declaration is None:
                blockers.append('IMPLEMENTATION_PRECEDES_DECLARATION')
            elif previous_order is not None:
                for path in changes:
                    if not _allowed(path, previous_order['allowedPaths']):
                        blockers.append(f'UNDECLARED_COMMIT_PATH:{path}')
        if declaration is None:
            blockers.append('NO_DECLARATION_IN_BASELINE_RANGE')
    changed = _paths(_git(root, 'diff', '--name-only', '-z', '--no-ext-diff', base, head)[1]) if not any(x.startswith('BASELINE_') for x in blockers) else []
    out_of_scope = sorted(set(p for p in changed + dirt if not _allowed(p, current['allowedPaths'])))
    if out_of_scope:
        blockers.append('OUT_OF_SCOPE_PATHS')
    if order in dirt:
        blockers.append('DIRTY_DECLARATION')
    dependency_checks = []
    for dep in current['dependencies']:
        if dep['kind'] == 'external':
            state = 'unknown'
        else:
            state = ('satisfied' if _git(root, 'merge-base', '--is-ancestor', dep['revision'], head,
                                         allow_failure=True)[0] == 0 else 'unresolved')
        dependency_checks.append({'id':dep['id'], 'scope':dep['scope'], 'status':state})
        if dep['scope'] == 'development' and state != 'satisfied':
            blockers.append('DEVELOPMENT_DEPENDENCY_UNRESOLVED:' + dep['id'])
    obligation_checks = []
    for ob in current['obligations']:
        refs = current['proofs'].get(ob['id'], [])
        present = []
        for ref in refs:
            tracked = _git(root, 'cat-file', '-e', f"HEAD:{ref['path']}", allow_failure=True)[0] == 0
            if tracked:
                present.append(ref['kind'])
        missing = sorted(set(ob['proofKinds']) - set(present))
        obligation_checks.append({'id':ob['id'], 'requiredProofKinds':ob['proofKinds'],
                                  'presentUnverified':sorted(set(present)), 'missing':missing,
                                  'verification':'unknown'})
    docs_changed = bool(changed) and all(p.startswith('docs/') or p in ('README.md', 'AGENTS.md', 'SKILLS.md', 'CLAUDE.md') for p in changed)
    if docs_changed and not {'preservation-review','diff-review'} <= {kind for o in current['obligations'] for kind in o['proofKinds']}:
        blockers.append('DOC_PROOF_KINDS_UNDECLARED')
    if dirt:
        warnings.append('DIRTY_WORKTREE_PRESERVED')
    blockers = sorted(set(blockers))
    state = 'blocked' if blockers else ('implementing' if changed and set(changed) != {order} else 'specified')
    return {'packageId':current['id'], 'operation':mode, 'baseline':current['baseline'],
            'head':head, 'headTree':head_tree, 'branch':branch,
            'declarationCommit':declaration, 'amendmentCommits':commit_order[1:],
            'changedPaths':sorted(changed), 'dirtyPaths':dirt, 'outOfScopePaths':out_of_scope,
            'dependencyChecks':dependency_checks, 'obligations':obligation_checks,
            'blockers':blockers, 'warnings':sorted(set(warnings)), 'state':state,
            'developmentReady':not blockers, 'providerCI': 'unknown',
            'accepted': 'unknown', 'externalEffectsAuthorized':False,
            'projectStateAuthority':'unchanged', 'readOnly':True}
