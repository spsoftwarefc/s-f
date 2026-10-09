# PQ-01A — Publisher verifier adapter candidate evidence

**Evidence status:** pending final source/CI validation; no live cryptographic attestation or publisher policy custody confirmed.

- Exact protected starting baseline: `09d5346c628560e7e33f947a8b08b44960cef14f`, tree `da32ea87b5c675d88436ffc517e51e78b34be609` (PQ-00 merged via protected PR #31). PQ-00 production planning docs are on `main`.
- Work-order-first commit: `83a37a937588abca2e5c0b2e6e2d9cc5bebcf94b` on `qualification/pq01a-verifier-adapter`, before code, tests and docs.
- Candidate source files: `src/sf/publisher.py`, `src/sf/cli.py`, `tests/test_publisher.py`. Documentation: `docs/factory/PQ01_PUBLISHER.md`, plan and this evidence record.
- Acceptance tests use a **mocked verifier subprocess** and synthetic bytes. This can prove reject/binding logic, not genuine Sigstore/GitHub cryptographic verification. No real artifact attestation bundle, pinned official GH executable/root digest or issuer policy has been independently obtained; no publisher-authentic or installed release is accepted.
- Required negative cases: altered policy with unchanged out-of-band digest, malformed/expired policy, wrong signer workflow/ref, epoch downgrade, tampered artifact, tool/root substitution, symlinked policy, invalid external release pin, nonzero verifier, mismatched subject, malformed output and unavailable binary.
- Preserve all old SF-13/13I/14/15/16/19 outputs, existing installed-byte checking and required CI workflow unchanged. The new command is separate and opt-in: no `integrate` or `upgrade` trust upgrade is claimed.
- Source review must verify the correct `gh attestation verify` identity flags and no untrusted shell, token propagation or source-self-trust. Input type/size and subprocess timeout are bounded.
- At writing, no new source candidate acceptance or CI run identity is claimed. Record actual local check/PR run/attempt/merge SHA only after observing them; no unchanged rerun for presentation.
- **PQ-01 remains IN PROGRESS**, and PQ-01B real publisher and installer-effect qualification remains blocked by external trust/publisher decisions.
