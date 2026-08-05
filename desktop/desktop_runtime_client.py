#!/usr/bin/env python3.12
"""CAPT Desktop Runtime M0 — operator client (desktop side, untrusted).

The desktop is an UNTRUSTED operator surface. It connects to the local CAPT
runtime service over an authenticated Unix-domain socket and issues *read*
queries. It never writes to the CAPT ledger and never promotes driver output
to authoritative state. All projections below are derived read models built
from authoritative runtime data; none duplicate CAPT authority.

This module is framework-agnostic so it can be driven headless by the
acceptance harness and by the Tk GUI view.
"""
from __future__ import annotations

import json
import socket
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from capt_runtime.store import EventStore  # only for local read-model typing; client uses IPC

from .capt_runtime_service import (  # local import to share demo stream ids
    DEMO_MISSION_ID,
    DEMO_TASK_ID,
    DEMO_DRIVER_RUN_ID,
    DEMO_GRANT_ID,
    DEMO_LEASE_ID,
    DEMO_CLAIM_ID,
)


class RuntimeClientError(RuntimeError):
    pass


class RuntimeClient:
    """Authenticated local IPC client to the CAPT runtime service."""

    def __init__(self, sock_path: str, token_file: str, connect_timeout: float = 5.0) -> None:
        self.sock_path = str(sock_path)
        self.token_file = str(token_file)
        self.connect_timeout = connect_timeout
        self._sock: Optional[socket.socket] = None
        self.operator_id: Optional[str] = None
        self.session_id: Optional[str] = None

    # -- connection lifecycle ---------------------------------------------

    def connect(self) -> Dict[str, Any]:
        token = Path(self.token_file).read_text().strip()
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.connect_timeout)
        s.connect(self.sock_path)
        self._send(s, {"token": token})
        auth_resp = self._recv(s)
        if not auth_resp.get("ok"):
            s.close()
            raise RuntimeClientError("authentication failed: %s" % auth_resp.get("error"))
        # Capture the operator/session identity bound to this connection.
        self.operator_id = auth_resp.get("operatorId")
        self.session_id = auth_resp.get("sessionId")
        self._sock = s
        return self.identity()

    def disconnect(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    @property
    def connected(self) -> bool:
        return self._sock is not None

    # -- query API (read-only) ---------------------------------------------

    def identity(self) -> Dict[str, Any]:
        return self._query({"op": "identity"})["result"]

    def capabilities(self) -> Dict[str, Any]:
        return self._query({"op": "capabilities"})["result"]

    def list_aggregates(self) -> List[Dict[str, Any]]:
        return self._query({"op": "list_aggregates"})["result"]

    def get_state(self, stream_id: str) -> Dict[str, Any]:
        return self._query({"op": "get_state", "streamId": stream_id})["result"]

    def get_stream_events(self, stream_id: str) -> List[Dict[str, Any]]:
        return self._query({"op": "get_stream_events", "streamId": stream_id})["result"]

    def event_timeline(self, after: int = 0) -> List[Dict[str, Any]]:
        return self._query({"op": "event_timeline", "after": after})["result"]

    def claimguard_disposition(self, statement: str) -> Dict[str, Any]:
        return self._query({"op": "claimguard", "statement": statement})["result"]

    def verification(self) -> Dict[str, Any]:
        return self._query({"op": "verification"})["result"]

    # -- command API (governed operator actions, M1) ----------------------

    def command(self, op: str, payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Issue a governed operator command to the runtime.

        The command envelope is bound to the authenticated connection's
        operatorId and sessionId. The desktop cannot claim a different
        operator or session — the runtime rejects such attempts as
        unauthorized. Returns the classified command receipt.
        """
        if self.operator_id is None or self.session_id is None:
            raise RuntimeClientError("not authenticated")
        import hashlib
        command_id = "cmd-" + hashlib.sha256(
            (op + json.dumps(payload, sort_keys=True)).encode()
        ).hexdigest()[:16]
        idek = idempotency_key or (command_id + "-idem")
        envelope = {
            "commandId": command_id,
            "operatorId": self.operator_id,
            "sessionId": self.session_id,
            "schemaVersion": "1.0.0",
            "correlationId": "corr-" + uuid.uuid4().hex,
            "idempotencyKey": idek,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "op": op,
            "payload": payload,
        }
        if self._sock is None:
            raise RuntimeClientError("not connected")
        self._send(self._sock, {"op": "command", "command": envelope})
        return self._recv(self._sock)

    # -- framed transport --------------------------------------------------

    @staticmethod
    def _send(sock: socket.socket, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        sock.sendall(len(data).to_bytes(4, "big") + data)

    @staticmethod
    def _recv(sock: socket.socket) -> Dict[str, Any]:
        header = sock.recv(4)
        if not header:
            raise RuntimeClientError("connection closed by runtime")
        length = int.from_bytes(header, "big")
        buf = b""
        while len(buf) < length:
            chunk = sock.recv(length - len(buf))
            if not chunk:
                raise RuntimeClientError("connection closed mid-frame")
            buf += chunk
        return json.loads(buf.decode("utf-8"))

    def _query(self, request: Dict[str, Any]) -> Dict[str, Any]:
        if self._sock is None:
            raise RuntimeClientError("not connected")
        self._send(self._sock, request)
        resp = self._recv(self._sock)
        if not resp.get("ok"):
            raise RuntimeClientError(resp.get("error", "unknown error"))
        return resp


# --------------------------------------------------------------------------
# Projections (read models derived from authoritative runtime state)
# --------------------------------------------------------------------------

def project_mission_view(client: RuntimeClient, mission_id: str = DEMO_MISSION_ID) -> Dict[str, Any]:
    """Build the full M0 vertical-slice view from authoritative runtime data.

    Returns a read model containing MissionSpec, TaskGraph, DriverRun,
    capability scopes, event timeline, evidence, verification result, and
    ClaimGuard disposition. Every field is sourced from the runtime service;
    nothing here is authoritative CAPT state — it is a projection.
    """
    mission_state = client.get_state("mission-" + mission_id)
    task_state = client.get_state("task-" + DEMO_TASK_ID)
    driver_run_state = client.get_state("driverrun-" + DEMO_DRIVER_RUN_ID)
    grant_state = client.get_state("capability-" + DEMO_GRANT_ID)
    # The lease is part of the grant aggregate state (CAPT stores leases under
    # the grant stream). No separate lease stream exists.
    lease_state = grant_state.get("lease") if grant_state else None
    claim_state = client.get_state("claim-" + DEMO_CLAIM_ID)

    mission_events = client.get_stream_events("mission-" + mission_id)
    timeline = client.event_timeline()

    # ClaimGuard disposition is computed by the runtime (read-only), not stored
    # as a desktop decision.
    claimguard = client.claimguard_disposition(
        claim_state.get("statement", "Repository inspected in read-only mode.")
        if claim_state else "Repository inspected in read-only mode."
    )

    return {
        "missionSpec": mission_state,
        "taskGraph": task_state,
        "driverRun": driver_run_state,
        "capabilityScopes": {
            "grant": grant_state,
            "lease": lease_state,
        },
        "eventTimeline": timeline,
        "missionEvents": mission_events,
        "claim": claim_state,
        "claimGuardDisposition": claimguard,
        "evidence": _extract_evidence(mission_events),
        "verification": client.verification(),
    }


def _extract_evidence(mission_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for env in mission_events:
        payload = env.get("payload", {})
        if payload.get("eventType") == "EvidenceRecorded":
            out.append(payload.get("evidence", {}))
    return out


# --------------------------------------------------------------------------
# M1 projections (governed operator actions read models)
# --------------------------------------------------------------------------

def project_approval_queue(client: RuntimeClient) -> List[Dict[str, Any]]:
    """Return all HumanApprovalRequest states from authoritative runtime data."""
    out = []
    for agg in client.list_aggregates():
        if agg["kind"] != "human_approval":
            continue
        st = client.get_state(agg["streamId"])
        if st:
            out.append(st)
    return out


def project_cancellation_state(client: RuntimeClient, target_id: str, kind: str) -> Optional[Dict[str, Any]]:
    """Return the authoritative cancellation/terminal state of a task or run."""
    st = client.get_state(kind + "-" + target_id)
    if not st:
        return None
    return {
        "targetId": target_id,
        "kind": kind,
        "state": st.get("state"),
        "reconciliationStatus": st.get("reconciliationStatus"),
    }


def project_authoritative_state(client: RuntimeClient) -> Dict[str, Any]:
    """Reconstruct the full authoritative desktop view from runtime state.

    Deterministic: built only from authoritative aggregates and the event
    timeline. Handles duplicate/out-of-order delivery safely because it reads
    final aggregate snapshots (idempotent) rather than replaying events.
    """
    aggregates = client.list_aggregates()
    missions, tasks, approvals, driver_runs, claims = [], [], [], [], []
    for agg in aggregates:
        st = client.get_state(agg["streamId"])
        if st is None:
            continue
        if agg["kind"] == "mission":
            missions.append(st)
        elif agg["kind"] == "task":
            tasks.append(st)
        elif agg["kind"] == "human_approval":
            approvals.append(st)
        elif agg["kind"] == "driverrun":
            driver_runs.append(st)
        elif agg["kind"] == "claim":
            claims.append(st)
    return {
        "missions": missions,
        "tasks": tasks,
        "approvals": approvals,
        "driverRuns": driver_runs,
        "claims": claims,
        "eventTimeline": client.event_timeline(),
        "verification": client.verification(),
        "identity": client.identity(),
    }


def project_mission_spec(client: RuntimeClient, mission_id: str) -> Optional[Dict[str, Any]]:
    """Return the authoritative MissionSpec (mission aggregate state)."""
    return client.get_state("mission-" + mission_id)


def project_task_graph(client: RuntimeClient, task_id: str) -> Optional[Dict[str, Any]]:
    """Return the authoritative TaskGraph (task aggregate state)."""
    return client.get_state("task-" + task_id)


def project_driver_run(client: RuntimeClient, driver_run_id: str) -> Optional[Dict[str, Any]]:
    """Return the authoritative DriverRun state."""
    return client.get_state("driverrun-" + driver_run_id)


def project_evidence(client: RuntimeClient, mission_id: str) -> List[Dict[str, Any]]:
    """Return evidence recorded for a mission (read-only projection)."""
    events = client.get_stream_events("mission-" + mission_id)
    return _extract_evidence(events)


def project_claimguard(client: RuntimeClient, statement: str) -> Dict[str, Any]:
    """Return the runtime-computed ClaimGuard disposition (read-only)."""
    return client.claimguard_disposition(statement)
