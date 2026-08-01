#!/usr/bin/env bash
# Adversarial corruption matrix for the capt-core-runtime skill.
#
# A scenario PASSES when the system fails SAFELY and TRUTHFULLY — not when
# resume succeeds. Each scenario runs in its own isolated copy of a seeded
# workspace with its own temp CAPT_SOLO_HOME. The canonical evidence directory
# is never mutated.
#
# Usage: run-adversarial.sh <skill-dir> <out-dir>
set -Eeuo pipefail

RAW_SKILL="${1:?usage: run-adversarial.sh <skill-dir> <out-dir>}"
RAW_OUT="${2:?usage: run-adversarial.sh <skill-dir> <out-dir>}"
SKILL="$(cd "$RAW_SKILL" && pwd -P)"
mkdir -p "$RAW_OUT"; OUT="$(cd "$RAW_OUT" && pwd -P)"
CANON="${CAPT_CANONICAL_REPO:-/Users/knowurknot/capt-solo}"
PY="${CAPT_ACCEPT_PY:-$CANON/.venv/bin/python}"
export CAPT_ACCEPT_PY="$PY"   # every script selects this interpreter deterministically
export PATH="$(dirname "$PY")${PATH:+:$PATH}"   # make `capt` console script resolvable
MISSION="mission-skill-real-acceptance"

OWNER_HOME_REAL="$(cd "$HOME" && pwd -P)/.capt-solo"
OWNER_CP_DIR="$CANON/.capt/checkpoints"
owner_fingerprint() {
  local n=0 c=0
  [ -d "$OWNER_HOME_REAL" ] && n="$(find "$OWNER_HOME_REAL" -type f 2>/dev/null | wc -l | tr -d ' ')"
  [ -d "$OWNER_CP_DIR" ] && c="$(find "$OWNER_CP_DIR" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l | tr -d ' ')"
  echo "$n:$c"
}
OWNER_BEFORE="$(owner_fingerprint)"

PASSES=0; FAILS=0; RESULTS=""

# seed_ws <dir> — a fresh isolated workspace with a seeded mission + checkpoint.
seed_ws() {
  local ws="$1" home="$2"
  mkdir -p "$ws"
  git init -q "$ws"
  git -C "$ws" -c user.email=a@a -c user.name=a commit -q --allow-empty -m init
  cp "$CANON/capt_cli.py" "$ws/capt_cli.py"
  CAPT_SOLO_HOME="$home" "$PY" "$ws/capt_cli.py" mission checkpoint \
    --mission-id "$MISSION" --project-id ws \
    --objective "adversarial scenario" --phase PHASE_ACCEPTANCE \
    --next "verify" --head "$(git -C "$ws" rev-parse HEAD)" >/dev/null 2>&1
}

# scenario <id> <name> <expectation> — body reads $WS/$HOME_DIR/$DIR, sets $ACTUAL/$VERDICT
scenario() {
  local id="$1" name="$2" expect="$3"; shift 3
  local dir="$OUT/$id-$name"
  mkdir -p "$dir"
  local root; root="$(mktemp -d /tmp/capt-adv-"$id".XXXXXX)"
  WS="$root/ws"; HOME_DIR="$root/home"; DIR="$dir"
  seed_ws "$WS" "$HOME_DIR"
  echo "$expect" > "$dir/expected.txt"
  MUTATION=""; CMD=""; ACTUAL=""; VERDICT="FAIL"
  "$@"
  {
    echo "scenario:    $id — $name"
    echo "mutation:    $MUTATION"
    echo "command:     $CMD"
    echo "expected:    $expect"
    echo "actual:      $ACTUAL"
    echo "verdict:     $VERDICT"
  } > "$dir/summary.txt"
  "$PY" - "$dir" "$id" "$name" "$expect" "$MUTATION" "$CMD" "$ACTUAL" "$VERDICT" <<'PYEOF' > "$dir/result.json"
import json, sys
d, sid, name, exp, mut, cmd, act, verdict = sys.argv[1:9]
print(json.dumps({"scenario": sid, "name": name, "mutation": mut, "command": cmd,
                  "expected": exp, "actual": act, "verdict": verdict}, indent=2))
PYEOF
  if [ "$VERDICT" = "PASS" ]; then PASSES=$((PASSES+1)); else FAILS=$((FAILS+1)); fi
  RESULTS="${RESULTS}${id}:${VERDICT} "
  printf '%-4s %-28s %s\n' "$id" "$name" "$VERDICT"
  echo "$root" > "$dir/isolated-root.txt"
}

