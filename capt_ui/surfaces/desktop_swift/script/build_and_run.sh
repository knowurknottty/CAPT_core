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

pkill -x "$EXECUTABLE" 2>/dev/null || true
if [[ ! -x "$HOME/.capt/runtime-venv/bin/capt" ]]; then
  "$ROOT/script/install_local_runtime.sh"
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
    if pgrep -x "$EXECUTABLE" >/dev/null; then
      echo "CAPT.app launched: PID $(pgrep -x "$EXECUTABLE" | head -1)"
      exit 0
    fi
    sleep 0.2
  done
  echo "CAPT.app did not remain running" >&2
  exit 1
fi
