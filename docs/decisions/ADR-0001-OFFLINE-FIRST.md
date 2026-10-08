# ADR-0001 — Local CLI before hosted orchestration

Decision: use an offline-first Python CLI plus pinned bundle; project adapters own commands and release policy. Alternative: hosted distributed coordinator. Reject now because cross-repository worker scheduling and remote recovery demand are unmeasured. Reverse when qualified workloads need concurrent remote coordination or standalone-binary distribution demonstrably outgrows the Python prerequisite.

Trust decision: repository discovery is read-only, no auto-execution; provider evidence needs independent verification; release effects are separately authorized. This is a design decision, not an implemented enforcement claim.