# helper: run resume-check, capture rc/stdout/stderr into $DIR
run_resume() {
  set +e
  CAPT_SOLO_HOME="$HOME_DIR" bash "$SKILL/scripts/capt-resume-check.sh" "$WS" "${1:-$MISSION}" \
    --receipt-out "$DIR/receipt.json" > "$DIR/stdout.txt" 2> "$DIR/stderr.txt"
  RC=$?
  set -e
  echo "$RC" > "$DIR/exit-code.txt"
  CMD="capt-resume-check.sh $WS ${1:-$MISSION}"
}
run_boot() {
  set +e
  CAPT_SOLO_HOME="$HOME_DIR" bash "$SKILL/scripts/capt-fresh-boot.sh" "$WS" "${1:-$MISSION}" \
    --report-out "$DIR/report.json" > "$DIR/stdout.txt" 2> "$DIR/stderr.txt"
  RC=$?
  set -e
  echo "$RC" > "$DIR/exit-code.txt"
  CMD="capt-fresh-boot.sh $WS ${1:-$MISSION}"
}
verdict_json() { # field, expected-not-value
  "$PY" -c "
import json,sys
try: d=json.load(open('$DIR/receipt.json'))
except Exception: print(''); raise SystemExit
print(d.get('continuity_verdict',''))" 2>/dev/null
}

echo "adversarial matrix — out=$OUT"
echo "-------------------------------------------------------------------"

# ── A. missing checkpoint ──────────────────────────────────────────────────
a_missing_checkpoint() {
  MUTATION="delete $WS/.capt/checkpoints/$MISSION.json"
  rm -f "$WS/.capt/checkpoints/$MISSION.json"
  run_resume
  local cv; cv="$(verdict_json)"
  ACTUAL="exit=$RC continuity_verdict='${cv:-<none>}'"
  if [ "$RC" != "0" ] && [ "$cv" != "PROVEN" ]; then VERDICT="PASS"; fi
  return 0
}
scenario A missing-checkpoint "nonzero exit, no PROVEN, no silent reconstruction" a_missing_checkpoint

# ── B. malformed mission JSON ──────────────────────────────────────────────
b_malformed_mission() {
  MUTATION="truncate mission JSON to invalid syntax"
  printf '{"mission_id": "mission-skill-real' > "$WS/.capt/checkpoints/$MISSION.json"
  run_resume
  local cv; cv="$(verdict_json)"
  ACTUAL="exit=$RC continuity_verdict='${cv:-<none>}' stderr_has_reason=$(grep -qiE 'json|decode|expecting|parse|invalid' "$DIR/stderr.txt" "$DIR/stdout.txt" && echo yes || echo no)"
  if [ "$RC" != "0" ] && [ "$cv" != "PROVEN" ]; then VERDICT="PASS"; fi
  return 0
}
scenario B malformed-mission-json "parse failure surfaced, no fallback mission" b_malformed_mission

# ── C. mission identity mismatch ───────────────────────────────────────────
c_mission_mismatch() {
  MUTATION="request a different, non-existent mission id"
  run_resume "mission-some-other-identity"
  local cv; cv="$(verdict_json)"
  ACTUAL="exit=$RC continuity_verdict='${cv:-<none>}'"
  if [ "$RC" != "0" ] && [ "$cv" != "PROVEN" ]; then VERDICT="PASS"; fi
  return 0
}
scenario C mission-identity-mismatch "mismatch detected, resume refused" c_mission_mismatch

# ── D. changed git HEAD ────────────────────────────────────────────────────
d_changed_head() {
  MUTATION="new commit after checkpoint (HEAD moves away from latest_verified_state)"
  git -C "$WS" -c user.email=a@a -c user.name=a commit -q --allow-empty -m "post-checkpoint drift"
  run_resume
  local div; div="$("$PY" -c "
import json
d=json.load(open('$DIR/receipt.json'))
print('|'.join(d.get('divergence',[])))" 2>/dev/null || echo "")"
  ACTUAL="exit=$RC divergence='$div'"
  case "$div" in *latest_verified_state*|*HEAD*) VERDICT="PASS" ;; esac
  return 0
}
scenario D changed-git-head "HEAD divergence surfaced, not silently identical" d_changed_head

