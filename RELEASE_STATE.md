# RELEASE_STATE.md — Release Readiness

- **package**: `capt-solo`
- **declared version**: `0.4.1` (pyproject.toml, plugin.json, README, installer banners).
- **license**: MIT (approved for this safe public release — Decision 6). LICENSE present.
- **release target**: `CAPT_core` public release (local only; **not published** — Decision 5).
- **last full test run**: **502 passed** (pre-engine baseline; will rise as engines land).
- **last runtime verify**: `46 pass / 0 warn / 0 fail / 0 skip`.
- **last registry validate**: `15 checks, 0 fail, 0 warn`.

## Owner decisions applied (ADR-0007)
1. **D1** Research modules (FILT/FSR/NEDA/CONS/QIPC/OUROBOROS) may be public *if real*; none have code in tree → documented specs only, not shipped.
2. **D2** Memory systems (HMC/ENGRAM/DREAM + episodic/autobiographical/semantic/governance/provenance/consent/replay/revision/retention/export/import/recovery) finished + public. HMC/ENGRAM/DREAM stay `CAPT_core` (registry reconciled to `partial`).
3. **D3** Puter KV + mesh sync PRIVATE; local consent/sync abstractions public.
4. **D4** PULSE public (optional, disabled-by-default); RYS private (excluded).
5. **D5** Do NOT publish. Local commits only; owner publishes manually.
6. **D6** MIT approved; reconcile metadata/headers/docs.

## Public/private boundary (canonical: docs/RELEASE_GOVERNANCE.md)
- **PUBLIC:** all `CAPT_core` code in tree + new Mathematics/Physics/Invention engines + PULSE (optional) + local consent/sync abstractions.
- **PRIVATE (excluded):** RYS, Puter KV, mesh, private coordination, credentials, endpoints. **None present in tree** (verified).
- **RESEARCH (spec, no code):** FILT/FSR/NEDA/CONS/QIPC/OUROBOROS/CIG/HDR/META/… (documented as specifications).

## Open release gates
- None blocking at code level. All prior [B]/[S] gates **resolved by owner decisions** (ADR-0007).
- Remaining: finish + test the three engines and memory convergence to reach
  **SAFE PUBLIC RELEASE READY** (owner's primary priority). Publication itself is
  withheld per D5 until owner triggers it.

## Recommended release decision
**RELEASE CANDIDATE** → progressing to **SAFE PUBLIC RELEASE READY** as engines
and memory convergence complete and verification passes. Publication deferred per D5.
