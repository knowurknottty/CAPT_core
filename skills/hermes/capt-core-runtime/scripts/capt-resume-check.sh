#!/usr/bin/env bash
# capt-resume-check.sh — fresh-process resume through CAPT, then compare the
# recovered state against repository evidence. Emits a recovery receipt.
#
# Runs the canonical command only:
#   capt --json agent resume --workspace WS --mission M
# Constructs no runtime object. Inherits no transcript.
#
# continuity_verdict: PROVEN requires a fresh process, no transcript
# inheritance, mission/session/checkpoint recovered from CAPT state, gate PASS,
# and recovered state consistent with repository evidence.
#
# Usage: capt-resume-check.sh <workspace> <mission-id> [--receipt-out PATH] [--expect-checkpoint ID]
# Exit:  0 PROVEN | 5 NOT_PROVEN | 4 BLOCKED | 2 bad invocation
set -uo pipefail

WS="${1:-}"; MISSION="${2:-}"; shift 2 2>/dev/null || true
RECEIPT=""; EXPECT_CP=""
while [ $# -gt 0 ]; do
  case "$1" in
    --receipt-out)       RECEIPT="${2:-}"; shift 2 ;;
    --expect-checkpoint) EXPECT_CP="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

[ -n "$WS" ] && [ -n "$MISSION" ] || { echo "usage: capt-resume-check.sh <workspace> <mission-id> [--receipt-out PATH] [--expect-checkpoint ID]" >&2; exit 2; }
[ -d "$WS" ] || { echo "workspace not found: $WS" >&2; exit 2; }
WS="$(cd "$WS" && pwd)"

# ── deterministic interpreter selection (single source of truth) ────────────
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1091
. "$HERE/capt-select-python.sh" "$WS" || { echo "REFUSED: interpreter selection failed" >&2; exit 2; }
PY="$CAPT_PY"

[ -x "$WS/.venv/bin/capt" ] && echo "note: workspace venv present at $WS/.venv (observed, not activated as fallback)" >&2
command -v capt >/dev/null || { echo "CAPT_NOT_FOUND" >&2; exit 2; }

# --mission is REQUIRED by capt agent resume.
RES="$(capt --json agent resume --workspace "$WS" --mission "$MISSION" 2>&1)"

if printf '%s' "$RES" | grep -q 'TypeError: MissionCheckpoint'; then
  echo "FAIL LEGACY_CHECKPOINT_SCHEMA" >&2; printf '%s\n' "$RES" >&2; exit 4
fi
printf '%s\n' "$RES"
echo

HEAD_SHA="$(git -C "$WS" rev-parse HEAD 2>/dev/null || echo "")"
BRANCH="$(git -C "$WS" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
DIRTY="$([ -z "$(git -C "$WS" status --porcelain 2>/dev/null)" ] && echo false || echo true)"

VERDICT="$(printf '%s' "$RES" | WS="$WS" MISSION="$MISSION" EXPECT_CP="$EXPECT_CP" \
  HEAD_SHA="$HEAD_SHA" BRANCH="$BRANCH" DIRTY="$DIRTY" "$PY" -c '
import json, os, sys, datetime, glob

raw = sys.stdin.read(); ws = os.environ["WS"]; mission = os.environ["MISSION"]
expect_cp = os.environ.get("EXPECT_CP",""); head = os.environ["HEAD_SHA"]
branch = os.environ["BRANCH"]; dirty = os.environ["DIRTY"] == "true"

try:
    r = json.loads(raw)
except Exception:
    print(json.dumps({"continuity_verdict":"NOT_PROVEN","reason":"resume did not return JSON",
                      "raw": raw[:1500]}, indent=2)); sys.exit(0)

checks = []
def chk(name, ok, detail):
    checks.append({"check": name, "verdict": "PASS" if ok else "FAIL", "detail": detail})
    return ok

ok = True
ok &= chk("fresh_process", r.get("reconstructed_in") == "fresh-process",
          "reconstructed_in=%s" % r.get("reconstructed_in"))
ok &= chk("mission_recovered", r.get("mission_id") == mission,
          "recovered=%s expected=%s" % (r.get("mission_id"), mission))
ok &= chk("session_recovered", bool(r.get("session_id")),
          "session_id=%s" % (r.get("session_id") or "<empty>"))
