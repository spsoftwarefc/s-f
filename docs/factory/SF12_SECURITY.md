# SF-12 — Security and dependency adapters

Status: implementation candidate, contract v1. `sf security assess` is an **explicit, read-only, offline assessment** of a named Git working tree and optional externally produced scanner evidence. It does not execute scanners, install packages, query an advisory database, authenticate scanner publishers, suppress security findings, grant acceptance, change GitHub rules or authorize a release.

## CLI and policy

```sh
sf security assess --root . --policy .factory/security-policy.json
```

Versioned policy fields are closed (unknown fields rejected):

```json
{
  "schemaVersion": 1,
  "owner": "security-owner",
  "candidateSha": "0123456789012345678901234567890123456789",
  "secretPaths": ["src/**", "tests/**"],
  "workflowPaths": [".github/workflows/**"],
  "requirementFiles": ["requirements.txt"],
  "scannerEvidence": [],
  "exceptions": []
}
```

Replace `candidateSha` with the **full local Git HEAD SHA**. The policy is untrusted caller-provided configuration, not an independently signed or baseline-controlled security standard. Root must be the real Git worktree root; a different HEAD rejects the policy. Dirty paths are explicitly flagged because scanned local bytes may differ from the named committed candidate. Untracked files, including scanner report files, do not receive trusted committed-source provenance. Git inventory and scanning are bounded (5,000 tracked entries, 512 KiB per source file, at most 500 findings); unsafe/symlinked/unreadable content is *unknown*, never silently clean. Only literal paths and `prefix/**` selectors are allowed; glob breadth is caller-controlled. Path scopes must be reviewed for omissions.

## Built-in observations

| Adapter | Evidence examined | Condition reported | Coverage limits |
|---|---|---|---|
| Secret patterns | Declared tracked files | GitHub token-like strings, AWS key identifiers, PEM private-key headers, long credential-like assignments | Heuristics only; false positives and uncaught secret formats possible; matched secret contents never printed |
| GitHub action pin audit | Declared tracked workflow paths | External `uses:` references without literal 40-character commit SHA (or Docker `sha256` digest) | Line-level YAML audit, not a full parser; unsafe/dynamic references are findings; does not independently verify publisher or actual action object |
| Python requirement pin audit | Explicit `requirements*.txt` entries | Missing exact `==` version or inline `--hash=sha256:...` | Conservative text-level check; does not prove hash matches downloaded distribution or validate transitive resolution |

Absent path declarations or zero matched tracked files remain **unknown/not configured**. Unsupported ecosystem lockfiles (for example Node, Rust, Java and system packages) require a configured external scanner report; the built-in Python pin audit must not be represented as a language-agnostic dependency resolver. No network is used and no source files are modified.

## External vulnerability, license and static-analysis evidence

Use `scannerEvidence` entries, one per kind: `vulnerability`, `license`, `static`:

```json
{
  "kind": "vulnerability",
  "path": "evidence/vulnerability.json",
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "maxAgeDays": 30
}
```

The local report JSON is a strict v1 document with exactly `schemaVersion`, `kind`, `candidateSha`, `generatedAt` (UTC `YYYY-MM-DDTHH:MM:SSZ`), `tool` (`name`, `version`), `database` (`name`, `revision` for vulnerability checks, nullable for other kinds), and `findings`. Each finding has exactly `id`, `severity` (`critical|high|medium|low`), safe relative `path` and `rule`. The report's file bytes must match the predeclared SHA-256; mismatch, malformed content, stale observation, absent report or missing feed yields unknown. Provenance and authenticity remain **unverified**, including for zero-finding reports. A supplied report with findings blocks; absence of findings cannot become "all vulnerabilities absent". Tool/database identities are assertions by the producer and need later independent qualification.

A scanner is not automatically run merely because the policy references it. The operator may use an existing project scanner and its separately authorized execution controls (SF-09) to produce a report, but that is not equivalent to authenticated scanner evidence. Do not upload secrets to an unapproved vendor or install tools merely to satisfy this adapter. No compulsory third-party service is introduced.

## Expiring exceptions and authority

An exception declares exact `findingId`, `path`, `owner`, `approvedBy`, `reason`, `expiresOn` (`YYYY-MM-DD`). It must match a surfaced finding. Dates and duplicate identities are checked; expiry is evaluated in UTC. Exception statuses: `unmatched`, `expired` or `declared-unverified`. An active **declaration is not an authenticated approval**, so it never removes a finding or flips a blocked scan into a pass. An independent project authority may subsequently accept an explicit, scoped residual risk through its own protected controls; no such approval mechanism is implemented in SF-12.

## Result and exit semantics

The JSON output includes `candidateSha`, `candidateTree`, policy owner, per-check coverage, bounded non-sensitive finding identifiers, unknown coverage, exception dispositions and explicit denials of qualification/acceptance/merge/release. `status=blocked` when findings exist, `incomplete` for unknowns, and `observed-clear-not-certified` only when all configured checks actually ran with no known findings or unknowns. **None** of these is a certified security or supply-chain assessment: `securityQualified=false`, `externalScannerResultsAuthenticated=false`, `accepted=false`, `mergeAuthorized=false`, and `releaseQualified=false` always.

Exit `0` means only all requested local observations completed without reported findings/unknowns, **not** security clearance; `1` means blocked or incomplete observations; `2` means invalid policy/prerequisites. The initial factory development policy should not configure scan gaps as passes. Zero configured external scanner reports leave vulnerability/license/static coverage incomplete by design.

## Qualification cases

Synthetic, independently defined negative tests seed fake tokens/private keys, action tags/dynamic references, unpinned Python requirements, intentionally vulnerable dependency/license/static report records, missing/stale/mismatched/invalid scanner evidence, symlink and source drift, expired/unmatched/self-declared exceptions, duplicate JSON keys and bounded parsing. CI/branch protections stay unchanged. Native Windows/Linux checks for the exact committed candidate are provider claims separate from these local fixture tests. The factory itself is not yet SF-19 v1 qualified.
