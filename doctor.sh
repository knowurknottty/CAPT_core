#!/usr/bin/env bash
# CAPT Solo v0.4.1 — doctor
# Diagnoses the local environment and reports what is and isn't available.
# Emits STRUCTURED checks: check_id | status | severity | summary | evidence | remediation | duration_ms
# Status: pass | warn | fail | skip
set -uo pipefail

CAPT_SOLO_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_PREFIX="${CAPT_SOLO_HOME:-$HOME/.capt-solo}"
HERMES_CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.hermes}"

echo "== CAPT Solo v0.4.1 doctor =="

emit() { # check_id status severity summary evidence remediation
  local cid="$1" st="$2" sev="$3" sum="$4" ev="$5" rem="$6"
  printf '[%-4s] %-28s sev=%-8s %s\n        evidence: %s\n        fix:      %s\n' \
    "$(echo "$st" | tr '[:lower:]' '[:upper:]')" "$cid" "$sev" "$sum" "$ev" "$rem"
}

t0=$(python3 -c 'import time; print(int(time.time()*1000))')

# --- environment ---
if command -v python3 >/dev/null 2>&1; then
  emit "env.python3" "pass" "info" "python3 present" "$(command -v python3)" "install python3"
else
  emit "env.python3" "fail" "critical" "python3 missing" "no python3" "install python3"
fi

if python3 -c 'import sqlite3' 2>/dev/null; then
  emit "env.sqlite3" "pass" "info" "sqlite3 stdlib importable" "sqlite3 present" "use system python"
else
  emit "env.sqlite3" "fail" "critical" "sqlite3 stdlib missing" "import failed" "reinstall python"
fi

if PYTHONPATH="$CAPT_SOLO_SRC" python3 -c 'import capt_solo' 2>/dev/null; then
  emit "env.package" "pass" "info" "CAPT Solo package importable" "capt_solo imports" "check PYTHONPATH"
else
  emit "env.package" "fail" "critical" "CAPT Solo package not importable" "import failed" "check install"
fi

# --- install state ---
if [ -d "$HERMES_CONFIG_DIR" ]; then
  emit "install.hermes_config" "pass" "info" "Hermes config dir exists" "$HERMES_CONFIG_DIR" "n/a"
else
  emit "install.hermes_config" "skip" "low" "Hermes config dir absent" "$HERMES_CONFIG_DIR" "run install.sh"
fi

if [ -f "$HERMES_CONFIG_DIR/plugins/capt-solo/plugin.json" ]; then
  emit "install.plugin" "pass" "info" "Plugin installed" "$HERMES_CONFIG_DIR/plugins/capt-solo/plugin.json" "n/a"
else
  emit "install.plugin" "warn" "low" "Plugin not installed at Hermes path" "missing plugin.json" "run install.sh to copy plugin"
fi

if [ -d "$INSTALL_PREFIX" ]; then
  emit "runtime.home" "pass" "info" "Runtime home exists" "$INSTALL_PREFIX" "n/a"
else
  emit "runtime.home" "warn" "low" "Runtime home not initialized" "$INSTALL_PREFIX" "run CAPT Solo once to init"
fi

if [ -f "$INSTALL_PREFIX/data/memory.db" ]; then
  emit "runtime.memory_db" "pass" "info" "Memory DB exists" "$INSTALL_PREFIX/data/memory.db" "n/a"
else
  emit "runtime.memory_db" "warn" "low" "Memory DB not present" "no memory.db" "init runtime"
fi

if [ -f "$INSTALL_PREFIX/data/ctp/journal.log" ]; then
  emit "runtime.ctp_journal" "pass" "info" "CTP journal exists" "$INSTALL_PREFIX/data/ctp/journal.log" "n/a"
else
  emit "runtime.ctp_journal" "warn" "low" "CTP journal not present" "no journal" "init runtime"
fi

# --- v0.4 checks ---
if PYTHONPATH="$CAPT_SOLO_SRC" python3 -c 'from capt_solo.memory.engine import SCHEMA_VERSION; import sys; sys.exit(0 if SCHEMA_VERSION==4 else 1)' 2>/dev/null; then
  emit "v04.schema_version" "pass" "critical" "Schema version is 4" "SCHEMA_VERSION=4" "run migration"
