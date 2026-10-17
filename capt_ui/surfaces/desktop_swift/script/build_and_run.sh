#!/bin/zsh
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(git -C "$ROOT" rev-parse --show-toplevel)"
APP_NAME="CAPT"
EXECUTABLE="CAPTNativeMac"
DIST_BUNDLE="$ROOT/dist/$APP_NAME.app"
INSTALLED_BUNDLE="$HOME/Applications/$APP_NAME.app"
BINARY="$ROOT/.build/debug/$EXECUTABLE"
STATE_DIR="${CAPT_STATE_DIR:-$HOME/.capt}"
RUNTIME_VENV="$STATE_DIR/runtime-venv"
RUNTIME_CLI="$RUNTIME_VENV/bin/capt"
RUNTIME_PYTHON="$RUNTIME_VENV/bin/python"
RUNTIME_HEAD_FILE="$RUNTIME_VENV/CAPT_SOURCE_HEAD"
BACKUP_DIR="${CAPT_APP_BACKUP_DIR:-$STATE_DIR/app-release-backups}"
VERIFY=0

for arg in "$@"; do
  case "$arg" in
    --verify) VERIFY=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

# Build only a committed, reproducible native source tree. Other unrelated
# untracked mission files outside this package are never touched.
if [[ -n "$(git -C "$ROOT" status --porcelain -- .)" ]]; then
  echo "CAPT native package has uncommitted files; refusing a misleading source marker." >&2
  exit 3
fi
SOURCE_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD)"
print -r -- "$SOURCE_HEAD" | grep -Eq '^[0-9a-f]{40}

INSTALLED_HEAD=""
if [[ -r "$RUNTIME_HEAD_FILE" ]]; then
  INSTALLED_HEAD="$(<"$RUNTIME_HEAD_FILE")"
fi
# Preserve the existing private runtime bootstrap contract.
if [[ ! -x "$RUNTIME_CLI" || "$INSTALLED_HEAD" != "$SOURCE_HEAD" ]]; then
  if [[ -x "$RUNTIME_CLI" ]]; then
    echo "CAPT private runtime is stale; refreshing $INSTALLED_HEAD -> $SOURCE_HEAD"
  else
    echo "CAPT private runtime is missing; installing $SOURCE_HEAD"
  fi
  CAPT_STATE_DIR="$STATE_DIR" "$ROOT/script/install_local_runtime.sh"
fi
[[ -x "$RUNTIME_PYTHON" ]] || { echo "CAPT runtime Python is unavailable" >&2; exit 4; }

CAPT_PACKAGE_VERSION="$("$RUNTIME_CLI" --version | awk '{print $2}')"
if ! print -r -- "$CAPT_PACKAGE_VERSION" | grep -Eq '^[0-9]+(\.[0-9]+){1,3}$'; then
  echo "Invalid CAPT package version: $CAPT_PACKAGE_VERSION" >&2
  exit 4
fi

cd "$ROOT"
swift build --product "$EXECUTABLE"

# Build and sign into a private temporary directory. Never overwrite
# either deployed app before the new complete bundle verifies.
STAGE_DIR="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/capt-app-build.XXXXXXXX")"
trap '/bin/rm -rf -- "$STAGE_DIR"' EXIT
STAGED_BUNDLE="$STAGE_DIR/$APP_NAME.app"
mkdir -p "$STAGED_BUNDLE/Contents/MacOS"
cp "$BINARY" "$STAGED_BUNDLE/Contents/MacOS/$EXECUTABLE"
chmod +x "$STAGED_BUNDLE/Contents/MacOS/$EXECUTABLE"
cat > "$STAGED_BUNDLE/Contents/Info.plist" <<PLIST
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
  <key>CFBundleShortVersionString</key><string>${CAPT_PACKAGE_VERSION}</string>
  <key>CAPTSourceCommit</key><string>${SOURCE_HEAD}</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSPrincipalClass</key><string>NSApplication</string>
</dict>
</plist>
PLIST

