#!/usr/bin/env bash
# capt-fresh-boot.sh — boot a CAPT mission through the canonical Agent Runner.
#
# Runs exactly one canonical command:
#   capt --json agent status --workspace WS --mission M
# and renders a boot report conforming to schemas/boot-report.schema.json.
# Constructs no runtime object; reconstructs no CAPT behaviour.
#
# Usage: capt-fresh-boot.sh <workspace> <mission-id> [--report-out PATH]
# Exit:  0 GOVERNED | 3 BOOTSTRAP_DEGRADED | 4 BLOCKED | 2 bad invocation
set -uo pipefail

WS="${1:-}"; MISSION="${2:-}"; shift 2 2>/dev/null || true
OUT=""
while [ $# -gt 0 ]; do
  case "$1" in --report-out) OUT="${2:-}"; shift 2 ;; *) shift ;; esac
done

if [ -z "$WS" ] || [ -z "$MISSION" ]; then
  echo "usage: capt-fresh-boot.sh <workspace> <mission-id> [--report-out PATH]" >&2
  echo "note: --mission is MANDATORY; auto-discovery raises TypeError on legacy checkpoints" >&2
  exit 2
fi
[ -d "$WS" ] || { echo "workspace not found: $WS" >&2; exit 2; }
WS="$(cd "$WS" && pwd)"

# ── deterministic interpreter selection (single source of truth) ────────────
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1091
. "$HERE/capt-select-python.sh" "$WS" || { echo "REFUSED: interpreter selection failed" >&2; exit 2; }
PY="$CAPT_PY"

[ -x "$WS/.venv/bin/capt" ] && echo "note: workspace venv present at $WS/.venv (observed, not activated as fallback)" >&2
command -v capt >/dev/null || { echo "CAPT_NOT_FOUND: capt not on PATH (set CAPT_ACCEPT_PY or activate the venv)" >&2; exit 2; }

BOOT_JSON="$(capt --json agent status --workspace "$WS" --mission "$MISSION" 2>&1)"

if printf '%s' "$BOOT_JSON" | grep -q 'TypeError: MissionCheckpoint'; then
  echo "FAIL LEGACY_CHECKPOINT_SCHEMA: the store holds pre-project_id checkpoints." >&2
  echo "$BOOT_JSON" >&2
  exit 4
fi

REPORT="$(printf '%s' "$BOOT_JSON" | WS="$WS" MISSION="$MISSION" "$PY" -c '
import json, os, subprocess, sys, datetime

raw = sys.stdin.read()
ws = os.environ["WS"]; mission = os.environ["MISSION"]

def git(*a):
    try:
        r = subprocess.run(["git","-C",ws,*a],capture_output=True,text=True,timeout=10)
        return r.stdout.strip() if r.returncode==0 else ""
    except Exception:
        return ""

try:
    boot = json.loads(raw)
except Exception:
    print(json.dumps({"error":"agent status did not return JSON","raw":raw[:2000]}, indent=2)); sys.exit(0)

# superseded directives + memory selection live in the persisted boot trace.
# Canonical location: <CAPT_SOLO_HOME>/data/evidence/agent-boot/<agent_run_id>.json
def find_trace(digest):
    import glob
    home = os.environ.get("CAPT_SOLO_HOME", os.path.expanduser("~/.capt-solo"))
    bases = [os.path.join(home, "data", "evidence", "agent-boot"),
             os.path.join(home, "evidence", "agent-boot"),
             os.path.join(ws, ".capt", "evidence", "agent-boot"),
             os.path.expanduser("~/.capt/evidence/agent-boot")]
    cands = []
    for b in bases:
        cands += [c for c in glob.glob(os.path.join(b, "*.json")) if not c.endswith(".sha256")]
    best = None
    for c in cands:
        try:
            t = json.load(open(c))
        except Exception:
            continue
        if t.get("mission_id") != mission:
            continue
        # exact match on this boot: same ContextPack digest
        if digest and t.get("contextpack_digest") == digest:
            t["_artifact_path"] = c
            t["_match"] = "contextpack_digest"
            return t
        if best is None or os.path.getmtime(c) > os.path.getmtime(best["_artifact_path"]):
            t["_artifact_path"] = c
            t["_match"] = "mission+mtime (digest did not match; fields may be from another run)"
            best = t
    return best or {}

