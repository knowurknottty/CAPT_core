# TERRA PR #47 OpenRouter authenticated transport acceptance

Classification: `OPENROUTER_AUTHENTICATED_TRANSPORT_VERIFIED`

## Artifact and transport

- Candidate source head: `10854b5a2b9835788478ee7770fcaa17bb4e1156`
- Wheel: `capt_solo-0.5.0-py3-none-any.whl`
- Wheel SHA-256: `db3ee232320e4a1cd63556c03813285dab24429e9c590e2712a7242145fc05e1`
- Provider: OpenRouter
- Transport: OpenAI-compatible Chat Completions
- Base URL: `https://openrouter.ai/api/v1`
- Requested preset: `@preset/inversion-labs-mimo2-5`
- Credential source: local environment; only presence was recorded.
- Raw credential persisted or disclosed: no.

## Journaled pre-dispatch gate

The installed runtime wrote and flushed a redacted evidence journal before remote dispatch. It retained approval-request and approval-decision receipts, independent EventStore checks, and a pre-dispatch snapshot.

The authoritative approval sequence was:

`HumanApprovalRequested → HumanApprovalDecided(state=approved, remainingUses=1) → no HumanApprovalConsumed/no DriverRun before dispatch`

## One authenticated CAPT dispatch

One installed CAPT ProviderDriver execution was dispatched against the exact preset. A response returned. The completed DriverRun, consumed approval, and `awaiting_verification` task state were read from EventStore. The runtime did not automatically create verification, ClaimGuard decision, or task-success authority.

Exact replay was idempotent with event delta zero. A materially different second use was rejected as `MODEL_PROMPT_APPROVAL_DIGEST_MISMATCH` with event delta zero.

## Secret audit

The durable local journal, receipts, replay receipts, and report evidence were scanned without disclosing secret material. No raw credential bytes were found. No Authorization header or bearer token was retained.

## Scope

This is transport evidence only. It does not modify source, wheel, PR head, or the earlier provider-authority evidence. D-09 / Hermes LOCAL-002 remains quarantined.