ok &= chk("checkpoint_recovered", bool(r.get("checkpoint_id")),
          "checkpoint_id=%s" % (r.get("checkpoint_id") or "<empty>"))
if expect_cp:
    ok &= chk("checkpoint_matches_pre_exit", r.get("checkpoint_id") == expect_cp,
              "recovered=%s expected=%s" % (r.get("checkpoint_id"), expect_cp))
ok &= chk("gate_pass", r.get("gate_result") == "PASS",
          "gate_result=%s block=%s" % (r.get("gate_result"), r.get("block_reason") or "none"))
ok &= chk("contextpack_built", bool(r.get("contextpack_digest")),
          "digest=%s" % (r.get("contextpack_digest") or "<empty>"))
ok &= chk("intent_reconstructed", bool(r.get("intent_id")),
          "intent_id=%s" % (r.get("intent_id") or "<empty>"))
ok &= chk("not_blocked", r.get("execution_mode") != "BLOCKED",
          "execution_mode=%s" % r.get("execution_mode"))
ok &= chk("next_action_present", bool(r.get("next_justified_action")),
          "present" if r.get("next_justified_action") else "absent")

# recovered state vs repository evidence
cp_head = ""
cpf = os.path.join(ws, ".capt", "checkpoints", mission + ".json")
if os.path.exists(cpf):
    try:
        cp_head = (json.load(open(cpf)).get("latest_verified_state") or "")
    except Exception:
        cp_head = ""
divergence = []
if cp_head and head and cp_head not in (head,) and head not in cp_head:
    divergence.append("checkpoint.latest_verified_state=%s vs repo HEAD=%s" % (cp_head[:12], head[:12]))
if dirty:
    divergence.append("worktree dirty")

# resume artifact
home = os.environ.get("CAPT_SOLO_HOME", os.path.expanduser("~/.capt-solo"))
art = ""; art_ok = None
for b in (os.path.join(home,"data","evidence","agent-resume"),
          os.path.join(home,"evidence","agent-resume"),
          os.path.join(ws,".capt","evidence","agent-resume")):
    p = os.path.join(b, mission + ".json")
    if os.path.exists(p):
        art = p; art_ok = os.path.exists(p + ".sha256"); break

verdict = "PROVEN" if ok else "NOT_PROVEN"
out = {
  "receipt": "capt-recovery-receipt",
  "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  "workspace": ws,
  "mission_id": r.get("mission_id",""),
  "session_id": r.get("session_id",""),
  "checkpoint_id": r.get("checkpoint_id",""),
  "source": r.get("source",""),
  "reconstructed_in": r.get("reconstructed_in",""),
  "transcript_inheritance": "none",
  "post_resume": {
    "execution_mode": r.get("execution_mode",""),
    "gate_result": r.get("gate_result",""),
    "contextpack_digest": r.get("contextpack_digest",""),
    "intent_id": r.get("intent_id",""),
    "active_directive_ids": r.get("active_directive_ids",[]),
  },
  "repository_evidence": {"branch": branch, "head": head, "dirty": dirty,
                          "checkpoint_latest_verified_state": cp_head},
  "divergence": divergence or ["none"],
  "resume_artifact": art or "UNPROVEN",
  "resume_artifact_sha256_sidecar": art_ok,
  "next_justified_action": r.get("next_justified_action",""),
  "checks": checks,
  "continuity_verdict": verdict,
  "capt_execution_mode": r.get("execution_mode",""),
  "hermes_session_mode": "BOOTSTRAP_DEGRADED",
  "hermes_session_mode_reason": "Hermes tool hooks are observational; model-facing context equality with the ContextPack is unverified",
}
print(json.dumps(out, indent=2))
')"

printf '%s\n' "$VERDICT"
[ -n "$RECEIPT" ] && printf '%s\n' "$VERDICT" > "$RECEIPT" && echo "receipt written: $RECEIPT" >&2

CV="$(printf '%s' "$VERDICT" | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("continuity_verdict",""))' 2>/dev/null || echo "")"
MODE="$(printf '%s' "$VERDICT" | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("capt_execution_mode",""))' 2>/dev/null || echo "")"
[ "$MODE" = "BLOCKED" ] && exit 4
[ "$CV" = "PROVEN" ] && exit 0 || exit 5
