#!/usr/bin/env bash
# CAPT Solo v0.1 — uninstaller
# Removes the plugin and skills from Hermes. Leaves data unless --purge given.
set -euo pipefail

HERMES_CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.hermes}"
PLUGIN_TARGET="$HERMES_CONFIG_DIR/plugins/capt-solo"
SKILLS_TARGET="$HERMES_CONFIG_DIR/skills"
PURGE="${1:-}"

echo "== CAPT Solo v0.1 uninstaller =="

if [ -d "$PLUGIN_TARGET" ]; then
  rm -rf "$PLUGIN_TARGET"
  echo "[OK] Removed plugin: $PLUGIN_TARGET"
else
  echo "[SKIP] Plugin not installed."
fi

for d in "$CAPT_SOLO_SRC"/capt_solo/skills/*/ 2>/dev/null; do :; done
for name in capt-bootstrap capt-debug capt-arch-decision capt-memory-review capt-knowledge-capture capt-transaction capt-session-recap capt-recovery; do
  if [ -d "$SKILLS_TARGET/$name" ]; then
    rm -rf "$SKILLS_TARGET/$name"
    echo "[OK] Removed skill: $name"
  fi
done

if [ "$PURGE" = "--purge" ]; then
  INSTALL_PREFIX="${CAPT_SOLO_HOME:-$HOME/.capt-solo}"
  if [ -d "$INSTALL_PREFIX" ]; then
    rm -rf "$INSTALL_PREFIX"
    echo "[OK] Purged local runtime data: $INSTALL_PREFIX"
  fi
else
  echo "[INFO] Local runtime data kept at ${CAPT_SOLO_HOME:-$HOME/.capt-solo} (use --purge to remove)."
fi

echo "Uninstall complete."
