"""MemoryGovernor — plugin-triggered, threshold-enforced context governor.

This is NOT a voluntary-call governor. The model is not a reliable trigger
source. Plugin hooks (pre_llm_call / post_llm_call / on_session_end) are the
ONLY trigger mechanism.

Responsibilities:
- Maintain deterministic context estimator from observable events
- Enforce SOFT/HARD/EMERGENCY thresholds BEFORE Hermes native compaction
- Offload exact governed state to CAPTMem with immutable references/digests
- Compile bounded ContextPack from persisted records
- Reinjection or durable session handoff without operator restatement

Semantic distinctions:
- HERMES_COMPRESSION: lossy provider/host-owned summary (UNTRUSTED)
- CAPTMEM_OFFLOAD: exact governed persistence outside model context (TRUSTED)
- CONTEXTPACK_REHYDRATION: bounded working context compiled from CAPTMem
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from .accounting import ContextAccounting, ContextUsage, TriggerState
from .contextpack import build_context_pack
from .engine import MemoryTriggerEngine, MemoryEnforcementError
from .policy import MemoryTriggerPolicy, PolicySource, TRIGGER_INTERVAL_TOKENS
from .query import build_memory_query
from .store import MemoryRecord, MemoryStore


class MemoryGovernor:
    """Plugin-triggered governor for CAPT memory continuity.

    Does NOT depend on model voluntarily calling it. Plugin hooks are the
    trigger mechanism. Enforces thresholds proactively before Hermes compaction.
    """

    def __init__(
        self,
        store: MemoryStore,
        engine: MemoryTriggerEngine,
        *,
        mission_id: str,
        operator_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model_provider: Optional[str] = None,
        effective_context_tokens: int = 64_768,
        ladder_step: int = 32_768,
        soft_threshold: Optional[int] = None,
        hard_threshold: Optional[int] = None,
        emergency_threshold: Optional[int] = None,
    ) -> None:
        self.store = store
        self.engine = engine
        self.mission_id = mission_id
        self.operator_id = operator_id
        self.session_id = session_id or "unknown"
        self.model_provider = model_provider or "unknown"
        self.effective_context_tokens = effective_context_tokens

        # Default thresholds per prompt specification
        self.ladder_step = ladder_step
        self.soft_threshold = soft_threshold or ladder_step
        self.hard_threshold = hard_threshold or min(
            self.ladder_step * 2 - 4_096,
            int(effective_context_tokens * 0.75)
        )
        self.emergency_threshold = emergency_threshold or int(
            effective_context_tokens * 0.85
        )

        # Estimator state
        self._estimated_tokens = 0
        self._system_prompt_baseline = 0
        self._skill_content_tokens = 0
        self._memory_provider_tokens = 0
        self._conversation_tokens = 0
        self._tool_output_tokens = 0
        self._last_offload_boundary = 0
        self._current_packet_id: Optional[str] = None
        self._exact_next_action: Optional[str] = None
        self._completed_packet_ids: List[str] = []
        self._unresolved_state: Dict[str, Any] = {}
        self._authority_state: Dict[str, Any] = {}
        self._threshold_crossed = {
            "soft": False,
            "hard": False,
            "emergency": False,
        }

        # Initialize mission checkpoint
        self._checkpoint_mission_start()

    def _checkpoint_mission_start(self) -> None:
        """Persist mission start checkpoint with exact provenance."""
        record = MemoryRecord(
            record_id=f"mission-start-{self.mission_id}-{self.session_id}",
            memory_class="episodic",
            owner=self.operator_id or "operator",
            source="capt_runtime.memory.governor",
            provenance=f"mission:{self.mission_id};session:{self.session_id}",
            trust="capt_authoritative",
            verification_status="verified",
            sensitivity="project",
            consent="project",
            content=json.dumps({
                "mission_id": self.mission_id,
                "session_id": self.session_id,
                "model_provider": self.model_provider,
                "effective_context_tokens": self.effective_context_tokens,
                "ladder_step": self.ladder_step,
                "soft_threshold": self.soft_threshold,
                "hard_threshold": self.hard_threshold,
                "emergency_threshold": self.emergency_threshold,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }),
        )
        self.store.store(record)

    def estimate_tokens_from_message(self, message: Dict[str, Any]) -> int:
        """Estimate tokens consumed by a single message."""
        content = message.get("content", "") or ""
        role = message.get("role", "unknown")
        # Approximate: 1 token ~= 4 chars for English text
        return max(1, len(content) // 4)

    def estimate_tokens_from_tool_call(self, tool_call: Dict[str, Any]) -> int:
        """Estimate tokens consumed by a tool call."""
        name = tool_call.get("name", "") or ""
        args = tool_call.get("args", {}) or {}
        args_str = json.dumps(args)
        return max(1, (len(name) + len(args_str)) // 4)

    def estimate_tokens_from_tool_result(self, result: Dict[str, Any]) -> int:
        """Estimate tokens consumed by tool output."""
        output = result.get("output", "") or result.get("result", "") or ""
        return max(1, len(str(output)) // 4)

    def update_estimator_on_pre_call(
        self,
        conversation_history: List[Dict[str, Any]],
        system_prompt_length: Optional[int] = None,
        skill_content_length: Optional[int] = None,
        memory_provider_length: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update estimator before model call. Returns threshold status."""
        # System prompt baseline (fixed per session start)
        if system_prompt_length is not None:
            self._system_prompt_baseline = system_prompt_length
        if skill_content_length is not None:
            self._skill_content_tokens = skill_content_length
        if memory_provider_length is not None:
            self._memory_provider_tokens = memory_provider_length

        # Conversation history accumulation
        self._conversation_tokens = sum(
            self.estimate_tokens_from_message(msg)
            for msg in conversation_history
        )

        # Total estimate
        self._estimated_tokens = (
            self._system_prompt_baseline +
            self._skill_content_tokens +
            self._memory_provider_tokens +
            self._conversation_tokens +
            self._tool_output_tokens
        )

        return self._check_thresholds()

    def update_estimator_on_post_call(
        self,
        assistant_message: Dict[str, Any],
        tool_calls: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Update estimator after model call with tool activity."""
        self._conversation_tokens += self.estimate_tokens_from_message(
            assistant_message
        )
        for tc in tool_calls:
            self._conversation_tokens += self.estimate_tokens_from_tool_call(tc)
        for tr in tool_results:
            self._tool_output_tokens += self.estimate_tokens_from_tool_result(tr)

        self._estimated_tokens = (
            self._system_prompt_baseline +
            self._skill_content_tokens +
            self._memory_provider_tokens +
            self._conversation_tokens +
            self._tool_output_tokens
        )

        return self._check_thresholds()

    def _check_thresholds(self) -> Dict[str, Any]:
        """Check which thresholds have been crossed."""
        status = {
            "estimated_tokens": self._estimated_tokens,
            "soft_threshold": self.soft_threshold,
            "hard_threshold": self.hard_threshold,
            "emergency_threshold": self.emergency_threshold,
            "crossed": [],
            "action_required": None,
        }

        if self._estimated_tokens >= self.emergency_threshold:
            if not self._threshold_crossed["emergency"]:
                self._threshold_crossed["emergency"] = True
                status["crossed"].append("emergency")
                status["action_required"] = "EMERGENCY_OFFLOAD"
        elif self._estimated_tokens >= self.hard_threshold:
            if not self._threshold_crossed["hard"]:
                self._threshold_crossed["hard"] = True
                status["crossed"].append("hard")
                status["action_required"] = "HARD_OFFLOAD"
        elif self._estimated_tokens >= self.soft_threshold:
            if not self._threshold_crossed["soft"]:
                self._threshold_crossed["soft"] = True
                status["crossed"].append("soft")
                status["action_required"] = "SOFT_OFFLOAD"

        return status

    def offload_governed_state(
        self,
        trigger_cause: str,
        current_packet_id: Optional[str] = None,
        exact_next_action: Optional[str] = None,
        completed_packet_ids: Optional[List[str]] = None,
        unresolved_state: Optional[Dict[str, Any]] = None,
        authority_state: Optional[Dict[str, Any]] = None,
        repository_state: Optional[Dict[str, Any]] = None,
        decisions_log: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Offload exact governed state to CAPTMem with immutable references."""
        # Build governed state record
        governed_state = {
            "mission_id": self.mission_id,
            "session_id": self.session_id,
            "trigger_cause": trigger_cause,
            "estimated_tokens_at_offload": self._estimated_tokens,
            "current_packet_id": current_packet_id or self._current_packet_id,
            "exact_next_action": exact_next_action or self._exact_next_action,
            "completed_packet_ids": completed_packet_ids or self._completed_packet_ids,
            "unresolved_state": unresolved_state or self._unresolved_state,
            "authority_state": authority_state or self._authority_state,
            "repository_state": repository_state or {},
            "decisions_log": decisions_log or [],
            "model_provider": self.model_provider,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Store as CAPTMem record with immutable digest
        content = json.dumps(governed_state, sort_keys=True)
        digest = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()

        record = MemoryRecord(
            record_id=f"offload-{self.mission_id}-{self.session_id}-{digest[-16:]}",
            memory_class="episodic",
            owner=self.operator_id or "operator",
            source="capt_runtime.memory.governor",
            provenance=f"mission:{self.mission_id};session:{self.session_id};trigger:{trigger_cause}",
            trust="capt_authoritative",
            verification_status="verified",
            sensitivity="project",
            consent="project",
            content=content,
        )
        record.digest = digest
        self.store.store(record)

        # Update internal state
        self._current_packet_id = current_packet_id
        self._exact_next_action = exact_next_action
        self._completed_packet_ids = completed_packet_ids or self._completed_packet_ids
        self._unresolved_state = unresolved_state or self._unresolved_state
        self._authority_state = authority_state or self._authority_state
        self._last_offload_boundary = self._estimated_tokens

        return {
            "offload_id": record.record_id,
            "digest": digest,
            "trigger_cause": trigger_cause,
            "estimated_tokens_at_offload": self._estimated_tokens,
            "timestamp": record.created_at,
        }

    def compile_context_pack(
        self,
        token_budget: int = 16_384,
        include_mission_state: bool = True,
        include_unresolved: bool = True,
    ) -> Dict[str, Any]:
        """Compile bounded ContextPack from persisted records."""
        # Build memory query for ContextPack assembly
        query = build_memory_query(
            mission_id=self.mission_id,
            task_id=self.mission_id,
            actor="runtime",
            requesting_subsystem="capt_runtime.memory.governor",
            trigger_boundary=self._last_offload_boundary,
            context_usage=self._estimated_tokens,
            requested_memory_classes=[
                "working", "episodic", "semantic", "procedural",
                "project", "user", "agent_private", "shared",
            ],
            purpose="governor context pack compilation",
            record_limit=10,
            token_budget=token_budget,
            consent_scope="project",
            sensitivity_allowance="project",
            trust_threshold=0.0,
        )

        # Build ContextPack via existing engine
        pack = build_context_pack(
            store=self.store,
            policy_version=self.engine.policy.policy_version,
            trigger_boundary=self._last_offload_boundary,
            context_usage_before=self._estimated_tokens,
            query=query,
            mission_id=self.mission_id,
        )

        # Inject mission state into ContextPack if requested
        if include_mission_state:
            pack["mission_state"] = {
                "mission_id": self.mission_id,
                "current_packet_id": self._current_packet_id,
                "exact_next_action": self._exact_next_action,
                "completed_packet_ids": self._completed_packet_ids,
            }

        if include_unresolved:
            pack["unresolved_state"] = self._unresolved_state

        return pack

    def prepare_reinjection(
        self,
        context_pack: Dict[str, Any],
        force_new_session: bool = False,
    ) -> Dict[str, Any]:
        """Prepare ContextPack for reinjection into model context."""
        return {
            "context_pack": context_pack,
            "force_new_session": force_new_session,
            "estimated_tokens": self._estimated_tokens,
            "threshold_status": self._threshold_crossed,
            "mission_id": self.mission_id,
            "session_id": self.session_id,
            "exact_next_action": self._exact_next_action,
        }

    def get_threshold_status(self) -> Dict[str, Any]:
        """Return current threshold status."""
        return {
            "estimated_tokens": self._estimated_tokens,
            "soft_threshold": self.soft_threshold,
            "hard_threshold": self.hard_threshold,
            "emergency_threshold": self.emergency_threshold,
            "crossed": self._threshold_crossed,
            "last_offload_boundary": self._last_offload_boundary,
        }

    def reset_thresholds_for_new_ladder(self) -> None:
        """Reset thresholds after successful ContextPack rotation."""
        self._threshold_crossed = {
            "soft": False,
            "hard": False,
            "emergency": False,
        }
        self._last_offload_boundary = self._estimated_tokens

    def checkpoint_session_end(
        self,
        reason: str = "session_boundary",
    ) -> Dict[str, Any]:
        """Checkpoint at session boundary before compaction."""
        return self.offload_governed_state(
            trigger_cause=reason,
            current_packet_id=self._current_packet_id,
            exact_next_action=self._exact_next_action,
            completed_packet_ids=self._completed_packet_ids,
            unresolved_state=self._unresolved_state,
            authority_state=self._authority_state,
        )

    def resume_from_checkpoints(
        self,
        mission_id: str,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Resume execution from persisted checkpoints."""
        # Query for last offload record
        records = self.store.query(
            classes=["episodic"],
            project_scope=mission_id,
            trust_threshold=0.0,
            limit=5,
            bypass_governance=True,
        )

        last_offload = None
        for rec in records:
            if rec.record_id.startswith(f"offload-{mission_id}"):
                content = json.loads(rec.content)
                if content.get("mission_id") == mission_id:
                    last_offload = content

        if last_offload:
            self._current_packet_id = last_offload.get("current_packet_id")
            self._exact_next_action = last_offload.get("exact_next_action")
            self._completed_packet_ids = last_offload.get("completed_packet_ids", [])
            self._unresolved_state = last_offload.get("unresolved_state", {})
            self._authority_state = last_offload.get("authority_state", {})

        return last_offload