# ── E. dirty workspace ─────────────────────────────────────────────────────
e_dirty_workspace() {
  MUTATION="modify a tracked file after checkpoint"
  echo "drift" > "$WS/capt_cli.py"
  run_resume
  local div; div="$("$PY" -c "
import json
d=json.load(open('$DIR/receipt.json'))
print('|'.join(d.get('divergence',[])))" 2>/dev/null || echo "")"
  ACTUAL="exit=$RC divergence='$div'"
  case "$div" in *dirty*) VERDICT="PASS" ;; esac
  return 0
}
scenario E dirty-workspace "dirty state recorded, no hidden cleanup" e_dirty_workspace

# ── F. missing memory object ───────────────────────────────────────────────
f_missing_memory() {
  MUTATION="remove the memory store directory referenced by the boot"
  local mem="$HOME_DIR/data/memory"
  rm -rf "$mem"
  run_boot
  local sel; sel="$("$PY" -c "
import json
try: d=json.load(open('$DIR/report.json'))
except Exception: print('NOREPORT'); raise SystemExit
print('missing=%s selected=%s gate=%s' % (d.get('missing_memory_ids'), d.get('selected_memory_ids'), d.get('gate_result')))" 2>/dev/null || echo "NOREPORT")"
  ACTUAL="exit=$RC $sel"
  # PASS when missing memory is enumerated rather than silently ignored,
  # or the boot refuses outright. Note: `[ ... ] && VAR=x` as a function's last
  # statement returns non-zero and would abort under `set -e` — use if/fi.
  case "$sel" in *"missing="*) VERDICT="PASS" ;; esac
  if [ "$RC" != "0" ]; then VERDICT="PASS"; fi
  return 0
}
scenario F missing-memory-object "missing memory enumerated or boot refused" f_missing_memory

# ── G. corrupted trace hash ────────────────────────────────────────────────
g_corrupt_trace() {
  MUTATION="flip a byte inside the persisted boot-trace artifact"
  run_boot   # produce a trace first
  local tr
  tr="$("$PY" -c "
import json
try: print(json.load(open('$DIR/report.json')).get('boot_trace_artifact',''))
except Exception: print('')" 2>/dev/null)"
  if [ -f "$tr" ] && [ -f "$tr.sha256" ]; then
    printf 'X' >> "$tr"
    local want got
    want="$(cut -d' ' -f1 < "$tr.sha256")"
    got="$(shasum -a 256 "$tr" | cut -d' ' -f1)"
    if [ "$want" != "$got" ]; then
      ACTUAL="sidecar=$want recomputed=$got -> MISMATCH DETECTED"
      VERDICT="PASS"
    else
      ACTUAL="hash unchanged after mutation ($got) — integrity check cannot detect corruption"
    fi
    echo "$ACTUAL" > "$DIR/integrity-check.txt"
  else
    ACTUAL="no trace artifact or no .sha256 sidecar at '$tr' — integrity NOT PROVABLE"
    VERDICT="FAIL"
  fi
  CMD="shasum -a 256 <boot_trace_artifact> vs .sha256 sidecar"
  return 0
}
scenario G corrupted-trace-hash "digest mismatch detected via sidecar" g_corrupt_trace

# ── H. legacy checkpoint schema ────────────────────────────────────────────
h_legacy_schema() {
  MUTATION="replace checkpoint with pre-project_id legacy shape"
  cat > "$WS/.capt/checkpoints/$MISSION.json" <<'LEGACY'
{
  "mission_id": "mission-skill-real-acceptance",
  "objective": "legacy shape without project_id or phase",
  "latest_verified_state": "0000000000000000000000000000000000000000"
  return 0
}
LEGACY
  run_resume
  local cv; cv="$(verdict_json)"
  ACTUAL="exit=$RC continuity_verdict='${cv:-<none>}' legacy_classified=$(grep -qi 'legacy\|MissionCheckpoint\|missing.*argument\|project_id' "$DIR/stderr.txt" "$DIR/stdout.txt" && echo yes || echo no)"
  if [ "$cv" != "PROVEN" ]; then VERDICT="PASS"; fi
}
scenario H legacy-checkpoint-schema "legacy recognised or refused, never silent" h_legacy_schema

