# CAPT Installation

This guide installs the canonical CAPT Core runtime and its operator surfaces
from the merged `main` lineage. It uses the normal-human CLI.

## Prerequisites

- Python 3.11+ (3.12 recommended; CI runs 3.10 and 3.12)
- `git`
- Optional: a local model provider for model execution — Ollama (default
  local), LM Studio, or an OpenAI-compatible endpoint. Model execution is a
  separate release gate; see `docs/PROVIDERS.md`.

## 1. Clone and prepare

```bash
git clone https://github.com/knowurknottty/CAPT_core.git
cd CAPT_core
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[ui]'   # includes the Textual TUI
```

## 2. Verify the install

```bash
which capt          # must point inside your venv (e.g. .../.venv/bin/capt)
capt --version
capt doctor         # environment diagnostics
```

> `which capt` must resolve to the venv binary, not a shell function or an
> unrelated CAPT checkout. `capt doctor` reports environment health.

## 3. First run (normal-human flow)

```bash
capt doctor
capt start                          # start the governed runtime (idempotent)
capt status                         # health + version + capabilities
capt memory store "CAPT is alive"   # store a durable memory
capt evidence                       # inspect what is recorded
capt checkpoint                     # save authoritative state
capt stop                           # stop the runtime
capt resume                         # resume from checkpoint (no repeated work)
```

State lives under `~/.capt` by default (override with `$CAPT_STATE_DIR`).
The EventStore ledger `~/.capt/runtime.db` is authoritative.

## 4. Operator surfaces

| Surface | Command | Status |
|---|---|---|
| CLI (normal) | `capt ...` | **SHIPPED** |
| Textual TUI | `capt-ui` | **SHIPPED** (MVP) |
| Tk desktop | `capt-ui` (operator layer) | **OPERATOR_MVP** (reference/fallback) |
| Native SwiftUI | `capt_ui/surfaces/desktop_swift` | **LIBRARY ONLY** (not yet a shipped app) |
| Expert harness | `capt harness ...` | **EXPERT/DEBUG** (requires socket/token paths) |

## 5. MCP Gateway (optional)

The CAPT MCP Gateway and CAPT Lite live in the companion repository
`knowurknottty/capt-workspace-mcp`. See that repository's `docs/integration/`
and `docs/lite/LITE_GUIDE.md`.

## Troubleshooting

See `docs/TROUBLESHOOTING.md`.
