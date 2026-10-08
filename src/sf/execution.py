"""SF-09: explicit, bounded local command execution and observed-only receipts.

The runner is *not* a sandbox, network firewall, or CI evidence verifier.
Profiles are declarative inputs, not execution permission; a caller must select a
command explicitly. Mutating/external risk categories remain outside SF-09.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .profile import ProfileError, read_profile

OUTPUT_LIMIT = 65536
CHUNK_SIZE = 8192
POLL_SECONDS = 0.1
STOP_GRACE_SECONDS = 0.6
MAX_RECEIPT_BYTES = 1024 * 1024
ENV_ALLOW = frozenset({
    'PATH', 'PATHEXT', 'SystemRoot', 'SYSTEMROOT', 'COMSPEC', 'WINDIR',
    'TEMP', 'TMP', 'TMPDIR', 'HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA',
    'LANG', 'LC_ALL', 'PYTHONIOENCODING',
})
SECRET_PATTERN = re.compile(r'(?i)(?:ghp_|github_pat_|gho_|ghu_|ghs_|ghr_)[a-z0-9_]{16,}')


class ExecutionError(ValueError):
    """Invalid input or unavailable execution prerequisite (no command executed)."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def _relative(value: str, *, label: str) -> Path:
    if (not isinstance(value, str) or not value or value.startswith(('/', '\\'))
            or ':' in value or '\\' in value or '\0' in value
            or any(part in ('', '.', '..', '.git') for part in value.split('/'))):
        raise ExecutionError(f'{label}: expected safe relative POSIX path')
    return Path(*value.split('/'))


def _rooted_file(root: Path, path: str, *, exists: bool) -> Path:
    relative = _relative(path, label='path')
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink() or not current.is_dir():
            raise ExecutionError(f'path parent unsafe or absent: {path}')
    target = root / relative
    if target.is_symlink() or (exists and not target.is_file()) or (not exists and target.exists()):
        raise ExecutionError(f'path absent, symlinked, or already exists: {path}')
    return target


