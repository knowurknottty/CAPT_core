#!/bin/zsh
set -euo pipefail
umask 077

# Build and validate versioned runtime before any activation.
# Never replace an existing live runtime from this staging command.
unset PYTHONPATH PYTHONHOME
SCRIPT_DIR="${0:A:h}"
REPO_ROOT="${SCRIPT_DIR:h:h:h:h}"
STATE_DIR="${CAPT_STATE_DIR:-$HOME/.capt}"
ACTIVE="$STATE_DIR/runtime-venv"
RELEASES="$STATE_DIR/runtime-releases"
MODE="${1:-}"
[[ -z "$MODE" || "$MODE" == "--stage-only" ]] || { echo "usage: $0 [--stage-only]" >&2; exit 2; }
[[ -z "$(git -C "$REPO_ROOT" status --porcelain --untracked-files=no)" ]] || {
 echo "CAPT_RELEASE_SOURCE_DIRTY" >&2; exit 3
}
SOURCE_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD)"
print -r -- "$SOURCE_HEAD" | grep -Eq '^[0-9a-f]{40}$' || { echo "CAPT_RELEASE_INVALID_SOURCE_HEAD" >&2; exit 3; }
mkdir -p "$RELEASES"
BUILD_DIR="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/capt-runtime-wheel.XXXXXXXX")"
STAGED=""
COMPLETE=0
cleanup() {
 /bin/rm -rf -- "$BUILD_DIR"
 if [[ "$COMPLETE" != 1 && -n "$STAGED" && -d "$STAGED" ]]; then
   /bin/rm -rf -- "$STAGED"
 fi
}
trap cleanup EXIT

cd "$REPO_ROOT"
python3 -m build --wheel --outdir "$BUILD_DIR"
WHEEL="$(find "$BUILD_DIR" -maxdepth 1 -name 'capt_solo-*.whl' -print -quit)"
[[ -n "$WHEEL" ]] || { echo "CAPT_RELEASE_WHEEL_MISSING" >&2; exit 4; }
WHEEL_SHA="$(shasum -a 256 "$WHEEL" | awk '{print $1}')"
STAGED="$RELEASES/$SOURCE_HEAD-$WHEEL_SHA"
[[ ! -e "$STAGED" && ! -L "$STAGED" ]] || { echo "CAPT_RELEASE_CANDIDATE_EXISTS=$STAGED" >&2; exit 5; }
python3 -m venv "$STAGED"
"$STAGED/bin/python" -m pip install --quiet "$WHEEL"
printf '%s\n' "$SOURCE_HEAD" > "$STAGED/CAPT_SOURCE_HEAD"
printf '%s\n' "$WHEEL_SHA" > "$STAGED/CAPT_WHEEL_SHA256"
"$STAGED/bin/capt" --help >/dev/null

# Isolated imports must resolve to the wheel, never the mutable repository.
(cd "$STATE_DIR" && "$STAGED/bin/python" -I -c '
import hashlib,pathlib,sys
repo=pathlib.Path(sys.argv[1]); installed=pathlib.Path(sys.argv[2])
for rel in ("capt_runtime/cohort_contract.py","capt_runtime/drivers/provider.py"):
 source=repo/rel
 sites=list((installed/"lib").glob("python*/site-packages"))
 if len(sites)!=1 or not (sites[0]/rel).is_file():
  raise SystemExit("CAPT_RELEASE_INSTALLED_MODULE_MISSING:"+rel)
 digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 if digest(source)!=digest(sites[0]/rel):
  raise SystemExit("CAPT_RELEASE_SOURCE_INSTALLED_MISMATCH:"+rel)
' "$REPO_ROOT" "$STAGED")
[[ "$(git -C "$REPO_ROOT" rev-parse HEAD)" == "$SOURCE_HEAD" ]] || {
 echo "CAPT_RELEASE_SOURCE_MOVED_DURING_BUILD" >&2; exit 6
}
COMPLETE=1
print -r -- "CAPT_RELEASE_STAGED=$STAGED"
print -r -- "CAPT_RELEASE_SOURCE_HEAD=$SOURCE_HEAD"
print -r -- "CAPT_RELEASE_WHEEL_SHA256=$WHEEL_SHA"
if [[ "$MODE" == "--stage-only" ]]; then exit 0; fi
# Only first-time provisioning can publish here. Quiescent upgrades require
# a separate authenticated transaction with a durable rollback receipt.
if [[ -e "$ACTIVE" || -L "$ACTIVE" ]]; then
 echo "CAPT_RELEASE_QUIESCENCE_REQUIRED: active runtime preserved" >&2; exit 7
fi
/bin/ln -s "$STAGED" "$ACTIVE"
[[ -x "$ACTIVE/bin/capt" ]] || { echo "CAPT_RELEASE_FIRST_INSTALL_VERIFICATION_FAILED" >&2; exit 8; }
print -r -- "CAPT_RELEASE_FIRST_INSTALL=$ACTIVE"
