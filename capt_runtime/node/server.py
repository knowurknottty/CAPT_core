"""Local-only CAPT Node RPC server."""

from __future__ import annotations

import base64
import os
import socket
import threading
from pathlib import Path
from typing import Any, Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .authority import verify_capability_authority
from .executor import NodeExecutor
from .identity import NodeIdentity
from .journal import NodeOperationJournal
from .pairing import PairingRecord, PairingState
from .protocol import canonical_json, decode_frame, encode_frame, request_from_wire
from .service import DenialLog, ServiceIdentityPolicy, peer_uid, require_scope_within_service, secure_socket
from .types import canonical_request_digest


class NodeServer:
    def __init__(
        self,
        socket_path: str | Path,
        node: NodeIdentity,
        journal: NodeOperationJournal,
        *,
        pairings: list[PairingRecord],
        authority_issuers: dict[str, bytes],
        now: Callable[[], Any],
        service_policy: ServiceIdentityPolicy | None = None,
        service_roots: tuple[str, ...] = (),
        denial_log: DenialLog | None = None,
    ) -> None:
        self.socket_path = Path(socket_path)
        # R0.4 service-identity mode: peer uid gate, scope ceiling, durable denials.
        self.service_policy = service_policy
        self.service_roots = tuple(service_roots)
        self.denial_log = denial_log
        self.node = node
        self.journal = journal
        self.pairings = {record.controller_id: record for record in pairings}
        self.authority_issuers = dict(authority_issuers)
        self.executor = NodeExecutor(node.node_id, journal, now=now)
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._workers_lock = threading.Lock()
        self._workers: set[threading.Thread] = set()
        # Different operation IDs may execute concurrently. Requests for the same
        # operation ID must still serialize so idempotency cannot double-dispatch.
        self._operation_locks_guard = threading.Lock()
        self._operation_locks: dict[str, tuple[threading.Lock, int]] = {}

    def start(self) -> None:
        if self._sock is not None:
            raise RuntimeError("node_server_already_started")
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.socket_path.unlink(missing_ok=True)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if self.service_policy is not None:
            # Bind with a closed umask so the socket never exists, even briefly, with
            # wider permissions than the policy allows; then chgrp + chmod to policy.
            previous = os.umask(0o177)
            try:
                sock.bind(str(self.socket_path))
            finally:
                os.umask(previous)
            secure_socket(self.socket_path, self.service_policy)
        else:
            sock.bind(str(self.socket_path))
        sock.listen(16)
        sock.settimeout(0.2)
        self._sock = sock
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            worker = threading.Thread(
                target=self._serve_connection,
                args=(conn,),
                daemon=True,
                name="capt-node-rpc",
            )
            with self._workers_lock:
                self._workers.add(worker)
            worker.start()

    def _serve_connection(self, conn: socket.socket) -> None:
        current = threading.current_thread()
        try:
            with conn:
                request: Any = None
                peer: int | None = None
                try:
                    if self.service_policy is not None:
                        peer = peer_uid(conn)
                        if peer is None or peer not in self.service_policy.allowed_peer_uids:
                            raise PermissionError("NODE_PEER_UID_DENIED")
                    request = self._recv(conn)
                    response = self._handle(request)
                except Exception as exc:
                    code = str(exc) or f"node_internal_exception:{type(exc).__name__}"
                    response = {"ok": False, "code": code}
                    if self.denial_log is not None and isinstance(exc, (PermissionError, KeyError, ValueError, RuntimeError)):
                        payload = request.get("payload") if isinstance(request, dict) else None
                        self.denial_log.record(
                            code,
                            peerUid=peer,
                            kind=request.get("kind") if isinstance(request, dict) else None,
                            controllerId=request.get("controllerId") if isinstance(request, dict) else None,
                            operationId=payload.get("operationId") if isinstance(payload, dict) else None,
                        )
                try:
                    frame = encode_frame(response)
                except ValueError as exc:
                    if str(exc) != "frame_too_large":
                        raise
                    frame = encode_frame(
                        {"ok": False, "code": "rpc_response_frame_too_large"}
                    )
                try:
                    conn.sendall(frame)
                except OSError:
                    pass
        finally:
            with self._workers_lock:
                self._workers.discard(current)

    def _recv(self, conn: socket.socket) -> dict[str, Any]:
        conn.settimeout(5.0)
        header = _recv_exact(conn, 4)
        size = int.from_bytes(header, "big")
        if size > 1024 * 1024:
            raise ValueError("frame_too_large")
        return decode_frame(header + _recv_exact(conn, size))

    def _pairing(self, controller_id: str) -> PairingRecord:
        record = self.pairings.get(controller_id)
        if record is None:
            raise PermissionError("controller_not_paired")
        if record.state is not PairingState.ACTIVE:
            raise PermissionError(f"pairing_{record.state.value}")
        if record.node_id != self.node.node_id:
            raise PermissionError("pairing_node_mismatch")
        return record

    def _authenticate(self, message: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        controller_id = message.get("controllerId")
        payload = message.get("payload")
        signature = message.get("signature")
        kind = message.get("kind")
        if not isinstance(controller_id, str) or not controller_id:
            raise PermissionError("controller_identity_missing")
        if not isinstance(kind, str) or not kind:
            raise ValueError("rpc_kind_missing")
        if not isinstance(payload, dict):
            raise ValueError("rpc_payload_not_object")
        if not isinstance(signature, str):
            raise PermissionError("signature_missing")
        record = self._pairing(controller_id)
        unsigned = {"kind": kind, "controllerId": controller_id, "payload": payload}
        try:
            Ed25519PublicKey.from_public_bytes(record.controller_public_key).verify(
                base64.b64decode(signature, validate=True), canonical_json(unsigned)
            )
        except (InvalidSignature, ValueError) as exc:
            raise PermissionError("signature_invalid") from exc
        return kind, payload

    def _handle(self, message: dict[str, Any]) -> dict[str, Any]:
        controller_id = str(message.get("controllerId") or "")
        kind, payload = self._authenticate(message)
        if kind == "evidence_read":
            operation_id = payload.get("operationId")
            ref = payload.get("ref")
            offset = payload.get("offset", 0)
            limit = payload.get("limit", 64 * 1024)
            if not isinstance(operation_id, str) or not operation_id:
                raise ValueError("operation_id_missing")
            bound_controller = self.journal.controller_id(operation_id)
            if bound_controller is None:
                raise PermissionError("evidence_controller_unbound")
            if bound_controller != controller_id:
                raise PermissionError("evidence_controller_mismatch")
            return {
                "ok": True,
                "result": self.executor.evidence_spool.read(
                    operation_id=operation_id,
                    ref=ref,
                    offset=offset,
                    limit=limit,
                ),
            }
        if kind == "status":
            operation_id = payload.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                raise ValueError("operation_id_missing")
            row = self.journal.lookup(operation_id)
            # Status is bound to the controller that issued the operation, like
            # evidence_read: another paired controller learns nothing, not even existence.
            if row is None or self.journal.controller_id(operation_id) != controller_id:
                raise KeyError("operation_not_found")
            return {"ok": True, "result": row}
        if kind != "execute":
            raise ValueError("rpc_kind_not_supported")
        request = request_from_wire(payload)
        if request.capability.controller_id != controller_id:
            raise PermissionError("controller_capability_mismatch")
        verify_capability_authority(request.capability, self.authority_issuers)
        if self.service_policy is not None:
            require_scope_within_service(request.capability.filesystem_roots, self.service_roots)
        operation_lock = self._retain_operation_lock(request.operation_id)
        operation_lock.acquire()
        try:
            existing = self.journal.lookup(request.operation_id)
            if existing is not None:
                prepared = self.journal.prepare(request)
                return {"ok": True, "result": {**prepared, "replayed": True}}
            result = self.executor.execute(request, controller_id=controller_id)
            return {
                "ok": True,
                "result": {
                    "operationId": result.operation_id,
                    "state": result.state.value,
                    "evidence": list(result.evidence),
                    "exitCode": result.exit_code,
                    "detail": result.detail,
                    "specificReason": result.specific_reason,
                    "requestDigest": canonical_request_digest(request),
                    "replayed": False,
                },
            }
        finally:
            operation_lock.release()
            self._release_operation_lock(request.operation_id, operation_lock)

    def _retain_operation_lock(self, operation_id: str) -> threading.Lock:
        with self._operation_locks_guard:
            current = self._operation_locks.get(operation_id)
            if current is None:
                lock = threading.Lock()
                self._operation_locks[operation_id] = (lock, 1)
                return lock
            lock, users = current
            self._operation_locks[operation_id] = (lock, users + 1)
            return lock

    def _release_operation_lock(
        self, operation_id: str, lock: threading.Lock
    ) -> None:
        with self._operation_locks_guard:
            current = self._operation_locks.get(operation_id)
            if current is None or current[0] is not lock:
                return
            _, users = current
            if users <= 1:
                self._operation_locks.pop(operation_id, None)
            else:
                self._operation_locks[operation_id] = (lock, users - 1)

    def close(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        with self._workers_lock:
            workers = list(self._workers)
        for worker in workers:
            worker.join(timeout=1.0)
        self.socket_path.unlink(missing_ok=True)


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise RuntimeError("rpc_connection_closed")
        chunks.extend(chunk)
    return bytes(chunks)
