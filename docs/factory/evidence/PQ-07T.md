# PQ-07T — read-only live-campaign intake

Work-order-first: `docs/factory/work-orders/PQ-07T.json` was committed at `f929ae86bcaa98fb13e64b62e3a1c82ef1cf34a5`, before runtime and tests.

Introduces a bounded, canonical JSON manifest intake with independent caller-supplied SHA-256 pins, exact source/tree/artifact/policy binding, frozen disposable Linux reference profile, 24-hour maximum clock interval, duplicate rejection and strict external decision declarations. The input is candidate origin; a digest **never** proves independent custody. Source-derived `approved`, `accepted`, true authority flags and duplicate decisions reject. Every emitted effect and production-qualification flag stays false even if all eight declarations are present.

Focused tests include positive read-only validation and negative wrong-pin, scope, expiry, profile, forged approval, duplicate decision and duplicate-key cases. No provider API call, grant, release workflow dispatch, credentials, real target, external custodian or production claim. Hosted verification belongs to the exact PR candidate; do not mark passed until provider reports success.

PQ-07 live NO-GO; PQ-08 NOT STARTED; SF-R10 UNMET overall.
