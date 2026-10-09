# PQ-07Q — isolated local crash/fencing source evidence

Work order committed first at `aef1a0e3f30696eeeb80ffa6d487302ac614c40b`. Parent PQ-07P `94f0c4481ec44a5d36cf07f0a60ec21f363b49a3`.

Added an isolated temporary SQLite reference target campaign where a **separate child process** commits generation 1 then exits deliberately with code 17; a fresh process reopens the durable receipt, verifies replay idempotency, rejects stale generation and contradictory operations, and commits generation 2 with proper CAS. Focused tests also reject unexpected child exit. The campaign returns `realRemoteFenceQualified=false`, `realServiceDeployed=false`, `productionQualified=false` without exceptions.

`PQ07_REFERENCE_RUNBOOK.md` freezes prospective live target, incident, recovery and authority checks, and explicitly requires separate operator-owned disposable Linux scope before effects. No service, credential, network, paid hosting or unrelated repository touched. PQ-07 live NO-GO; PQ-08 not started; SF-R10 remains unmet.
