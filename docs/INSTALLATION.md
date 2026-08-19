# CAPT Installation

This guide installs the current merged `main` operator surfaces. See [`CURRENT_STATE.md`](CURRENT_STATE.md) for the distinction between package version, merged capabilities, and active integration work.

## Recommended development/evaluation install

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

`pyproject.toml` currently declares package version `0.5.0`; later productization code is present on `main` without a new numbered package release yet.

## First run

```zsh
capt start
capt status
capt memory store "CAPT is alive"
capt evidence
capt checkpoint
capt-ui dashboard
```

Then test restart continuity:

```zsh
capt stop
capt start
capt resume
capt status
```

## State paths

Default normal-user state is `~/.capt`, overridable with `$CAPT_STATE_DIR`.

The normal on-ramp creates/uses the canonical local runtime socket/token layout (`runtime.sock` and `runtime.token`). The merged UI bootstrap resolves that same layout.

## Surfaces

| Surface | Status on merged `main` |
|---|---|
| `capt` normal CLI | shipped/merged |
| `capt harness ...` | expert/debug surface |
| Textual TUI | shipped MVP |
| Tk desktop | operator MVP/reference fallback |
| SwiftUI | client-contract library; not a shipped `.app` |
| active PR #47 cockpit/provider execution | unmerged integration work |

## Provider note

Provider registration/discovery on `main` and provider **execution** in the active PR #47 lineage are different states. Do not treat a configured provider as proof of governed live inference. See [`PROVIDERS.md`](PROVIDERS.md).

## Platform note

macOS is the primary development environment and Linux has established CI/release paths. Windows should remain labeled unverified until separately proven.

## Troubleshooting

Run `capt doctor` first, then use [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).