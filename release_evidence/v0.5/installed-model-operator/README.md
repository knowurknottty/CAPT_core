# Installed Model-Operator Proof — CAPT Core v0.5

**Evidence class:** `LOCAL_REAL_PROCESS_PROVEN` + `INSTALLED_WHEEL_PROVEN`
**Executed:** locally on macOS; installed wheel; real Hermes process; externally dependent model/provider.
**NOT rerun by hosted CI** (requires local Hermes + model provider).

## Full lifecycle path exercised

```
installed capt CLI
→ authenticated Unix-socket service
→ mission/task/session authority
→ TaskResolver
→ DriverHost
→ real Hermes process
→ untrusted model result
→ build_verification_result()
→ strip_view()
→ frozen VerificationResult validation
→ EventStore persistence (ClaimVerified)
→ ClaimGuard (ClaimGuardDecided)
→ checkpoint → stop → socket cleanup → restart (same ledger)
→ resume (execution=not_repeated)
→ second distinct governed action
→ final checkpoint → final stop
```

## Identity

| Field | Value |
|-------|-------|
| Proof wheel source | `4005809` |
| Proof wheel sha256 | `2a8a6ef95f688b546227b162b603bcb07b644e7686c11a44bffa30fbd5397be2` |
| Hermes executable | `/Users/knowurknot/.local/bin/hermes` |
| Hermes version | v0.20.0 (2026.8.3) |
| model / provider | nvidia/nemotron-3-ultra-550b-a55b:free / openrouter |
| mission / task | m-model-version-audit-7 / m-model-version-audit-7-task-1 |
| driver-run | dr-model-version-audit-7 |
| claim | cl-model-version-audit-7 |
| evidence | ev-sha256:01997b44a |
| verification | vr-sha256:44c5f6eef |
| checkpoint | cp-cmd-3e02c666f8c60dcb |
| idempotency key | idem-version-audit-7 |
| artifact digest | sha256:13ab095c591f23fb94c0f0187cdbf3bf73cd4f30afafe563b85d69eb4c5eab21 |

## Ledger head progression

| Stage | Ledger head |
|-------|-------------|
| after seed | 13 |
| after first governed action | 29 |
| after duplicate (idempotent) action | 29 (unchanged) |
| after second distinct governed action | 45 |

## Rate-limit condition — honest disclosure

The Hermes model process reported `HTTP 429 Rate limit exceeded: free-models-per-day-high-balance` after 3 retries during mission-audit-7. The runtime still produced an untrusted observation and artifact (294 bytes), and the **full CAPT lifecycle completed normatively** — the verification path validated the artifact (repo unchanged, artifact digest matched), persisted the ClaimVerified event, and produced the ClaimGuard decision. This is an external provider condition, not a CAPT defect. The artifact content is therefore minimal but the governance/lifecycle proof is complete.

The second governed action (mission m-model-verify-2) succeeded with a substantive model response (33-module package inspection), proving the model operator can produce real evidence-backed output when the provider is not rate-limited.

## Persisted VerificationResult proof

See `persisted-verification-payload.json`. Confirmed:
- `claimId`: present (non-null)
- `strategy`: present
- `verifiedAt`: present
- `supportingEvidenceIds`: present (cites recorded evidence)
- `_view`: excluded from persisted payload
- top-level `trust`: excluded
- top-level `checks`: excluded
- top-level `observedBy`: excluded
- passes frozen VerificationResult contract validation
- no contract schema change required

## Idempotency proof

- Repeated identical command + same idempotency key → `status=idempotent, classification=duplicate`
- no second Hermes process execution
- duplicate artifact: none
- duplicate verification: none
- duplicate evidence: none
- duplicate ClaimGuard promotion: none
- ledger head unchanged (29)

## Restart / no-repeat proof

1. checkpoint → clean stop
2. socket removed (cleanup confirmed)
3. restart with same state directory (same ledger, head=29 preserved)
4. resume → `execution=not_repeated` (checkpoint verified)
5. original driver-run (dr-model-version-audit-7) and verification (vr-sha256:44c5f6eef) IDs unchanged
6. second distinct governed action executed → accepted (head 45)
7. final checkpoint → final clean stop
