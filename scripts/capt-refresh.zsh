#!/bin/zsh
# Single operator-invoked recovery; no secrets on argv.
set -eu
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
exec /opt/homebrew/bin/python3 "$ROOT/scripts/capt_recover.py" --recover "$@"
