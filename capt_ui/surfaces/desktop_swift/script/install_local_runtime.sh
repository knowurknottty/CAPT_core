#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
REPO_ROOT="${SCRIPT_DIR:h:h:h:h}"
STATE_DIR="${CAPT_STATE_DIR:-$HOME/.capt}"
VENV="$STATE_DIR/runtime-venv"
BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/capt-native-runtime.XXXXXX")"
trap 'rm -rf "$BUILD_DIR"' EXIT

mkdir -p "$STATE_DIR"
cd "$REPO_ROOT"
SOURCE_HEAD="$(git rev-parse HEAD)"
python3 -m build --wheel --outdir "$BUILD_DIR"
WHEEL="$(find "$BUILD_DIR" -maxdepth 1 -name 'capt_solo-*.whl' -print -quit)"
[[ -n "$WHEEL" ]] || { echo "CAPT wheel build failed" >&2; exit 1; }

rm -rf "$VENV"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet "$WHEEL"
WHEEL_SHA="$(shasum -a 256 "$WHEEL" | awk '{print $1}')"
printf '%s\n' "$SOURCE_HEAD" > "$VENV/CAPT_SOURCE_HEAD"
printf '%s\n' "$WHEEL_SHA" > "$VENV/CAPT_WHEEL_SHA256"

"$VENV/bin/capt" --help >/dev/null
printf 'CAPT private runtime installed\n'
printf '  source: %s\n' "$SOURCE_HEAD"
printf '  wheel:  %s\n' "$WHEEL_SHA"
printf '  cli:    %s\n' "$VENV/bin/capt"
