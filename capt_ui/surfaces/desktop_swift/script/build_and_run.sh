#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="CAPT"
EXECUTABLE="CAPTNativeMac"
BUNDLE="$ROOT/dist/$APP_NAME.app"
BINARY="$ROOT/.build/debug/$EXECUTABLE"
VERIFY=0

for arg in "$@"; do
  case "$arg" in
    --verify) VERIFY=1 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

BUNDLE_EXECUTABLE="$BUNDLE/Contents/MacOS/$EXECUTABLE"
bundle_pids() {
  ps -axo pid=,command= | while read -r pid command; do
    [[ "$command" == "$BUNDLE_EXECUTABLE" ]] && print -r -- "$pid"
  done
}

while IFS= read -r pid; do
  [[ -z "$pid" ]] && continue
  kill "$pid" 2>/dev/null || true
done < <(bundle_pids)
STATE_DIR="${CAPT_STATE_DIR:-$HOME/.capt}"
RUNTIME_VENV="$STATE_DIR/runtime-venv"
RUNTIME_CLI="$RUNTIME_VENV/bin/capt"
RUNTIME_HEAD_FILE="$RUNTIME_VENV/CAPT_SOURCE_HEAD"
SOURCE_HEAD="$(git -C "$ROOT" rev-parse HEAD)"
INSTALLED_HEAD=""
if [[ -r "$RUNTIME_HEAD_FILE" ]]; then
  INSTALLED_HEAD="$(<"$RUNTIME_HEAD_FILE")"
fi
if [[ ! -x "$RUNTIME_CLI" || "$INSTALLED_HEAD" != "$SOURCE_HEAD" ]]; then
  if [[ -x "$RUNTIME_CLI" ]]; then
    echo "CAPT private runtime is stale; refreshing $INSTALLED_HEAD -> $SOURCE_HEAD"
  else
    echo "CAPT private runtime is missing; installing $SOURCE_HEAD"
  fi
  CAPT_STATE_DIR="$STATE_DIR" "$ROOT/script/install_local_runtime.sh"
fi
cd "$ROOT"
swift build --product "$EXECUTABLE"

rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/Contents/MacOS"
cp "$BINARY" "$BUNDLE/Contents/MacOS/$EXECUTABLE"
chmod +x "$BUNDLE/Contents/MacOS/$EXECUTABLE"
cat > "$BUNDLE/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>CAPTNativeMac</string>
  <key>CFBundleIdentifier</key><string>com.inversionlabs.capt</string>
  <key>CFBundleName</key><string>CAPT</string>
  <key>CFBundleDisplayName</key><string>CAPT</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSPrincipalClass</key><string>NSApplication</string>
</dict>
</plist>
PLIST

SIGN_IDENTITY="${CAPT_CODESIGN_IDENTITY:-}"
if [[ -z "$SIGN_IDENTITY" ]]; then
  SIGN_IDENTITY="$(security find-identity -v -p codesigning 2>/dev/null \
    | sed -n 's/.*"\(Apple Development:[^"]*\)".*/\1/p' | head -1)"
fi
if [[ -n "$SIGN_IDENTITY" ]]; then
  /usr/bin/codesign --force --sign "$SIGN_IDENTITY" --identifier com.inversionlabs.capt "$BUNDLE"
  echo "CAPT.app signed: $SIGN_IDENTITY"
else
  /usr/bin/codesign --force --sign - --identifier com.inversionlabs.capt "$BUNDLE"
  echo "CAPT.app signed ad-hoc (no development identity available)"
fi
/usr/bin/codesign --verify --strict --verbose=2 "$BUNDLE"

/usr/bin/open -n "$BUNDLE"

if (( VERIFY )); then
  for _ in {1..30}; do
    PID="$(bundle_pids | head -1 || true)"
    if [[ -n "$PID" ]]; then
      echo "CAPT.app launched: PID $PID"
      exit 0
    fi
    sleep 0.2
  done
  echo "CAPT.app did not remain running" >&2
  exit 1
fi
