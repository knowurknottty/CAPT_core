"""IPC principals for RuntimeService connections.

A RuntimeService connection historically had exactly one principal: whoever held
``runtime.token`` was the human operator, and every command it sent was recorded
with ``actor_kind="human"``. That is sound while every process able to read the
token belongs to the human. It is not sound once an agent host (Hermes, an MCP
server, a child process) is given access to the runtime, because such a process
could decide its own HumanApprovals.

This module adds a second, optional principal:

* ``human`` — authenticated by ``runtime.token``; unchanged behaviour.
* ``agent`` — authenticated by a separate token (``--agent-token-file``). It may
  issue every read-only query and exactly the command operations in
  :data:`AGENT_PRINCIPAL_COMMAND_OPS`. Its commands carry
  ``actor_kind="external_driver"``, which the authority table permits for no
  human act, so a regression in the allowlist still cannot mint an approval.

The agent principal is execute-only by design: it may spend a capability a human
approved and activated, but it may not author missions, decide approvals,
activate capabilities, or administer the runtime.
"""
from __future__ import annotations

import os
import secrets
import socket
import struct
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

PRINCIPAL_HUMAN = "human"
PRINCIPAL_AGENT = "agent"

#: Actor kind stamped on command metadata for each principal.
PRINCIPAL_ACTOR_KIND = {
    PRINCIPAL_HUMAN: "human",
    PRINCIPAL_AGENT: "external_driver",
}

#: The complete set of command operations an agent principal may send.
#: Everything else (authoring, deciding, activating, administering) is refused at
#: the IPC boundary, before any command-service subclass sees the envelope.
AGENT_PRINCIPAL_COMMAND_OPS = frozenset({"run_tool"})

#: Additive features advertised in the authentication reply.
IPC_FEATURES = ("principal.v1", "tool_request_commitment.v1", "peer_uid.v1")

AGENT_PRINCIPAL_OP_DENIED = "AGENT_PRINCIPAL_OP_DENIED"
HUMAN_PRINCIPAL_PEER_DENIED = "HUMAN_PRINCIPAL_PEER_DENIED"

_XUCRED_VERSION = 0
_XUCRED_SIZE = 76  # struct xucred: u_int version, uid_t uid, short ngroups, gid_t groups[16]


def peer_uid(conn: socket.socket) -> Optional[int]:
    """Effective uid of the peer of a connected AF_UNIX socket, or ``None``.

    Linux: ``SO_PEERCRED``. macOS: ``LOCAL_PEERCRED`` (the mechanism behind
    ``getpeereid(3)``), level ``SOL_LOCAL`` = 0; verified on macOS 26.4.1 /
    Python 3.14.7, where ``socket.SOL_LOCAL`` is not exported. Other platforms: None.
    """
    try:
        if sys.platform.startswith("linux") and hasattr(socket, "SO_PEERCRED"):
            raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            _pid, uid, _gid = struct.unpack("3i", raw)
            return uid
        if sys.platform == "darwin":
            raw = conn.getsockopt(0, getattr(socket, "LOCAL_PEERCRED", 0x001), _XUCRED_SIZE)
            version, uid = struct.unpack_from("=II", raw, 0)
            return uid if version == _XUCRED_VERSION else None
    except OSError:
        return None
    return None


def human_peer_denial(principal: Optional[str], peer: Optional[int],
                      human_uids: Optional[frozenset[int]]) -> Optional[str]:
    """When peer enforcement is on, a human-token connection must come from a human uid.

    ``human_uids is None`` means enforcement is off (historical single-user mode).
    An undeterminable peer fails closed.
    """
    if human_uids is None or principal != PRINCIPAL_HUMAN:
        return None
    if peer is None or peer not in human_uids:
        return HUMAN_PRINCIPAL_PEER_DENIED
    return None


def match_principal(
    presented: Any, human_token: str, agent_token: Optional[str]
) -> Optional[str]:
    """Return the principal whose token equals ``presented``, else ``None``.

    Comparison is constant-time per candidate. A non-string presentation never
    matches.
    """
    if not isinstance(presented, str) or not presented:
        return None
    if secrets.compare_digest(presented, human_token):
        return PRINCIPAL_HUMAN
    if agent_token and secrets.compare_digest(presented, agent_token):
        return PRINCIPAL_AGENT
    return None


def agent_command_denial(command: Mapping[str, Any]) -> Optional[str]:
    """Return a denial code when an agent principal may not send ``command``."""
    op = command.get("op") if isinstance(command, Mapping) else None
    if op in AGENT_PRINCIPAL_COMMAND_OPS:
        return None
    return AGENT_PRINCIPAL_OP_DENIED


def resolve_group_id(group: Optional[str]) -> Optional[int]:
    """Resolve a group name or numeric gid; ``None`` when no group is configured."""
    if group is None or group == "":
        return None
    if group.isdigit():
        return int(group)
    import grp  # POSIX only; RuntimeService is POSIX only.

    return grp.getgrnam(group).gr_gid


def write_secret_file(path: Path, value: str, *, mode: int, gid: Optional[int] = None) -> str:
    """Atomically create ``path`` containing ``value`` with ``mode`` from birth.

    The previous implementation wrote the token with ``write_text`` and then
    ``chmod``-ed it, leaving a window in which the file existed with the process
    umask (``0644`` under the common ``022``). Here the bytes are written to a
    fresh ``O_EXCL | O_NOFOLLOW`` temporary created with mode ``0600``, the final
    mode and group are applied to the open descriptor, the data is fsynced, and the
    temporary is renamed over ``path``. Returns the value read back from ``path``.
    """
    if mode & 0o007:
        raise ValueError("secret files must not be world-accessible")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(".%s.%s.tmp" % (path.name, secrets.token_hex(8)))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temp, flags, 0o600)
    try:
        if gid is not None:
            os.fchown(fd, -1, gid)
        os.fchmod(fd, mode)
        data = value.encode("utf-8")
        written = 0
        while written < len(data):
            written += os.write(fd, data[written:])
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    os.close(fd)
    os.replace(temp, path)
    try:
        dir_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        dir_fd = None
    if dir_fd is not None:
        try:
            os.fsync(dir_fd)
        except OSError:
            pass
        finally:
            os.close(dir_fd)
    return path.read_text(encoding="utf-8").strip()