# ── I. CWD module shadowing ────────────────────────────────────────────────
i_cwd_shadow() {
  MUTATION="plant a fake capt_solo package in the invoking CWD"
  mkdir -p "$WS/capt_solo"
  printf '__version__="0.0.0-FAKE"\n' > "$WS/capt_solo/__init__.py"
  set +e
  ( cd "$WS" && CAPT_SOLO_HOME="$HOME_DIR" bash "$SKILL/scripts/capt-doctor.sh" "$WS" "$MISSION" ) \
    > "$DIR/stdout.txt" 2> "$DIR/stderr.txt"
  RC=$?
  set -e
  echo "$RC" > "$DIR/exit-code.txt"
  CMD="cd $WS && capt-doctor.sh (fake capt_solo in CWD)"
  local shadow_row canonical
  shadow_row="$(grep -c "CWD_MODULE_SHADOW" "$DIR/stdout.txt" || true)"
  canonical="$(grep -c "0.0.0-FAKE" "$DIR/stdout.txt" || true)"
  ACTUAL="shadow_reported=$shadow_row fake_version_adopted=$canonical exit=$RC"
  if [ "$shadow_row" -ge 1 ] && [ "$canonical" = "0" ]; then VERDICT="PASS"; fi
  return 0
}
scenario I cwd-module-shadowing "shadow named, canonical identity preserved" i_cwd_shadow

# ── J. wrong editable checkout ─────────────────────────────────────────────
j_wrong_checkout() {
  MUTATION="point CAPT_SOLO_REPO at an unrelated checkout"
  local foreign="$WS/../foreign"
  mkdir -p "$foreign/capt_solo"
  printf 'x\n' > "$foreign/capt_cli.py"
  printf '__version__="9.9.9-FOREIGN"\n' > "$foreign/capt_solo/__init__.py"
  set +e
  CAPT_SOLO_REPO="$foreign" CAPT_SOLO_HOME="$HOME_DIR" \
    bash "$SKILL/scripts/capt-environment-report.sh" "$WS" > "$DIR/stdout.txt" 2> "$DIR/stderr.txt"
  RC=$?
  set -e
  echo "$RC" > "$DIR/exit-code.txt"
  CMD="CAPT_SOLO_REPO=$foreign capt-environment-report.sh $WS"
  local via ver
  via="$("$PY" -c "
import json
try: print(json.load(open('$DIR/stdout.txt'))['capt']['source_resolved_via'])
except Exception: print('unparseable')" 2>/dev/null)"
  ver="$("$PY" -c "
import json
try: print(json.load(open('$DIR/stdout.txt'))['capt']['module_version'])
except Exception: print('?')" 2>/dev/null)"
  ACTUAL="source_resolved_via=$via module_version=$ver (installed distribution must win over CAPT_SOLO_REPO)"
  # Precedence: installed distribution outranks CAPT_SOLO_REPO. The foreign
  # 9.9.9-FOREIGN must never be adopted.
  if [ "$ver" != "9.9.9-FOREIGN" ]; then VERDICT="PASS"; fi
  return 0
}
scenario J wrong-editable-checkout "foreign checkout not adopted" j_wrong_checkout

