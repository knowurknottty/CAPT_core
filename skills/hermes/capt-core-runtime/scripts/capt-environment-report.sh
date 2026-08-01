#!/usr/bin/env bash
# capt-environment-report.sh — CAPT Core identity record (read-only).
#
# Resolves the canonical CAPT source by strict precedence and emits a JSON
# identity record. Constructs NOTHING: no CAPTRuntime, no subsystem. The single
# python invocation imports capt_solo only to read __file__ and __version__.
#
# Usage: capt-environment-report.sh [workspace]   (default: $PWD)
set -euo pipefail

WS="${1:-$PWD}"
[ -d "$WS" ] || { echo "{\"error\":\"workspace not found\",\"workspace\":\"$WS\"}"; exit 2; }
WS="$(cd "$WS" && pwd)"

# ── deterministic interpreter selection (single source of truth) ────────────
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1091
. "$HERE/capt-select-python.sh" "$WS" || { echo "{\"error\":\"interpreter selection failed\"}"; exit 2; }
PY_BIN="$CAPT_PY"

j() { printf '%s' "$1" | "$PY_BIN" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'; }

# --- git identity ---
GIT_ROOT="$(git -C "$WS" rev-parse --show-toplevel 2>/dev/null || echo "")"
GIT_BRANCH="$(git -C "$WS" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
GIT_HEAD="$(git -C "$WS" rev-parse HEAD 2>/dev/null || echo "")"
GIT_DIRTY="unknown"
if [ -n "$GIT_ROOT" ]; then
  if [ -z "$(git -C "$WS" status --porcelain 2>/dev/null)" ]; then GIT_DIRTY="clean"; else GIT_DIRTY="dirty"; fi
fi
WORKTREES="$(git -C "$WS" worktree list 2>/dev/null | wc -l | tr -d ' ')"

# --- capt executable ---
CAPT_BIN="$(command -v capt || echo "")"

# --- package identity (import for identity only; constructs nothing) ---
PKG_FILE="$CAPT_PKG_FILE"
PKG_VER="$CAPT_PKG_VERSION"
SHADOW=""
if [ "$PWD" != "$WS" ]; then
  CWD_FILE="$($PY_BIN -c 'import capt_solo;print(capt_solo.__file__)' 2>/dev/null || echo "")"
  [ -n "$CWD_FILE" ] && [ "$CWD_FILE" != "$PKG_FILE" ] && SHADOW="$CWD_FILE"
fi
PKG_LOCATION="$($PY_BIN -m pip show capt-solo 2>/dev/null | awk -F': ' '/^Location:/{print $2}' || echo "")"
PKG_EDITABLE="$CAPT_PKG_EDITABLE"
DOCTOR_VER="$(capt doctor 2>/dev/null | awk '/package.version/{getline;getline;print $2}' || echo "")"

# --- source precedence resolution ---
SOURCE_ROOT=""; SOURCE_VIA=""
if [ -n "$PKG_EDITABLE" ]; then
  SOURCE_ROOT="$PKG_EDITABLE"; SOURCE_VIA="installed-distribution(editable)"
elif [ -n "$PKG_LOCATION" ] && [ -n "$PKG_FILE" ]; then
  SOURCE_ROOT="$PKG_LOCATION"; SOURCE_VIA="installed-distribution"
elif [ -n "${CAPT_SOLO_REPO:-}" ] && [ -f "${CAPT_SOLO_REPO}/capt_cli.py" ] && [ -d "${CAPT_SOLO_REPO}/capt_solo" ]; then
  SOURCE_ROOT="$CAPT_SOLO_REPO"; SOURCE_VIA="CAPT_SOLO_REPO"
elif [ -f "$WS/capt_cli.py" ] && [ -d "$WS/capt_solo" ]; then
  SOURCE_ROOT="$WS"; SOURCE_VIA="repository-relative"
else
  SOURCE_VIA="unresolved"
fi

# foreign-checkout check: imported module must live under the resolved root
CHECKOUT_VERDICT="NOT_PROVEN"
if [ -n "$PKG_FILE" ] && [ -n "$SOURCE_ROOT" ]; then
  case "$PKG_FILE" in
    "$SOURCE_ROOT"/*) CHECKOUT_VERDICT="PASS" ;;
    *)                CHECKOUT_VERDICT="FAIL:WRONG_CHECKOUT" ;;
  esac
fi

# --- CAPT home + stores ---
CAPT_HOME_RESOLVED="${CAPT_SOLO_HOME:-$HOME/.capt-solo}"
CKPT_DIR="$WS/.capt/checkpoints"
CKPT_COUNT=0
[ -d "$CKPT_DIR" ] && CKPT_COUNT="$(find "$CKPT_DIR" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l | tr -d ' ')"

# --- plugin parity ---
PLUGIN_INSTALLED="$HOME/.hermes/plugins/capt-solo/__init__.py"
PLUGIN_SOURCE="${SOURCE_ROOT:-$WS}/capt_solo/plugin/__init__.py"
PLUGIN_PARITY="NOT_PROVEN"
if [ -f "$PLUGIN_INSTALLED" ] && [ -f "$PLUGIN_SOURCE" ]; then
  if [ "$(shasum -a 256 "$PLUGIN_INSTALLED" | cut -d' ' -f1)" = "$(shasum -a 256 "$PLUGIN_SOURCE" | cut -d' ' -f1)" ]; then
    PLUGIN_PARITY="PASS"; else PLUGIN_PARITY="WARN:STALE_PLUGIN"; fi
elif [ ! -f "$PLUGIN_INSTALLED" ]; then
  PLUGIN_PARITY="WARN:PLUGIN_NOT_INSTALLED"
fi

# --- installed skill provenance ---
SKILL_DIR="$HOME/.hermes/skills/capt/capt-core-runtime"
SKILL_PROV="$SKILL_DIR/.install-provenance.json"
SKILL_INSTALLED="absent"
[ -f "$SKILL_DIR/SKILL.md" ] && SKILL_INSTALLED="present"
SKILL_SHA=""
[ -f "$SKILL_PROV" ] && SKILL_SHA="$($PY_BIN -c 'import json,sys;print(json.load(open(sys.argv[1])).get("content_digest",""))' "$SKILL_PROV" 2>/dev/null || echo "")"

# --- secrets: presence + mechanism ONLY, never values ---
secret_presence() { if [ -n "${!1:-}" ]; then echo "present (env)"; else echo "absent"; fi; }
LMS="$(secret_presence LM_STUDIO_API_KEY)"
MODEL_ENDPOINT_SET="$([ -n "${CAPT_MODEL_ENDPOINT:-}" ] && echo yes || echo no)"
MODEL_ID_SET="$([ -n "${CAPT_MODEL_ID:-}" ] && echo yes || echo no)"

cat <<EOF
{
  "report": "capt-environment-report",
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "workspace": $(j "$WS"),
  "interpreter": {
    "executable": $(j "$CAPT_PY"),
    "selection_source": $(j "$CAPT_PY_SOURCE"),
    "version": $(j "$CAPT_PY_VERSION"),
    "prefix": $(j "$CAPT_PY_PREFIX"),
    "disagrees_with_capt_console_script": $(j "$CAPT_PY_DISAGREES"),
    "capt_solo_module": $(j "$PKG_FILE"),
    "capt_solo_version": $(j "$PKG_VER"),
    "editable_location": $(j "$PKG_EDITABLE")
  },
  "git": {
    "root": $(j "$GIT_ROOT"),
    "branch": $(j "$GIT_BRANCH"),
    "head": $(j "$GIT_HEAD"),
    "state": $(j "$GIT_DIRTY"),
    "worktree_count": $WORKTREES
  },
  "python": {
    "executable": $(j "$PY_BIN"),
    "version": $(j "$CAPT_PY_VERSION"),
    "prefix": $(j "$CAPT_PY_PREFIX"),
    "venv_activated": "none (selection is explicit, not via shell activation)"
  },
  "capt": {
    "executable": $(j "$CAPT_BIN"),
    "module_file": $(j "$PKG_FILE"),
    "module_version": $(j "$PKG_VER"),
    "doctor_version": $(j "$DOCTOR_VER"),
    "site_packages": $(j "$PKG_LOCATION"),
    "editable_location": $(j "$PKG_EDITABLE"),
    "source_root": $(j "$SOURCE_ROOT"),
    "source_resolved_via": $(j "$SOURCE_VIA"),
    "checkout_verdict": $(j "$CHECKOUT_VERDICT"),
    "cwd_shadowing_module": $(j "$SHADOW"),
    "capt_solo_home": $(j "$CAPT_HOME_RESOLVED"),
    "capt_solo_home_env_set": $([ -n "${CAPT_SOLO_HOME:-}" ] && echo true || echo false),
    "workspace_checkpoint_dir": $(j "$CKPT_DIR"),
    "workspace_checkpoint_count": $CKPT_COUNT
  },
  "plugin": {
    "installed_path": $(j "$PLUGIN_INSTALLED"),
    "source_path": $(j "$PLUGIN_SOURCE"),
    "parity": $(j "$PLUGIN_PARITY")
  },
  "skill": {
    "installed_path": $(j "$SKILL_DIR"),
    "installed": $(j "$SKILL_INSTALLED"),
    "content_digest": $(j "$SKILL_SHA")
  },
  "credentials": {
    "note": "presence and mechanism only; values are never read, printed, hashed, or persisted",
    "LM_STUDIO_API_KEY": $(j "$LMS"),
    "CAPT_MODEL_ENDPOINT_set": $(j "$MODEL_ENDPOINT_SET"),
    "CAPT_MODEL_ID_set": $(j "$MODEL_ID_SET")
  }
}
EOF

case "$CHECKOUT_VERDICT" in FAIL:*) exit 3 ;; esac
[ "$SOURCE_VIA" = "unresolved" ] && exit 4
exit 0
