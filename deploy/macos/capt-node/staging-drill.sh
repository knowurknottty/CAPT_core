#!/bin/bash
# R0.4 R3 staging drill: run the whole deployment kit against the STAGING prefix with
# disposable accounts, inject failures, roll back and uninstall. Production paths, the live
# Node, the bridge and the runtime are not touched (the receipt checks the live process table).
#
#   sudo bash deploy/macos/capt-node/staging-drill.sh
set -uo pipefail
[[ "$(uname -s)" == "Darwin" && "$(id -u)" -eq 0 ]] || { echo "macOS, with sudo" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"; SRC="$(cd "$HERE/../../.." && pwd)"
HUMAN="${CAPT_NODE_HUMAN:-${SUDO_USER:-}}"; AGENT="${CAPT_NODE_AGENT:-agent}"
[[ -n "$HUMAN" && "$HUMAN" != root ]] || { echo "run via sudo from the human account" >&2; exit 2; }
COMMIT="$(git -c safe.directory="$SRC" -C "$SRC" rev-parse HEAD)"
[[ -z "$(git -c safe.directory="$SRC" -C "$SRC" status --porcelain --untracked-files=no)" ]] || { echo "source tree has edits; drill needs a clean commit" >&2; exit 2; }
I="$HERE/install.sh"; PREFIX=/Library/CAPTNodeStaging; LABEL=online.inversionlabs.capt-node-staging; SVC=_captnodestg
APPROVE="CAPT_NODE_ACTIVATE=I-APPROVE-R04-CUTOVER"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"; OUT="$SRC/evidence/r04"; mkdir -p "$OUT"; R="$OUT/macos_install_drill_${STAMP}.txt"
PASS=0; FAIL=0
log() { echo "$*" | tee -a "$R"; }
check() { # name, expected rc (0 = must succeed, N = must fail), command...
  local name="$1" want="$2"; shift 2
  local out rc; out="$("$@" 2>&1)"; rc=$?
  if { [[ "$want" == 0 && $rc -eq 0 ]] || [[ "$want" != 0 && $rc -ne 0 ]]; }; then PASS=$((PASS+1)); log "PASS $name (rc=$rc)"
  else FAIL=$((FAIL+1)); log "FAIL $name (rc=$rc, wanted $( [[ $want == 0 ]] && echo success || echo failure))"; fi
  sed 's/^/    /' <<<"$out" | tail -8 | tee -a "$R" >/dev/null
}
live() { ps -axo pid=,uid=,lstart=,command= | grep -i '[c]apt' | grep -v -e staging -e captnodestg -e 'capt-node-staging' | awk '{print $1,$2,$3,$4,$5,$6,$7}'; }
BEFORE="$(live)"
log "CAPT R0.4 macOS deployment-kit staging drill"; log "utc: $STAMP  source: $COMMIT  macos: $(sw_vers -productVersion)"

check "prepare (accounts, layout, pinned app, hash-pinned venv)" 0 bash "$I" --staging prepare --commit "$COMMIT"
check "app is root-owned and not writable by the service" 0 sudo -n -u "$SVC" /bin/sh -c "! test -w $PREFIX/app/capt_runtime/node/server.py && ! test -w $PREFIX/etc"
check "operator (as the human, no sudo)" 0 sudo -n -u "$HUMAN" env CAPT_NODE_HUMAN="$HUMAN" bash "$I" --staging operator
check "trust + preflight as the service uid" 0 bash "$I" --staging trust
check "node key moved: operator no longer holds it" 0 /bin/sh -c "! ls /Users/$HUMAN/.capt-node-operator-staging/.capt-node-state/node.key"
check "operator re-run after trust re-signs the capability, pairing untouched" 0 sudo -n -u "$HUMAN" env CAPT_NODE_HUMAN="$HUMAN" bash "$I" --staging operator
check "trust anchors unchanged by the re-run" 0 cmp -s "$PREFIX/trust/pairings.json" "/Users/$HUMAN/.capt-node-operator-staging/.capt-node-state/pairings.json"

# Failure drill A: a trust anchor the service can rewrite must block activation.
chown "$SVC" "$PREFIX/trust/pairings.json"
check "drill A: service-owned trust anchor refuses activation" 1 env $APPROVE bash "$I" --staging activate
chown root "$PREFIX/trust/pairings.json"
check "drill A: no daemon left running" 0 /bin/sh -c "! launchctl print system/$LABEL 2>/dev/null | grep -q 'pid = '"

check "activate without approval is refused" 1 bash "$I" --staging activate
check "activate (verifies RUNNING uid from the process table, probes as the human)" 0 env $APPROVE bash "$I" --staging activate
check "status" 0 bash "$I" --staging status

# Failure drill B: crash → launchd restarts it, still as the service uid.
PID="$(launchctl print system/$LABEL | awk '/^\tpid = /{print $3; exit}')"
kill -9 "$PID" 2>/dev/null; sleep 12
NEW="$(launchctl print system/$LABEL | awk '/^\tpid = /{print $3; exit}')"
check "drill B: crash restart keeps the service uid" 0 /bin/sh -c "[ -n '$NEW' ] && [ '$NEW' != '$PID' ] && [ \"\$(ps -o uid= -p $NEW | tr -d ' ')\" = \"$(id -u $SVC)\" ]"

# Failure drill C: launched as the HUMAN uid, the Node refuses and stays down (no uid-501 recovery).
CPL=/Library/LaunchDaemons/online.inversionlabs.capt-node-staging-as-human.plist
sed -e "s|<key>UserName</key><string>$SVC</string>|<key>UserName</key><string>$HUMAN</string>|" \
    -e "s|<key>GroupName</key><string>$SVC</string>|<key>GroupName</key><string>staff</string>|" -e "s|$LABEL|$LABEL-as-human|" \
    -e "s|$PREFIX/state/node.log|/private/tmp/capt-node-drill-c.log|g" "$PREFIX/etc/$LABEL.plist" > "$CPL"
chown root:wheel "$CPL"; chmod 0644 "$CPL"; rm -f /private/tmp/capt-node-drill-c.log
launchctl bootstrap system "$CPL"; sleep 4
check "drill C: started as the human, the Node refused (NODE_RUNNING_AS_FORBIDDEN_UID)" 0 grep -q NODE_RUNNING_AS_FORBIDDEN_UID /private/tmp/capt-node-drill-c.log
check "drill C: and was not restarted" 0 /bin/sh -c "! launchctl print system/$LABEL-as-human 2>/dev/null | grep -q 'pid = '"
launchctl bootout "system/$LABEL-as-human" 2>/dev/null; rm -f "$CPL" /private/tmp/capt-node-drill-c.log

# Failure drill D: the agent account cannot reach the socket.
check "drill D: agent cannot connect to the Node socket" 1 sudo -n -u "$AGENT" /usr/bin/python3 -I -c \
  "import socket; s=socket.socket(socket.AF_UNIX); s.connect('$PREFIX/run/capt-node.sock')"

check "rollback (stop + revoke service uid; no legacy restore)" 0 bash "$I" --staging rollback
check "after rollback: no service-uid process, no daemon" 0 /bin/sh -c "[ \"\$(pgrep -u $SVC | wc -l | tr -d ' ')\" = 0 ] && ! launchctl print system/$LABEL >/dev/null 2>&1"
check "restore-legacy is refused in staging" 1 env CAPT_NODE_ACCEPT_SAME_UID_EXPOSURE=YES bash "$I" --staging rollback --restore-legacy
check "uninstall staging" 0 bash "$I" --staging uninstall

AFTER="$(live)"
if [[ "$BEFORE" == "$AFTER" ]]; then log "live runtime: unchanged (same pids, uids, start times)"; else log "live runtime: CHANGED"; FAIL=$((FAIL+1)); log "$BEFORE"; log "---"; log "$AFTER"; fi
log "result: pass=$PASS fail=$FAIL"
chown -R "$HUMAN" "$OUT"; shasum -a 256 "$R"
[[ $FAIL -eq 0 ]]
