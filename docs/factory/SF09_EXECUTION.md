# SF-09 — Explicit command execution and local observation receipts

Status: implementation candidate. Receipt contract: `schemaVersion=1`, `kind=sf-local-command-observation`. The execution adapter is a **local process runner, not a sandbox, network firewall, remote CI proof, or authorization mechanism for release or deployment**.

## Command syntax

```sh
sf run unit-tests --root . --profile .factory/profile.json
sf run unit-tests --root . --profile .factory/profile.json --receipt-out .factory/receipts/unit-tests.json
sf run network-check --root . --profile .factory/profile.json --allow-network
sf run unit-tests --root . --profile .factory/profile.json --redact-env LOCAL_TEST_TOKEN
```

`unit-tests` is an exact command ID from the v1 project profile, **not arbitrary inline shell text**. The v1 contract requires a populated `commands[id].argv` vector and a relative `cwd`; it permits `risk`, `network`, and `timeoutSeconds`. The CLI never executes profile commands during inventory, installation planning, profile validation, or work start/resume. A human or coding host must explicitly invoke `sf run`.

For SF-09, `read-only` and `build` risk categories are permitted; `mutating` and `external` are rejected rather than silently treating the caller as a release authority. These category labels are declarations: an executable named `build` can perform arbitrary effects. The executor does **not** provide process isolation from a malicious repository. A project executing untrusted code must use a separately qualified OS/container isolation boundary.

Network declarations are **not enforced** by the OS adapter: `network=true` requires `--allow-network`, but `network=false` still means only *requested intent*, never verified egress denial. The receipt always declares `networkIsolation: not-enforced`. The child inherits a deliberately limited environment variable allowlist, not the entire developer environment. Secret access through files, intentionally passed argv, or host permissions is not prevented. Do not execute untrusted commands on a credentialed or production host.

## Execution and outcome

`subprocess.Popen` uses `shell=False`, a literal argv array, validated project-relative cwd, stdin closed, and read-only Git inspection before/after. Each stdout/stderr stream is continuously drained while retaining up to 65,536 raw bytes. Counts, truncation indicators and SHA-256 of **redacted retained text** are captured. Explicit `--redact-env NAME` replaces referenced environment values of length at least four; known GitHub token patterns are redacted as an additional best-effort measure. These are not a guarantee that unknown credentials or arbitrary sensitive data cannot appear in logs: provide only synthetic/approved outputs.

The timeout defaults to 300 seconds unless declared in the validated profile (1–3600 seconds). The CLI handles SIGINT/SIGTERM by requesting cancellation, then terminates the owned POSIX process group or Windows Job Object. On Windows, Job Object attachment is attempted immediately after launch; lack of support fails rather than claiming descendant cleanup. Neither model can control a deliberately detached process that has escaped the ownership boundary, nor remove every launch-to-attachment race. No unrelated process is killed by name or guessed PID. A process-group child holding pipes open causes bounded drain handling instead of an indefinite wait.

Possible outcomes: `success`, `failed`, `timeout`, `cancelled`, `spawn-error`, `indeterminate`. A zero exit code means only the command itself exited successfully. If repository identity becomes unreadable after execution, the outcome is `indeterminate`, regardless of observed exit code. A changed worktree is recorded; it never becomes immutable source proof. Output truncation or capture error is separately reported. CLI exit: 0 command success, 1 non-success command result, 2 rejected configuration/prerequisite or receipt persistence error.

## Receipt identity and persistence

Receipts bind a Git commit/tree, before/after dirty-status fingerprint, project ID, command ID and argv, exact profile/command digests, cwd, declared risk/network, observed runner/system identity, start/end time, elapsed time, process cleanup mechanism, code and stdout/stderr results. They record `evidenceVerified=false`, `ciVerified=false` and `accepted=false`. Hashes establish observed byte equality, not truth or independently attested provenance. SF-10 adds provider validation and SF-11 adds assurance; local receipt status cannot promote itself.

The optional `--receipt-out` path must be repository-relative; its parent must already exist, be a real directory, and contain no symlink traversal. The destination must not exist. The runner creates a new mode-0600 file (subject to platform behavior) using exclusive creation; it never overwrites an existing receipt or automatically creates new folders. A failed execution still produces a receipt when persistence is possible. **If persistence fails after execution, do not retry automatically**: an external effect may have happened and must be reconciled first. Receipts should be stored under a project-controlled evidence directory and reviewed before publication.

## Verification and exclusions

SF-09 regression coverage includes an explicit vector without shell interpolation, unknown check rejection, risk/network gating, cwd/symlink rejection, redaction, environment filtering, timeout, cancellation, child process cleanup, stderr/nonzero/launch errors, bounded large outputs, exclusive persistence, pre-execution cancellation, dirty source changes and post-execution Git identity loss. Native Linux/Windows verification must bind to the actual candidate and state any unsupported platform capability. No live external network checks or production commands are included. GitHub-hosted runs exercise code and fixtures only, not authorization to merge, distribute or deploy.
