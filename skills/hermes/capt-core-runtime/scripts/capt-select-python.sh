#!/usr/bin/env bash
# capt-select-python.sh — deterministic CAPT interpreter selection.
#
# This is the single source of truth for "which python runs CAPT". It is
# sourced by every other capt-*.sh script and by the acceptance/adversarial/
# external-replay harnesses. No other script may call `command -v python`
# itself.
#
# Precedence (first match wins, each validated as existing + executable):
#   1. $CAPT_ACCEPT_PY            — explicit operator override (validated)
#   2. $WS/.venv/bin/python       — project-local venv, when unambiguously present
#   3. python3 from PATH
#   4. python  from PATH
#   5. otherwise: deterministic dependency failure (no silent fallback)
#
# Hard rules:
#   * The selected interpreter is recorded with its source.
#   * If an explicit override ($CAPT_ACCEPT_PY) is set but missing/non-executable,
#     selection FAILS precisely (exit 2) — no hidden fallback to PATH.
#   * We never silently switch interpreters. If the interpreter that downstream
#     `capt` console scripts actually use disagrees with the one we selected,
#     that disagreement is reported, not hidden.
#   * No correctness claim may depend on an activated shell or ambient venv.
#
# Outputs (caller-visible variables):
#   CAPT_PY            selected python executable (absolute, validated)
#   CAPT_PY_SOURCE     one of: explicit:CAPT_ACCEPT_PY | workspace-venv |
#                      path:python3 | path:python | none
#   CAPT_PY_VERSION    "Python X.Y.Z"
#   CAPT_PY_PREFIX     sys.prefix of the selected interpreter
#   CAPT_PKG_FILE      capt_solo.__file__ as imported by the selected interpreter
#   CAPT_PKG_VERSION   capt_solo.__version__
#   CAPT_PKG_EDITABLE  editable project location, when applicable
#   CAPT_PY_DISAGREES  "yes"/"no" — whether `capt`'s own interpreter differs
#
# Usage:  source capt-select-python.sh [workspace]
#         then inspect $CAPT_PY etc. Selection failure prints to stderr and
#         returns 2 (so `set -e` callers abort). A successful selection returns 0.
set -uo pipefail

_csp_ws="${1:-}"

_csp_fail() { echo "CAPT_PY_SELECTION_FAILED: $*" >&2; return 2; }

# 1. explicit override
if [ -n "${CAPT_ACCEPT_PY:-}" ]; then
  if [ -x "$CAPT_ACCEPT_PY" ]; then
    CAPT_PY="$(cd "$(dirname "$CAPT_ACCEPT_PY")" && pwd -P)/$(basename "$CAPT_ACCEPT_PY")"
    CAPT_PY_SOURCE="explicit:CAPT_ACCEPT_PY"
  else
    _csp_fail "CAPT_ACCEPT_PY='$CAPT_ACCEPT_PY' is set but missing or not executable"
    return 2
  fi
# 2. project-local venv
elif [ -n "$_csp_ws" ] && [ -x "$_csp_ws/.venv/bin/python" ]; then
  CAPT_PY="$(cd "$_csp_ws/.venv/bin" && pwd -P)/python"
  CAPT_PY_SOURCE="workspace-venv"
# 3/4. PATH
elif command -v python3 >/dev/null 2>&1; then
  CAPT_PY="$(command -v python3)"; CAPT_PY_SOURCE="path:python3"
elif command -v python >/dev/null 2>&1; then
  CAPT_PY="$(command -v python)"; CAPT_PY_SOURCE="path:python"
# 5. deterministic failure
else
  _csp_fail "no python interpreter found (set CAPT_ACCEPT_PY or install python3)"
  return 2
fi

# Validate the selected interpreter actually runs.
CAPT_PY_VERSION="$($CAPT_PY --version 2>&1 || echo unknown)"
CAPT_PY_PREFIX="$($CAPT_PY -c 'import sys;print(sys.prefix)' 2>/dev/null || echo "")"
if [ -z "$CAPT_PY_PREFIX" ]; then
  _csp_fail "selected interpreter '$CAPT_PY' cannot start"
  return 2
fi

# Package identity via the SELECTED interpreter (isolated probe, -P, to match
# the `capt` console script's real resolution — see capt-doctor.sh notes).
CAPT_PKG_FILE="$($CAPT_PY -P -c 'import capt_solo;print(capt_solo.__file__)' 2>/dev/null || echo "")"
CAPT_PKG_VERSION="$($CAPT_PY -P -c 'import capt_solo;print(getattr(capt_solo,"__version__","unknown"))' 2>/dev/null || echo "")"
CAPT_PKG_EDITABLE="$($CAPT_PY -m pip show capt-solo 2>/dev/null | awk -F': ' '/^Editable project location:/{print $2}')"

# Export all caller-visible variables so they survive into heredoc/python
# subprocesses (os.environ), not just the sourcing shell.
export CAPT_PY CAPT_PY_SOURCE CAPT_PY_VERSION CAPT_PY_PREFIX
export CAPT_PKG_FILE CAPT_PKG_VERSION CAPT_PKG_EDITABLE CAPT_PY_DISAGREES

# Disagreement detection: which python does the `capt` console script use?
CAPT_BIN="$(command -v capt 2>/dev/null || echo "")"
CAPT_PY_DISAGREES="no"
if [ -n "$CAPT_BIN" ]; then
  _csp_tmp="$(mktemp /tmp/capt-select-python.XXXXXX.py)"
  cat > "$_csp_tmp" <<'PY'
import sys, os
binp = sys.argv[1]
try:
    with open(binp) as f:
        first = f.readline()
    if first.startswith("#!"):
        print(first[2:].strip().split()[0] if first[2:].strip() else "")
    else:
        print("")
except Exception:
    print("")
PY
  _csp_capt_py="$($CAPT_PY "$_csp_tmp" "$CAPT_BIN" 2>/dev/null || echo "")"
  rm -f "$_csp_tmp"
  if [ -n "$_csp_capt_py" ] && [ "$_csp_capt_py" != "$CAPT_PY" ]; then
    CAPT_PY_DISAGREES="yes"
  fi
fi

return 0
