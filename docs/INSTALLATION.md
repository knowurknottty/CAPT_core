# CAPT Installation

This guide distinguishes the protected `main` install from the terminal PR #117 convergence candidate. See [`CURRENT_STATE.md`](CURRENT_STATE.md) before treating advanced functionality as released.

## Development/evaluation install

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
capt-ui dashboard
```

Default local state is `~/.capt`, overridable with `$CAPT_STATE_DIR`. The canonical runtime uses the local `runtime.sock` / `runtime.token` layout.

## Native macOS candidate

On the terminal convergence branch:

```zsh
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

`CAPTNativeMac` is a real application target, not merely a contract library. Fresh candidate verification includes normal Swift, strict concurrency/warnings-as-errors, and ThreadSanitizer passes.

That is source/build evidence—not signing, notarization, distribution, or release-security authorization.

## Provider note

The convergence line supports governed Ollama and configured local/authenticated OpenAI-compatible execution. A configured/healthy provider is not automatically proof of a completed governed mission. The generic direct native MLX placeholder is intentionally unregistered unless a real adapter/configuration exists.

## Platform note

macOS is the primary development environment. Linux has established CI/release-era paths. Windows remains unverified unless newer exact-head platform evidence says otherwise.

## Troubleshooting

Run `capt doctor` first, then use [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).
