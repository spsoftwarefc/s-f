---
name: factory-implementation
description: Implement one declared s-f work package while preserving project authority, evidence boundaries and resource limits.
---

Read `AGENTS.md`, the active work order, `docs/factory/PROJECT.md`, and the relevant project-owned requirements.

Before changing implementation files, confirm that the work order is already committed and identifies the baseline, allowed scope, obligations and expected proof.

Implementation sequence:
1. Establish exact revision, branch/base and dirty paths.
2. Use the context skill to inspect affected authority, interfaces, callers and tests.
3. Reproduce or record the before-state where the package requires behavioral proof.
4. Implement the smallest coherent slice inside declared scope.
5. Run focused local checks first; correct failures before broader verification.
6. Update tests/fixtures/docs that own the changed contract, without weakening the oracle to match the implementation.
7. Review the actual diff against the work order and capture after-evidence.
8. Run the final applicable local acceptance once on the stable candidate.
9. Use hosted CI only for claims that require the hosted provider or integration environment.

Continue reversible authorized work without repeatedly asking for permission. Stop only when an external, destructive, compliance, licensing, credential, budget or product decision is required.

Never turn an unavailable check into a pass, and never treat a green test count as acceptance by itself.
