# CAPT TUI — Textual Operator Console

The TUI is a thin interactive operator surface over CAPT RuntimeService. It is not a second runtime.

## Launch

```zsh
python -m pip install -e '.[ui]'
capt start
capt-ui dashboard
```

The bootstrap resolves the canonical local runtime socket/token layout.

## Operator capabilities

The TUI/operator layer exposes runtime/mission/task state, memory/context, provider/model state, approvals, evidence/verification/ClaimGuard projections, logs, checkpoint/resume/cancel, CaveCAPT presentation controls, and the reconciled prompt/provider run controls from the older stacked cockpit line.

The enhancement/presentation layer may propose or display context; it may not grant capability, bypass RuntimeService approval, make a provider result verified, or declare task/mission completion.

## Merged convergence status

PR #117 is merged into `main` and contains the coherent cumulative implementation rather than treating PR #47 as the active authority. The merged line also carries durable Cohort/steering projections, replay/forensic/provenance/security operator surfaces, native macOS work, and the provider/model-coherence semantics from closed-unmerged PR #118.

Fresh 2026-08-19 Core verification is green across the Python suite and Swift normal/strict/ThreadSanitizer suites. Cross-surface acceptance with MCP PR #2 also passes against one shared disposable RuntimeService/EventStore.

## Current classification

- protected-main TUI foundation: **MERGED**;
- cumulative TUI/provider/operator line: **MERGED / INTEGRATED**;
- native macOS source/build: **MERGED / ENGINEERING-VERIFIED**;
- release authorization: **BLOCKED pending Security Closure Cockpit evidence**.

See [`CURRENT_STATE.md`](CURRENT_STATE.md) and [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md).
