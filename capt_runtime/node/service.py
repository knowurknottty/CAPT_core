"""Service-identity profile for CAPT Node (R0.4).

CAPT Node executes remotely requested processes. Whatever it can reach, a remote
controller with a valid capability can reach. Before R0.4 it ran as the human
operator's uid, so ``shell.exec`` could read the human CAPT credential. This module
lets the Node run as a dedicated, non-admin service uid and *refuse to start* when the
deployment would hand that uid more authority than intended.

The checks are observations made by the running process about itself (effective uid,
``os.access`` on concrete paths, ownership). They are not a sandbox: the operating
system's permissions are the boundary; this module refuses to run when that boundary is
visibly wrong, and records every refusal.

Enabled only when the Node config carries a ``serviceIdentity`` object; otherwise the
legacy same-uid behaviour is unchanged.
"""
from __future__ import annotations

import grp
import json
import os
import stat
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

SIGNING_KEY_GLOBS = ("authority.key", "controller-*.key")


class ServicePreflightError(PermissionError):
    """Startup refused; ``code`` is stable, ``detail`` names the offending path."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ServiceIdentityPolicy:
    trust_dir: Path
    state_dir: Path
    allowed_peer_uids: frozenset[int]
    forbidden_uids: frozenset[int]
    forbidden_readable_paths: tuple[Path, ...]
    socket_group: Optional[str] = None
    socket_mode: int = 0o660

    @classmethod
    def from_config(cls, raw: Mapping[str, Any]) -> Optional["ServiceIdentityPolicy"]:
        block = raw.get("serviceIdentity")
        if block is None:
            return None
        if not isinstance(block, Mapping):
            raise ValueError("node_service_identity_must_be_object")

        def _abs(key: str) -> Path:
            value = block.get(key)
            if not isinstance(value, str) or not Path(value).is_absolute():
                raise ValueError(f"node_service_identity_{key}_must_be_absolute")
            return Path(value)

        def _uids(key: str, required: bool) -> frozenset[int]:
            value = block.get(key, [])
            if not isinstance(value, list) or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in value):
                raise ValueError(f"node_service_identity_{key}_invalid")
            if required and not value:
                raise ValueError(f"node_service_identity_{key}_required")
            return frozenset(value)

        paths = block.get("forbiddenReadablePaths", [])
        if not isinstance(paths, list) or any(not isinstance(p, str) or not Path(p).is_absolute() for p in paths):
            raise ValueError("node_service_identity_forbiddenReadablePaths_invalid")
        group = block.get("socketGroup")
        if group is not None and (not isinstance(group, str) or not group):
            raise ValueError("node_service_identity_socketGroup_invalid")
        return cls(
            trust_dir=_abs("trustDir"),
            state_dir=_abs("stateDir"),
            allowed_peer_uids=_uids("allowedPeerUids", required=True),
            forbidden_uids=_uids("forbiddenUids", required=True),
            forbidden_readable_paths=tuple(Path(p) for p in paths),
            socket_group=group,
        )


def _writable(path: Path) -> bool:
    # launchd UserName= and runuser set real == effective uid, so plain access() is exact.
    return path.exists() and os.access(path, os.W_OK)


def _owned_by_me(path: Path) -> bool:
    try:
        return path.lstat().st_uid == os.geteuid()
    except FileNotFoundError:
        return False


def _within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _signing_keys(directories: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for pattern in SIGNING_KEY_GLOBS:
            found.extend(p for p in directory.glob(pattern) if p.exists())
    return found


def preflight(
    policy: ServiceIdentityPolicy,
    *,
    config_path: Path,
    workspace_roots: Iterable[str],
    code_root: Path,
    legacy_state_dir: Path,
) -> dict[str, Any]:
    """Refuse to serve unless this process holds only the intended authority."""
    euid = os.geteuid()
    if euid == 0:
        raise ServicePreflightError("NODE_REFUSES_ROOT")
    if euid in policy.forbidden_uids:
        raise ServicePreflightError("NODE_RUNNING_AS_FORBIDDEN_UID", str(euid))

    # Trust anchors decide who may command this Node. The service must not be able to
    # replace them (write, or rename within a writable or self-owned directory).
    trust_paths = [policy.trust_dir, policy.trust_dir.parent,
                   policy.trust_dir / "authority.pub", policy.trust_dir / "pairings.json"]
    for path in trust_paths:
        if _owned_by_me(path):
            raise ServicePreflightError("NODE_TRUST_ANCHOR_OWNED_BY_SERVICE", str(path))
        if _writable(path):
            raise ServicePreflightError("NODE_TRUST_ANCHOR_WRITABLE", str(path))
    for required in ("authority.pub", "pairings.json"):
        if not (policy.trust_dir / required).is_file():
            raise ServicePreflightError("NODE_TRUST_ANCHOR_MISSING", required)

    # Signing keys mint capabilities and controller sessions: never reachable by the service.
    for key in _signing_keys([policy.trust_dir, policy.state_dir, legacy_state_dir]):
        if os.access(key, os.R_OK):
            raise ServicePreflightError("NODE_SIGNING_KEY_REACHABLE", str(key))

    for path in policy.forbidden_readable_paths:
        if os.access(path, os.R_OK):
            raise ServicePreflightError("NODE_HUMAN_CREDENTIAL_REACHABLE", str(path))

    # Code and configuration define the Node's behaviour; the Node must not rewrite them.
    for path in (code_root, code_root / "capt_runtime", code_root / "capt_runtime" / "node",
                 config_path, config_path.parent):
        if _owned_by_me(path) or _writable(path):
            raise ServicePreflightError("NODE_CODE_OR_CONFIG_WRITABLE", str(path))

    state = policy.state_dir
    try:
        st = state.lstat()
    except FileNotFoundError as exc:
        raise ServicePreflightError("NODE_STATE_DIR_MISSING", str(state)) from exc
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != euid or st.st_mode & 0o022:
        raise ServicePreflightError("NODE_STATE_DIR_INSECURE", str(state))

    resolved_protected = [code_root.resolve(), policy.trust_dir.resolve(), state.resolve()]
    for root in workspace_roots:
        resolved = Path(root).resolve()
        for protected in resolved_protected:
            if _within(resolved, protected) or _within(protected, resolved):
                raise ServicePreflightError("NODE_WORKSPACE_OVERLAPS_SERVICE", f"{root} ~ {protected}")

    return {
        "serviceUid": euid,
        "serviceGid": os.getegid(),
        "groups": sorted(os.getgroups()),
        "trustDir": str(policy.trust_dir),
        "stateDir": str(state),
        "allowedPeerUids": sorted(policy.allowed_peer_uids),
        "forbiddenUids": sorted(policy.forbidden_uids),
        "checkedForbiddenPaths": len(policy.forbidden_readable_paths),
    }


def secure_socket(path: Path, policy: ServiceIdentityPolicy) -> None:
    """Restrict the RPC socket to its owner and the configured client group."""
    if policy.socket_group is not None:
        try:
            gid = grp.getgrnam(policy.socket_group).gr_gid
        except KeyError as exc:
            raise ServicePreflightError("NODE_SOCKET_GROUP_MISSING", policy.socket_group) from exc
        os.chown(path, -1, gid)
    os.chmod(path, policy.socket_mode)


def peer_uid(conn: Any) -> Optional[int]:
    """Kernel-reported uid of the connected peer (shared with RuntimeService IPC)."""
    from desktop.ipc_principal import peer_uid as _peer_uid
    return _peer_uid(conn)


def require_scope_within_service(capability_roots: Iterable[str], service_roots: Iterable[str]) -> None:
    """A capability may narrow, never widen, the roots this service was deployed with."""
    allowed = [Path(r).resolve() for r in service_roots]
    for root in capability_roots:
        resolved = Path(root).resolve()
        if not any(_within(resolved, base) for base in allowed):
            raise PermissionError("NODE_CAPABILITY_ROOT_OUTSIDE_SERVICE_SCOPE")


class DenialLog:
    """Append-only JSON-lines record of refused requests (durable, fsynced)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def record(self, code: str, **fields: Any) -> None:
        entry = {"at": datetime.now(timezone.utc).isoformat(), "code": code}
        entry.update({k: v for k, v in fields.items() if v is not None})
        line = (json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o640)
            try:
                os.write(fd, line)
                os.fsync(fd)
            finally:
                os.close(fd)
