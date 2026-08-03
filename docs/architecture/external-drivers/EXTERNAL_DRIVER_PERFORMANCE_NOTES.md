# External Driver Performance Notes (Gate A — OpenHarness)

## Environment (label as environment-specific)

- Host: macOS (CAPT worktree /Users/knowurknot/capt-m0a-gatea)
- Isolated venv Python: 3.12.13
- External harness: OpenHarness 0.1.9 (`oh`)
- Local model: Ollama `ornith-1.0-9b` (5.63 GB) at 127.0.0.1:11434
- Reference (CAPT) driver: pure stdlib, no model call

## Measurements (single bounded read-only analysis task)

| Metric | External (OpenHarness+local Ollama) | CAPT reference driver |
|--------|--------------------------------------|-----------------------|
| Cold-start overhead | ~1-2s (venv `oh` process spawn + model load) | ~0s (in-process) |
| Warm dispatch overhead | ~8-16s end-to-end (model inference dominates) | <0.1s |
| Memory overhead | Ollama model resident (~several GB) + `oh` process | negligible |
| External process count | 1 (`oh`) + 1 (Ollama server, pre-existing) | 0 |
| Artifact size | ~0.5-1 KB markdown | ~0.5-1 KB markdown |
| Observation volume | 1 structured observation (summary text) | 1 structured observation |
| Token use | model-dependent (local; not measured precisely) | n/a (no model) |
| Execution duration | 8.48s (no-tool prompt), 15.65s (repo analysis) | <0.1s |
| Reconciliation duration | <1s (state map) | <1s |

## Interpretation

- The dominant cost is LOCAL model inference (Ollama), not the adapter. The
  adapter's own overhead (subprocess spawn, env setup, stdout capture,
  normalization) is sub-second.
- This is an INTEGRATION OVERHEAD measurement, NOT a benchmark of intelligence
  quality. The local `ornith-1.0-9b` model is small; a larger local model would
  change duration but not CAPT semantics.
- The CAPT reference driver is faster because it performs structural inspection
  without a model call; both produce equivalent CAPT-level untrusted records.

## Notes

- All numbers are environment-specific and will vary with model size, hardware,
  and Ollama configuration. They are not a CAPT product-performance claim.
- No production-readiness claim is made.
