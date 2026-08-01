#!/usr/bin/env bash
# capt-doctor.sh — CAPT Core runtime diagnosis.
#
# 18 checks. Each reports PASS | WARN | FAIL | NOT_PROVEN.
# "Available" is never reported as "operational".
# Orchestrates the canonical capt CLI only. Constructs no runtime object.
#
# Usage: capt-doctor.sh [workspace] [mission-id]
# Exit:  0 = no FAIL, 1 = at least one FAIL, 2 = bad invocation
set -uo pipefail

WS="${1:-$PWD}"
MISSION="${2:-}"
[ -d "$WS" ] || { echo "FAIL  invocation            workspace not found: $WS"; exit 2; }
WS="$(cd "$WS" && pwd)"

FAILS=0
row() { # verdict, check, detail
  printf '%-11s %-26s %s\n' "$1" "$2" "$3"
  [ "${1%%:*}" = "FAIL" ] && FAILS=$((FAILS+1))
  return 0
}

echo "capt-doctor  workspace=$WS  mission=${MISSION:-<none supplied>}"
echo "-------------------------------------------------------------------------------"

# 0. environment activation
if [ -x "$WS/.venv/bin/capt" ]; then
  # shellcheck disable=SC1091
  . "$WS/.venv/bin/activate"
fi

# 1. python
PY_BIN="$(command -v python || command -v python3 || echo "")"
PY_VER="$($PY_BIN --version 2>&1 || echo unknown)"
case "$PY_VER" in
  "Python 3.1"[0-9]*|"Python 3.9"*) : ;;
esac
if [ -z "$PY_BIN" ]; then row FAIL "python" "no interpreter"
elif [ "${PY_VER#Python 3.9}" != "$PY_VER" ]; then row FAIL "python" "$PY_VER ($PY_BIN) — system python, capt-solo needs >=3.10 [WRONG_PYTHON]"
else row PASS "python" "$PY_VER ($PY_BIN)"; fi

# 2. virtualenv
PY_PREFIX="$($PY_BIN -c 'import sys;print(sys.prefix)' 2>/dev/null || echo "")"
if [ -d "$WS/.venv" ] && [ "$PY_PREFIX" != "$WS/.venv" ]; then
  row FAIL "virtualenv" "sys.prefix=$PY_PREFIX but $WS/.venv exists [WRONG_VENV]"
elif [ -n "$PY_PREFIX" ]; then row PASS "virtualenv" "$PY_PREFIX"
else row NOT_PROVEN "virtualenv" "could not read sys.prefix"; fi

# 3. capt executable
CAPT_BIN="$(command -v capt || echo "")"
if [ -z "$CAPT_BIN" ]; then row FAIL "capt.executable" "not on PATH [CAPT_NOT_FOUND]"
else row PASS "capt.executable" "$CAPT_BIN"; fi

# 4. installed package source
PKG_FILE="$($PY_BIN -c 'import capt_solo;print(capt_solo.__file__)' 2>/dev/null || echo "")"
PKG_VER="$($PY_BIN -c 'import capt_solo;print(getattr(capt_solo,"__version__","unknown"))' 2>/dev/null || echo "")"
EDITABLE="$(pip show capt-solo 2>/dev/null | awk -F': ' '/^Editable project location:/{print $2}')"
if [ -z "$PKG_FILE" ]; then row FAIL "package.source" "capt_solo not importable"
else row PASS "package.source" "$PKG_FILE v$PKG_VER${EDITABLE:+ (editable: $EDITABLE)}"; fi

