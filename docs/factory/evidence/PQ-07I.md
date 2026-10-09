# PQ-07I — read-only operator campaign intake command

Parent stacked PR #46 at `104c0a3b228382f68b8040de7c8638a0bad26a7c` (tree `0d92183c788dc92b7086466051fcebfc79fe04d5`).

Invoke with `python tools/pq07_campaign.py --manifest /abs/path/to/manifest.json --manifest-sha256 <operator-independent-digest> --source-commit <SHA40> --source-tree <SHA40> --artifact-sha256 <SHA256> --policy-sha256 <SHA256>` (angle-bracket metavariables replaced by actual values). No network call or target write is made.

Exit 0 means local bytes and input structure were assessed and a JSON **NO-GO** report was printed, *never* production acceptance. Exit 2 means malformed/unavailable/mismatched inputs. Do not derive a policy pin, verifier identity or authority from the manifest itself. Do not pass secrets; only public identities/digests.

Subprocess tests check valid-but-unqualified output, manifest digest mismatch, unsupported production environment and forged `productionQualified`. The live campaign still needs authenticated signer/provider receipts, independently protected policy/grant/replay, retained distribution, live fenced reference Linux deployment and authenticated operational incidents. SF-R10 remains unmet.

Draft package only; do not independently merge PR #47 or publish. PR #50 remains the protected cumulative merge checkpoint.
