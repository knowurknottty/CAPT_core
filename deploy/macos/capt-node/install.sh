#!/bin/bash
# R0.4 CAPT Node service-identity deployment for macOS. Every step is explicit; nothing
# activates production without CAPT_NODE_ACTIVATE=I-APPROVE-R04-CUTOVER.
#
#   sudo  install.sh [--staging] prepare --commit <sha>   accounts, /Library layout, pinned app + venv, plist (not loaded)
#         install.sh [--staging] operator                 (as the human, no sudo) operator identity, pairing, capability
#   sudo  install.sh [--staging] trust                    node key + trust anchors into place, service config, preflight
#   sudo  CAPT_NODE_ACTIVATE=I-APPROVE-R04-CUTOVER install.sh [--staging] activate
#                                                         load the LaunchDaemon, verify the RUNNING uid, probe as the human
#         install.sh [--staging] bridge-switch            (as the human) back up and repoint the Commander bridge config
#   sudo  CAPT_NODE_ACTIVATE=I-APPROVE-R04-CUTOVER install.sh retire-legacy
#                                                         stop and disable the uid-501 LaunchAgent Node(s)
#   sudo  install.sh [--staging] status                   facts from the process table, socket and preflight
#   sudo  install.sh [--staging] rollback                 stop the service Node; leaves Commander without a Node
#   sudo  CAPT_NODE_ACCEPT_SAME_UID_EXPOSURE=YES install.sh rollback --restore-legacy
#                                                         ALSO restore the uid-501 Node: a security downgrade
#   sudo  install.sh --staging uninstall                  remove the staging daemon, prefix and accounts
#
# --staging uses /Library/CAPTNodeStaging, label …capt-node-staging, accounts _captnodestg /
# captnodestgclients and ~/.capt-node-operator-staging, so every step can be drilled without
# touching the production paths.
set -euo pipefail
[[ "$(uname -s)" == "Darwin" ]] || { echo "macOS only" >&2; exit 2; }

STAGING=0; FLAG=""
if [[ "${1:-}" == "--staging" ]]; then STAGING=1; FLAG=" --staging"; shift; fi
CMD="${1:-}"; shift || true

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$(cd "$HERE/../../.." && pwd)"
HUMAN="${CAPT_NODE_HUMAN:-${SUDO_USER:-$(id -un)}}"
HUMAN_HOME="$(dscl . -read "/Users/$HUMAN" NFSHomeDirectory | awk '{print $2}')"
AGENT="${CAPT_NODE_AGENT:-agent}"
CONTROLLER="${CAPT_NODE_CONTROLLER:-inversion-commander}"
if [[ $STAGING -eq 1 ]]; then
  PREFIX=/Library/CAPTNodeStaging; LABEL=online.inversionlabs.capt-node-staging
  ACCOUNT=_captnodestg; CLIENTS=captnodestgclients; OPERATOR="$HUMAN_HOME/.capt-node-operator-staging"
else
  PREFIX=/Library/CAPTNode; LABEL=online.inversionlabs.capt-node
  ACCOUNT=_captnode; CLIENTS=captnodeclients; OPERATOR="$HUMAN_HOME/.capt-node-operator"
fi
PLIST="/Library/LaunchDaemons/$LABEL.plist"
LEGACY_LABELS=(online.inversionlabs.capt-node-primary)
PY_CANDIDATES=(/opt/homebrew/opt/python@3.14/bin/python3.14 /opt/homebrew/opt/python@3.13/bin/python3.13)
APPROVAL="I-APPROVE-R04-CUTOVER"

die() { echo "install.sh: $*" >&2; exit 1; }
need_root() { [[ "$(id -u)" -eq 0 ]] || die "$CMD needs sudo"; }
need_human() { [[ "$(id -un)" == "$HUMAN" ]] || die "$CMD runs as $HUMAN without sudo"; }
need_approval() { [[ "${CAPT_NODE_ACTIVATE:-}" == "$APPROVAL" ]] || die "$CMD requires CAPT_NODE_ACTIVATE=$APPROVAL (explicit owner approval)"; }
as_svc() { sudo -n -u "$ACCOUNT" -- env -i PATH=/usr/bin:/bin HOME="$PREFIX/state" "$PREFIX/app/.venv/bin/python" -I -m capt_runtime.node.cli "$@"; }
node_cli_human() { "$PREFIX/app/.venv/bin/python" -I -m capt_runtime.node.cli "$@"; }

