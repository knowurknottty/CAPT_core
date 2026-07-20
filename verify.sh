#!/usr/bin/env bash
# CAPT Solo v0.1 — verification harness
# Runs memory, CTP, and KHSB subsystem tests and prints a detailed report.
set -uo pipefail

CAPT_SOLO_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_PREFIX="${CAPT_SOLO_HOME:-$HOME/.capt-solo}"
export CAPT_SOLO_HOME="$INSTALL_PREFIX"

echo "== CAPT Solo v0.1 verification =="
echo "Home: $INSTALL_PREFIX"
echo ""

PYTHONPATH="$CAPT_SOLO_SRC" python3 "$CAPT_SOLO_SRC/verify_runtime.py"
rc=$?
echo ""
if [ $rc -eq 0 ]; then
  echo "VERIFY: PASS — all subsystems healthy."
else
  echo "VERIFY: FAIL — see report above."
fi
exit $rc
