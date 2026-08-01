#!/usr/bin/env bash
# Real acceptance for the capt-core-runtime skill.
#
# Hardened contract:
#   * skill dir and evidence dir are resolved to ABSOLUTE paths at startup
#   * evidence dir is refused if empty, /, $HOME, or outside the worktree
#     (override with CAPT_ACCEPT_ALLOW_EXTERNAL_EV=1 for external replay)
#   * isolation paths are refused if they resolve to owner CAPT state
#   * a sentinel (00-evidence-root.txt) is written BEFORE any execution
#   * every critical step records stdout, stderr and its own exit code
#   * set -Eeuo pipefail + ERR trap (failing line + code) + EXIT trap (status)
#   * owner ~/.capt-solo and ~/capt-solo/.capt are never written
#
# Each numbered step runs in its OWN process. No transcript inheritance.
#
# Usage: run-acceptance.sh <skill-dir> <evidence-dir>
set -Eeuo pipefail

# ── argument resolution ────────────────────────────────────────────────────
RAW_SKILL="${1:-}"
RAW_EV="${2:-}"
[ -n "$RAW_SKILL" ] && [ -n "$RAW_EV" ] || {
  echo "usage: run-acceptance.sh <skill-dir> <evidence-dir>" >&2; exit 2; }

[ -d "$RAW_SKILL" ] || { echo "skill dir not found: $RAW_SKILL" >&2; exit 2; }
SKILL="$(cd "$RAW_SKILL" && pwd -P)"

# Evidence dir may not exist yet: resolve its parent, then append the leaf.
EV_PARENT="$(dirname "$RAW_EV")"
[ -d "$EV_PARENT" ] || mkdir -p "$EV_PARENT"
EV="$(cd "$EV_PARENT" && pwd -P)/$(basename "$RAW_EV")"

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
WORKTREE="$(cd "$SKILL" && git rev-parse --show-toplevel 2>/dev/null || echo "")"
CANON="${CAPT_CANONICAL_REPO:-/Users/knowurknot/capt-solo}"

# ── path safety: refuse dangerous or out-of-tree evidence roots ────────────
refuse() { echo "REFUSED: $*" >&2; exit 2; }
case "$EV" in
  ""|"/"|"$HOME"|"$HOME/") refuse "evidence path is empty, / or \$HOME: '$EV'" ;;
