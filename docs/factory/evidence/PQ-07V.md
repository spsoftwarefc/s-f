# PQ-07V — prospective disposable reference-target contract

Work order committed before implementation at `5028a40fc7974b9a8d2a0319df90664dc62449ec`. This pure source validator checks a declared target profile, bounded resources, declared destination-side CAS/idempotency/status, and twelve explicitly **planned** live fault scenarios. It rejects production VPS scope, oversized budgets, missing required capabilities, preclaimed successes and extra authorization flags. Nothing opens a network connection, accesses credentials or exercises a real target.

A declarative CAS flag **cannot establish** atomic remote fencing. Actual signed target work order, credentials, provider status, process kill/restore and authenticated receipts remain unavailable. Live PQ-07 NO-GO; PQ-08 NOT STARTED; SF-R10 UNMET.
