# Imported checker: retained requirements, not retained enforcement

Status: SF-00 reconciliation note.

The extracted `tools/check_factory_evidence.py` was not accepted into the portable baseline. It hard-coded CTJ inventory/manifest/project-map paths and described CI/evidence behavior that s-f had not qualified. Keeping it under `tools/` would make those source assumptions look active.

The executable is removed in SF-00. Its reusable assurance intentions are retained here as requirements for later schema/CLI packages rather than discarded:

1. work-order declaration precedes scoped implementation;
2. candidate/base revisions are valid and correctly related;
3. changed paths are covered by declared scope;
4. evidence binds to the candidate it claims to verify;
5. a record cannot self-reference its own future commit;
6. stale or post-candidate acceptance-affecting changes invalidate evidence;
7. malformed or unknown-schema data fails validation;
8. routing targets and required instruction references resolve;
9. weakening/removing a control requires explicit control-change assessment;
10. candidate-stage incompleteness differs from acceptance failure;
11. hosted run facts require provider verification before supporting a CI-verified claim;
12. missing, skipped, cancelled, neutral or inaccessible required checks are not successes;
13. resume/handoff reports expose revision, dirty/out-of-scope work, completed obligations and remaining work;
14. validator tests use self-contained synthetic repositories rather than application-specific fixtures.

SF-02 and SF-10 are the intended implementation points for schema/local validation and verified hosted evidence. Reintroduction must use versioned portable contracts and negative tests; this note is not executable enforcement.
