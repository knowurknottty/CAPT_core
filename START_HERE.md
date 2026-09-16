# Start Here

**CAPT Core is a local-first governed runtime and continuity substrate around replaceable AI models.**

> The model is an inference component. CAPT keeps durable state, memory, authority, evidence, and recovery outside the model session.

Before evaluating advanced features, read [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md). The 2026-09-15 source snapshot is `1e85bac5d17cde342a1ae55e6ee3da5fa681ff61`: PR #146, #148 plus the semantic operator-control API, #153 Model Council alpha, #155 hardening, and #156 SOMA M0 are merged. Merged integration, the `0.5.0` package line, and release authorization are intentionally different states; older exact-SHA security receipts do not authorize this HEAD.

## Install the CLI and TUI

```zsh
git clone https://github.com/knowurknottty/CAPT_core.git
cd CAPT_core
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[ui]'
```

Confirm resolution:

```zsh
which capt
capt --version
capt doctor
```

The package metadata still reports `capt-solo 0.5.0` even though repository integration work is newer.

## First success: durable state

```zsh
capt memory store "CAPT keeps durable state outside the model."
capt memory search "durable state"
capt start
capt status
capt evidence
capt checkpoint
```

`capt memory store/search` use the local CAPT Solo MemoryEngine directly, while `capt start/status/evidence/checkpoint` use RuntimeService. A successful memory search does not prove EventStore admission or model-visible continuation context.

Evidence, verification, ClaimGuard, task completion, and mission completion are distinct authority states.

## Launch the operator console

```zsh
capt tui
```

The TUI is a RuntimeService projection/control surface; it does not own the ledger or bypass governance.

## Native macOS application

On current `main`:

```zsh
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

The native target and integration tests are present in source. PR #148 adds the control center and Prompt Intelligence; `42a6cd2` adds the semantic operator-control API. `d33a5e4` separates model answers from retained execution details, and `1e85bac` expands AUTO routing signals for actionable requests, including list/match; the four-word minimum and operator-selected engine/mode still apply. These fixes do not complete the human-first results layer or Search/Deep Research product. Signing/notarization/distribution and exact-HEAD release-security authorization remain separate gates.

## Restart continuity

```zsh
capt checkpoint --idempotency-key first-cp
capt stop
capt start
capt resume --idempotency-key first-resume
capt status
```

This exercises runtime checkpoint/restart/resume. It does not by itself prove restored workload contents, no-repeat external effects, or cross-model continuation; those require a workload and matching evidence across the restart.

## Next

- [Current repository state](docs/CURRENT_STATE.md)
- [Functionality matrix](docs/FUNCTIONALITY_MATRIX.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Desktop/native status](docs/DESKTOP.md)
- [Providers](docs/PROVIDERS.md)
- [Security boundaries](docs/SECURITY.md)
- [Release evidence](docs/RELEASE_EVIDENCE.md)
- [Roadmap](docs/ROADMAP.md)

If prose and exact source/evidence disagree, exact source/contracts/evidence win.