free_id() {
  local used; used="$(dscl . -list "/$1" "$2" | awk '{print $2}')"
  for i in $(seq 450 499); do grep -qx "$i" <<<"$used" || { echo "$i"; return 0; }; done
  die "no free id in 450-499 for $1"
}

ensure_accounts() {
  if ! dscl . -read "/Groups/$ACCOUNT" >/dev/null 2>&1; then
    dscl . -create "/Groups/$ACCOUNT"; dscl . -create "/Groups/$ACCOUNT" PrimaryGroupID "$(free_id Groups PrimaryGroupID)"
    dscl . -create "/Groups/$ACCOUNT" RealName "CAPT Node service"; dscl . -create "/Groups/$ACCOUNT" Password '*'
  fi
  if ! dscl . -read "/Users/$ACCOUNT" >/dev/null 2>&1; then
    dscl . -create "/Users/$ACCOUNT"
    dscl . -create "/Users/$ACCOUNT" UniqueID "$(free_id Users UniqueID)"
    dscl . -create "/Users/$ACCOUNT" PrimaryGroupID "$(dscl . -read "/Groups/$ACCOUNT" PrimaryGroupID | awk '{print $2}')"
    dscl . -create "/Users/$ACCOUNT" UserShell /usr/bin/false
    dscl . -create "/Users/$ACCOUNT" NFSHomeDirectory /var/empty
    dscl . -create "/Users/$ACCOUNT" RealName "CAPT Node service"
    dscl . -create "/Users/$ACCOUNT" IsHidden 1
    dscl . -create "/Users/$ACCOUNT" Password '*'
  fi
  if ! dscl . -read "/Groups/$CLIENTS" >/dev/null 2>&1; then
    dscl . -create "/Groups/$CLIENTS"; dscl . -create "/Groups/$CLIENTS" PrimaryGroupID "$(free_id Groups PrimaryGroupID)"
    dscl . -create "/Groups/$CLIENTS" RealName "CAPT Node clients"; dscl . -create "/Groups/$CLIENTS" Password '*'
  fi
  dseditgroup -o edit -a "$HUMAN" -t user "$CLIENTS"
  dseditgroup -o edit -a "$ACCOUNT" -t user "$CLIENTS"
  ! dseditgroup -o checkmember -m "$AGENT" "$CLIENTS" >/dev/null 2>&1 || die "$AGENT must not be in $CLIENTS"
  ! dseditgroup -o checkmember -m "$ACCOUNT" admin >/dev/null 2>&1 || die "$ACCOUNT must not be an admin"
}

