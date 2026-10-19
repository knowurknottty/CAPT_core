#!/bin/zsh
set -euo pipefail

# Never let caller Python import overrides shadow the freshly built CAPT runtime.
unset PYTHONPATH PYTHONHOME

SCRIPT_DIR="${0:A:h}"
REPO_ROOT="${SCRIPT_DIR:h:h:h:h}"
STATE_DIR="${CAPT_STATE_DIR:-$HOME/.capt}"
STAGING_ROOT="$STATE_DIR/runtime-release-candidates"
mkdir -p "$STAGING_ROOT"
RELEASE_DIR="$(mktemp -d "$STAGING_ROOT/runtime.XXXXXXXX")"
VENV="$RELEASE_DIR/venv"
READY=0
BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/capt-native-runtime.XXXXXX")"
cleanup_stage() {
  rm -rf -- "$BUILD_DIR"
  if [[ "$READY" != "1" ]]; then rm -rf -- "$RELEASE_DIR"; fi
}
trap cleanup_stage EXIT

mkdir -p "$STATE_DIR"
cd "$REPO_ROOT"
SOURCE_HEAD="$(git rev-parse HEAD)"
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "Refusing to mark uncommitted runtime source with a committed SHA" >&2
  exit 3
fi
python3 -m build --wheel --outdir "$BUILD_DIR"
WHEEL="$(find "$BUILD_DIR" -maxdepth 1 -name 'capt_solo-*.whl' -print -quit)"
[[ -n "$WHEEL" ]] || { echo "CAPT wheel build failed" >&2; exit 1; }

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet "$WHEEL"
WHEEL_SHA="$(shasum -a 256 "$WHEEL" | awk '{print $1}')"
printf '%s\n' "$SOURCE_HEAD" > "$VENV/CAPT_SOURCE_HEAD"
printf '%s\n' "$WHEEL_SHA" > "$VENV/CAPT_WHEEL_SHA256"

"$VENV/bin/capt" --help >/dev/null
READY=1
printf 'CAPT candidate runtime STAGED (not active)\n'
printf '  source: %s\n' "$SOURCE_HEAD"
printf '  wheel:  %s\n' "$WHEEL_SHA"
printf '  cli:    %s\n' "$VENV/bin/capt"

printf '  candidate: %s\n' "$RELEASE_DIR"
