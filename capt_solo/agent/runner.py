"""CAPT Agent Runner — narrow turn loop (ADR-0001, Outcome C).

The runner is the canonical OUTER loop. It composes the single composition root
:class:`capt_solo.runtime.CAPTRuntime` and its governed model path
``execute_model_task`` — which already enforces MemoryUseGate-before-provider at
RUNTIME (runtime.py:636-674). The runner does NOT re-implement the gate, CTP,
KHSB, ClaimGuard, or checkpoints; it threads them.

V1 scope: boot → mint bounded Intent → one governed no-tool turn → checkpoint →
render via OutputPolicy. No tools: a model-emitted tool request is reported and
NOT executed. Continuity across processes is via CAPT state (fresh-process
resume), never the transcript.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from capt_solo.agent import output as output_mod
from capt_solo.agent.boot import boot
from capt_solo.agent.contracts import (
    EXECUTION_MODE_BLOCKED,
    AgentBootRequest,
    AgentBootResult,
    AgentRunState,
    AgentTurnRequest,
    AgentTurnResult,
    IntentRecord,
)
from capt_solo.contextpack import MissionIntent, RecordRef
from capt_solo.evidence import CheckpointStore
from capt_solo.runtime import CAPTRuntime, GateDeniedError, RuntimeConfiguration


class AgentRunner:
    """Composes CAPTRuntime for a bounded agent run. Single composition root."""

    def __init__(self, runtime: CAPTRuntime) -> None:
        # The runner does not construct canonical subsystems; it borrows the
        # runtime's owned instances (gate/ctp/khsb/claimguard/lifecycle).
        self.rt = runtime

    # ----- lifecycle --------------------------------------------------------
    @classmethod
    def load(cls, configuration: Optional[RuntimeConfiguration] = None) -> "AgentRunner":
        return cls(CAPTRuntime.load(configuration))

    def close(self) -> None:
        self.rt.close()

    # ----- boot -------------------------------------------------------------
    def boot(
        self,
        request: AgentBootRequest,
        *,
        session_bound_mission_id: Optional[str] = None,
    ) -> AgentBootResult:
        return boot(
            request, runtime=self.rt, session_bound_mission_id=session_bound_mission_id
        )

    def run_state(self, boot_result: AgentBootResult) -> AgentRunState:
        return AgentRunState(
            agent_run_id=(
                boot_result.boot_trace.agent_run_id
                if boot_result.boot_trace
                else "agentrun-" + uuid.uuid4().hex[:16]
            ),
            execution_mode=boot_result.execution_mode,
            mission_id=boot_result.mission_id,
            session_id=boot_result.session_id,
            workspace_path=boot_result.workspace_path,
            git_sha=boot_result.git_sha,
            output_policy=boot_result.output_policy,
            last_checkpoint_id=boot_result.checkpoint_id,
        )

    # ----- one governed turn ------------------------------------------------
    def run_turn(
        self,
        state: AgentRunState,
        request: AgentTurnRequest,
        *,
        provider: Any,
    ) -> AgentTurnResult:
        """Execute exactly one governed, no-tool model turn.

        The provider is invoked EXACTLY once, inside
        ``CAPTRuntime.execute_model_task``, which runs the mandatory
        MemoryUseGate before the invocation. On BLOCKED boot state the provider
        is never reached.
        """
        intent = request.intent
        turn_id = intent.turn_id

        if state.execution_mode == EXECUTION_MODE_BLOCKED:
            return self._blocked_turn(intent, "boot execution mode is BLOCKED; provider not invoked")

        # Intent-bounded objective + rendered evidence (protected facts must be
        # carried into the request or the gate blocks — proving materiality).
        objective = intent.current_goal
        evidence_refs, rendered = self._intent_context(state, intent, request.user_input)
        mission_intent = MissionIntent(
            purpose=objective,
            priority="critical",
            tradeoffs=("governance strictness", "speed"),
            success_definition="; ".join(intent.completion_criteria) or "turn completes in a committed CTP tx",
            safety_constraints=("no ungoverned model execution", "no tool execution in V1"),
        )
        records = {
            "selected": f"intent={intent.intent_id} mission={state.mission_id} goal={objective}"[:400],
            "rejected": "; ".join(intent.prohibited_scope)[:400] or "none",
            "stale": "none",
            "missing": "none",
            "conflicting": "none",
        }

        # Persist the Intent as durable evidence BEFORE invocation.
        self._persist_intent(state, intent)

        self.rt.bus.publish(
            "agent.turn.started",
            {"turn_id": turn_id, "intent_id": intent.intent_id,
             "mission_id": state.mission_id, "session_id": state.session_id},
        )

        try:
            result = self.rt.execute_model_task(
                task_id=turn_id,
                mission_id=state.mission_id,
                objective=objective,
                provider=provider,
                user_prompt=request.user_input,
                capability_id=request.capability_id,
                records=records,
                intent=mission_intent,
                evidence=tuple(evidence_refs),
                rendered_context=rendered,
                session_id=state.session_id,
                claim_text=request.claim_text,
                idempotency_key=intent.digest[-16:],
                metadata={"intent_id": intent.intent_id, "intent_digest": intent.digest},
            )
        except GateDeniedError as exc:
            return self._blocked_turn(intent, f"MemoryUseGate denied: {exc}")

        # V1: reject (never execute) any model-emitted tool calls.
        tool_calls = self._extract_tool_calls(result)
        safety: List[str] = []
        if tool_calls:
            safety.append(
                f"model requested {len(tool_calls)} tool call(s); tools are out of scope in V1 "
                f"and were NOT executed"
            )

        claim_verdict = result.get("claim_verdict") or {}
        state.last_checkpoint_id = result.get("checkpoint_id", state.last_checkpoint_id)

        visible = output_mod.render(
            state.output_policy,
            summary=self._cave_summary(state, result),
            gate_result=result.get("contextpack", {}).get("validation", "PASS"),
            safety=safety,
            phase_completions=["Mission resumed.", "Memory gate passed."],
            evidence_ids=[result.get("response_artifact_id", "")],
            provider_response=result.get("response_text", ""),
        )

        return AgentTurnResult(
            ok=True,
            turn_id=turn_id,
            intent_id=intent.intent_id,
            mission_id=state.mission_id,
            session_id=state.session_id,
            tx_id=result.get("tx_id", ""),
            checkpoint_id=result.get("checkpoint_id", ""),
            response_text=result.get("response_text", ""),
            contextpack_digest=result.get("contextpack", {}).get("digest", ""),
            gate_result=result.get("contextpack", {}).get("validation", "PASS"),
            claim_supported=claim_verdict.get("supported") if claim_verdict else None,
            claim_language=claim_verdict.get("language", "") if claim_verdict else "",
            provider=result.get("provider", ""),
            model_id=result.get("model_id", ""),
            visible_output=visible,
            evidence_path=result.get("evidence_path", ""),
        )

    # ----- helpers ----------------------------------------------------------
    def _blocked_turn(self, intent: IntentRecord, reason: str) -> AgentTurnResult:
        visible = output_mod.render(intent.output_policy, blockers=[reason])
        return AgentTurnResult(
            ok=False, turn_id=intent.turn_id, intent_id=intent.intent_id,
            mission_id=intent.mission_id, session_id=intent.session_id, tx_id="",
            checkpoint_id="", response_text="", contextpack_digest="", gate_result="BLOCKED",
            block_reason=reason, visible_output=visible,
        )

    def _intent_context(self, state, intent, user_input):
        import hashlib

        embedded = {
            "intent_id": intent.intent_id,
            "mission_id": state.mission_id,
            "goal": intent.current_goal,
            "head": state.git_sha[:12],
        }
        digest = hashlib.sha256(
            json.dumps(embedded, sort_keys=True).encode()
        ).hexdigest()
        ref = RecordRef("evidence:intent-context", digest, "capt-agent-runner", embedded)
        rendered = (
            f"INTENT {intent.intent_id} mission={state.mission_id} "
            f"goal={intent.current_goal} head={state.git_sha[:12]} | "
            f"{json.dumps(embedded, sort_keys=True)}"
        )
        return [ref], rendered

    def _persist_intent(self, state: AgentRunState, intent: IntentRecord) -> str:
        import hashlib

        try:
            base = self.rt.config.evidence_dir or (Path.home() / ".capt" / "evidence")
            d = Path(base) / "agent-intent"
            d.mkdir(parents=True, exist_ok=True, mode=0o700)
            body = json.dumps(intent.to_dict(), indent=2, sort_keys=True, default=str)
            path = d / f"{intent.intent_id}.json"
            path.write_text(body, encoding="utf-8")
            h = hashlib.sha256(body.encode()).hexdigest()
            path.with_suffix(".json.sha256").write_text(f"sha256:{h}  {path.name}\n", encoding="utf-8")
            self.rt.proof.record(
                "artifact_hash", f"agent-intent:{intent.intent_id}", h,
                "capt agent intent", scope=state.mission_id,
            )
            return f"agent-intent:{intent.intent_id}"
        except Exception:
            return ""

    @staticmethod
    def _extract_tool_calls(result: Dict[str, Any]) -> List[Any]:
        tc = result.get("tool_calls")
        if tc:
            return list(tc)
        return []

    @staticmethod
    def _cave_summary(state: AgentRunState, result: Dict[str, Any]) -> str:
        return (
            f"Next: {result.get('response_text','').strip().splitlines()[0][:200]}"
            if result.get("response_text")
            else "Turn committed."
        ) + "\nCheckpoint written."


# ---------------------------------------------------------------------------
# fresh-process resume
# ---------------------------------------------------------------------------
def resume_report(
    *,
    workspace_path: str,
    mission_id: str,
    configuration: Optional[RuntimeConfiguration] = None,
) -> Dict[str, Any]:
    """Reconstruct mission state in a FRESH process from CAPT state only.

    Receives only workspace path + mission id (+ runtime config for isolated
    homes). Discovers the checkpoint, recovers the session, retrieves memory,
    reconstructs the next Intent, builds a new ContextPack, and passes the
    MemoryUseGate — no copied summary, no prior transcript. Returns an
    independent reconstruction report (also persisted).
    """
    runner = AgentRunner.load(configuration)
    try:
        boot_result = runner.boot(
            AgentBootRequest(workspace_path=workspace_path, mission_id=mission_id)
        )
        store = CheckpointStore(str(Path(workspace_path).resolve()), create=False)
        cp = store.load(mission_id)
        next_action = cp.next_safe_action if cp else ""
        report = {
            "reconstructed_in": "fresh-process",
            "mission_id": boot_result.mission_id,
            "session_id": boot_result.session_id,
            "checkpoint_id": boot_result.checkpoint_id,
            "execution_mode": boot_result.execution_mode,
            "gate_result": boot_result.gate_result,
            "active_directive_ids": list(boot_result.active_directive_ids),
            "contextpack_digest": (
                boot_result.boot_trace.contextpack_digest if boot_result.boot_trace else ""
            ),
            "intent_id": boot_result.boot_trace.intent_id if boot_result.boot_trace else "",
            "next_justified_action": next_action,
            "block_reason": boot_result.block_reason,
            "source": "CAPT state (no transcript, no copied summary)",
        }
        _persist_resume_report(runner.rt, mission_id, report)
        return report
    finally:
        runner.close()


def _persist_resume_report(runtime: CAPTRuntime, mission_id: str, report: Dict[str, Any]) -> None:
    import hashlib

    try:
        base = runtime.config.evidence_dir or (Path.home() / ".capt" / "evidence")
        d = Path(base) / "agent-resume"
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        body = json.dumps(report, indent=2, sort_keys=True, default=str)
        path = d / f"{mission_id}.json"
        path.write_text(body, encoding="utf-8")
        h = hashlib.sha256(body.encode()).hexdigest()
        path.with_suffix(".json.sha256").write_text(f"sha256:{h}  {path.name}\n", encoding="utf-8")
    except Exception:
        pass
