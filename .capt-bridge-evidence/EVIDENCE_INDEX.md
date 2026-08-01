# CAPT BOOTSTRAP BRIDGE — EVIDENCE INDEX

All evidence under `.capt-bridge-evidence/`. Generated evidence is explicitly
**NOT** canonical CAPT source; it is bootstrap proof that the bridge performed a
real runtime handoff.

## Baseline (Phase 1) — defect reproduction
- `baseline/BOOTSTRAP_BRIDGE_BASELINE.md` — narrative of the fresh-Hermes-process
  reproduction of `SKILL_LOADED_CAPT_RUNNER_NOT_ACTIVE`.
- `baseline/BOOTSTRAP_BRIDGE_BASELINE.json` — machine-readable classification with
  runtime evidence (skill digest, CAPT source path, runner-absence, provider owner
  = Hermes, no ContextPack/MemoryUseGate/CTP/KHSB, no manual checkpoint artifacts).
- `baseline/hermes-baseline-stdout.txt` — raw Hermes stdout from the fresh process.
- `baseline/hermes-baseline-stderr.txt` — raw Hermes stderr.
- `baseline/hermes-baseline-exit.txt` — exit code (2, provider-loop-only).

## Seam map & decision (Phase 2)
- `docs/bridge/CAPT_BOOTSTRAP_SEAM_MAP.md` — verified Hermes ↔ CAPT seam, with
  source paths and line numbers.
- `docs/bridge/CAPT_BOOTSTRAP_DECISION.md` — where the bridge lives, how the skill
  invokes it, how provider ownership transfers, how Hermes-native dispatch is
  suppressed (the `llm_execution` middleware + fail-closed-by-return contract),
  how CAPT output returns, and how cancellation/exit propagate.

## Acceptance (Phase 10)
- `acceptance/ACCEPTANCE_MANIFEST.json` — three scenarios (success / failure /
  ownership), all passing, with per-check evidence.
- `acceptance/receipts/*.json` — `RUNTIME_OWNERSHIP_DENIAL` receipts emitted when
  an external skill mutation was attempted.

## Provenance
- Every evidence file is sidecar-hashed (`.sha256`) where produced.
- No credential, token, or secret is present in any evidence file. The launch
  nonce is redacted (`<redacted>`) wherever serialized.