cmd_prepare() {
  need_root
  local commit=""
  while [[ $# -gt 0 ]]; do case "$1" in --commit) commit="$2"; shift 2;; *) die "unknown option $1";; esac; done
  [[ "$commit" =~ ^[0-9a-f]{40}$ ]] || die "--commit <full 40-hex sha> required"
  git -C "$SRC" cat-file -e "$commit^{commit}" || die "commit $commit not present in $SRC"
  local py=""; for c in "${PY_CANDIDATES[@]}"; do [[ -x "$c" ]] && { py="$c"; break; }; done
  [[ -n "$py" ]] || die "Homebrew python@3.14 or @3.13 required"
  ensure_accounts
  install -d -o root -g wheel -m 0755 "$PREFIX" "$PREFIX/etc" "$PREFIX/trust" "$PREFIX/workspaces"
  install -d -o "$ACCOUNT" -g "$CLIENTS" -m 2750 "$PREFIX/state"
  install -d -o "$ACCOUNT" -g "$CLIENTS" -m 0750 "$PREFIX/run"
  install -d -o "$ACCOUNT" -g "$CLIENTS" -m 2770 "$PREFIX/workspaces/main"
  chmod +a "user:$HUMAN allow list,add_file,search,add_subdirectory,delete_child,readattr,writeattr,readextattr,writeextattr,readsecurity,file_inherit,directory_inherit" "$PREFIX/workspaces/main"
  # Code: an exact commit, exported (no .git, no working-tree edits), root-owned and read-only.
  local stage; stage="$(mktemp -d "/private/tmp/capt-node-app.XXXXXX")"
  git -C "$SRC" archive --format=tar "$commit" | tar -x -C "$stage"
  rm -rf "$PREFIX/app.new"; mv "$stage" "$PREFIX/app.new"
  "$py" -m venv "$PREFIX/app.new/.venv"
  "$PREFIX/app.new/.venv/bin/python" -m pip install --quiet --no-cache-dir --require-hashes --only-binary=:all: \
    -r "$PREFIX/app.new/deploy/macos/capt-node/requirements-macos-arm64.txt"
  local site; site="$("$PREFIX/app.new/.venv/bin/python" -c 'import sysconfig;print(sysconfig.get_paths()["purelib"])')"
  echo "$PREFIX/app" > "$site/capt-node-app.pth"
  echo "$commit" > "$PREFIX/app.new/COMMIT"
  chown -R root:wheel "$PREFIX/app.new"; chmod -R a+rX,go-w "$PREFIX/app.new"
  if [[ -d "$PREFIX/app" ]]; then rm -rf "$PREFIX/app.prev"; mv "$PREFIX/app" "$PREFIX/app.prev"; fi
  mv "$PREFIX/app.new" "$PREFIX/app"
  sed -e "s|@LABEL@|$LABEL|g" -e "s|@ACCOUNT@|$ACCOUNT|g" -e "s|@PREFIX@|$PREFIX|g" \
    "$PREFIX/app/deploy/macos/capt-node/online.inversionlabs.capt-node.plist.in" > "$PREFIX/etc/$LABEL.plist"
  chown root:wheel "$PREFIX/etc/$LABEL.plist"; chmod 0644 "$PREFIX/etc/$LABEL.plist"
  plutil -lint "$PREFIX/etc/$LABEL.plist" >/dev/null
  echo "prepared $PREFIX at $commit for $ACCOUNT ($(id -u "$ACCOUNT")); next: install.sh$FLAG operator (as $HUMAN)"
}

cmd_operator() {
  need_human
  [[ -x "$PREFIX/app/.venv/bin/python" ]] || die "run prepare first"
  umask 077
  mkdir -p "$OPERATOR"; chmod 0700 "$OPERATOR"
  local cfg="$OPERATOR/node.json"
  if [[ ! -f "$cfg" ]]; then
    node_cli_human init --config "$cfg" --workspace "$PREFIX/workspaces/main" >/dev/null
    "$PREFIX/app/.venv/bin/python" -I - "$cfg" "$PREFIX" <<'PY'
import json, sys
cfg, prefix = sys.argv[1], sys.argv[2]
raw = json.load(open(cfg))
raw["endpoint"] = f"unix://{prefix}/run/capt-node.sock"
raw["emergencyStopHotkey"] = None
json.dump(raw, open(cfg, "w"), indent=2)
PY
  fi
  local pend code
  pend="$(node_cli_human pair --config "$cfg" --controller-id "$CONTROLLER")"
  code="$("$PREFIX/app/.venv/bin/python" -I -c 'import json,sys;print(json.loads(sys.argv[1]).get("verificationCode",""))' "$pend")"
  if [[ -n "$code" ]]; then node_cli_human pair --config "$cfg" --controller-id "$CONTROLLER" --approve-code "$code" >/dev/null; fi
  node_cli_human mcp-authorize --config "$cfg" --controller-id "$CONTROLLER" \
    --capability-file "$OPERATOR/$CONTROLLER.capability.json" --expires-minutes "${CAPT_NODE_CAPABILITY_MINUTES:-1440}" >/dev/null
  echo "operator ready in $OPERATOR (controller $CONTROLLER); next: sudo install.sh$FLAG trust"
}

cmd_trust() {
  need_root
  local opstate="$OPERATOR/.capt-node-state"
  [[ -f "$opstate/authority.pub" && -f "$opstate/pairings.json" ]] || die "run operator first"
  # The Node identity becomes the service's: moved, not copied, so the operator side no longer holds it.
  if [[ -f "$opstate/node.key" ]]; then
    install -o "$ACCOUNT" -g "$ACCOUNT" -m 0600 "$opstate/node.key" "$PREFIX/state/node.key"
    rm -f "$opstate/node.key"
  fi
  [[ -f "$PREFIX/state/node.key" ]] || die "no node key"
  install -o root -g wheel -m 0644 "$opstate/authority.pub" "$PREFIX/trust/authority.pub"
  install -o root -g wheel -m 0644 "$opstate/pairings.json" "$PREFIX/trust/pairings.json"
  local agent_home; agent_home="$(dscl . -read "/Users/$AGENT" NFSHomeDirectory 2>/dev/null | awk '{print $2}')"
  "$PREFIX/app/.venv/bin/python" -I - "$OPERATOR/node.json" "$PREFIX" "$CLIENTS" "$(id -u "$HUMAN")" "$(id -u "$AGENT")" \
      "$HUMAN_HOME" "$OPERATOR" "${agent_home:-/nonexistent}" > "$PREFIX/etc/node.json.new" <<'PY'
import glob, json, sys
op_cfg, prefix, clients, human_uid, agent_uid, home, operator, agent_home = sys.argv[1:9]
raw = json.load(open(op_cfg))
forbidden = sorted(set(
    [f"{home}/.capt/runtime.token", f"{home}/.capt/ui/helm.token", f"{operator}/.capt-node-state/authority.key",
     f"{home}/.capt-node/.capt-node-state/authority.key", f"{home}/.inversion-commander/bridge-token",
     f"{agent_home}/.capt/agent.token"]
    + glob.glob(f"{operator}/.capt-node-state/controller-*.key")
    + glob.glob(f"{home}/.capt/*.token")))
svc = {k: raw[k] for k in ("endpoint", "workspaceRoots", "nodeId", "authorityId", "deviceName")}
svc["emergencyStopHotkey"] = None
svc["serviceIdentity"] = {
    "trustDir": f"{prefix}/trust", "stateDir": f"{prefix}/state",
    "allowedPeerUids": [int(human_uid)], "forbiddenUids": [int(human_uid), int(agent_uid)],
    "forbiddenReadablePaths": forbidden, "socketGroup": clients,
}
print(json.dumps(svc, indent=2))
PY
  mv "$PREFIX/etc/node.json.new" "$PREFIX/etc/node.json"
  chown root:wheel "$PREFIX/etc/node.json"; chmod 0644 "$PREFIX/etc/node.json"
  as_svc serve --config "$PREFIX/etc/node.json" --preflight-only
  echo "trust installed and preflight passed; next: sudo CAPT_NODE_ACTIVATE=$APPROVAL install.sh$FLAG activate"
}

running_pid() { launchctl print "system/$LABEL" 2>/dev/null | awk '/^\tpid = /{print $3; exit}'; }

cmd_activate() {
  need_root; need_approval
  [[ -f "$PREFIX/etc/node.json" ]] || die "run trust first"
  as_svc serve --config "$PREFIX/etc/node.json" --preflight-only >/dev/null || die "preflight refused; not activating"
  install -o root -g wheel -m 0644 "$PREFIX/etc/$LABEL.plist" "$PLIST"
  launchctl bootout "system/$LABEL" 2>/dev/null || true
  launchctl bootstrap system "$PLIST"
  local pid="" i
  for i in $(seq 1 50); do pid="$(running_pid)"; [[ -n "$pid" && -S "$PREFIX/run/capt-node.sock" ]] && break; sleep 0.2; done
  [[ -n "$pid" ]] || { tail -5 "$PREFIX/state/node.log" >&2 || true; die "daemon did not start"; }
  # Identity of the RUNNING process, from the kernel's process table, not from the plist.
  local uid; uid="$(ps -o uid= -p "$pid" | tr -d ' ')"
  [[ "$uid" == "$(id -u "$ACCOUNT")" ]] || { launchctl bootout "system/$LABEL"; die "running uid $uid is not $ACCOUNT — booted out"; }
  [[ "$uid" != "0" && "$uid" != "$(id -u "$HUMAN")" ]] || { launchctl bootout "system/$LABEL"; die "refusing uid $uid"; }
  stat -f '%Su:%Sg %Lp %N' "$PREFIX/run/capt-node.sock"
  # Probe as the human through the operator identity: the Node must report the service uid.
  local probe; probe="$(sudo -n -u "$HUMAN" -- "$PREFIX/app/.venv/bin/python" -I -m capt_runtime.node.cli exec \
      --config "$OPERATOR/node.json" --controller-id "$CONTROLLER" --operation-id "activate-probe-$(date +%s)" \
      --cwd "$PREFIX/workspaces/main" /usr/bin/id -u)"
  "$PREFIX/app/.venv/bin/python" -I -c '
import json, sys
r = json.loads(sys.argv[1]); ev = (r.get("evidence") or [{}])[0]
sys.exit(0 if r.get("state") == "closed" and (ev.get("stdout") or "").strip() == sys.argv[2] else 1)' \
    "$probe" "$(id -u "$ACCOUNT")" || { echo "$probe" >&2; die "probe did not run as $ACCOUNT"; }
  echo "active: $LABEL pid=$pid uid=$uid ($ACCOUNT); probe ok. Legacy Node is still running until retire-legacy."
}

cmd_bridge_switch() {
  need_human
  local cfg="$HUMAN_HOME/.inversion-commander/config.json"
  [[ -f "$cfg" ]] || die "no bridge config at $cfg"
  [[ -f "$OPERATOR/$CONTROLLER.capability.json" ]] || die "run operator first"
  local backup; backup="$cfg.pre-r04-$(date -u +%Y%m%dT%H%M%SZ)"
  cp -p "$cfg" "$backup"; chmod 0600 "$backup"
  "$PREFIX/app/.venv/bin/python" -I - "$cfg" "$PREFIX" "$OPERATOR" "$CONTROLLER" <<'PY'
import json, os, sys
cfg, prefix, operator, controller = sys.argv[1:5]
raw = json.load(open(cfg))
raw.update({"captNodeRoot": f"{prefix}/app", "captNodeConfig": f"{operator}/node.json",
            "captControllerId": controller, "captCapabilityFile": f"{operator}/{controller}.capability.json"})
tmp = cfg + ".tmp"
with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as fh:
    json.dump(raw, fh, indent=2)
os.replace(tmp, cfg)
PY
  echo "bridge config repointed (backup: $backup). Restart the bridge to apply:"
  echo "  launchctl kickstart -k gui/$(id -u)/online.inversionlabs.inversion-commander-bridge"
}

cmd_retire_legacy() {
  need_root; need_approval
  [[ $STAGING -eq 0 ]] || die "retire-legacy is production-only"
  local pid; pid="$(running_pid)"; [[ -n "$pid" ]] || die "service Node is not running; refusing to retire the legacy Node"
  local huid; huid="$(id -u "$HUMAN")"
  for l in "${LEGACY_LABELS[@]}"; do
    launchctl bootout "gui/$huid/$l" 2>/dev/null || true
    launchctl disable "gui/$huid/$l"
    echo "retired $l (disabled; plist left in place for rollback)"
  done
}

cmd_status() {
  need_root
  local pid; pid="$(running_pid)"
  echo "label: $LABEL"
  if [[ -n "$pid" ]]; then echo "running: pid=$pid uid=$(ps -o uid= -p "$pid" | tr -d ' ') ($(ps -o user= -p "$pid"))"; else echo "running: no"; fi
  [[ -S "$PREFIX/run/capt-node.sock" ]] && stat -f 'socket: %Su:%Sg %Lp' "$PREFIX/run/capt-node.sock"
  [[ -f "$PREFIX/app/COMMIT" ]] && echo "app commit: $(cat "$PREFIX/app/COMMIT")"
  [[ -f "$PREFIX/etc/node.json" ]] && { as_svc serve --config "$PREFIX/etc/node.json" --preflight-only || true; }
  local huid; huid="$(id -u "$HUMAN")"
  for l in "${LEGACY_LABELS[@]}"; do
    local lp; lp="$(launchctl print "gui/$huid/$l" 2>/dev/null | awk '/^\tpid = /{print $3; exit}')"
    echo "legacy $l: ${lp:+running pid=$lp uid=$(ps -o uid= -p "$lp" | tr -d ' ')}${lp:-not running}"
  done
  [[ -f "$PREFIX/state/denials.jsonl" ]] && echo "denials: $(wc -l < "$PREFIX/state/denials.jsonl" | tr -d ' ')"
  echo "service-uid processes: $(pgrep -u "$ACCOUNT" | wc -l | tr -d ' ')"
}

cmd_rollback() {
  need_root
  local restore=0; [[ "${1:-}" == "--restore-legacy" ]] && restore=1
  launchctl bootout "system/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  pkill -KILL -u "$ACCOUNT" 2>/dev/null || true   # revocation: nothing of the service uid survives
  sleep 0.5
  [[ "$(pgrep -u "$ACCOUNT" | wc -l | tr -d ' ')" == "0" ]] || die "service-uid processes still present"
  echo "service Node stopped and revoked; trust anchors, state and accounts kept for inspection."
  if [[ $restore -eq 1 ]]; then
    [[ $STAGING -eq 0 ]] || die "--restore-legacy is production-only"
    [[ "${CAPT_NODE_ACCEPT_SAME_UID_EXPOSURE:-}" == "YES" ]] || die "restoring the uid-501 Node re-opens remote execution as the human: set CAPT_NODE_ACCEPT_SAME_UID_EXPOSURE=YES to accept that downgrade explicitly"
    local huid; huid="$(id -u "$HUMAN")"
    for l in "${LEGACY_LABELS[@]}"; do
      launchctl enable "gui/$huid/$l"
      launchctl bootstrap "gui/$huid" "$HUMAN_HOME/Library/LaunchAgents/$l.plist" 2>/dev/null || launchctl kickstart "gui/$huid/$l"
      echo "SECURITY DOWNGRADE: restored $l (uid $huid)"
    done
    local latest; latest="$(ls -t "$HUMAN_HOME"/.inversion-commander/config.json.pre-r04-* 2>/dev/null | head -1 || true)"
    if [[ -n "$latest" ]]; then
      sudo -n -u "$HUMAN" cp -p "$latest" "$HUMAN_HOME/.inversion-commander/config.json"
      echo "bridge config restored from $latest; restart the bridge: launchctl kickstart -k gui/$huid/online.inversionlabs.inversion-commander-bridge"
    fi
  fi
}

cmd_uninstall() {
  need_root
  [[ $STAGING -eq 1 ]] || die "uninstall is staging-only; production keeps its accounts and state"
  cmd_rollback
  [[ "$PREFIX" == /Library/CAPTNodeStaging ]] && rm -rf "$PREFIX"
  rm -rf "$OPERATOR"
  dscl . -delete "/Users/$ACCOUNT" 2>/dev/null || true
  dscl . -delete "/Groups/$CLIENTS" 2>/dev/null || true
  dscl . -delete "/Groups/$ACCOUNT" 2>/dev/null || true
  echo "staging removed"
}

case "$CMD" in
  prepare) cmd_prepare "$@";; operator) cmd_operator;; trust) cmd_trust;; activate) cmd_activate;;
  bridge-switch) cmd_bridge_switch;; retire-legacy) cmd_retire_legacy;; status) cmd_status;;
  rollback) cmd_rollback "$@";; uninstall) cmd_uninstall;;
  *) sed -n '2,25p' "$0"; exit 2;;
esac
