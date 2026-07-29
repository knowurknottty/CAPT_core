#!/usr/bin/env bash
# CAPT Solo v0.5.0 — uninstaller
# Removes the plugin and skills from Hermes. Leaves data unless --purge given.
set -euo pipefail

HERMES_CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.hermes}"
PLUGIN_TARGET="$HERMES_CONFIG_DIR/plugins/capt-solo"
SKILLS_TARGET="$HERMES_CONFIG_DIR/skills"
PURGE="${1:-}"

echo "== CAPT Solo v0.5.0 uninstaller =="

safe_remove_dir() {
  local target="$1"
  local resolved_target resolved_home
  resolved_target="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$target")"
  resolved_home="$(python3 -c 'import os; print(os.path.realpath(os.path.expanduser("~")))')"
  case "$resolved_target" in
    ""|"/"|"$resolved_home")
      echo "[ERROR] Refusing unsafe removal target: $resolved_target" >&2
      return 1
      ;;
  esac
  rm -rf -- "$resolved_target"
}

if [ -d "$PLUGIN_TARGET" ]; then
  safe_remove_dir "$PLUGIN_TARGET"
  echo "[OK] Removed plugin: $PLUGIN_TARGET"
else
  echo "[SKIP] Plugin not installed."
fi

for name in capt-bootstrap capt-debug capt-arch-decision capt-memory-review capt-knowledge-capture capt-transaction capt-session-recap capt-recovery; do
  if [ -d "$SKILLS_TARGET/$name" ]; then
    safe_remove_dir "$SKILLS_TARGET/$name"
    echo "[OK] Removed skill: $name"
  fi
done

if [ "$PURGE" = "--purge" ]; then
  INSTALL_PREFIX="${CAPT_SOLO_HOME:-$HOME/.capt-solo}"
  if [ -d "$INSTALL_PREFIX" ]; then
    safe_remove_dir "$INSTALL_PREFIX"
    echo "[OK] Purged local runtime data: $INSTALL_PREFIX"
  fi
else
  echo "[INFO] Local runtime data kept at ${CAPT_SOLO_HOME:-$HOME/.capt-solo} (use --purge to remove)."
fi

echo "Uninstall complete."
