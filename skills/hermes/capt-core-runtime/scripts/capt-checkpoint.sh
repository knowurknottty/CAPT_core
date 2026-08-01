#!/usr/bin/env bash
# capt-checkpoint.sh — write a CAPT mission checkpoint and verify it reloads.
#
# Runs the canonical commands only:
#   capt --json agent checkpoint --workspace WS --mission M
#   capt --json agent status     --workspace WS --mission M   (reload verification)
# Constructs no runtime object.
#
# A checkpoint that does not reload is not a checkpoint.
#
# Usage: capt-checkpoint.sh <workspace> <mission-id> [--receipt-out PATH]
# Exit:  0 written+verified | 4 write or verification failed | 2 bad invocation
set -uo pipefail

WS="${1:-}"; MISSION="${2:-}"; shift 2 2>/dev/null || true
RECEIPT=""
while [ $# -gt 0 ]; do
  case "$1" in --receipt-out) RECEIPT="${2:-}"; shift 2 ;; *) shift ;; esac
done

[ -n "$WS" ] && [ -n "$MISSION" ] || { echo "usage: capt-checkpoint.sh <workspace> <mission-id> [--receipt-out PATH]" >&2; exit 2; }
[ -d "$WS" ] || { echo "workspace not found: $WS" >&2; exit 2; }
WS="$(cd "$WS" && pwd)"

[ -x "$WS/.venv/bin/capt" ] && . "$WS/.venv/bin/activate"
command -v capt >/dev/null || { echo "CAPT_NOT_FOUND" >&2; exit 2; }
PY="$(command -v python || command -v python3)"

jget() { "$PY" -c 'import json,sys
try: d=json.load(sys.stdin)
except Exception: print(""); raise SystemExit
print(d.get(sys.argv[1],"") if not isinstance(d.get(sys.argv[1]),list) else ",".join(map(str,d[sys.argv[1]])))' "$1" 2>/dev/null; }

echo "== 1. write checkpoint =="
CP_JSON="$(capt --json agent checkpoint --workspace "$WS" --mission "$MISSION" 2>&1)"
if printf '%s' "$CP_JSON" | grep -q 'TypeError: MissionCheckpoint'; then
  echo "FAIL LEGACY_CHECKPOINT_SCHEMA" >&2; printf '%s\n' "$CP_JSON" >&2; exit 4
fi
printf '%s\n' "$CP_JSON"

CP_ID="$(printf '%s'  "$CP_JSON" | jget checkpoint_id)"
CP_MODE="$(printf '%s' "$CP_JSON" | jget execution_mode)"
CP_GATE="$(printf '%s' "$CP_JSON" | jget gate_result)"
CP_DIG="$(printf '%s'  "$CP_JSON" | jget contextpack_digest)"

if [ -z "$CP_ID" ]; then echo "FAIL: no checkpoint_id returned" >&2; exit 4; fi
if [ "$CP_MODE" = "BLOCKED" ]; then
  echo "FAIL: checkpoint boot BLOCKED codes=$(printf '%s' "$CP_JSON" | jget block_codes)" >&2; exit 4
fi

echo
echo "== 2. verify it reloads (independent boot) =="
RL_JSON="$(capt --json agent status --workspace "$WS" --mission "$MISSION" 2>&1)"
RL_ID="$(printf '%s'   "$RL_JSON" | jget checkpoint_id)"
RL_MODE="$(printf '%s' "$RL_JSON" | jget execution_mode)"
RL_GATE="$(printf '%s' "$RL_JSON" | jget gate_result)"
RL_DIG="$(printf '%s'  "$RL_JSON" | jget contextpack_digest)"

VERDICT="PASS"
[ "$RL_ID" = "$CP_ID" ]        || { echo "FAIL: checkpoint_id mismatch write=$CP_ID reload=$RL_ID"; VERDICT="FAIL"; }
[ "$RL_MODE" != "BLOCKED" ]    || { echo "FAIL: reload BLOCKED"; VERDICT="FAIL"; }
[ -n "$RL_DIG" ]               || { echo "FAIL: reload produced no ContextPack digest"; VERDICT="FAIL"; }

echo "checkpoint_id:        $CP_ID"
echo "reload checkpoint_id: $RL_ID"
echo "gate  write/reload:   $CP_GATE / $RL_GATE"
echo "mode  write/reload:   $CP_MODE / $RL_MODE"
echo "digest write:         $CP_DIG"
echo "digest reload:        $RL_DIG"
echo "note: digests differ by design — a new ContextPack is built per boot."
echo "verdict: $VERDICT"

if [ -n "$RECEIPT" ]; then
  HEAD_SHA="$(git -C "$WS" rev-parse HEAD 2>/dev/null || echo "")"
  BRANCH="$(git -C "$WS" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
  DIRTY="$([ -z "$(git -C "$WS" status --porcelain 2>/dev/null)" ] && echo false || echo true)"
  cat > "$RECEIPT" <<EOF
{
  "receipt": "capt-checkpoint",
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "workspace": "$WS",
  "mission_id": "$MISSION",
  "checkpoint_id": "$CP_ID",
  "reload_checkpoint_id": "$RL_ID",
  "git": {"branch": "$BRANCH", "head": "$HEAD_SHA", "dirty": $DIRTY},
  "write":  {"execution_mode": "$CP_MODE", "gate_result": "$CP_GATE", "contextpack_digest": "$CP_DIG"},
  "reload": {"execution_mode": "$RL_MODE", "gate_result": "$RL_GATE", "contextpack_digest": "$RL_DIG"},
  "reload_verified": $([ "$VERDICT" = "PASS" ] && echo true || echo false),
  "hermes_session_mode": "BOOTSTRAP_DEGRADED"
}
EOF
  echo "receipt written: $RECEIPT"
fi

[ "$VERDICT" = "PASS" ] && exit 0 || exit 4
