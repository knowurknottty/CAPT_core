#!/usr/bin/env bash
# External replay proof for the capt-core-runtime skill.
#
# Proves that CAPT continuity is recoverable from EXPLICITLY PERSISTED ARTIFACTS
# alone, in a fresh clone at a new path, in a fresh process, with no transcript,
# no shared shell state, and no shared temp directory.
#
# What is transferred: the checkpoint + CAPT state + mission metadata + memory
# objects + workspace metadata + skill files, enumerated in a replay manifest.
# What is NOT transferred: the transcript, the original processes, the original
# temp root, or any environment variable not recorded in the manifest.
#
# Semantic (not byte) identity is the standard: session ids, timestamps, PIDs,
# filesystem roots and ContextPack digests are legitimately per-process.
#
# Usage: run-external-replay.sh <skill-dir> <out-dir> [replay-root]
set -Eeuo pipefail

RAW_SKILL="${1:?usage: run-external-replay.sh <skill-dir> <out-dir> [replay-root]}"
RAW_OUT="${2:?usage: run-external-replay.sh <skill-dir> <out-dir> [replay-root]}"
REPLAY_ROOT="${3:-/Users/knowurknot/capt-core-external-replay}"

SKILL="$(cd "$RAW_SKILL" && pwd -P)"
mkdir -p "$RAW_OUT"; OUT="$(cd "$RAW_OUT" && pwd -P)"
CANON="${CAPT_CANONICAL_REPO:-/Users/knowurknot/capt-solo}"
PY="${CAPT_ACCEPT_PY:-$CANON/.venv/bin/python}"
export CAPT_ACCEPT_PY="$PY"   # every script selects this interpreter deterministically
export PATH="$(dirname "$PY")${PATH:+:$PATH}"   # make `capt` console script resolvable
MISSION="mission-external-replay"

OWNER_HOME_REAL="$(cd "$HOME" && pwd -P)/.capt-solo"
owner_fp() {
  local n=0 c=0
  [ -d "$OWNER_HOME_REAL" ] && n="$(find "$OWNER_HOME_REAL" -type f 2>/dev/null | wc -l | tr -d ' ')"
  [ -d "$CANON/.capt/checkpoints" ] && c="$(find "$CANON/.capt/checkpoints" -maxdepth 1 -name '*.json' | wc -l | tr -d ' ')"
  echo "$n:$c"
}
OWNER_BEFORE="$(owner_fp)"

