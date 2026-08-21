# Start Here

**CAPT Core is a local-first governed runtime and continuity substrate around replaceable AI models.**

> The model is an inference component. CAPT keeps durable state, memory, authority, evidence, and recovery outside the model session.

Before evaluating advanced features, read [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md). Protected `main`, the terminal PR #117 candidate, and release authorization are intentionally different states.

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

Evidence, verification, ClaimGuard, task completion, and mission completion are distinct authority states.

## Launch the operator console

```zsh
capt-ui dashboard
```

The TUI is a RuntimeService projection/control surface; it does not own the ledger or bypass governance.

## Native macOS candidate

On the terminal convergence line:

```zsh
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

The native target is real and integration-tested, but signing/notarization/distribution and release-security authorization remain separate gates.

## Restart continuity

```zsh
capt checkpoint --idempotency-key first-cp
capt stop
capt start
capt resume --idempotency-key first-resume
capt status
```

Continuity belongs to CAPT state rather than a model transcript.

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
