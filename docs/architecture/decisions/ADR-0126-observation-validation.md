---
status: Accepted (M0-B)
date: 2026-08-03
relates_to: ADR-0120, ADR-0124
---

# ADR-0126 — Observation and receipt ingestion

## Context
The driver emits observations and claim proposals. CAPT must validate them and
prevent driver-generated authoritative events, duplicate observations, fake
receipts, and authority escalation.

## Decision
All driver output is treated as untrusted input. `capt_runtime/ingestion.py`
validates: schema, driver identity, run ID, sequence number, timestamp bounds,
content size, artifact path, checksum, duplicate status, capability scope,
work-order relationship. It rejects:
- authoritative CAPT `EventEnvelope` types from the driver,
- fabricated `CapabilityConsumptionRecord`s,
- fabricated `VerificationResult`s,
- fabricated ClaimGuard decisions,
- path escapes / symlink escapes,
- observations for another mission or task,
- duplicate observations with conflicting payloads,
- receipts without verifiable artifacts,
- success claims unsupported by evidence.

CAPT alone creates authoritative records. Promotion is via the verification
pipeline (ADR-0120).

## Reversal conditions
None for M0-B.