case "$REPLAY_ROOT" in
  ""|"/"|"$HOME") echo "REFUSED: unsafe replay root" >&2; exit 2 ;;
  "$CANON"|"$CANON"/*) echo "REFUSED: replay root inside canonical repo" >&2; exit 2 ;;
esac

echo "external replay"
echo "  skill:       $SKILL"
echo "  out:         $OUT"
echo "  replay root: $REPLAY_ROOT"
echo "-------------------------------------------------------------------"

# ── ORIGIN: build a real mission in an isolated origin workspace ───────────
ORIGIN="$(mktemp -d /tmp/capt-replay-origin.XXXXXX)"
O_WS="$ORIGIN/ws"; O_HOME="$ORIGIN/home"
mkdir -p "$O_WS"
git init -q "$O_WS"
git -C "$O_WS" -c user.email=a@a -c user.name=a commit -q --allow-empty -m "origin init"
cp "$CANON/capt_cli.py" "$O_WS/capt_cli.py"
O_HEAD="$(git -C "$O_WS" rev-parse HEAD)"

# CAPT binds a checkpoint's project_id to the workspace directory name and
# refuses a mismatch with block_codes=[FOREIGN_WORKSPACE]. That guard is
# correct and must not be worked around: seed project_id = basename(workspace).
O_PROJECT="$(basename "$O_WS")"
CAPT_SOLO_HOME="$O_HOME" "$PY" "$O_WS/capt_cli.py" mission checkpoint \
  --mission-id "$MISSION" --project-id "$O_PROJECT" \
  --objective "prove persisted-state recovery in a fresh clone" \
  --phase "PHASE_EXTERNAL_REPLAY" --next "verify replay continuity" \
  --head "$O_HEAD" > "$OUT/origin-seed.txt" 2>&1

echo "== origin: boot + checkpoint =="
CAPT_SOLO_HOME="$O_HOME" bash "$SKILL/scripts/capt-fresh-boot.sh" "$O_WS" "$MISSION" \
  --report-out "$OUT/origin-boot-report.json" > /dev/null 2>&1 || true
CAPT_SOLO_HOME="$O_HOME" bash "$SKILL/scripts/capt-checkpoint.sh" "$O_WS" "$MISSION" \
  --receipt-out "$OUT/origin-checkpoint-receipt.json" > "$OUT/origin-checkpoint.txt" 2>&1 || true
echo "origin checkpoint: $("$PY" -c "import json;print(json.load(open('$OUT/origin-checkpoint-receipt.json'))['checkpoint_id'])")"

# ── TRANSFER: only explicitly enumerated persisted artifacts ───────────────
rm -rf "$REPLAY_ROOT"
mkdir -p "$REPLAY_ROOT/ws" "$REPLAY_ROOT/home"

# Fresh clone of the workspace (git history only — no working temp state).
#
# COMPATIBILITY CONSTRAINT (discovered, not worked around): CAPT binds a
# checkpoint's project_id to the workspace DIRECTORY NAME and refuses a
# mismatch with block_codes=[FOREIGN_WORKSPACE]. A legitimate replay therefore
# reproduces the workspace basename at a different filesystem root. Renaming
# the directory is a genuine foreign workspace and CAPT is right to block it.
CLONE_NAME="$(basename "$O_WS")"
R_CLONE="$REPLAY_ROOT/$CLONE_NAME"
git clone -q "$O_WS" "$R_CLONE"
cp "$CANON/capt_cli.py" "$R_CLONE/capt_cli.py"

# CAPT persisted state: workspace checkpoint store + CAPT home data
mkdir -p "$R_CLONE/.capt"
cp -R "$O_WS/.capt/." "$R_CLONE/.capt/" 2>/dev/null || true
cp -R "$O_HOME/." "$REPLAY_ROOT/home/" 2>/dev/null || true

# the skill itself (as an installed package would be)
mkdir -p "$REPLAY_ROOT/skill"
cp -R "$SKILL/." "$REPLAY_ROOT/skill/"

CLONE_NAME="$CLONE_NAME" "$PY" - "$REPLAY_ROOT" "$MISSION" "$O_HEAD" "$SKILL" <<'PYEOF' > "$OUT/replay-input-manifest.json"
import json, os, sys, hashlib
root, mission, head, skill = sys.argv[1:5]
items = []
for base in (os.path.join(root, os.environ.get("CLONE_NAME","ws"), ".capt"), os.path.join(root, "home")):
    for dirpath, _, files in os.walk(base):
        for fn in files:
            p = os.path.join(dirpath, fn)
            try:
                b = open(p, "rb").read()
            except Exception:
                continue
            items.append({"path": os.path.relpath(p, root),
                          "bytes": len(b),
                          "sha256": hashlib.sha256(b).hexdigest()})
print(json.dumps({
    "manifest": "capt-external-replay-input",
    "mission_id": mission,
    "origin_head": head,
    "replay_root": root,
    "transferred": {
        "workspace": "fresh git clone (history only)",
        "capt_workspace_state": "<workspace>/.capt (checkpoints, evidence)",
        "capt_home_state": "home (memory, ctp, evidence)",
        "skill": "skill/ (copied skill package)",
    },
    "explicitly_not_transferred": [
        "transcript / conversation history",
        "originating shell or process state",
        "original temp directory",
        "environment variables not listed in replay-environment.json",
    ],
    "artifact_count": len(items),
    "artifacts": sorted(items, key=lambda x: x["path"]),
}, indent=2))
PYEOF
shasum -a 256 "$OUT/replay-input-manifest.json" | awk '{print $1}' > "$OUT/replay-input-manifest.sha256"
echo "transferred artifacts: $("$PY" -c "import json;print(json.load(open('$OUT/replay-input-manifest.json'))['artifact_count'])")"

# ── REPLAY: fresh shell, fresh process, only the transferred artifacts ─────
R_WS="$R_CLONE"; R_HOME="$REPLAY_ROOT/home"
cat > "$OUT/replay-environment.json" <<EOF
{
  "report": "capt-external-replay-environment",
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "replay_root": "$REPLAY_ROOT",
  "workspace": "$R_WS",
  "capt_solo_home": "$R_HOME",
  "python": "$PY",
  "hostname": "$(hostname)",
  "declared_env": ["CAPT_SOLO_HOME", "PATH", "HOME"],
  "transcript_inherited": false,
  "shares_temp_root_with_origin": false,
  "origin_temp_root": "$ORIGIN"
}
EOF

echo "capt-resume-check.sh $R_WS $MISSION  (fresh process, CAPT_SOLO_HOME=$R_HOME)" \
  > "$OUT/replay-command.txt"

set +e
env -i HOME="$HOME" PATH="/usr/bin:/bin:$CANON/.venv/bin" CAPT_SOLO_HOME="$R_HOME" \
  bash "$REPLAY_ROOT/skill/scripts/capt-resume-check.sh" "$R_WS" "$MISSION" \
  --receipt-out "$OUT/replay-receipt.json" \
  > "$OUT/replay-stdout.txt" 2> "$OUT/replay-stderr.txt"
RRC=$?
set -e
echo "$RRC" > "$OUT/replay-exit-code.txt"
echo "replay exit: $RRC"

# ── COMPARE: semantic identity, with nondeterministic fields excluded ──────
"$PY" - "$OUT" "$MISSION" "$ORIGIN" "$REPLAY_ROOT" <<'PYEOF' > "$OUT/replay-comparison.json"
import json, os, sys
out, mission, origin, root = sys.argv[1:5]

def load(p):
    try: return json.load(open(os.path.join(out, p)))
    except Exception: return {}

ob = load("origin-boot-report.json")
oc = load("origin-checkpoint-receipt.json")
rr = load("replay-receipt.json")

identical, differing, checks = [], [], []
def must_match(field, a, b):
    ok = (a == b) and a not in (None, "")
    identical.append({"field": field, "origin": a, "replay": b, "match": ok})
    checks.append({"check": f"identical:{field}", "verdict": "PASS" if ok else "FAIL",
                   "detail": f"origin={a} replay={b}"})
def must_differ(field, a, b, why):
    ok = a != b
    differing.append({"field": field, "origin": a, "replay": b,
                      "expected_to_differ": True, "differs": ok, "reason": why})
    checks.append({"check": f"differs:{field}", "verdict": "PASS" if ok else "FAIL",
                   "detail": f"origin={a} replay={b} ({why})"})

must_match("mission_id", ob.get("mission_id"), rr.get("mission_id"))
must_match("checkpoint_id", oc.get("checkpoint_id"), rr.get("checkpoint_id"))
must_match("next_justified_action", ob.get("next_justified_action"), rr.get("next_justified_action"))

must_differ("session_id", ob.get("session_id"), rr.get("session_id"),
            "a session is per-process by design")
must_differ("contextpack_digest", ob.get("contextpack_digest"),
            (rr.get("post_resume") or {}).get("contextpack_digest"),
            "a new ContextPack is built on every boot")
must_differ("workspace_root", ob.get("workspace_root"), rr.get("workspace"),
            "replay runs from a different filesystem root")

for name, ok, detail in [
    ("continuity_proven", rr.get("continuity_verdict") == "PROVEN", str(rr.get("continuity_verdict"))),
    ("no_transcript_inheritance", rr.get("transcript_inheritance") == "none", str(rr.get("transcript_inheritance"))),
    ("fresh_process", rr.get("reconstructed_in") == "fresh-process", str(rr.get("reconstructed_in"))),
    ("gate_pass", (rr.get("post_resume") or {}).get("gate_result") == "PASS",
     str((rr.get("post_resume") or {}).get("gate_result"))),
    ("recovered_from_capt_state", "CAPT state" in (rr.get("source") or ""), str(rr.get("source"))),
    ("hermes_mode_not_overclaimed", rr.get("hermes_session_mode") == "BOOTSTRAP_DEGRADED",
     str(rr.get("hermes_session_mode"))),
]:
    checks.append({"check": name, "verdict": "PASS" if ok else "FAIL", "detail": detail})

print(json.dumps({
    "report": "capt-external-replay-comparison",
    "standard": "semantic identity — byte-identical receipts are NOT expected",
    "fields_expected_identical": identical,
    "fields_expected_to_differ": differing,
    "checks": checks,
    "verdict": "PASS" if all(c["verdict"] == "PASS" for c in checks) else "FAIL",
}, indent=2))
PYEOF

OWNER_AFTER="$(owner_fp)"
"$PY" - "$OUT" "$OWNER_BEFORE" "$OWNER_AFTER" "$RRC" <<'PYEOF' > "$OUT/replay-verdict.json"
import json, os, sys
out, before, after, rrc = sys.argv[1:5]
cmp_ = json.load(open(os.path.join(out, "replay-comparison.json")))
ok = cmp_["verdict"] == "PASS" and before == after and rrc == "0"
print(json.dumps({
    "report": "capt-external-replay-verdict",
    "replay_exit_code": int(rrc),
    "comparison_verdict": cmp_["verdict"],
    "owner_fingerprint_before": before,
    "owner_fingerprint_after": after,
    "owner_state_unchanged": before == after,
    "continuity_from_persisted_artifacts_only": ok,
    "verdict": "PASS" if ok else "FAIL",
}, indent=2))
PYEOF

"$PY" -c "
import json
c=json.load(open('$OUT/replay-comparison.json'))
for x in c['checks']: print(f\"  {x['verdict']:5} {x['check']:34} {x['detail']}\")
print('comparison:', c['verdict'])
v=json.load(open('$OUT/replay-verdict.json'))
print('replay verdict:', v['verdict'], '| owner unchanged:', v['owner_state_unchanged'])
"

( cd "$OUT" && find . -type f ! -name 'MANIFEST.sha256' -print0 | sort -z | xargs -0 shasum -a 256 > MANIFEST.sha256 )
echo "origin temp root retained: $ORIGIN"
V="$("$PY" -c "import json;print(json.load(open('$OUT/replay-verdict.json'))['verdict'])")"
[ "$V" = "PASS" ] && exit 0 || exit 1
