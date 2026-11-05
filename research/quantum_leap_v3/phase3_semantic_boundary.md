# Quantum Leap v3 — Phase 3 evidence boundary

Pinned CAPT revision: e28b66504c422946a66409d0de12e71f1646aae6.
Research branch: experiment/quantum-leap-v3-hardening.
Status: experimental, observe-only, not installed into CAPT.

## What was checked

Five synthetic Git counterexamples were constructed and evaluated with the original v3 predicates. Each satisfies its corresponding predicate while disproving a stronger interpretation:

- C1/HO5: unused token check present while active admission bypasses it.
- C2/AS9: a named digest function returns one constant.
- C3/AS6: non-reactivation marker exists while replay logic reuses historical authority.
- C4/HO3: a context-selection function exists but drops context.
- C5/PU13: the expected field name is absent from the counted file, but exists in an imported migration.

These are deliberate hypothetical tests, **not evidence that CAPT itself has these defects**. The original 52-claim corpus is unchanged. The 52-entry semantic review register keeps every semantic verdict NOT_ASSESSED. P0/P1/P2 are review priorities, not truth certifications.

## Request identity preflight

The read-only request_preflight module uses CAPT's actual ToolRequest schema validator and tool_request_fingerprint implementation. It recomputes the finite-decision advisory assessment, checks exact typed arguments, the supplied operation/tool identities, and the supplied world/policy digests.

The module never authorizes a tool, consumes approval, writes an EventStore stream, dispatches a capability, or verifies completion. All positive results are IDENTITY_MATCH_ONLY. Supplied identities/digests are NOT cryptographically authenticated by this module. Model-supplied probability is NOT calibration or authority.

## Existing CAPT boundaries

- ToolBroker remains responsible for registered descriptor validation, risk/effect classification, grant/lease validation, preparation, dispatch, settlement and reconciliation.
- WorldReceipt structural verification is not an independent readback of a mutated target.
- Model approval binding and prepared model execution differ from tool execution authorization.
- User/operator presence and evaluator custody remain separately unverified.

## Gates still closed

1. Independent natural-language claim/predicate adjudication; synthetic counterexamples are not an adjudicator.
2. Runtime-minted offering with verifiable issuer, nonce, grant binding, expiry and revocation.
3. Current-world revalidation at ToolBroker admission.
4. Independently custodied world readback, protected from same-UID write access.
5. Verified postconditions and truthful task completion.
6. Production shadow evaluation and calibrated comparison with local-rules and provider-timeout baselines.

No production runtime, gate, model call, or approval was changed.
