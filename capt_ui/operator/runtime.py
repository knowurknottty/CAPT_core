"""Shared operator runtime facade.

A thin, surface-agnostic wrapper over RuntimeClient that exposes a stable
operator API consumed by CLI, TUI, Desktop, and future Web surfaces.

It reuses the proven projection functions in desktop.desktop_runtime_client
and never duplicates runtime authority. All mutations route through governed
command ops.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .epistemics import project_epistemic_ladder
from .leases import project_capability_leases

from .cohort_chamber import project_cohort_chamber
from .contract import (
    ApproxRequest,
    Dashboard,
    EvidenceView,
    OperatorStatus,
    RuntimeHealth,
    health_of,
)

try:  # fall back so pure-view code can import without a live socket
    from desktop.desktop_runtime_client import (  # type: ignore
        RuntimeClient,
        project_approval_queue,
        project_authoritative_state,
        project_claimguard,
        project_evidence,
        project_mission_spec,
        project_mission_view,
    )
except Exception:  # pragma: no cover - dev convenience
    RuntimeClient = None  # type: ignore
    project_authoritative_state = None  # type: ignore


class OperatorError(RuntimeError):
    """Raised for operator-layer errors, translated for the user."""


class Operator:
    """The single shared operator API over CAPT RuntimeService."""

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

    def cohort_chamber(self, cohort_id: str) -> Dict[str, Any]:
        """Project one authoritative Cohort aggregate for operator inspection."""
        state = self._client.get_state("cohort-" + str(cohort_id))
        if not state:
            raise OperatorError("Cohort %s not found" % cohort_id)
        return project_cohort_chamber(state)

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

    # -- governed controls ------------------------------------------------
    def replay_state_at(self, global_sequence: int, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """Read deterministic historical state without mutating RuntimeService."""
        request: Dict[str, Any] = {
            "op": "replay_state_at",
            "globalSequence": int(global_sequence),
        }
        if stream_id is not None:
            request["streamId"] = stream_id
        return self._client._query(request)["result"]  # type: ignore

    def create_replay_fork(
        self, payload: Dict[str, Any], idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit governed replay-fork intent; RuntimeService builds authority state."""
        return self._client.command("create_replay_fork", payload, idempotency_key)

    def create_mission(self, payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        return self._client.command("create_mission", payload, idempotency_key)

    def compile_prompt_proposal(
        self, payload: Dict[str, Any], idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Ask RuntimeService to compile a durable PromptProposal."""
        return self._client.command("compile_prompt_proposal", payload, idempotency_key)

    def request_prompt_proposal_approval(
        self, payload: Dict[str, Any], idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Request HumanApproval bound to one exact PromptProposal revision/selection."""
        return self._client.command("request_prompt_proposal_approval", payload, idempotency_key)

    def request_prompt_approval(
        self, payload: Dict[str, Any], idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Request a runtime-owned approval receipt for the exact prompt assembly."""
        return self._client.command("request_model_prompt_approval", payload, idempotency_key)

    def decide_approval(self, request_id: str, decision: str, note: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"requestId": request_id, "decision": decision}
        if note:
            payload["note"] = note
        return self._client.command("submit_approval_decision", payload)

    def approval_state(self, request_id: str) -> Dict[str, Any]:
        """Read the authoritative HumanApproval aggregate after a decision."""
        state = self._client.get_state("human_approval-" + str(request_id))
        if not isinstance(state, dict):
            raise OperatorError("HumanApproval %s not found" % request_id)
        return state

    def request_council_workflow(self, workflow: Any) -> Dict[str, Any]:
        """Request one exact HumanApproval per cohort without auto-approving."""
        from .council_workflow import bind_approval_results, workflow_digest

        workflow.validate()
        digest = workflow_digest(workflow)
        short = digest.split(":", 1)[-1][:16]
        approvals: List[Dict[str, Any]] = []
        for index, payload in enumerate(workflow.approval_payloads(), 1):
            receipt = self.request_prompt_approval(
                payload, "council-workflow:%s:approval:%02d" % (short, index)
            )
            if receipt.get("status") not in ("accepted", "idempotent"):
                raise OperatorError(
                    "Cohort approval request rejected: %s"
                    % (receipt.get("detail") or receipt.get("error") or receipt)
                )
            approvals.append(dict(receipt["result"]))
        return {
            "schemaVersion": "1.0.0",
            "workflowDigest": digest,
            "workflow": workflow.to_record(),
            "approvals": approvals,
            "executions": bind_approval_results(workflow, approvals),
        }

    def council_workflow_status(self, session: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return authoritative approval state for every cohort in a prepared session."""
        rows: List[Dict[str, Any]] = []
        for approval in session.get("approvals") or []:
            request_id = str(approval.get("requestId") or "")
            state = self.approval_state(request_id)
            rows.append({
                "cohortId": (approval.get("cohortSpec") or {}).get("cohortId"),
                "provider": approval.get("provider"),
                "model": approval.get("model"),
                "requestId": request_id,
                "state": state.get("state"),
                "consumedBy": state.get("consumedBy"),
                "consumedAt": state.get("consumedAt"),
                "commandIssuedAt": state.get("commandIssuedAt"),
                "driverRunId": state.get("driverRunId"),
                "missionId": state.get("missionId"),
                "taskId": state.get("taskId"),
                "remainingUses": state.get("remainingUses"),
                "expiresAt": state.get("expiresAt"),
            })
        return rows

    def decide_council_workflow(
        self, session: Dict[str, Any], decision: str, note: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Apply an explicit human approve/deny decision to each pending cohort."""
        if decision not in ("approve", "deny"):
            raise OperatorError("Council decision must be approve or deny")
        receipts: List[Dict[str, Any]] = []
        for row in self.council_workflow_status(session):
            if row["state"] == "requested":
                receipts.append(self.decide_approval(row["requestId"], decision, note))
        return receipts

    def run_council_workflow(
        self, session: Dict[str, Any], *, reattach: bool = False
    ) -> Dict[str, Any]:
        """Launch only after every runtime-owned cohort approval is approved.

        With ``reattach=True`` (see :meth:`reattach_council_workflow`), an
        approval already ``consumed`` by this exact council lineage may be
        reattached after transport loss: the approval's ``consumedBy`` must
        equal the expected per-cohort use id derived from the session's own
        workflow digest (``<run_key>:cohort:<cohortId>``). A consumed approval
        from any other council, workflow, or idempotency lineage fails closed.

        Reattach re-observes durable state and replays the same durable
        idempotency identity through the existing duplicate path: completed
        runs are harvestable, running runs are observable, and provider
        dispatch happens at most once. It never manufactures a fresh attempt
        or redispatches provider inference.
        """
        from .council_workflow import (
            CouncilWorkflow,
            council_launch_payload,
            workflow_digest,
        )

        caps = self._client.capabilities()
        if "run_approved_council_inspection" not in set(caps.get("commandOperations") or []):
            raise OperatorError("Runtime lacks governed Council execution support")
        statuses = self.council_workflow_status(session)
        # P0.2: validate structure, then recompute the canonical digest and
        # require exact equality with the session's claimed digest BEFORE
        # deriving any identity. A mutated workflow with a stale digest, or a
        # forged digest for a different workflow, fails closed here.
        workflow = CouncilWorkflow.from_mapping(session["workflow"]).validate()
        actual_digest = workflow_digest(workflow)
        claimed_digest = session.get("workflowDigest")
        if not isinstance(claimed_digest, str) or claimed_digest != actual_digest:
            raise OperatorError(
                "Council workflow digest mismatch: session claims %r but the "
                "validated workflow digests to %r"
                % (claimed_digest, actual_digest)
            )
        # The run key derives from the RECOMPUTED digest, never from the
        # caller-supplied string.
        short = actual_digest.split(":")[-1][:16]
        run_key = "council-workflow:%s:run" % short
        blockers = []
        for row in statuses:
            state = row.get("state")
            if state == "approved":
                continue
            expected_use_id = "%s:cohort:%s" % (run_key, row.get("cohortId"))
            if (
                reattach
                and state == "consumed"
                and row.get("consumedBy") == expected_use_id
            ):
                # Same council lineage: this cohort's approval was consumed by
                # this council's own admission. Reattach replays the durable
                # idempotency identity; dispatch happens at most once.
                continue
            blockers.append({
                "cohortId": row.get("cohortId"),
                "state": state,
                "consumedBy": row.get("consumedBy"),
                "expectedUseId": expected_use_id,
            })
        if blockers:
            raise OperatorError("Council approvals are not all approved: %s" % blockers)
        payload = council_launch_payload(workflow, session.get("executions") or [])
        return self._client.command(
            "run_approved_council_inspection",
            payload,
            run_key,
        )

    def reattach_council_workflow(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Reattach a council session after transport loss.

        Equivalent to ``run_council_workflow(session, reattach=True)``: only
        approvals already consumed by this exact council lineage are accepted;
        anything else fails closed. Repeated reattachment is idempotent and
        never redispatches provider inference.
        """
        return self.run_council_workflow(session, reattach=True)
    def cancel_task(self, task_id: str, reason: str = "operator stop") -> Dict[str, Any]:
        return self._client.command("cancel_task", {"taskId": task_id, "reason": reason})

    def cancel_driver_run(self, driver_run_id: str, reason: str = "operator stop") -> Dict[str, Any]:
        return self._client.command("cancel_driver_run", {"driverRunId": driver_run_id, "reason": reason})

    def steer_deliberation(
        self, cohort_id: str, directive: str, *, reason: str = "operator steering"
    ) -> Dict[str, Any]:
        """Submit a governed human steering directive for a durable Cohort."""
        return self._client.command(
            "steer_deliberation",
            {"cohortId": cohort_id, "directive": directive, "reason": reason},
        )

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

    def store_memory(
        self,
        content: str,
        *,
        namespace: str = "default",
        tags: Optional[List[str]] = None,
        provenance: str = "operator",
    ) -> Dict[str, Any]:
        try:
            from capt_solo.memory.engine import MemoryEngine
            from capt_solo.core.config import memory_db_path

            engine = MemoryEngine(memory_db_path())
            mem = engine.store(
                content, namespace=namespace, tags=tags or [], provenance=provenance
            )
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
        request_id=a.get("requestId", ""),
        mission_id=a.get("missionId", ""),
        task_id=a.get("taskId", ""),
        capability=a.get("requestedCapability", ""),
        operation=a.get("operation", ""),
        scope=str(a.get("scope", "")),
        risk=a.get("riskClassification", ""),
        state=a.get("state", ""),
        policy_reason=a.get("policyReason", ""),
    )


def _human(exc: Exception) -> str:
    msg = str(exc).strip()
    if not msg:
        return exc.__class__.__name__
    return (msg.splitlines() or [msg])[0][:200]