tr = find_trace(boot.get("contextpack_digest", ""))

def pyver():
    return "%d.%d.%d" % sys.version_info[:3]

# Report the module the canonical CLI actually loads, not whatever the invoking
# CWD shadows. The `capt` console script sets sys.path[0] to the venv bin dir,
# so it is never CWD-shadowed; a plain "import capt_solo" here would be, and
# would misreport the runtime identity whenever the boot runs from a directory
# containing a capt_solo/ tree. Probe in isolated mode (-P) to match the CLI.
capt_file = ""; capt_ver = "unknown"; capt_shadow = ""
try:
    _r = subprocess.run(
        [sys.executable, "-P", "-c",
         "import capt_solo;print(capt_solo.__file__);print(getattr(capt_solo,\"__version__\",\"unknown\"))"],
        capture_output=True, text=True, timeout=30)
    if _r.returncode == 0:
        _lines = _r.stdout.strip().splitlines()
        capt_file = _lines[0] if _lines else ""
        capt_ver = _lines[1] if len(_lines) > 1 else "unknown"
except Exception:
    pass
try:
    import capt_solo as _cwd_mod
    if _cwd_mod.__file__ != capt_file:
        capt_shadow = _cwd_mod.__file__
except Exception:
    pass

report = {
  "report": "capt-boot-report",
  "schema": "capt-core-runtime/boot-report/v1",
  "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  "workspace_root": ws,
  "branch": git("rev-parse","--abbrev-ref","HEAD"),
  "head": git("rev-parse","HEAD"),
  "dirty": bool(git("status","--porcelain")),
  "python": {"version": pyver(), "executable": sys.executable},
  "capt": {"module_file": capt_file, "version": capt_ver,
           "cwd_shadowing_module": capt_shadow,
           "home": os.environ.get("CAPT_SOLO_HOME", os.path.expanduser("~/.capt-solo"))},
  "mission_id": boot.get("mission_id",""),
  "session_id": boot.get("session_id",""),
  "checkpoint_id": boot.get("checkpoint_id",""),
  "active_directive_ids": boot.get("active_directive_ids",[]),
  "superseded_directive_ids": tr.get("superseded_directive_ids", "UNPROVEN"),
  "selected_memory_ids": tr.get("selected_memory_ids", "UNPROVEN"),
  "rejected_memory_ids": tr.get("rejected_memory_ids", "UNPROVEN"),
  "missing_memory_ids": tr.get("missing_memory_ids", "UNPROVEN"),
  "conflict_ids": tr.get("conflict_ids", "UNPROVEN"),
  "stale_memory_ids": tr.get("stale_memory_ids", "UNPROVEN"),
  "intent_id": boot.get("intent_id", tr.get("intent_id","")),
  "contextpack_digest": boot.get("contextpack_digest",""),
  "memory_use_decision_id": tr.get("memory_use_decision_id","UNPROVEN"),
  "gate_result": boot.get("gate_result",""),
  "capt_execution_mode": boot.get("execution_mode",""),
  "hermes_session_mode": "BOOTSTRAP_DEGRADED",
  "hermes_session_mode_reason": "Hermes tool hooks are observational; model-facing context equality with the ContextPack is unverified",
  "block_reason": boot.get("block_reason",""),
  "block_codes": boot.get("block_codes",[]),
  "next_justified_action": boot.get("next_justified_action",""),
  "latest_verified_milestone": "NOT_ASSERTED (read from checkpoint phase / repository evidence)",
  "boot_trace_artifact": tr.get("_artifact_path","UNPROVEN"),
  "boot_trace_artifact_hash": tr.get("artifact_hash","UNPROVEN"),
  "boot_trace_match": tr.get("_match","none"),
  "agent_run_id": tr.get("agent_run_id","UNPROVEN"),
}
print(json.dumps(report, indent=2))
')"

printf '%s\n' "$REPORT"
[ -n "$OUT" ] && printf '%s\n' "$REPORT" > "$OUT" && echo "report written: $OUT" >&2

MODE="$(printf '%s' "$REPORT" | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("capt_execution_mode",""))' 2>/dev/null || echo "")"
case "$MODE" in
  GOVERNED)            exit 0 ;;
  BOOTSTRAP_DEGRADED)  exit 3 ;;
  *)                   exit 4 ;;
esac