def _git(root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ['git', '-C', str(root), '-c', 'core.fsmonitor=false',
             '-c', 'core.untrackedCache=false', '--no-pager', *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0'},
            timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExecutionError(f'Git identity unavailable: {type(exc).__name__}') from exc
    if proc.returncode:
        raise ExecutionError(f'Git identity unavailable: git {args[0]} failed')
    return proc.stdout.decode('utf-8', 'replace').strip()


def _repo_identity(root: Path) -> dict[str, str]:
    top = Path(_git(root, 'rev-parse', '--show-toplevel')).resolve(strict=True)
    if top != root:
        raise ExecutionError('root must be the top-level Git worktree')
    return {'commit': _git(root, 'rev-parse', 'HEAD'),
            'tree': _git(root, 'rev-parse', 'HEAD^{tree}'),
            'dirtyStatusSha256': _sha(_git(root, 'status', '--porcelain=v1', '--untracked-files=all').encode('utf-8'))}


class _Capture:
    def __init__(self) -> None:
        self.data = bytearray()
        self.total = 0
        self.failure: str | None = None

    def drain(self, stream: Any) -> None:
        try:
            while True:
                chunk = stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                self.total += len(chunk)
                available = OUTPUT_LIMIT - len(self.data)
                if available > 0:
                    self.data.extend(chunk[:available])
        except OSError as exc:
            self.failure = type(exc).__name__
        finally:
            stream.close()


def _filtered_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k in ENV_ALLOW}


def _redactor(secret_env_names: list[str]) -> tuple[Any, list[str]]:
    if any(not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', k) for k in secret_env_names):
        raise ExecutionError('invalid redaction environment variable name')
    values = sorted({os.environ[k] for k in secret_env_names if k in os.environ
                     and len(os.environ[k]) >= 4}, key=len, reverse=True)

    def redact(value: str) -> str:
        for secret in values:
            value = value.replace(secret, '[REDACTED]')
        return SECRET_PATTERN.sub('[REDACTED]', value)

    return redact, sorted(set(secret_env_names))


def _stream_record(capture: _Capture, redact: Any) -> dict[str, Any]:
    sanitized = redact(bytes(capture.data).decode('utf-8', 'replace'))
    return {'text': sanitized, 'sha256': _sha(sanitized.encode('utf-8')),
            'bytesObserved': capture.total, 'bytesRetained': len(capture.data),
            'truncated': capture.total > len(capture.data),
            'readError': capture.failure}


def _make_job(proc: subprocess.Popen[bytes]) -> Any:
    """On Windows, attach the owned process to a dedicated Job Object."""
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ExecutionError('Windows Job Object unavailable')
    if not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(int(proc._handle))):
        kernel.CloseHandle(handle)
        raise ExecutionError('cannot assign process to Windows Job Object')
    return (kernel, handle)


def _terminate_owned(proc: subprocess.Popen[bytes], job: Any) -> None:
    if os.name == 'nt':
        if job is not None:
            kernel, handle = job
            kernel.TerminateJobObject(handle, 1)
        else:
            # Attachment failed before ownership qualification. Terminate only
            # the known process, not a guessed process tree by name or PID.
            if proc.poll() is None:
                proc.kill()
        return
    # start_new_session=True makes proc.pid the newly-owned process-group ID.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    # Kill remaining descendants even if the group leader already exited.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _run_process(argv: list[str], cwd: Path, seconds: int, cancel_event: threading.Event) -> tuple[dict, _Capture, _Capture]:
    stdout = _Capture()
    stderr = _Capture()
    proc: subprocess.Popen[bytes] | None = None
    job = None
    started = time.monotonic()
    outcome = 'spawn-error'
    exit_code: int | None = None
    detail: str | None = None
    windows = os.name == 'nt'
    try:
        proc = subprocess.Popen(argv, cwd=str(cwd), env=_filtered_env(),
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, shell=False,
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if windows else 0,
                                start_new_session=not windows, close_fds=True)
        try:
            job = _make_job(proc)
        except ExecutionError:
            _terminate_owned(proc, None)
            proc.wait(timeout=2)
            raise
        assert proc.stdout is not None and proc.stderr is not None
        threads = [threading.Thread(target=stdout.drain, args=(proc.stdout,), daemon=True),
                   threading.Thread(target=stderr.drain, args=(proc.stderr,), daemon=True)]
        for thread in threads:
            thread.start()
        while True:
            if cancel_event.is_set():
                outcome = 'cancelled'
                _terminate_owned(proc, job)
                break
            if time.monotonic() - started >= seconds:
                outcome = 'timeout'
                _terminate_owned(proc, job)
                break
            try:
                exit_code = proc.wait(timeout=min(POLL_SECONDS, max(0.01, seconds - (time.monotonic() - started))))
                outcome = 'success' if exit_code == 0 else 'failed'
                break
            except subprocess.TimeoutExpired:
                pass
        if proc.poll() is None:
            proc.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=2)
        if any(thread.is_alive() for thread in threads):
            _terminate_owned(proc, job)
            for thread in threads:
                thread.join(timeout=2)
            outcome = 'failed'
            detail = 'output drain incomplete or child inherited output pipe'
    except (OSError, ExecutionError, subprocess.TimeoutExpired) as exc:
        detail = f'{type(exc).__name__}: {str(exc)[:160]}'
        outcome = 'spawn-error' if outcome == 'spawn-error' else 'failed'
    finally:
        if proc is not None and proc.poll() is None:
            _terminate_owned(proc, job)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                detail = 'owned process termination unconfirmed'
                outcome = 'failed'
        if job is not None:
            kernel, handle = job
            kernel.CloseHandle(handle)
    return ({'outcome': outcome, 'exitCode': exit_code,
             'durationMs': round((time.monotonic() - started) * 1000),
             'diagnostic': detail,
             'processCleanup': 'windows-job' if windows and job is not None else
                               ('posix-process-group' if not windows else 'unqualified')}, stdout, stderr)


def _persist(root: Path, relative: str, receipt: dict) -> None:
    target = _rooted_file(root, relative, exists=False)
    payload = _canonical(receipt)
    if len(payload) > MAX_RECEIPT_BYTES:
        raise ExecutionError('receipt exceeds maximum size')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=True) as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        # Don't delete evidence of a potentially partial write or repeat a
        # command after failure: the command's external effect may have occurred.
        raise