else
  emit "v04.schema_version" "fail" "critical" "Schema version != 4" "check engine.SCHEMA_VERSION" "run migration"
fi

if [ -d "$INSTALL_PREFIX/backups" ]; then
  emit "v04.backup_dir" "pass" "high" "Migration backup dir present" "$INSTALL_PREFIX/backups" "n/a"
else
  emit "v04.backup_dir" "warn" "medium" "Migration backup dir absent" "no backups/" "init triggers backup"
fi

if PYTHONPATH="$CAPT_SOLO_SRC" python3 -c 'from capt_solo.foundry import DEGRADATION_REASONS; import sys; sys.exit(0 if len(DEGRADATION_REASONS)==12 else 1)' 2>/dev/null; then
  emit "v04.foundry_import" "pass" "high" "Foundry importable + 12 degradation codes" "DEGRADATION_REASONS=12" "n/a"
else
  emit "v04.foundry_import" "fail" "high" "Foundry import or codes failed" "import/count error" "check foundry package"
fi

if PYTHONPATH="$CAPT_SOLO_SRC" python3 "$CAPT_SOLO_SRC/capt_cli.py" --help >/dev/null 2>&1; then
  emit "v04.cli_available" "pass" "medium" "CLI available" "capt_cli.py --help ok" "n/a"
else
  emit "v04.cli_available" "fail" "medium" "CLI not runnable" "cli error" "check capt_cli.py"
fi

if PYTHONPATH="$CAPT_SOLO_SRC" python3 -c "import json,sys; d=json.load(open('$HERMES_CONFIG_DIR/plugins/capt-solo/plugin.json')); sys.exit(0 if len(d.get('tools',[]))==47 else 1)" 2>/dev/null; then
  emit "v04.plugin_tools" "pass" "high" "Plugin tool count is 47" "47 tools" "n/a"
elif [ -f "$CAPT_SOLO_SRC/capt_solo/plugin/plugin.json" ]; then
  CNT=$(python3 -c "import json; print(len(json.load(open('$CAPT_SOLO_SRC/capt_solo/plugin/plugin.json')).get('tools',[])))")
  emit "v04.plugin_tools" "warn" "medium" "Plugin tools counted from source (not installed)" "source tools=$CNT" "run install.sh to deploy plugin"
else
  emit "v04.plugin_tools" "fail" "high" "Plugin tool count != 47" "no plugin.json" "add v0.4.1 tools"
fi

# --- anti-token-extraction component (optional, independently degradable) ---
if PYTHONPATH="$CAPT_SOLO_SRC" CAPT_SOLO_HOME="$(mktemp -d)" python3 -c '
from capt_solo.components import AntiTokenExtractionComponent
import sys
st = AntiTokenExtractionComponent().status()
healthy = st.get("healthy")
pinned = st.get("pinned_verified")
if st.get("state") == "absent":
    print("ABSENT"); sys.exit(0)   # optional: absence is not a failure
if healthy and pinned:
    print("OK"); sys.exit(0)
print("DEGRADED"); sys.exit(2)
' 2>/dev/null; then
  emit "v04.anti_token_extraction" "pass" "high" "Anti-token-extraction component healthy + pinned" "status ok" "n/a"
elif [ $? -eq 0 ]; then
  emit "v04.anti_token_extraction" "warn" "low" "Anti-token-extraction component absent (optional)" "state=absent" "bootstrap to enable; absence does not block CAPT"
else
  emit "v04.anti_token_extraction" "warn" "medium" "Anti-token-extraction degraded (scoped)" "health/pin mismatch" "degrade only this capability; CAPT core unaffected"
fi

if PYTHONPATH="$CAPT_SOLO_SRC" CAPT_SOLO_HOME="$(mktemp -d)" python3 "$CAPT_SOLO_SRC/verify_runtime.py" >/dev/null 2>&1; then
  emit "v04.verify_runtime" "pass" "critical" "verify_runtime passes" "exit 0" "n/a"
else
  emit "v04.verify_runtime" "fail" "critical" "verify_runtime failed" "nonzero exit" "run verify_runtime.py for details"
fi

t1=$(python3 -c 'import time; print(int(time.time()*1000))')
echo ""
echo "Doctor complete in $((t1 - t0))ms."
