# CAPT Installation

This guide covers merged Core source as of 2026-09-15, including PR #117 and later operator integrations. See [`CURRENT_STATE.md`](CURRENT_STATE.md) before treating advanced functionality as released.

## Development/evaluation install

Use a Python environment compatible with the resolved dependencies. The repository's Linux CI matrix targets Python 3.10 and 3.12; the package's declared `>=3.8` minimum alone is not proof that the current dependency set installs on Python 3.8.

```zsh
git clone https://github.com/knowurknottty/CAPT_core.git
cd CAPT_core
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[ui]'
```

Verify resolution:

```zsh
which capt
which capt-ui
capt --version
capt doctor
```

`pyproject.toml` still declares `capt-solo 0.5.0`; repository integration state is newer than that package version.

## First run

```zsh
capt start
capt status
capt memory store "CAPT is alive"
capt evidence
capt checkpoint
capt tui
```

Default runtime state is `~/.capt`, overridable with `$CAPT_STATE_DIR`. The canonical runtime uses the local `runtime.sock` / `runtime.token` layout. The standalone `capt memory store` command above instead writes Solo memory under `~/.capt-solo` (`CAPT_SOLO_HOME` overrides it); it does not seed runtime memory or establish a completed inference. `capt-ui dashboard` prints a summary rather than launching the interactive TUI.

## Native macOS application

From the merged source checkout, on macOS 13 or later with a Swift 5.9-compatible or newer toolchain:

```zsh
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

`CAPTNativeMac` is a real application target, not merely a contract library. Historical convergence verification includes normal Swift, strict concurrency/warnings-as-errors, and ThreadSanitizer passes; those results do not certify a later checkout. Merged source now includes governed Settings/Skills/authority controls and separate model-answer/execution-receipt rendering.

That is source/build evidence—not signing, notarization, distribution, or release-security authorization.

## Provider note

Merged Core supports governed Ollama and configured local/authenticated OpenAI-compatible execution. Provider configuration/health proves neither completed inference nor a completed governed mission. The generic direct native MLX placeholder remains unregistered; a configured MLX/MTPLX OpenAI-compatible service uses a separate supported adapter path.

## Platform note

macOS is the primary development environment. Linux has established CI/release-era paths. Windows remains unverified unless newer exact-head platform evidence says otherwise.

## Troubleshooting

Run `capt doctor` first, then use [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).