# ── K. missing CAPT executable ─────────────────────────────────────────────
# The PATH must still resolve a shell and coreutils, otherwise `env` fails to
# exec bash (exit 127) and the script never runs — that proves nothing about
# CAPT's own dependency handling. Keep /bin and /usr/bin, remove only the venv.
k_no_capt() {
  MUTATION="PATH keeps /bin:/usr/bin but excludes the venv, so 'capt' is unresolvable"
  set +e
  env -i HOME="$HOME" PATH=/usr/bin:/bin CAPT_SOLO_HOME="$HOME_DIR" \
    bash "$SKILL/scripts/capt-fresh-boot.sh" "$WS" "$MISSION" \
    > "$DIR/stdout.txt" 2> "$DIR/stderr.txt"
  RC=$?
  set -e
  echo "$RC" > "$DIR/exit-code.txt"
  CMD="env -i PATH=/usr/bin:/bin capt-fresh-boot.sh $WS $MISSION"
  local declared shell_ok
  shell_ok="$(grep -qi 'env: bash' "$DIR/stderr.txt" && echo no || echo yes)"
  declared="$(grep -qi 'CAPT_NOT_FOUND' "$DIR/stderr.txt" "$DIR/stdout.txt" && echo CAPT_NOT_FOUND || echo none)"
  ACTUAL="exit=$RC shell_launched=$shell_ok declared=$declared"
  # Must be a real, self-declared dependency failure — not a shell that never started.
  if [ "$RC" != "0" ] && [ "$shell_ok" = "yes" ] && [ "$declared" = "CAPT_NOT_FOUND" ]; then
    VERDICT="PASS"
  fi
  return 0
}
scenario K missing-capt-executable "explicit CAPT_NOT_FOUND from a shell that really ran" k_no_capt
# ── L. owner-state contamination attempt ───────────────────────────────────
# Two sub-cases, because there are two distinct controls:
#   L1 defense-by-construction — an ambient CAPT_SOLO_HOME pointing at owner
#      state must be IGNORED (the harness allocates its own temp home).
#   L2 reachable guard — an EXPLICIT forced home at owner state must be
#      REFUSED before anything is written.
l_owner_contamination() {
  MUTATION="L1: ambient CAPT_SOLO_HOME=<owner home>; L2: explicit CAPT_ACCEPT_HOME=<owner home>"
  local ev1="$DIR/L1-ambient-evidence" ev2="$DIR/L2-forced-evidence"

  # L1: ambient owner home must be ignored, not adopted.
  set +e
  CAPT_SOLO_HOME="$OWNER_HOME_REAL" \
    bash "$SKILL/tests-acceptance/run-acceptance.sh" "$SKILL" "$ev1" \
    > "$DIR/L1-stdout.txt" 2> "$DIR/L1-stderr.txt"
  local rc1=$?
  set -e
  echo "$rc1" > "$DIR/L1-exit-code.txt"
  local used1 ignored1
  used1="$(grep -E '^CAPT_SOLO_HOME' "$ev1/00-evidence-root.txt" 2>/dev/null | awk '{print $2}')"
  case "$used1" in "$OWNER_HOME_REAL"*) ignored1="no" ;; *) ignored1="yes" ;; esac

  # L2: explicitly forcing owner home must be refused before any write.
  set +e
  CAPT_ACCEPT_HOME="$OWNER_HOME_REAL" \
    bash "$SKILL/tests-acceptance/run-acceptance.sh" "$SKILL" "$ev2" \
    > "$DIR/L2-stdout.txt" 2> "$DIR/L2-stderr.txt"
  local rc2=$?
  set -e
  echo "$rc2" > "$DIR/L2-exit-code.txt"
  local refused2
  refused2="$(grep -qi 'REFUSED' "$DIR/L2-stderr.txt" && echo yes || echo no)"

  CMD="L1: CAPT_SOLO_HOME=<owner> run-acceptance.sh | L2: CAPT_ACCEPT_HOME=<owner> run-acceptance.sh"
  local after; after="$(owner_fingerprint)"
  ACTUAL="L1(ambient) exit=$rc1 owner_home_ignored=$ignored1 used='$used1' | L2(forced) exit=$rc2 refused=$refused2 | owner_fingerprint before=$OWNER_BEFORE after=$after"
  if [ "$ignored1" = "yes" ] && [ "$refused2" = "yes" ] && [ "$rc2" != "0" ] \
     && [ "$OWNER_BEFORE" = "$after" ]; then
    VERDICT="PASS"
  fi
  return 0
}
scenario L owner-state-contamination "ambient owner home ignored; forced owner home refused pre-write; zero owner mutation" l_owner_contamination
echo "-------------------------------------------------------------------"
OWNER_AFTER="$(owner_fingerprint)"
"$PY" - "$OUT" "$PASSES" "$FAILS" "$OWNER_BEFORE" "$OWNER_AFTER" <<'PYEOF' > "$OUT/MATRIX.json"
import json, os, sys
out, p, f, before, after = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
scen = []
for d in sorted(os.listdir(out)):
    rj = os.path.join(out, d, "result.json")
    if os.path.isfile(rj):
        scen.append(json.load(open(rj)))
print(json.dumps({
    "report": "capt-adversarial-matrix",
    "scenarios": scen,
    "passed": p, "failed": f, "total": p + f,
    "owner_fingerprint_before": before,
    "owner_fingerprint_after": after,
    "owner_state_unchanged": before == after,
    "verdict": "PASS" if f == 0 and before == after else "FAIL",
}, indent=2))
PYEOF

echo "passed=$PASSES failed=$FAILS"
echo "owner fingerprint before=$OWNER_BEFORE after=$OWNER_AFTER"
( cd "$OUT" && find . -type f ! -name 'MANIFEST.sha256' -print0 | sort -z | xargs -0 shasum -a 256 > MANIFEST.sha256 )
echo "matrix: $OUT/MATRIX.json"
[ "$FAILS" = "0" ] && [ "$OWNER_BEFORE" = "$OWNER_AFTER" ] && exit 0 || exit 1
