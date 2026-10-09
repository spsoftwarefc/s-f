# PQ-07O — provider review source evidence

Work order committed before implementation at `a06c8a8cb9862cd68bc40925ff4b6671ed8a825f`. Parent PQ-07N commit `65108eed5b82109e7778f4ead637cff38bc5a592`.

`tools/pq07_provider.py --policy ABSOLUTE.json --policy-sha256 INDEPENDENT_SHA256` invokes existing production `observe_pinned_ci` to independently hash the operator-selected policy before live GitHub API fetch, including run/attempt/workflow/check and artifact metadata verification. A successful code 0 means **read-only provider observation**, never effect grant. Malformed/contradictory evidence exits 2; provider unavailability exits 3. Error output never echoes credentials or the policy contents.

New focused tests cover no-authority on valid simulated observation, rejection of assertion escalation, and distinct blocked/unavailable paths. Existing test_ci_evidence and test_release_authority cover negative provider job identities, source bounds and policy digest mismatch. No real credential provisioned, GitHub run triggered, artifact downloaded, grant issued or target used. Exact provider and checkout claims still require independent live campaign. PQ-07 live NO-GO; PQ-08 not started; SF-R10 unmet.
