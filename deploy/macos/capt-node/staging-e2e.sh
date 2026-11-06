#!/bin/bash
# R0.4 macOS staging: prove CAPT Node service-identity isolation with REAL macOS users.
#
#   sudo bash deploy/macos/capt-node/staging-e2e.sh            # create disposable accounts, run, receipt
#   sudo bash deploy/macos/capt-node/staging-e2e.sh teardown   # delete the disposable accounts and venv
#
# Disposable, staging-only identities (never the production ones):
#   _captnodestg        hidden service account (uid 450-499, shell /usr/bin/false, home /var/empty,
#                       no password, not admin) — runs the Node under test
#   captnodestgclients  socket client group: the human account and _captnodestg only
# The human account (default: the user who invoked sudo) owns a DISPOSABLE token created by the
# test; the agent account (default: agent) must reach nothing. No live credential, Keychain item,
# LaunchAgent, LaunchDaemon, runtime or ledger is read, modified or restarted. The receipt records
# the live CAPT process table before and after so that is checkable.
set -euo pipefail
[[ "$(uname -s)" == "Darwin" ]] || { echo "macOS only" >&2; exit 2; }
[[ "$(id -u)" -eq 0 ]] || { echo "run with sudo" >&2; exit 2; }

SVC=_captnodestg
CLIENTS=captnodestgclients
HUMAN="${CAPT_NODE_STG_HUMAN:-${SUDO_USER:-}}"
AGENT="${CAPT_NODE_STG_AGENT:-agent}"
VENV=/Users/Shared/capt-node-stg-venv
SRC="$(cd "$(dirname "$0")/../../.." && pwd)"
MODE="${1:-run}"

free_id() { # $1 = Users|Groups, $2 = UniqueID|PrimaryGroupID
  local used
  used="$(dscl . -list "/$1" "$2" | awk '{print $2}')"
  for i in $(seq 450 499); do
    grep -qx "$i" <<<"$used" || { echo "$i"; return 0; }
  done
  echo "no free id in 450-499 for $1" >&2; return 1
}

if [[ "$MODE" == "teardown" ]]; then
  dscl . -read "/Users/$SVC" >/dev/null 2>&1 && dscl . -delete "/Users/$SVC"
  dscl . -read "/Groups/$CLIENTS" >/dev/null 2>&1 && dscl . -delete "/Groups/$CLIENTS"
  dscl . -read "/Groups/$SVC" >/dev/null 2>&1 && dscl . -delete "/Groups/$SVC"
  [[ -d "$VENV" && ! -L "$VENV" ]] && rm -rf "$VENV"
  echo "teardown complete: $SVC, $CLIENTS, $VENV removed"
  exit 0
fi
[[ "$MODE" == "run" ]] || { echo "usage: $0 [run|teardown]" >&2; exit 2; }
[[ -n "$HUMAN" && "$HUMAN" != root ]] || { echo "set CAPT_NODE_STG_HUMAN or run via sudo from the human account" >&2; exit 2; }
id "$HUMAN" >/dev/null && id "$AGENT" >/dev/null

# --- disposable service account and groups
if ! dscl . -read "/Groups/$SVC" >/dev/null 2>&1; then
  gid="$(free_id Groups PrimaryGroupID)"
  dscl . -create "/Groups/$SVC"
  dscl . -create "/Groups/$SVC" PrimaryGroupID "$gid"
  dscl . -create "/Groups/$SVC" RealName "CAPT Node staging service"
  dscl . -create "/Groups/$SVC" Password '*'
fi
if ! dscl . -read "/Users/$SVC" >/dev/null 2>&1; then
  uid="$(free_id Users UniqueID)"
  dscl . -create "/Users/$SVC"
  dscl . -create "/Users/$SVC" UniqueID "$uid"
  dscl . -create "/Users/$SVC" PrimaryGroupID "$(dscl . -read "/Groups/$SVC" PrimaryGroupID | awk '{print $2}')"
  dscl . -create "/Users/$SVC" UserShell /usr/bin/false
  dscl . -create "/Users/$SVC" NFSHomeDirectory /var/empty
  dscl . -create "/Users/$SVC" RealName "CAPT Node staging service"
  dscl . -create "/Users/$SVC" IsHidden 1
  dscl . -create "/Users/$SVC" Password '*'
