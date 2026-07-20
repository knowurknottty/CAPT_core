#!/usr/bin/env bash
# CAPT Solo v0.1 — installer
# One-command install: detect Hermes, install plugin + skills, init runtime.
set -euo pipefail

CAPT_SOLO_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_PREFIX="${CAPT_SOLO_HOME:-$HOME/.capt-solo}"
HERMES_CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.hermes}"
PLUGIN_TARGET="$HERMES_CONFIG_DIR/plugins/capt-solo"
SKILLS_TARGET="$HERMES_CONFIG_DIR/skills"

echo "== CAPT Solo v0.1 installer =="
echo "Source : $CAPT_SOLO_SRC"
echo "Home   : $INSTALL_PREFIX"
echo "Hermes : $HERMES_CONFIG_DIR"

# 1. Detect Hermes
if [ ! -d "$HERMES_CONFIG_DIR" ]; then
  echo "[WARN] Hermes config dir not found at $HERMES_CONFIG_DIR"
  echo "[WARN] Plugin/skills will be staged but Hermes may not be installed."
else
  echo "[OK] Hermes config dir detected: $HERMES_CONFIG_DIR"
fi

# 2. Initialize local runtime
export CAPT_SOLO_HOME="$INSTALL_PREFIX"
mkdir -p "$INSTALL_PREFIX/data" "$INSTALL_PREFIX/backups"
python3 - <<'PY'
import sys
sys.path.insert(0, "$CAPT_SOLO_SRC")
from capt_solo.core.config import ensure_dirs
from capt_solo.api import MemoryEngine, CTPRuntime, health
ensure_dirs()
# Touch the stores so a fresh install is immediately verifiable.
eng = MemoryEngine()
eng.integrity_check()
eng.close()
ctp = CTPRuntime()
ctp.integrity_check()
ctp.close()
print("[OK] Runtime initialized at $INSTALL_PREFIX (memory.db + ctp journal present)")
print("[OK] Health:", health()["status"])
PY

# 3. Install plugin
if [ -d "$HERMES_CONFIG_DIR" ]; then
  mkdir -p "$PLUGIN_TARGET"
  cp -R "$CAPT_SOLO_SRC/capt_solo" "$PLUGIN_TARGET/"
  cp "$CAPT_SOLO_SRC/capt_solo/plugin/plugin.json" "$PLUGIN_TARGET/plugin.json"
  echo "[OK] Plugin installed to $PLUGIN_TARGET"
fi

# 4. Install skills
if [ -d "$HERMES_CONFIG_DIR" ]; then
  mkdir -p "$SKILLS_TARGET"
  for d in "$CAPT_SOLO_SRC"/capt_solo/skills/*/; do
    name="$(basename "$d")"
    mkdir -p "$SKILLS_TARGET/$name"
    cp "$d"SKILL.md "$SKILLS_TARGET/$name/SKILL.md"
    echo "[OK] Skill installed: $name"
  done
fi

echo ""
echo "Install complete. Run './verify.sh' to validate the installation."
echo "Uninstall with './uninstall.sh'."