SIGN_IDENTITY="${CAPT_CODESIGN_IDENTITY:-}"
if [[ -z "$SIGN_IDENTITY" ]]; then
  SIGN_IDENTITY="$(/usr/bin/security find-identity -v -p codesigning 2>/dev/null \
    | sed -n 's/.*"\(Apple Development:[^"]*\)".*/\1/p' | head -1)"
fi
if [[ -n "$SIGN_IDENTITY" ]]; then
  /usr/bin/codesign --force --sign "$SIGN_IDENTITY" --identifier com.inversionlabs.capt "$STAGED_BUNDLE"
elif [[ "${CAPT_ALLOW_ADHOC_SIGNING:-0}" == "1" ]]; then
  /usr/bin/codesign --force --sign - --identifier com.inversionlabs.capt "$STAGED_BUNDLE"
else
  echo "Stable Apple Development identity required. Refusing ad-hoc replacement of TIA-targeted CAPT.app." >&2
  exit 5
fi
/usr/bin/codesign --verify --strict --verbose=2 "$STAGED_BUNDLE"

# Freeze source identity across build and any concurrent merge.
if [[ "$(git -C "$REPO_ROOT" rev-parse HEAD)" != "$SOURCE_HEAD" ]] ||
   [[ -n "$(git -C "$ROOT" status --porcelain -- .)" ]]; then
  echo "CAPT source changed during build; refusing publication." >&2
  exit 6
fi

# Publish identical signed bytes to both paths; launch ~/Applications only.
"$RUNTIME_PYTHON" "$ROOT/script/install_signed_bundle.py" \
  --signed "$STAGED_BUNDLE" \
  --dist "$DIST_BUNDLE" \
  --installed "$INSTALLED_BUNDLE" \
  --backup-root "$BACKUP_DIR" \
  --source-commit "$SOURCE_HEAD"

if (( VERIFY )); then
  echo "CAPT.app build/install/launch and canonical-bundle parity verified."
fi
 || { echo "Invalid CAPT source SHA" >&2; exit 3; }

INSTALLED_HEAD=""
if [[ -r "$RUNTIME_HEAD_FILE" ]]; then
  INSTALLED_HEAD="$(<"$RUNTIME_HEAD_FILE")"
fi
# Preserve the existing private runtime bootstrap contract.
if [[ ! -x "$RUNTIME_CLI" || "$INSTALLED_HEAD" != "$SOURCE_HEAD" ]]; then
  if [[ -x "$RUNTIME_CLI" ]]; then
    echo "CAPT private runtime is stale; refreshing $INSTALLED_HEAD -> $SOURCE_HEAD"
  else
    echo "CAPT private runtime is missing; installing $SOURCE_HEAD"
  fi
  CAPT_STATE_DIR="$STATE_DIR" "$ROOT/script/install_local_runtime.sh"
fi
[[ -x "$RUNTIME_PYTHON" ]] || { echo "CAPT runtime Python is unavailable" >&2; exit 4; }

CAPT_PACKAGE_VERSION="$("$RUNTIME_CLI" --version | awk '{print $2}')"
if ! print -r -- "$CAPT_PACKAGE_VERSION" | grep -Eq '^[0-9]+(\.[0-9]+){1,3}$'; then
  echo "Invalid CAPT package version: $CAPT_PACKAGE_VERSION" >&2
  exit 4
fi

cd "$ROOT"
swift build --product "$EXECUTABLE"

# Build and sign into a private temporary directory. Never overwrite
# either deployed app before the new complete bundle verifies.
STAGE_DIR="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/capt-app-build.XXXXXXXX")"
trap '/bin/rm -rf -- "$STAGE_DIR"' EXIT
STAGED_BUNDLE="$STAGE_DIR/$APP_NAME.app"
mkdir -p "$STAGED_BUNDLE/Contents/MacOS"
cp "$BINARY" "$STAGED_BUNDLE/Contents/MacOS/$EXECUTABLE"
chmod +x "$STAGED_BUNDLE/Contents/MacOS/$EXECUTABLE"
cat > "$STAGED_BUNDLE/Contents/Info.plist" <<PLIST
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
  <key>CFBundleShortVersionString</key><string>${CAPT_PACKAGE_VERSION}</string>
  <key>CAPTSourceCommit</key><string>${SOURCE_HEAD}</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSPrincipalClass</key><string>NSApplication</string>
</dict>
</plist>
PLIST

SIGN_IDENTITY="${CAPT_CODESIGN_IDENTITY:-}"
if [[ -z "$SIGN_IDENTITY" ]]; then
  SIGN_IDENTITY="$(/usr/bin/security find-identity -v -p codesigning 2>/dev/null \
    | sed -n 's/.*"\(Apple Development:[^"]*\)".*/\1/p' | head -1)"
fi
if [[ -n "$SIGN_IDENTITY" ]]; then
  /usr/bin/codesign --force --sign "$SIGN_IDENTITY" --identifier com.inversionlabs.capt "$STAGED_BUNDLE"
elif [[ "${CAPT_ALLOW_ADHOC_SIGNING:-0}" == "1" ]]; then
  /usr/bin/codesign --force --sign - --identifier com.inversionlabs.capt "$STAGED_BUNDLE"
else
  echo "Stable Apple Development identity required. Refusing ad-hoc replacement of TIA-targeted CAPT.app." >&2
  exit 5
fi
/usr/bin/codesign --verify --strict --verbose=2 "$STAGED_BUNDLE"

# Freeze source identity across build and any concurrent merge.
if [[ "$(git -C "$REPO_ROOT" rev-parse HEAD)" != "$SOURCE_HEAD" ]] ||
   [[ -n "$(git -C "$ROOT" status --porcelain -- .)" ]]; then
  echo "CAPT source changed during build; refusing publication." >&2
  exit 6
fi

# Publish identical signed bytes to both paths; launch ~/Applications only.
"$RUNTIME_PYTHON" "$ROOT/script/install_signed_bundle.py" \
  --signed "$STAGED_BUNDLE" \
  --dist "$DIST_BUNDLE" \
  --installed "$INSTALLED_BUNDLE" \
  --backup-root "$BACKUP_DIR" \
  --source-commit "$SOURCE_HEAD"

if (( VERIFY )); then
  echo "CAPT.app build/install/launch and canonical-bundle parity verified."
fi