def execute_check(root: Path, profile_path: str, check_id: str, *,
                  receipt_out: str | None = None, allow_network: bool = False,
                  redact_env: list[str] | None = None,
                  cancel_event: threading.Event | None = None) -> dict:
    """Execute exactly one declared command. Returns a *local observation* only."""
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', check_id):
        raise ExecutionError('invalid check id')
    if root.is_symlink() or not root.is_dir():
        raise ExecutionError('root is absent, symlinked, or not a directory')
    root = root.resolve(strict=True)
    identity_before = _repo_identity(root)
    profile_file = _rooted_file(root, profile_path, exists=True)
    if profile_file.stat().st_size > 1024 * 1024:
        raise ExecutionError('profile exceeds size limit')
    data = read_profile(profile_file, root=root)
    if check_id not in data['commands']:
        raise ExecutionError('check ID was not declared in the profile')
    command = data['commands'][check_id]
    risk = command.get('risk', 'build')
    if risk not in ('read-only', 'build'):
        raise ExecutionError(f'unsupported risk category {risk}; SF-09 allows read-only/build only')
    network_requested = command.get('network', False)
    if network_requested and not allow_network:
        raise ExecutionError('network-declared check requires --allow-network')
    profile_digest = _sha(profile_file.read_bytes())
    command_digest = _sha(_canonical(command))
    cwd = root if command['cwd'] == '.' else root.joinpath(*command['cwd'].split('/'))
    if receipt_out is not None:
        _rooted_file(root, receipt_out, exists=False)
    redact, redaction_names = _redactor(redact_env or [])
    cancelled = cancel_event or threading.Event()
    if cancelled.is_set():
        raise ExecutionError('execution cancelled before dispatch')
    started_at = datetime.now(timezone.utc).isoformat()
    result, out, err = _run_process(command['argv'], cwd, command.get('timeoutSeconds', 300), cancelled)
    ended_at = datetime.now(timezone.utc).isoformat()
    try:
        after = _repo_identity(root)
        identity_unavailable = False
    except ExecutionError:
        after = None
        identity_unavailable = True
    if result['diagnostic'] is not None:
        result['diagnostic'] = redact(result['diagnostic'])
    stdout = _stream_record(out, redact)
    stderr = _stream_record(err, redact)
    if stdout['readError'] or stderr['readError']:
        result['outcome'] = 'failed'
    if identity_unavailable:
        result['diagnostic'] = 'Git identity unavailable after command; inspect repository before retry'
        result['outcome'] = 'indeterminate'
    receipt = {
        'schemaVersion': 1, 'kind': 'sf-local-command-observation',
        'projectId': data['project']['id'], 'checkId': check_id,
        'repository': {'before': identity_before, 'after': after,
                       'sourceChangedDuringExecution': after != identity_before,
                       'postExecutionIdentityUnavailable': identity_unavailable},
        'profileSha256': profile_digest, 'commandSha256': command_digest,
        'argv': [redact(arg) for arg in command['argv']],
        'cwd': command['cwd'], 'risk': risk,
        'environment': {'policy': 'limited-allowlist', 'redactedNames': redaction_names,
                        'networkDeclared': network_requested, 'networkIsolation': 'not-enforced',
                        'secretIsolation': 'not-guaranteed'},
        'runner': {'name': 'sf-local-v1', 'python': platform.python_version(),
                   'system': platform.system()},
        'startedAt': started_at, 'endedAt': ended_at,
        'result': result, 'stdout': stdout, 'stderr': stderr,
        'outputComplete': not (stdout['truncated'] or stderr['truncated'] or
                               stdout['readError'] or stderr['readError']),
        'evidenceVerified': False, 'ciVerified': False, 'accepted': False,
    }
    if receipt_out is not None:
        try:
            _persist(root, receipt_out, receipt)
        except (OSError, ExecutionError) as exc:
            raise ExecutionError('command has executed but receipt persistence failed; '
                                 'inspect target before any retry') from exc
    return receipt
