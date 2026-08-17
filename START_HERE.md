# Start Here

**CAPT Core is a local-first governed runtime and continuity substrate around replaceable AI models.**

> The model is an inference component. CAPT keeps durable state, memory, authority, evidence, and recovery outside the model session.

This walkthrough exercises the **merged `main` path**. It does not require a model or cloud credential.

For exact current status before evaluating advanced features, read [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md).

## Prerequisites

- macOS or Linux for the currently exercised path;
- Python 3.10–3.12 are the established CI/release-era versions; 3.12 is a good default;
- `git` and a POSIX shell.

Windows remains unverified unless a newer exact-head platform proof says otherwise.

## Install the CLI and TUI

```zsh
git clone https://github.com/knowurknottty/CAPT_core.git
cd CAPT_core
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[ui]'
```

Confirm what you installed:

```zsh
which capt
capt --version
capt doctor
```

The package metadata currently reports `capt-solo 0.5.0` even though `main` contains later productization work. That version/state distinction is intentional and documented.

## First success: durable memory

```zsh
capt memory store "CAPT keeps durable state outside the model."
capt memory search "durable state"
capt memory list
```

## Start the governed runtime

```zsh
capt start
capt status
```

Normal state defaults to `~/.capt` unless `$CAPT_STATE_DIR` is set. The normal user does not need to provide socket, token, or ledger paths.

## Inspect evidence

```zsh
capt evidence
```

Evidence, verification, and ClaimGuard are different concepts. A recorded observation is not automatically verified, and verification is not automatically mission completion.

## Launch the merged Textual TUI

```zsh
capt-ui dashboard
```

The merged TUI is an operator/control surface over RuntimeService. It does not own the ledger or bypass governance.

The richer prompt/cognitive cockpit controls described in [`docs/TUI.md`](docs/TUI.md) are currently part of the active PR #47 integration lane, not the numbered package release.

## Checkpoint, stop, restart, resume

```zsh
capt checkpoint --idempotency-key first-cp
capt stop
capt start
capt resume --idempotency-key first-resume
capt status
```

The purpose of this path is to demonstrate that continuity belongs to CAPT state rather than to a model transcript.

## Next

- [Current repository state](docs/CURRENT_STATE.md)
- [Mental model](docs/MENTAL_MODEL.md)
- [User workflows](docs/USER_GUIDE.md)
- [TUI](docs/TUI.md)
- [Providers](docs/PROVIDERS.md)
- [Capability matrix](docs/CAPABILITY_MATRIX.md)
- [Demos](docs/DEMOS.md)
- [Security boundaries](docs/SECURITY.md)
- [Release evidence](docs/RELEASE_EVIDENCE.md)

If a guide and an executable surface disagree, the exact source/contract and exact-head evidence win.