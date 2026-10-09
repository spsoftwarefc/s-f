# PQ-07C — real process-death and local recovery cross-check

Source-only campaign exercises abrupt Python child termination via `os._exit(73)` at durable intent, generation reservation, after possible send, and after target SQLite commit. It reopens distinct WAL/FULL single-host SQLite databases and checks committed records across process restart. Unknown outcomes forbid new reservations; an effect receipt found locally is still unverified as a remote service outcome. The read-only assessor never authorizes another write.

**Qualification limits:** abrupt process death is not an OS power cut or disk failure, and no physical restore, remote authenticated receipt, credential, live Linux reference service, multi-host fence or external release authority is exercised. The local read-only assessor returns `retryAuthorized=false`, `targetReceiptAuthenticated=false` and `productionQualified=false` for all cases. No publisher or adopter effects are authorized.

CI evidence pending exact stable PR run. No changes to existing SF-15/SF-19 fixture semantics.
