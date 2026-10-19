# Start Here

**CAPT Core is a local-first governed runtime and continuity substrate around replaceable AI models.**

> The model is an inference component. CAPT keeps durable state, memory, authority, evidence, and recovery outside the model session.

Begin with the [documentation index](docs/README.md) and [role-based onboarding](docs/ONBOARDING.md) if you are new to the system. The [state report](docs/CURRENT_STATE.md) is a **dated October 8 snapshot**, not current-HEAD release certification. This guide's earlier September 15 snapshot (`1e85bac5d17cde342a1ae55e6ee3da5fa681ff61`) is historical lineage; the earlier OMEGA pass examined `0d8e46d095243e80febd4e30f5ae52c9202316d9`; a later 2026-10-18 check pinned `main` at `c956c45e33119cd31ce7e61c55334e803f20bf3f`. Package version `0.5.0`, source integration, and release authorization remain separate states.

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

**Disposable first exercise (optional):** if you prefer not to write to your existing Solo memory, use a temporary local state root. This example stores and searches one record, then removes **only** the temporary directory created for this exercise:

```zsh
(
  scratch="$(mktemp -d /tmp/capt-solo-docs.XXXXXX)" || exit 1
  trap 'rm -rf "$scratch"' EXIT
  export CAPT_SOLO_HOME="$scratch/solo"
  capt memory store "CAPT documentation trial" --namespace docs-demo
  capt memory search "CAPT documentation trial"
)
```

**Expected:** the store and search both exit successfully, and the search prints the saved text and a memory ID. This was exercised in an isolated temporary directory using the pinned 2026-10-18 checkout; it does **not** test the canonical runtime event ledger or a model provider.

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
