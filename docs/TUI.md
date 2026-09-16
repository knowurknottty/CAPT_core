# CAPT TUI — Textual Operator Console

The TUI is a thin interactive operator surface over CAPT RuntimeService. It is not a second runtime.

## Launch

```zsh
python -m pip install -e '.[ui]'
capt start
capt tui
```

The bootstrap resolves the canonical local runtime socket/token layout.

`capt-ui dashboard` is a noninteractive summary command, not the TUI launcher.

## Operator capabilities

The TUI/operator layer exposes runtime/mission/task state, memory/context, provider/model state, approvals, evidence/verification/ClaimGuard projections, logs, checkpoint/resume/cancel, CaveCAPT presentation controls, and the reconciled prompt/provider run controls from the older stacked cockpit line.

The enhancement/presentation layer may propose or display context; it may not grant capability, bypass RuntimeService approval, make a provider result verified, or declare task/mission completion.

## Merged convergence status

PR #117 is merged into `main` and contains the coherent cumulative implementation rather than treating PR #47 as the active authority. The merged line also carries durable Cohort/steering projections, replay/forensic/provenance/security operator surfaces, native macOS work, and the provider/model-coherence semantics from closed-unmerged PR #118.

Historical 2026-08-19 Core verification was green across the Python suite and Swift normal/strict/ThreadSanitizer suites. Historical cross-surface acceptance with MCP PR #2 also passed against one shared disposable RuntimeService/EventStore.

The later PR #148 native/TUI golden authority tranche adds explicit filesystem/write/shell/provider-network scope, prompt-proposal review, and provider-result review. Approval binds the selected scope; successful dispatch does not silently complete verification. The semantic operator-control API and runtime read projections extend the shared integration contract; they do not imply every query has a dedicated TUI widget.

## Current classification

- TUI foundation on `main`: **MERGED**;
- cumulative TUI/provider/operator line: **MERGED SOURCE**, with historical integration evidence;
- native macOS source: **MERGED**, with historical build/integration evidence;
- release authorization: **not established for the 2026-09-15 HEAD by these historical checks; exact-source Security Closure Cockpit evidence is required**.

See [`CURRENT_STATE.md`](CURRENT_STATE.md) and [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md).
