#!/usr/bin/env bash
# Create the three real Unix identities used by the CAPT Node service-identity E2E (R0.4).
#   cnode-svc     — runs CAPT Node (stands in for the macOS service account)
#   cnode-human   — the operator (stands in for uid 501): holds the human token and signing keys
#   cnode-agent   — an agent account that must reach nothing
#   cnode-clients — may connect to the Node socket: cnode-human and cnode-svc (socket chgrp)
# Idempotent. Linux only; run as root on a disposable machine or CI runner.
set -euo pipefail
[[ "$(uname -s)" == "Linux" ]] || { echo "Linux only" >&2; exit 2; }
[[ "$(id -u)" -eq 0 ]] || { echo "run as root" >&2; exit 2; }
getent group cnode-clients >/dev/null || groupadd --system cnode-clients
for u in cnode-svc cnode-human cnode-agent; do
  id "$u" >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin "$u"
done
usermod -aG cnode-clients cnode-human
usermod -aG cnode-clients cnode-svc
PY="${CAPT_NODE_E2E_PYTHON:-/opt/capt-venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  python3 -m venv /opt/capt-venv
  /opt/capt-venv/bin/python -m pip install --quiet 'cryptography>=47' pytest
  chmod -R a+rX /opt/capt-venv
fi
id cnode-svc; id cnode-human; id cnode-agent
echo "ready: CAPT_NODE_E2E_PYTHON=$PY"
