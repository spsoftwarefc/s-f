# PQ-07D — exact retained byte audit

New read-only audit requires an independent expected manifest digest plus separately supplied local SBOM, provenance and toolchain lock files. It reads *previously staged* retained source bytes, rehashes them and rejects input substitution, missing evidence, role aliases, digest mismatches and corrupted retention. Nothing rebuilds, downloads or publishes an artifact during the audit.

The test campaign uses synthetic bytes. An apparent provenance document or SBOM with a matching hash is **not independently authenticated**, signed, semantically validated or released. Mandatory live builder/attestation/retention custodian and promotion rights remain pending. Qualification and publisher-custody flags stay false. All external deployment and publication effects remain disallowed.