# 5. checkout identity
SRC_ROOT="${EDITABLE:-${CAPT_SOLO_REPO:-$WS}}"
if [ -z "$PKG_FILE" ]; then row NOT_PROVEN "checkout.identity" "package not importable"
else
  case "$PKG_FILE" in
    "$SRC_ROOT"/*) row PASS "checkout.identity" "import resolves under $SRC_ROOT" ;;
    *)             row FAIL "checkout.identity" "import $PKG_FILE outside $SRC_ROOT [WRONG_CHECKOUT]" ;;
  esac
fi
WT="$(git -C "$WS" worktree list 2>/dev/null | wc -l | tr -d ' ')"
[ "${WT:-0}" -gt 1 ] && row WARN "checkout.worktrees" "$WT worktrees — verify which venv is active"

# 6. capt doctor (runtime self-inspection)
DOCTOR_OUT="$(capt doctor 2>&1)"; DOCTOR_RC=$?
if [ $DOCTOR_RC -ne 0 ]; then row FAIL "runtime.doctor" "capt doctor exit=$DOCTOR_RC"
elif printf '%s' "$DOCTOR_OUT" | grep -q '^ok: True'; then
  row PASS "runtime.doctor" "ok=True; $(printf '%s' "$DOCTOR_OUT" | grep -c 'status: pass') checks pass"
else row FAIL "runtime.doctor" "ok not True"; fi

# 7. CAPT home + stores
CAPT_HOME_R="${CAPT_SOLO_HOME:-$HOME/.capt-solo}"
if [ -d "$CAPT_HOME_R" ]; then row PASS "capt.home" "$CAPT_HOME_R${CAPT_SOLO_HOME:+ (CAPT_SOLO_HOME set)}"
else row WARN "capt.home" "$CAPT_HOME_R does not exist yet"; fi

# 8. mission store
CKPT_DIR="$WS/.capt/checkpoints"
if [ ! -d "$CKPT_DIR" ]; then row FAIL "mission.store" "$CKPT_DIR absent [MISSION_MISSING]"
else
  N="$(find "$CKPT_DIR" -maxdepth 1 -name '*.json' | wc -l | tr -d ' ')"
  [ "$N" -eq 0 ] && row FAIL "mission.store" "no checkpoints in $CKPT_DIR [MISSION_MISSING]" \
                 || row PASS "mission.store" "$N checkpoint(s) in $CKPT_DIR"
fi

# 9. legacy checkpoint schema (the discovery-crash cause)
if [ -d "$CKPT_DIR" ]; then
  LEGACY="$($PY_BIN - "$CKPT_DIR" <<'PY' 2>/dev/null || echo ""
import json,sys,glob,os
bad=[]
for f in sorted(glob.glob(os.path.join(sys.argv[1],"*.json"))):
    try: d=json.load(open(f))
    except Exception: bad.append(os.path.basename(f)[:-5]+"(unparseable)"); continue
    if not isinstance(d,dict): continue
    miss=[k for k in ("project_id","objective") if k not in d]
    if miss: bad.append(os.path.basename(f)[:-5])
print(",".join(bad))
PY
)"
  if [ -n "$LEGACY" ]; then row WARN "mission.schema" "legacy records: $LEGACY — auto-discovery will raise TypeError [LEGACY_CHECKPOINT_SCHEMA]; always pass --mission"
  else row PASS "mission.schema" "all checkpoints carry project_id+objective"; fi
else row NOT_PROVEN "mission.schema" "no store"; fi

# 10. checkpoint digest integrity
if [ -d "$CKPT_DIR" ]; then
  ZERO="$(grep -l '"event_digest": "sha256:0\{64\}"' "$CKPT_DIR"/*.json 2>/dev/null | xargs -n1 basename 2>/dev/null | sed 's/\.json$//' | tr '\n' ',' )"
  if [ -n "$ZERO" ]; then row WARN "checkpoint.digest" "placeholder digest in: ${ZERO%,} — will BLOCK with CHECKPOINT_INTEGRITY"
  else row PASS "checkpoint.digest" "no placeholder digests"; fi
else row NOT_PROVEN "checkpoint.digest" "no store"; fi

# 11. memory store readable
MEM="$(capt --json memory list 2>&1)"
if printf '%s' "$MEM" | head -c 1 | grep -q '\['; then
  MCOUNT="$(printf '%s' "$MEM" | $PY_BIN -c 'import json,sys;print(len(json.load(sys.stdin)))' 2>/dev/null || echo "?")"
  [ "$MCOUNT" = "0" ] && row WARN "memory.store" "readable but empty [EMPTY_MEMORY_STORE]" \
                      || row PASS "memory.store" "$MCOUNT record(s) readable"
else row FAIL "memory.store" "memory list did not return JSON"; fi

# 12. session store
SESS="$(capt --json session list 2>&1)"
if printf '%s' "$SESS" | head -c 1 | grep -q '\['; then
  SCOUNT="$(printf '%s' "$SESS" | $PY_BIN -c 'import json,sys;print(len(json.load(sys.stdin)))' 2>/dev/null || echo "?")"
  row PASS "session.store" "$SCOUNT session(s)"
else row FAIL "session.store" "session list did not return JSON"; fi

# 13. single composition root
AGD="$(capt --json agent doctor --workspace "$WS" 2>&1)"
if printf '%s' "$AGD" | grep -q '"single_composition_root": true'; then
  row PASS "composition.root" "single_composition_root=true"
elif printf '%s' "$AGD" | grep -q '"single_composition_root"'; then
  row FAIL "composition.root" "single_composition_root=false — a second root exists"
else row FAIL "composition.root" "agent doctor did not report; $(printf '%s' "$AGD" | head -1)"; fi

# 14. Hermes plugin discovery + parity
PI="$HOME/.hermes/plugins/capt-solo/__init__.py"; PS="$SRC_ROOT/capt_solo/plugin/__init__.py"
if [ ! -f "$PI" ]; then row WARN "plugin.installed" "not installed at $PI [PLUGIN_NOT_LOADED]"
elif [ ! -f "$HOME/.hermes/plugins/capt-solo/plugin.yaml" ]; then
  row WARN "plugin.installed" "plugin.yaml missing — legacy plugin.json shape is not loaded by Hermes v0.19"
elif [ -f "$PS" ] && [ "$(shasum -a 256 "$PI" | cut -d' ' -f1)" = "$(shasum -a 256 "$PS" | cut -d' ' -f1)" ]; then
  row PASS "plugin.installed" "installed copy matches source (sha256)"
else row WARN "plugin.installed" "installed copy differs from source [STALE_PLUGIN]"; fi

# 15. ContextPack + MemoryUseGate capability (requires a mission)
if [ -z "$MISSION" ]; then
  row NOT_PROVEN "contextpack" "no mission supplied — pass a mission id to probe"
  row NOT_PROVEN "memoryusegate" "no mission supplied — pass a mission id to probe"
  row NOT_PROVEN "boot.recovery" "no mission supplied"
else
  BOOT="$(capt --json agent status --workspace "$WS" --mission "$MISSION" 2>&1)"
  DIGEST="$(printf '%s' "$BOOT" | $PY_BIN -c 'import json,sys;print(json.load(sys.stdin).get("contextpack_digest",""))' 2>/dev/null || echo "")"
  GATE="$(printf '%s' "$BOOT"  | $PY_BIN -c 'import json,sys;print(json.load(sys.stdin).get("gate_result",""))'        2>/dev/null || echo "")"
  MODE="$(printf '%s' "$BOOT"  | $PY_BIN -c 'import json,sys;print(json.load(sys.stdin).get("execution_mode",""))'     2>/dev/null || echo "")"
  CODES="$(printf '%s' "$BOOT" | $PY_BIN -c 'import json,sys;print(",".join(json.load(sys.stdin).get("block_codes",[])))' 2>/dev/null || echo "")"
  if printf '%s' "$BOOT" | grep -q 'TypeError: MissionCheckpoint'; then
    row FAIL "boot.recovery" "LEGACY_CHECKPOINT_SCHEMA — discovery loaded a legacy record"
    row NOT_PROVEN "contextpack" "boot crashed"; row NOT_PROVEN "memoryusegate" "boot crashed"
  else
    [ -n "$DIGEST" ] && row PASS "contextpack" "digest ${DIGEST:0:23}…" \
                     || row FAIL "contextpack" "no digest returned [INVALID_CONTEXTPACK]"
    case "$GATE" in
      PASS)     row PASS "memoryusegate" "gate_result=PASS (runtime-enforced pre-provider)" ;;
      DEGRADED) row WARN "memoryusegate" "gate_result=DEGRADED (durable authorization present)" ;;
      BLOCKED)  row FAIL "memoryusegate" "gate_result=BLOCKED codes=$CODES [GATE_FAILED]" ;;
      *)        row NOT_PROVEN "memoryusegate" "gate_result=${GATE:-<none>}" ;;
    esac
    [ "$MODE" = "BLOCKED" ] && row FAIL "boot.recovery" "execution_mode=BLOCKED codes=$CODES" \
                            || row PASS "boot.recovery" "execution_mode=$MODE"
  fi
fi

# 16. CTP journal
CTPD="$CAPT_HOME_R/data/ctp"
if [ -d "$CTPD" ]; then row PASS "ctp.journal" "$CTPD present"
elif [ -d "$CAPT_HOME_R" ]; then row NOT_PROVEN "ctp.journal" "no journal dir under $CAPT_HOME_R yet"
else row NOT_PROVEN "ctp.journal" "CAPT home absent"; fi

# 17. KHSB events
KH="$CAPT_HOME_R/data/khsb/events.jsonl"
if [ "${CAPT_KHSB_ENABLE:-1}" = "0" ]; then row NOT_PROVEN "khsb.events" "CAPT_KHSB_ENABLE=0 — bus deliberately disabled"
elif [ -f "$KH" ]; then row PASS "khsb.events" "$(wc -l < "$KH" | tr -d ' ') event(s) at $KH"
else row WARN "khsb.events" "no event log at $KH [KHSB_NO_EVENTS]"; fi

# 18. ClaimGuard availability (available != operational)
if $PY_BIN -c 'from capt_solo.foundry import ClaimGuard' 2>/dev/null; then
  row NOT_PROVEN "claimguard" "importable from capt_solo.foundry = AVAILABLE_NOT_WIRED; a real verdict is required to prove operation"
else row FAIL "claimguard" "not importable from capt_solo.foundry"; fi

# 19. stale transcript / session risk
if [ -n "${HERMES_SESSION_ID:-}" ]; then
  row WARN "session.risk" "running inside Hermes session ${HERMES_SESSION_ID}; transcript is NOT authoritative — recover from CAPT state"
else row NOT_PROVEN "session.risk" "no HERMES_SESSION_ID"; fi

# 20. Hermes governance enforcement (the honest line)
row NOT_PROVEN "hermes.tool_auth" "plugin pre/post_tool_call are OBSERVATIONAL — tool authorization is NOT runtime-enforced in Hermes"

echo "-------------------------------------------------------------------------------"
echo "FAIL count: $FAILS"
echo "hermes_session_mode: BOOTSTRAP_DEGRADED (default; tool authorization not runtime-enforced)"
[ $FAILS -gt 0 ] && exit 1
exit 0