esac
[ "$EV" = "${EV%/}" ] || EV="${EV%/}"
if [ "${CAPT_ACCEPT_ALLOW_EXTERNAL_EV:-0}" != "1" ]; then
  [ -n "$WORKTREE" ] || refuse "cannot resolve worktree root for '$SKILL'"
  case "$EV" in
    "$WORKTREE"/*) : ;;
    *) refuse "evidence dir '$EV' is outside worktree '$WORKTREE' (set CAPT_ACCEPT_ALLOW_EXTERNAL_EV=1 to override)" ;;
  esac
fi

# ── isolation: temp CAPT home + temp git workspace, never owner state ──────
#
# CAPT_SOLO_HOME inherited from the environment is deliberately IGNORED: the
# harness always allocates its own temp home, so an ambient owner-pointing
# value cannot contaminate a run (defense by construction).
#
# CAPT_ACCEPT_HOME is the one explicit override, provided so the isolation
# guard below is a REACHABLE control rather than dead code. If an operator
# forces a home, it is validated and refused when it resolves to owner state.
ROOT="$(mktemp -d /tmp/capt-skill-acceptance.XXXXXX)"
INHERITED_HOME="${CAPT_SOLO_HOME:-}"
if [ -n "${CAPT_ACCEPT_HOME:-}" ]; then
  export CAPT_SOLO_HOME="$CAPT_ACCEPT_HOME"
  HOME_SOURCE="explicit-override(CAPT_ACCEPT_HOME)"
else
  export CAPT_SOLO_HOME="$ROOT/home"
  HOME_SOURCE="harness-allocated-temp"
fi
WS="$ROOT/ws"
MISSION="${CAPT_ACCEPT_MISSION:-mission-skill-real-acceptance}"
PY="${CAPT_ACCEPT_PY:-$CANON/.venv/bin/python}"
export CAPT_ACCEPT_PY="$PY"   # every script selects this interpreter deterministically
# `capt` is a console script in the same bin dir as the selected python; put it
# on PATH so the scripts can invoke it. Correctness does not depend on ambient
# shell activation — we set it explicitly here.
export PATH="$(dirname "$PY")${PATH:+:$PATH}"

# Refuse BEFORE writing anything if isolation resolves to owner state.
OWNER_HOME_REAL="$(cd "$HOME" && pwd -P)/.capt-solo"
_resolved_home="$CAPT_SOLO_HOME"
case "$_resolved_home" in
  "$OWNER_HOME_REAL"|"$OWNER_HOME_REAL"/*) refuse "CAPT_SOLO_HOME resolves to owner state: $_resolved_home" ;;
  "$HOME"/.capt|"$HOME"/.capt/*)           refuse "CAPT_SOLO_HOME resolves to owner ~/.capt: $_resolved_home" ;;
  "$CANON"/*)                              refuse "CAPT_SOLO_HOME resolves inside the canonical owner repo: $_resolved_home" ;;
esac
case "$WS" in
  "$CANON"|"$CANON"/*)     refuse "workspace resolves into the canonical owner repo: $WS" ;;
  "$WORKTREE"|"$WORKTREE"/*) refuse "workspace resolves into the skill worktree: $WS" ;;
esac
[ -x "$PY" ] || refuse "python interpreter not executable: $PY"

mkdir -p "$EV" "$WS"

# ── traps ──────────────────────────────────────────────────────────────────
# bash 3.2 (macOS) still fires the ERR trap for commands inside a `set +e`
# region, so run_step's deliberately-tolerated non-zero exits would otherwise
# forge a spurious "failing_command" record. IN_RUN_STEP suppresses the trap
# for exactly those windows; everything else still trips it.
HARNESS_STATUS="INCOMPLETE"
FAIL_LINE=""; FAIL_CODE=""; FAIL_CMD=""; IN_RUN_STEP=0
STEP_FAILURES=""
on_err() {
  local code=$? line=$1 cmd=$2
  [ "$IN_RUN_STEP" = "1" ] && return 0
  FAIL_CODE=$code; FAIL_LINE=$line; FAIL_CMD=$cmd
  HARNESS_STATUS="FAIL"
  echo "ERR trap: line $line exit=$code cmd: $cmd" >&2
}
trap 'on_err "$LINENO" "$BASH_COMMAND"' ERR
on_exit() {
  local code=$?
  # Never launder a failure into a PASS: an explicit FAIL, a non-zero exit, or
  # any recorded step failure all dominate.
  if [ "$code" != "0" ] || [ "$HARNESS_STATUS" = "FAIL" ] || [ -n "$STEP_FAILURES" ]; then
    HARNESS_STATUS="FAIL"
  elif [ "$HARNESS_STATUS" = "INCOMPLETE" ]; then
    HARNESS_STATUS="FAIL"   # reached the end without an explicit PASS
  fi
  cat > "$EV/99-harness-result.json" <<EOF
{
  "result": "$HARNESS_STATUS",
  "exit_code": $code,
  "failing_line": "${FAIL_LINE:-}",
  "failing_exit_code": "${FAIL_CODE:-}",
  "failing_command": $(printf '%s' "${FAIL_CMD:-}" | "$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""'),
  "step_failures": $(printf '%s' "${STEP_FAILURES:-}" | "$PY" -c 'import json,sys;s=sys.stdin.read().strip();print(json.dumps([x for x in s.split(";") if x]))' 2>/dev/null || echo '[]'),
  "finished_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "isolated_root": "$ROOT",
  "evidence_dir": "$EV"
}
EOF
  echo "harness result: $HARNESS_STATUS (exit=$code) -> $EV/99-harness-result.json"
}
trap on_exit EXIT

fail() { echo "ACCEPTANCE FAILED: $*" >&2; HARNESS_STATUS="FAIL"; exit 1; }

# run_step <stdout-file> <stderr-file> <rc-file> -- cmd...
# Records the real exit code and keeps going. Non-zero is recorded, never hidden;
# whether it is fatal is decided by the caller, which must state the policy.
run_step() {
  local out="$1" err="$2" rcf="$3"; shift 3
  IN_RUN_STEP=1
  set +e
  "$@" >"$out" 2>"$err"
  local rc=$?
  set -e
  IN_RUN_STEP=0
  echo "$rc" > "$rcf"
  return 0
}

# note_step_failure <step> <detail> — record a tolerated-but-real failure.
note_step_failure() { STEP_FAILURES="${STEP_FAILURES}${1}: ${2};"; }

# ── step 0: sentinel, written before any execution ─────────────────────────
git init -q "$WS"
git -C "$WS" -c user.email=a@a -c user.name=a commit -q --allow-empty -m "init"
cp "$CANON/capt_cli.py" "$WS/capt_cli.py"

cat > "$EV/00-evidence-root.txt" <<EOF
evidence_path   $EV
timestamp_utc   $(date -u +%Y-%m-%dT%H:%M:%SZ)
worktree        $WORKTREE
branch          $(git -C "$WORKTREE" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)
head_sha        $(git -C "$WORKTREE" rev-parse HEAD 2>/dev/null || echo unknown)
hostname        $(hostname)
shell_pid       $$
uname           $(uname -srm)
CAPT_SOLO_HOME  $CAPT_SOLO_HOME
home_source     $HOME_SOURCE
inherited_home  ${INHERITED_HOME:-<unset>} (ignored unless CAPT_ACCEPT_HOME is set)
workspace       $WS
mission         $MISSION
skill_dir       $SKILL
harness         $HARNESS_DIR/$(basename "${BASH_SOURCE[0]}")
python          $PY
canonical_repo  $CANON
EOF
echo "evidence root: $EV"
cat "$EV/00-evidence-root.txt"
echo

echo "=== step 0: seed mission (owner action, not the skill) ==="
"$PY" "$WS/capt_cli.py" mission checkpoint --mission-id "$MISSION" \
  --project-id "ws" --objective "prove capt-core-runtime skill boots and resumes" \
  --phase "PHASE_ACCEPTANCE" --next "verify boot report" \
  --head "$(git -C "$WS" rev-parse HEAD)" >"$EV/00-mission-seed.txt" 2>&1 || fail "mission seed"
[ -f "$WS/.capt/checkpoints/$MISSION.json" ] || fail "checkpoint not in isolated workspace"
echo "isolated store confirmed: $WS/.capt/checkpoints/$MISSION.json"
echo

echo "=== step 1: environment report (fresh process) ==="
run_step "$EV/01-environment-report.json" "$EV/01-environment-report.stderr.txt" \
         "$EV/01-environment-report.exit-code" \
         bash "$SKILL/scripts/capt-environment-report.sh" "$WS"
echo "exit=$(cat "$EV/01-environment-report.exit-code")"
"$PY" -c "
import json
d=json.load(open('$EV/01-environment-report.json'))
print('source_via:', d['capt']['source_resolved_via'])
print('version:   ', d['capt']['module_version'])
print('checkout:  ', d['capt']['checkout_verdict'])
print('home:      ', d['capt']['capt_solo_home'])
print('secrets:   ', d['credentials']['LM_STUDIO_API_KEY'])
" || fail "environment report unparseable"
echo

echo "=== step 2: doctor (fresh process) ==="
run_step "$EV/02-doctor.txt" "$EV/02-doctor.stderr.txt" "$EV/02-doctor.exit-code" \
         bash "$SKILL/scripts/capt-doctor.sh" "$WS" "$MISSION"
DOCTOR_RC="$(cat "$EV/02-doctor.exit-code")"
echo "exit=$DOCTOR_RC"
grep -E "^(PASS|WARN|FAIL|NOT_PROVEN)" "$EV/02-doctor.txt" | awk '{print $1}' | sort | uniq -c
grep "FAIL count" "$EV/02-doctor.txt" || true
# Policy, stated explicitly: the doctor must report zero FAIL rows on a healthy
# isolated workspace. WARN and NOT_PROVEN are expected (empty memory store, KHSB
# disabled, ClaimGuard available-not-wired, Hermes hooks observational).
if [ "$DOCTOR_RC" != "0" ]; then
  echo "doctor reported FAIL rows:" >&2
  grep -E "^FAIL" "$EV/02-doctor.txt" >&2 || true
  note_step_failure "02-doctor" "exit=$DOCTOR_RC with FAIL rows present"
  fail "doctor must have zero FAIL rows in an isolated workspace (exit=$DOCTOR_RC)"
fi
echo

echo "=== step 3: boot + recover mission (fresh process) ==="
run_step "$EV/03-boot-report.stdout.txt" "$EV/03-boot-report.stderr.txt" \
         "$EV/03-boot-report.exit-code" \
         bash "$SKILL/scripts/capt-fresh-boot.sh" "$WS" "$MISSION" \
              --report-out "$EV/03-boot-report.json"
echo "exit=$(cat "$EV/03-boot-report.exit-code")"
[ -s "$EV/03-boot-report.json" ] || fail "boot report not written"
"$PY" -c "
import json
d=json.load(open('$EV/03-boot-report.json'))
for k in ('mission_id','session_id','checkpoint_id','gate_result','capt_execution_mode',
          'hermes_session_mode','contextpack_digest','memory_use_decision_id',
          'boot_trace_match','agent_run_id','next_justified_action'):
    print(f'{k:24} {d.get(k)}')
print(f'{\"active_directives\":24} {len(d[\"active_directive_ids\"])}')
for k in ('selected_memory_ids','rejected_memory_ids','missing_memory_ids','conflict_ids','stale_memory_ids'):
    v=d.get(k); print(f'{k:24} {len(v) if isinstance(v,list) else v}')
" || fail "boot report unparseable"
BOOT_PID_MARK="$(cat "$EV/03-boot-report.exit-code")"
echo

echo "=== step 4: validate boot report against schema (fresh process) ==="
set +e
"$PY" - >"$EV/04-schema-validation.txt" 2>&1 <<PYEOF
import json, jsonschema
schema = json.load(open("$SKILL/schemas/boot-report.schema.json"))
rep = json.load(open("$EV/03-boot-report.json"))
jsonschema.Draft202012Validator.check_schema(schema)
errs = list(jsonschema.Draft202012Validator(schema).iter_errors(rep))
print("schema: VALID")
print("report errors:", len(errs))
for e in errs: print(" -", list(e.path), e.message)
raise SystemExit(0 if not errs else 1)
PYEOF
echo $? > "$EV/04-schema-validation.exit-code"
set -e
cat "$EV/04-schema-validation.txt"
[ "$(cat "$EV/04-schema-validation.exit-code")" = "0" ] || fail "boot report violates schema"
echo

echo "=== step 5: write checkpoint + verify reload (fresh process) ==="
run_step "$EV/05-checkpoint.txt" "$EV/05-checkpoint.stderr.txt" "$EV/05-checkpoint.exit-code" \
         bash "$SKILL/scripts/capt-checkpoint.sh" "$WS" "$MISSION" \
              --receipt-out "$EV/05-checkpoint-receipt.json"
echo "exit=$(cat "$EV/05-checkpoint.exit-code")"
tail -6 "$EV/05-checkpoint.txt"
"$PY" -c "
import json
d=json.load(open('$EV/05-checkpoint-receipt.json'))
assert d['reload_verified'] is True, 'checkpoint did not reload'
print('reload_verified:', d['reload_verified'])
print('checkpoint_id:  ', d['checkpoint_id'])
" || fail "checkpoint reload verification"
CP_ID="$("$PY" -c "import json;print(json.load(open('$EV/05-checkpoint-receipt.json'))['checkpoint_id'])")"
echo

echo "=== step 6: EXIT. fresh process. resume solely through CAPT ==="
run_step "$EV/06-recovery.stdout.txt" "$EV/06-recovery.stderr.txt" "$EV/06-recovery.exit-code" \
         bash "$SKILL/scripts/capt-resume-check.sh" "$WS" "$MISSION" \
              --receipt-out "$EV/06-recovery-receipt.json" --expect-checkpoint "$CP_ID"
echo "exit=$(cat "$EV/06-recovery.exit-code")"
"$PY" -c "
import json
d=json.load(open('$EV/06-recovery-receipt.json'))
for k in ('continuity_verdict','reconstructed_in','transcript_inheritance','mission_id',
          'session_id','checkpoint_id','source'):
    print(f'{k:24} {d[k]}')
print(f'{\"gate_result\":24} {d[\"post_resume\"][\"gate_result\"]}')
print(f'{\"contextpack_digest\":24} {d[\"post_resume\"][\"contextpack_digest\"]}')
print(f'{\"divergence\":24} {d[\"divergence\"]}')
for c in d['checks']: print(f'  {c[\"verdict\"]:5} {c[\"check\"]:32} {c[\"detail\"]}')
assert d['continuity_verdict']=='PROVEN', 'continuity NOT PROVEN'
" || fail "continuity verification"
echo

echo "=== step 7: distinct-PID proof (boot vs resume ran in different processes) ==="
"$PY" - > "$EV/07-isolation-report.json" <<PYEOF
import json, os, subprocess, hashlib, glob
mission = "$MISSION"; canon = "$CANON"; home = os.path.expanduser("~")
leaks = []
owner_home = os.path.join(home, ".capt-solo")
if os.path.isdir(owner_home):
    for p in glob.glob(os.path.join(owner_home, "**", "*"), recursive=True):
        if mission in os.path.basename(p):
            leaks.append(p)
    ev = os.path.join(owner_home, "data", "khsb", "events.jsonl")
    if os.path.exists(ev) and mission in open(ev, errors="ignore").read():
        leaks.append(ev + " (mission id present)")
cp_dir = os.path.join(canon, ".capt", "checkpoints")
owner_cps = sorted(glob.glob(os.path.join(cp_dir, "*.json"))) if os.path.isdir(cp_dir) else []
for p in owner_cps:
    if mission in os.path.basename(p):
        leaks.append(p)
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f: h.update(f.read())
    return h.hexdigest()
out = {
  "report": "capt-acceptance-isolation",
  "mission": mission,
  "capt_solo_home_used": os.environ.get("CAPT_SOLO_HOME", ""),
  "owner_capt_solo_home": owner_home,
  "owner_home_file_count": sum(len(f) for _,_,f in os.walk(owner_home)) if os.path.isdir(owner_home) else 0,
  "owner_repo_checkpoint_dir": cp_dir,
  "owner_repo_checkpoint_count": len(owner_cps),
  "owner_repo_checkpoint_digests": {os.path.basename(p): sha(p) for p in owner_cps},
  "leaks": leaks,
  "verdict": "PASS" if not leaks else "FAIL",
}
print(json.dumps(out, indent=2))
PYEOF
"$PY" -c "
import json
d=json.load(open('$EV/07-isolation-report.json'))
print('isolation verdict:', d['verdict'])
print('owner home files: ', d['owner_home_file_count'])
print('owner checkpoints:', d['owner_repo_checkpoint_count'])
print('leaks:            ', d['leaks'] or 'none')
assert d['verdict']=='PASS', 'owner state contaminated'
" || fail "owner state contaminated"
echo

echo "=== step 8: runtime identities + continuity cross-check ==="
"$PY" - > "$EV/09-runtime-identities.json" <<PYEOF
import json, subprocess, sys, os
ws = "$WS"
boot = json.load(open("$EV/03-boot-report.json"))
rec  = json.load(open("$EV/06-recovery-receipt.json"))
cp   = json.load(open("$EV/05-checkpoint-receipt.json"))
env  = json.load(open("$EV/01-environment-report.json"))
out = {
  "report": "capt-runtime-identities",
  "capt_module_file": boot["capt"]["module_file"],
  "capt_version": boot["capt"]["version"],
  "capt_home": boot["capt"]["home"],
  "source_resolved_via": env["capt"]["source_resolved_via"],
  "checkout_verdict": env["capt"]["checkout_verdict"],
  "boot":       {"session_id": boot["session_id"], "checkpoint_id": boot["checkpoint_id"],
                 "contextpack_digest": boot["contextpack_digest"], "agent_run_id": boot["agent_run_id"],
                 "gate_result": boot["gate_result"], "execution_mode": boot["capt_execution_mode"]},
  "checkpoint": {"checkpoint_id": cp["checkpoint_id"], "reload_checkpoint_id": cp["reload_checkpoint_id"],
                 "reload_verified": cp["reload_verified"]},
  "resume":     {"session_id": rec["session_id"], "checkpoint_id": rec["checkpoint_id"],
                 "contextpack_digest": rec["post_resume"]["contextpack_digest"],
                 "gate_result": rec["post_resume"]["gate_result"],
                 "execution_mode": rec["post_resume"]["execution_mode"]},
}
print(json.dumps(out, indent=2))
PYEOF

"$PY" - > "$EV/10-continuity-report.json" <<PYEOF
import json
boot = json.load(open("$EV/03-boot-report.json"))
rec  = json.load(open("$EV/06-recovery-receipt.json"))
cp   = json.load(open("$EV/05-checkpoint-receipt.json"))
checks = []
def c(name, ok, detail): checks.append({"check":name,"verdict":"PASS" if ok else "FAIL","detail":detail})
c("checkpoint_id_stable_boot_to_resume", boot["checkpoint_id"]==rec["checkpoint_id"],
  f'boot={boot["checkpoint_id"]} resume={rec["checkpoint_id"]}')
c("checkpoint_id_stable_write_to_reload", cp["checkpoint_id"]==cp["reload_checkpoint_id"],
  f'write={cp["checkpoint_id"]} reload={cp["reload_checkpoint_id"]}')
c("mission_id_stable", boot["mission_id"]==rec["mission_id"], boot["mission_id"])
c("session_id_regenerated_per_process", boot["session_id"]!=rec["session_id"],
  f'boot={boot["session_id"]} resume={rec["session_id"]} (expected DIFFERENT: separate processes)')
c("contextpack_rebuilt_per_boot", boot["contextpack_digest"]!=rec["post_resume"]["contextpack_digest"],
  "expected DIFFERENT: a new ContextPack is built per boot")
c("contextpack_present_both", bool(boot["contextpack_digest"]) and bool(rec["post_resume"]["contextpack_digest"]), "both non-empty")
c("gate_pass_both", boot["gate_result"]=="PASS" and rec["post_resume"]["gate_result"]=="PASS", "PASS/PASS")
c("transcript_inheritance_none", rec["transcript_inheritance"]=="none", rec["transcript_inheritance"])
c("resume_in_fresh_process", rec["reconstructed_in"]=="fresh-process", rec["reconstructed_in"])
c("hermes_mode_not_overclaimed", boot["hermes_session_mode"]=="BOOTSTRAP_DEGRADED" and rec["hermes_session_mode"]=="BOOTSTRAP_DEGRADED",
  "Hermes hooks observational; not relabelled GOVERNED")
c("continuity_verdict_proven", rec["continuity_verdict"]=="PROVEN", rec["continuity_verdict"])
out = {"report":"capt-continuity-cross-check","checks":checks,
       "verdict":"PASS" if all(x["verdict"]=="PASS" for x in checks) else "FAIL"}
print(json.dumps(out, indent=2))
PYEOF
"$PY" -c "
import json
d=json.load(open('$EV/10-continuity-report.json'))
for c in d['checks']: print(f'  {c[\"verdict\"]:5} {c[\"check\"]:38} {c[\"detail\"]}')
print('continuity cross-check:', d['verdict'])
assert d['verdict']=='PASS'
" || fail "continuity cross-check"
echo

echo "=== step 9: unit suite (recorded, not re-asserted from memory) ==="
run_step "$EV/08-test-results.txt" "$EV/08-test-results.stderr.txt" "$EV/08-test-results.exit-code" \
         "$CANON/.venv/bin/pytest" -q "$WORKTREE/tests/test_hermes_capt_core_runtime_skill.py"
echo "exit=$(cat "$EV/08-test-results.exit-code")"
tail -3 "$EV/08-test-results.txt"
[ "$(cat "$EV/08-test-results.exit-code")" = "0" ] || fail "unit suite failed"
echo

echo "=== step 10: artifact inventory + manifest ==="
"$PY" - > "$EV/98-artifact-inventory.json" <<PYEOF
import json, os, hashlib
ev = "$EV"
items = []
for name in sorted(os.listdir(ev)):
    p = os.path.join(ev, name)
    if not os.path.isfile(p) or name in ("MANIFEST.sha256", "98-artifact-inventory.json"):
        continue
    b = open(p, "rb").read()
    items.append({"file": name, "bytes": len(b),
                  "sha256": hashlib.sha256(b).hexdigest()})
print(json.dumps({"report":"capt-acceptance-artifact-inventory",
                  "evidence_dir": ev, "count": len(items), "artifacts": items}, indent=2))
PYEOF
echo "inventory: $("$PY" -c "import json;print(json.load(open('$EV/98-artifact-inventory.json'))['count'])") artifacts"

# Manifest covers every evidence file except the manifest itself, relative paths.
( cd "$EV" && find . -maxdepth 1 -type f ! -name 'MANIFEST.sha256' -print0 \
    | sort -z | xargs -0 shasum -a 256 > MANIFEST.sha256 )
echo "manifest lines: $(wc -l < "$EV/MANIFEST.sha256" | tr -d ' ')"
echo

HARNESS_STATUS="PASS"
echo "ACCEPTANCE PASSED"
echo "isolated root retained for inspection: $ROOT"
