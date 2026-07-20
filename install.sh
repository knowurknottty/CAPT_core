#!/usr/bin/env bash
# CAPT Solo v0.4.1 installer
set -euo pipefail

CAPT_SOLO_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_PREFIX="${CAPT_SOLO_HOME:-$HOME/.capt-solo}"
HERMES_CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.hermes}"
PLUGIN_TARGET="$HERMES_CONFIG_DIR/plugins/capt-solo"
SKILLS_TARGET="$HERMES_CONFIG_DIR/skills"
ATE_REPO="https://github.com/knowurknottty/anti-token-extraction.git"
ATE_COMMIT="b68adac7311b2315d992592b479e6761aa9dc856"

export CAPT_SOLO_HOME="$INSTALL_PREFIX"
export CAPT_SOLO_SRC

echo "== CAPT Solo v0.4.1 installer =="
echo "Source : $CAPT_SOLO_SRC"
echo "Home   : $INSTALL_PREFIX"
echo "Hermes : $HERMES_CONFIG_DIR"

if [ ! -d "$HERMES_CONFIG_DIR" ]; then
  echo "[WARN] Hermes config dir not found at $HERMES_CONFIG_DIR"
else
  echo "[OK] Hermes config dir detected: $HERMES_CONFIG_DIR"
fi

mkdir -p "$INSTALL_PREFIX/data" "$INSTALL_PREFIX/backups"
chmod 700 "$INSTALL_PREFIX" "$INSTALL_PREFIX/data" "$INSTALL_PREFIX/backups" 2>/dev/null || true

python3 - <<'PY'
import os
import sys
sys.path.insert(0, os.environ["CAPT_SOLO_SRC"])
from capt_solo.core.config import ensure_dirs
from capt_solo.api import MemoryEngine, CTPRuntime, health
ensure_dirs()
eng = MemoryEngine()
eng.integrity_check()
eng.close()
ctp = CTPRuntime()
ctp.integrity_check()
ctp.close()
print("[OK] Runtime initialized")
print("[OK] Health:", health()["status"])
PY

# Anti-Token-Extraction requires Python 3.10+. On older CAPT-compatible Python,
# the capability remains absent and independently degraded.
if python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  echo "[INFO] Installing pinned Anti-Token-Extraction runtime"
  python3 -m pip install --disable-pip-version-check --no-input \
    "git+$ATE_REPO@$ATE_COMMIT"
  python3 - <<'PY'
import os
import sys
sys.path.insert(0, os.environ["CAPT_SOLO_SRC"])
from capt_solo.components import bootstrap_anti_token_extraction
result = bootstrap_anti_token_extraction()
if not result.get("healthy"):
    raise SystemExit(f"pinned anti-token-extraction verification failed: {result}")
print(f"[OK] Anti-Token-Extraction verified at {result['installed_commit']}")
PY
else
  echo "[WARN] Python <3.10: Anti-Token-Extraction remains unavailable; CAPT core continues"
fi

if [ -d "$HERMES_CONFIG_DIR" ]; then
  mkdir -p "$PLUGIN_TARGET"
  cp -R "$CAPT_SOLO_SRC/capt_solo" "$PLUGIN_TARGET/"
  cp "$CAPT_SOLO_SRC/capt_solo/plugin/plugin.json" "$PLUGIN_TARGET/plugin.json"
  echo "[OK] Plugin installed to $PLUGIN_TARGET"
fi

if [ -d "$HERMES_CONFIG_DIR" ]; then
  mkdir -p "$SKILLS_TARGET"
  for d in "$CAPT_SOLO_SRC"/capt_solo/skills/*/; do
    name="$(basename "$d")"
    mkdir -p "$SKILLS_TARGET/$name"
    cp "$d"SKILL.md "$SKILLS_TARGET/$name/SKILL.md"
    echo "[OK] Skill installed: $name"
  done
fi

echo
echo "Install complete. Run './verify.sh' to validate the installation."
echo "Uninstall with './uninstall.sh'."