fi
if ! dscl . -read "/Groups/$CLIENTS" >/dev/null 2>&1; then
  dscl . -create "/Groups/$CLIENTS"
  dscl . -create "/Groups/$CLIENTS" PrimaryGroupID "$(free_id Groups PrimaryGroupID)"
  dscl . -create "/Groups/$CLIENTS" RealName "CAPT Node staging clients"
  dscl . -create "/Groups/$CLIENTS" Password '*'
fi
dseditgroup -o edit -a "$HUMAN" -t user "$CLIENTS"
dseditgroup -o edit -a "$SVC" -t user "$CLIENTS"
if dseditgroup -o checkmember -m "$AGENT" "$CLIENTS" >/dev/null 2>&1; then
  echo "$AGENT must not be a member of $CLIENTS" >&2; exit 3
fi
if dseditgroup -o checkmember -m "$SVC" admin >/dev/null 2>&1; then
  echo "$SVC must not be an admin" >&2; exit 3
fi

# --- root-owned interpreter the service account can execute but not modify
if [[ ! -x "$VENV/bin/python" ]]; then
  PYBASE=""
  for c in /opt/homebrew/opt/python@3.13/bin/python3.13 /opt/homebrew/opt/python@3.12/bin/python3.12 \
           /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    [[ -x "$c" ]] && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' && { PYBASE="$c"; break; }
  done
  [[ -n "$PYBASE" ]] || { echo "no python >= 3.10 found" >&2; exit 2; }
  "$PYBASE" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --quiet 'cryptography>=47' pytest
  chown -R root:wheel "$VENV"
  chmod -R a+rX,go-w "$VENV"
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$SRC/evidence/r04"
mkdir -p "$OUT"
RECEIPT="$OUT/macos_node_service_identity_${STAMP}.txt"
live_capt() { ps -axo pid=,uid=,lstart=,command= | grep -i '[c]apt' | grep -v staging-e2e | grep -v pytest || true; }
BEFORE="$(live_capt)"
{
  echo "CAPT R0.4 macOS Node service-identity staging receipt"
  echo "utc: $STAMP"
  echo "source: $(git -C "$SRC" rev-parse HEAD 2>/dev/null || echo unknown) dirty=$(git -C "$SRC" status --porcelain 2>/dev/null | grep -v '^?? evidence/' | wc -l | tr -d ' ')"
  echo "macos: $(sw_vers -productVersion) $(uname -m)"
  echo "service: $(id "$SVC")"
  echo "human:   $(id "$HUMAN")"
  echo "agent:   $(id "$AGENT")"
  echo "python:  $("$VENV/bin/python" -V) cryptography=$("$VENV/bin/python" -c 'import cryptography;print(cryptography.__version__)')"
  echo "--- live CAPT processes before"
  echo "$BEFORE"
  echo "--- pytest"
} | tee "$RECEIPT"

set +e
env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/var/root PYTHONDONTWRITEBYTECODE=1 \
  CAPT_NODE_E2E_REQUIRED=1 CAPT_NODE_E2E_SVC="$SVC" CAPT_NODE_E2E_HUMAN="$HUMAN" \
  CAPT_NODE_E2E_AGENT="$AGENT" CAPT_NODE_E2E_CLIENTS="$CLIENTS" CAPT_NODE_E2E_PYTHON="$VENV/bin/python" \
  "$VENV/bin/python" -m pytest -q -rs -p no:cacheprovider \
  --junitxml="$OUT/macos_node_service_identity_${STAMP}.xml" \
  "$SRC/tests/capt_runtime/test_node_service_identity_e2e.py" 2>&1 | tee -a "$RECEIPT"
rc="${PIPESTATUS[0]}"
set -e

AFTER="$(live_capt)"
{
  echo "--- live CAPT processes after"
  echo "$AFTER"
  if [[ "$(awk '{print $1,$2,$3,$4,$5,$6,$7}' <<<"$BEFORE")" == "$(awk '{print $1,$2,$3,$4,$5,$6,$7}' <<<"$AFTER")" ]]; then
    echo "live runtime: unchanged (same pids, uids, start times)"
  else
    echo "live runtime: CHANGED — inspect the two tables above"
    rc=4
  fi
  echo "exit: $rc"
} | tee -a "$RECEIPT"
chown -R "$HUMAN" "$OUT"
shasum -a 256 "$RECEIPT" "$OUT/macos_node_service_identity_${STAMP}.xml" 2>/dev/null || true
exit "$rc"
