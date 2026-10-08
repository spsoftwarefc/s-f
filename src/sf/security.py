"""SF-12: explicit read-only security/dependency observations, not security certification.

Policy and scanner reports are untrusted data. No scanner commands, network calls,
third-party libraries, or Git write operations occur in this module.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

MAX_JSON = 1024 * 1024
MAX_FILE = 512 * 1024
MAX_FILES = 5000
MAX_FINDINGS = 500
MAX_AGE = 90
_SHA = re.compile(r'[0-9a-f]{40}\Z')
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[A-Za-z][A-Za-z0-9_.:-]{0,127}\Z')
_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,100}\Z')
_KINDS = ('vulnerability', 'license', 'static')
_POLICY = {'schemaVersion', 'owner', 'candidateSha', 'secretPaths', 'workflowPaths',
           'requirementFiles', 'scannerEvidence', 'exceptions'}
_REPORT = {'schemaVersion', 'kind', 'candidateSha', 'generatedAt', 'tool', 'database', 'findings'}
_FINDING = {'id', 'severity', 'path', 'rule'}
_SECRET_PATTERNS = (
    ('github-token', re.compile(rb'(?i)(?:ghp_|github_pat_|gho_|ghu_|ghs_|ghr_)[a-z0-9_]{16,}')),
    ('aws-access-id', re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('private-key', re.compile(rb'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----')),
    ('credential-assignment', re.compile(rb'(?i)\b(?:password|api[_-]?key|secret|token)\s*[:=]\s*[\'\"]?[A-Za-z0-9/+_.=-]{16,}')),
)
_USES = re.compile(r'^\s*(?:-\s*)?uses\s*:\s*(.*)$')
_REQ = re.compile(r'^([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.!+~-]*)\b')
_REQ_HASH = re.compile(r'--hash=sha256:[0-9a-fA-F]{64}\b')


class SecurityError(ValueError):
    """Invalid, unsafe, or uninspectable policy/input."""


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs(items: list[tuple[str, Any]]) -> dict:
    data = {}
    for k, v in items:
        if k in data:
            raise SecurityError('duplicate JSON key')
        data[k] = v
    return data


def _json(raw: bytes, label: str) -> dict:
    if len(raw) > MAX_JSON:
        raise SecurityError(f'{label}: oversized JSON')
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)
    except SecurityError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise SecurityError(f'{label}: invalid JSON or UTF-8') from exc
    if type(data) is not dict:
        raise SecurityError(f'{label}: expected object')
    return data


def _date(raw: Any) -> date:
    if type(raw) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
        raise SecurityError('date must be YYYY-MM-DD')
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise SecurityError('invalid date') from exc


def _path(raw: Any, *, glob: bool = False) -> str:
    if (type(raw) is not str or not raw or len(raw) > 1024 or raw != raw.strip()
            or raw.startswith(('/', '\\')) or '\\' in raw or ':' in raw or '\x00' in raw):
        raise SecurityError('unsafe path or pattern')
    parts = raw.split('/')
    if any(p in ('', '.', '..', '.git') for p in parts):
        raise SecurityError('noncanonical path')
    if any(any(c in p for c in '*?[]') for p in parts):
        if not (glob and len(parts) >= 2 and parts[-1] == '**'
                and not any(any(c in p for c in '*?[]') for p in parts[:-1])):
            raise SecurityError('only prefix/** scope patterns are allowed')
    return raw


def _paths(raw: Any, *, glob: bool = False) -> list[str]:
    if type(raw) is not list or len(raw) > 100:
        raise SecurityError('expected bounded path list')
    out = [_path(p, glob=glob) for p in raw]
    if len(set(x.casefold() for x in out)) != len(out):
        raise SecurityError('duplicate paths')
    return out


def _fields(raw: Any, expected: set[str], name: str) -> dict:
    if type(raw) is not dict or set(raw) != expected:
        raise SecurityError(f'{name}: unknown or missing fields')
    return raw


def _nonblank(s: Any, field: str) -> str:
    if type(s) is not str or not s.strip() or s.strip() != s or len(s) > 256 or '\x00' in s:
        raise SecurityError(f'{field}: invalid value')
    return s


def validate_policy(raw: Any) -> dict:
    p = _fields(raw, _POLICY, 'policy')
    if type(p['schemaVersion']) is not int or p['schemaVersion'] != 1:
        raise SecurityError('unsupported policy schema')
    _nonblank(p['owner'], 'owner')
    if type(p['candidateSha']) is not str or not _SHA.fullmatch(p['candidateSha']):
        raise SecurityError('candidateSha must be full git commit SHA')
    for field in ('secretPaths', 'workflowPaths'):
        _paths(p[field], glob=True)
    for x in _paths(p['requirementFiles']):
        if not x.endswith('.txt'):
            raise SecurityError('only Python requirements .txt supported; other stacks need external adapter')
    evidence = p['scannerEvidence']
    if type(evidence) is not list or len(evidence) > 3:
        raise SecurityError('scannerEvidence must be a bounded list')
    kinds = set()
    for item in evidence:
        e = _fields(item, {'kind', 'path', 'sha256', 'maxAgeDays'}, 'scanner evidence')
        if e['kind'] not in _KINDS or e['kind'] in kinds:
            raise SecurityError('unknown/duplicate scanner evidence kind')
        kinds.add(e['kind'])
        _path(e['path'])
        if type(e['sha256']) is not str or not _HASH.fullmatch(e['sha256']):
            raise SecurityError('scanner evidence requires exact sha256')
        if type(e['maxAgeDays']) is not int or not 1 <= e['maxAgeDays'] <= MAX_AGE:
            raise SecurityError('invalid scanner evidence freshness bound')
    exceptions = p['exceptions']
    if type(exceptions) is not list or len(exceptions) > 100:
        raise SecurityError('invalid exceptions')
    seen = set()
    for item in exceptions:
        e = _fields(item, {'findingId', 'path', 'owner', 'reason', 'expiresOn', 'approvedBy'}, 'exception')
        if type(e['findingId']) is not str or not _ID.fullmatch(e['findingId']):
            raise SecurityError('invalid exception findingId')
        _path(e['path'])
        for key in ('owner', 'reason', 'approvedBy'):
            _nonblank(e[key], key)
        _date(e['expiresOn'])
        k = (e['findingId'], e['path'])
        if k in seen:
            raise SecurityError('duplicate exception')
        seen.add(k)
    return p


def read_policy(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON:
        raise SecurityError('missing, symlinked or oversized policy file')
    return validate_policy(_json(path.read_bytes(), 'policy'))


def _git(root: Path, *args: str) -> bytes:
    try:
        proc = subprocess.run(['git', '-C', str(root), '-c', 'core.fsmonitor=false',
                               '-c', 'core.untrackedCache=false', '--no-pager', *args],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0'},
                              check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SecurityError('git unavailable') from exc
    if proc.returncode:
        raise SecurityError(f'git {args[0]} failed')
    return proc.stdout


def _safe_file(root: Path, path: str) -> Path | None:
    p = root
    for part in _path(path).split('/'):
        p = p / part
        if p.is_symlink():
            return None
    if not p.is_file() or not p.resolve(strict=True).is_relative_to(root):
        return None
    return p


def _match(path: str, patterns: list[str]) -> bool:
    return any(path == p or (p.endswith('/**') and path.startswith(p[:-3] + '/')) for p in patterns)


def _finding(kind: str, path: str, rule: str, severity: str = 'high') -> dict:
    # Deterministic id that contains no matched secret bytes.
    tag = _digest(f'{kind}\0{path}\0{rule}'.encode())[:18]
    return {'id': f'SEC-{tag}', 'kind': kind, 'path': path, 'rule': rule, 'severity': severity,
            'exception': 'none'}


def _secret_findings(raw: bytes, path: str) -> list[dict]:
    return [_finding('secret', path, rule, 'critical') for rule, pat in _SECRET_PATTERNS
            if pat.search(raw)]


def _action_findings(raw: bytes, path: str) -> list[dict]:
    result = []
    for line in raw.decode('utf-8', 'replace').splitlines():
        hit = _USES.match(line)
        if hit:
            value = hit.group(1).strip().split(' #', 1)[0].strip()
            if value.startswith('./'):
                continue
            if (value.startswith('docker://') and re.fullmatch(r'docker://[^\s@]+@sha256:[0-9a-f]{64}', value)):
                continue
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?@[0-9a-f]{40}', value):
                result.append(_finding('action-pinning', path, 'action-missing-full-sha'))
                break
    return result


def _requirement_findings(raw: bytes, path: str) -> list[dict]:
    for line in raw.decode('utf-8', 'replace').splitlines():
        row = line.strip()
        if not row or row.startswith('#'):
            continue
        row = row.split(' #', 1)[0].strip()
        if not _REQ.match(row) or not _REQ_HASH.search(row):
            return [_finding('dependency-pinning', path, 'requirement-missing-version-or-sha256')]
    return []


def _parse_timestamp(value: Any) -> datetime:
    if type(value) is not str or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value):
        raise SecurityError('scanner generatedAt needs UTC ISO second timestamp')
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise SecurityError('invalid scanner generatedAt') from exc


def _scanner_report(raw: bytes, kind: str, candidate: str, now: datetime, days: int) -> tuple[str, list[dict]]:
    d = _fields(_json(raw, 'scanner report'), _REPORT, 'scanner report')
    if type(d['schemaVersion']) is not int or d['schemaVersion'] != 1 or d['kind'] != kind or d['candidateSha'] != candidate:
        raise SecurityError('scanner report schema, kind or candidate mismatch')
    tool = _fields(d['tool'], {'name', 'version'}, 'scanner tool')
    for k in ('name', 'version'):
        _nonblank(tool[k], k)
    db = d['database']
    if kind == 'vulnerability':
        _fields(db, {'name', 'revision'}, 'vulnerability database')
        _nonblank(db['name'], 'database.name')
        _nonblank(db['revision'], 'database.revision')
    elif db is not None:
        _fields(db, {'name', 'revision'}, 'database')
        _nonblank(db['name'], 'database.name')
        _nonblank(db['revision'], 'database.revision')
    when = _parse_timestamp(d['generatedAt'])
    if when > now or (now - when).total_seconds() > days * 86400:
        return 'stale', []
    if type(d['findings']) is not list or len(d['findings']) > MAX_FINDINGS:
        raise SecurityError('scanner findings limit exceeded')
    findings = []
    seen = set()
    for f in d['findings']:
        _fields(f, _FINDING, 'scanner finding')
        if type(f['id']) is not str or not _ID.fullmatch(f['id']) or f['id'] in seen:
            raise SecurityError('scanner finding invalid/duplicate ID')
        seen.add(f['id'])
        _path(f['path'])
        if f['severity'] not in ('critical','high','medium','low'):
            raise SecurityError('unsupported severity')
        rule = _nonblank(f['rule'], 'rule')
        findings.append({'id': f['id'], 'kind': kind, 'path': f['path'], 'rule': rule,
                         'severity': f['severity'], 'exception': 'none'})
    return 'present-unverified', findings


def assess_security(root: Path, policy: dict, *, today: date | None = None) -> dict:
    """Return bounded observations, unknown coverage and blockers; never authorize acceptance."""
    p = validate_policy(policy)
    if root.is_symlink() or not root.is_dir():
        raise SecurityError('root must be real Git directory')
    root = root.resolve(strict=True)
    if Path(_git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != root:
        raise SecurityError('root must be Git worktree root')
    candidate = _git(root, 'rev-parse', 'HEAD').decode().strip()
    if candidate != p['candidateSha']:
        raise SecurityError('stale policy candidateSha')
    tree = _git(root, 'rev-parse', 'HEAD^{tree}').decode().strip()
    dirty = _git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
    names_raw = _git(root, 'ls-files', '-z', '--cached')
    names = [x.decode('utf-8', 'surrogateescape') for x in names_raw.split(b'\0') if x]
    if len(names) > MAX_FILES:
        raise SecurityError('too many tracked files to scan')
    findings: list[dict] = []
    unknowns: list[str] = []
    coverage: dict[str, str] = {}
    for kind, patterns, audit in [
        ('secrets', p['secretPaths'], _secret_findings),
        ('actionPins', p['workflowPaths'], _action_findings),
        ('pythonPins', p['requirementFiles'], _requirement_findings),
    ]:
        if not patterns:
            coverage[kind] = 'not-configured'
            unknowns.append(kind + ':not-configured')
            continue
        selected = sorted(x for x in names if _match(x, patterns))
        if not selected:
            coverage[kind] = 'no-matching-tracked-files'
            unknowns.append(kind + ':no-matching-tracked-files')
            continue
        unreadable = False
        for name in selected:
            file = _safe_file(root, name)
            if file is None or file.stat().st_size > MAX_FILE:
                unreadable = True
                continue
            raw = file.read_bytes()
            if b'\x00' in raw:
                unreadable = True
                continue
            findings.extend(audit(raw, name))
            if len(findings) > MAX_FINDINGS:
                raise SecurityError('too many security findings')
        coverage[kind] = 'partial' if unreadable else 'locally-scanned'
        if unreadable:
            unknowns.append(kind + ':unreadable-or-unsupported-file')
    now = (datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc)
           if today is not None else datetime.now(timezone.utc))
    for kind in _KINDS:
        evidence = next((v for v in p['scannerEvidence'] if v['kind'] == kind), None)
        if evidence is None:
            coverage[kind] = 'not-configured'
            unknowns.append(kind + ':scanner-unavailable')
            continue
        file = _safe_file(root, evidence['path'])
        if file is None or file.stat().st_size > MAX_JSON:
            coverage[kind] = 'unavailable'
            unknowns.append(kind + ':evidence-unavailable')
            continue
        raw = file.read_bytes()
        if _digest(raw) != evidence['sha256']:
            coverage[kind] = 'mismatched'
            unknowns.append(kind + ':evidence-digest-mismatch')
            continue
        try:
            status, output = _scanner_report(raw, kind, candidate, now, evidence['maxAgeDays'])
        except SecurityError:
            coverage[kind] = 'invalid'
            unknowns.append(kind + ':invalid-report')
            continue
        coverage[kind] = status
        if status != 'present-unverified':
            unknowns.append(kind + ':stale-report')
        findings.extend(output)
    current = today or datetime.now(timezone.utc).date()
    exception_dispositions: list[dict] = []
    for e in p['exceptions']:
        expires = _date(e['expiresOn'])
        match = next((f for f in findings if f['id'] == e['findingId'] and f['path'] == e['path']), None)
        status = ('unmatched' if match is None else 'expired' if expires < current else 'declared-unverified')
        if match is not None:
            match['exception'] = status
        exception_dispositions.append({'findingId': e['findingId'], 'path': e['path'], 'status': status,
                                       'owner': e['owner'], 'expiresOn': e['expiresOn']})
        if status != 'declared-unverified':
            unknowns.append('exception:' + status)
    if dirty:
        unknowns.append('dirty-worktree:source-bytes-not-identical-to-HEAD')
    findings.sort(key=lambda x: (x['kind'], x['path'], x['rule'], x['id']))
    status = 'blocked' if findings else 'incomplete' if unknowns else 'observed-clear-not-certified'
    return {'schemaVersion': 1, 'status': status, 'candidateSha': candidate, 'candidateTree': tree,
            'policyOwner': p['owner'], 'coverage': coverage, 'findings': findings,
            'unknowns': sorted(set(unknowns)), 'exceptions': exception_dispositions,
            'checksLocallyObserved': True, 'externalScannerResultsAuthenticated': False,
            'exceptionsApproved': False, 'securityQualified': False, 'accepted': False,
            'mergeAuthorized': False, 'releaseQualified': False}
