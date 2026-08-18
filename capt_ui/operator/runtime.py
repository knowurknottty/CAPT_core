"""Shared operator runtime facade.

A thin, surface-agnostic wrapper over RuntimeClient that exposes a stable
operator API consumed by CLI, TUI, Desktop, and future Web surfaces.
All mutations route through governed command ops; UI-derived state is projection only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .contract import ApproxRequest, Dashboard, EvidenceView, OperatorStatus, RuntimeHealth, health_of
from .epistemics import project_epistemic_ladder
from .leases import project_capability_leases

try:
    from desktop.desktop_runtime_client import (  # type: ignore
        RuntimeClient,
        project_approval_queue,
        project_authoritative_state,
        project_claimguard,
        project_evidence,
        project_mission_spec,
        project_mission_view,
    )
except Exception:  # pragma: no cover
    RuntimeClient = None  # type: ignore
    project_authoritative_state = None  # type: ignore


class OperatorError(RuntimeError):
    pass


class Operator:
    def __init__(self, sock_path: str, token_file: str) -> None:
        if RuntimeClient is None:
            raise OperatorError("runtime client unavailable")
        self._client = RuntimeClient(sock_path, token_file)
        self._identity: Dict[str, Any] = {}
        self._connected = False

    @property
    def client(self) -> Any:
        return self._client

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> Dict[str, Any]:
        try:
            self._identity = self._client.connect()
            self._connected = True
        except Exception as exc:  # noqa: BLE001
            self._connected = False
            raise OperatorError("Could not connect to the CAPT runtime: %s" % _human(exc))
        return self._identity

    def disconnect(self) -> None:
        try:
            self._client.disconnect()
        finally:
            self._connected = False

    def status(self) -> OperatorStatus:
        if not self._connected:
            return OperatorStatus(health=RuntimeHealth.STOPPED)
        ident = self._client.identity()
        caps = self._client.capabilities()
        return OperatorStatus(
            health=health_of(ident, True),
            runtime_version=ident.get("runtimeVersion", ""),
            integrity=ident.get("integrity", ""),
            head_sequence=ident.get("headSequence", 0) or 0,
            raw={
                "id": str(ident),
                "query_ops": caps.get("queryOperations", []),
                "command_ops": caps.get("commandOperations", []),
            },
        )

    def dashboard(self) -> Dashboard:
        if not self._connected:
            return Dashboard()
        st = project_authoritative_state(self._client)  # type: ignore
        approvals = project_approval_queue(self._client)  # type: ignore
        claims = list(st.get("claims", []))
        verifications_by_claim = dict(st.get("verificationsByClaim", {}))
        if len(verifications_by_claim) == 1:
            compatibility_verification = next(iter(verifications_by_claim.values()))
        elif len(verifications_by_claim) > 1:
            compatibility_verification = {
                "status": {"kind": "claim_scoped"},
                "claimCount": len(verifications_by_claim),
                "note": "Use verifications_by_claim / epistemic_ladder; no global verification scalar exists.",
            }
        else:
            compatibility_verification = {}
        dash = Dashboard(
            status=OperatorStatus(health=health_of(self._client.identity(), True)),
            missions=st.get("missions", []),
            tasks=st.get("tasks", []),
            approvals=[_to_approval(a) for a in approvals],
            driver_runs=st.get("driverRuns", []),
            claims=claims,
            events=st.get("eventTimeline", []),
            verification=compatibility_verification,
            verifications_by_claim=verifications_by_claim,
            epistemic_ladder=project_epistemic_ladder(claims, verifications_by_claim),
            ledger_chain_digest=st.get("identity", {}).get("ledgerChainDigest", ""),
        )
        dash.status.head_sequence = st.get("identity", {}).get("headSequence", 0) or 0
        dash.status.integrity = st.get("identity", {}).get("integrity", "")
        dash.status.approvals_pending = len(dash.approvals)
        dash.evidence = EvidenceView(verification=dash.verification)
        return dash

    def capability_leases(self, now: Optional[str] = None) -> List[Dict[str, Any]]:
        """Project current authoritative capability/lease states for display."""
        states: List[Dict[str, Any]] = []
        for aggregate in self._client.list_aggregates():
            if aggregate.get("kind") != "capability":
                continue
            state = self._client.get_state(aggregate["streamId"])
            if state:
                states.append(state)
        return project_capability_leases(states, now=now)

    def create_mission(self, payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        return self._client.command("create_mission", payload, idempotency_key)

    def decide_approval(self, request_id: str, decision: str, note: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"requestId": request_id, "decision": decision}
        if note:
            payload["note"] = note
        return self._client.command("submit_approval_decision", payload)

    def cancel_task(self, task_id: str, reason: str = "operator stop") -> Dict[str, Any]:
        return self._client.command("cancel_task", {"taskId": task_id, "reason": reason})

    def cancel_driver_run(self, driver_run_id: str, reason: str = "operator stop") -> Dict[str, Any]:
        return self._client.command("cancel_driver_run", {"driverRunId": driver_run_id, "reason": reason})

    def steer_deliberation(self, cohort_id: str, directive: str, *, reason: str = "operator steering") -> Dict[str, Any]:
        return self._client.command("steer_deliberation", {"cohortId": cohort_id, "directive": directive, "reason": reason})

    def revoke_capability(
        self,
        grant_id: str,
        *,
        target_kind: str,
        target_id: str,
        reason: str,
        revocation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request governed grant/lease revocation through RuntimeService authority."""
        payload: Dict[str, Any] = {
            "grantId": grant_id,
            "targetKind": target_kind,
            "targetId": target_id,
            "reason": reason,
        }
        if revocation_id:
            payload["revocationId"] = revocation_id
        return self._client.command("revoke_capability", payload, idempotency_key)

    def update_memory_policy(self, payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        return self._client.command("update_memory_trigger_policy", payload, idempotency_key)

    def checkpoint(self) -> Dict[str, Any]:
        return self._client.command("checkpoint_runtime", {})

    def resume(self) -> Dict[str, Any]:
        return self._client.command("resume_runtime", {})

    def shutdown(self) -> Dict[str, Any]:
        return self._client.command("shutdown", {})

    def evidence(self, mission_id: str = "") -> EvidenceView:
        if not self._connected:
            return EvidenceView()
        try:
            artifacts = project_evidence(self._client, mission_id)  # type: ignore
        except Exception:  # noqa: BLE001
            artifacts = []
        return EvidenceView(artifacts=artifacts, verification=self.dashboard().verification)

    def claimguard(self, statement: str) -> Dict[str, Any]:
        return project_claimguard(self._client, statement)  # type: ignore

    def memory_policy(self) -> Dict[str, Any]:
        try:
            return self._client._query({"op": "get_memory_policy"})["result"]  # type: ignore
        except Exception:  # noqa: BLE001
            return {}

    def memory_state(self) -> Dict[str, Any]:
        try:
            return self._client._query({"op": "get_memory_state", "missionId": ""})["result"]  # type: ignore
        except Exception:  # noqa: BLE001
            return {}

    def store_memory(self, content: str, *, namespace: str = "default", tags: Optional[List[str]] = None, provenance: str = "operator") -> Dict[str, Any]:
        try:
            from capt_solo.memory.engine import MemoryEngine
            from capt_solo.core.config import memory_db_path
            engine = MemoryEngine(memory_db_path())
            mem = engine.store(content, namespace=namespace, tags=tags or [], provenance=provenance)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:160]}
        return {
            "ok": True,
            "memory_id": getattr(mem, "memory_id", ""),
            "content": getattr(mem, "content", ""),
            "namespace": getattr(mem, "namespace", namespace),
            "tier": getattr(mem, "tier", "durable"),
        }


def _to_approval(a: Dict[str, Any]) -> ApproxRequest:
    return ApproxRequest(
        request_id=a.get("requestId", ""), mission_id=a.get("missionId", ""),
        task_id=a.get("taskId", ""), capability=a.get("requestedCapability", ""),
        operation=a.get("operation", ""), scope=str(a.get("scope", "")),
        risk=a.get("riskClassification", ""), state=a.get("state", ""),
        policy_reason=a.get("policyReason", ""),
    )


def _human(exc: Exception) -> str:
    msg = str(exc).strip()
    if not msg:
        return exc.__class__.__name__
    return (msg.splitlines() or [msg])[0][:200]
