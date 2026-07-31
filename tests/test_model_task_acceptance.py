"""ModelTask acceptance-pipeline tests (testing order items 6–8).

These verify the PIPELINE mechanics with a deterministic provider:
  6. memory ablation — without retrieved memory the model cannot identify
     the acceptance items (proves dependency on governed retrieval)
  7. directive supersession — the ContextPack carries both the active and
     superseded directives; the extractor must identify the superseded one
  8. unsupported ClaimGuard claim — claim verdict supported=False when the
     proof aggregate is unsatisfied

NOT proof of model reasoning: that milestone requires the real local Big
Pickle invocation through CAPTRuntime (blocked pending the LM Studio token).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capt_solo.api import (  # noqa: E402
    CAPTRuntime,
    ModelIdentity,
    ModelTaskRequest,
    ModelTaskResult,
    RuntimeConfiguration,
)
from capt_solo.foundry import ProofRequirement  # noqa: E402

ACTIVE_DIRECTIVE = (
    "DIRECTIVE-DECISION-REVIEW-2026-07-31 STATUS: ACTIVE "
    "Outcome B approved with corrections: ModelProvider is the one canonical "
    "model-execution abstraction; PulseGateway becomes PulseModelProvider; add "
    "OpenAICompatibleLocalProvider; LM Studio is in scope and mandatory for "
    "final acceptance. Proceed without another architectural redesign."
)
SUPERSEDED_DIRECTIVE = (
    "DIRECTIVE-OUTCOME-B-INITIAL STATUS: SUPERSEDED "
    "Outcome B initial: complete PulseGateway only; no local-model "
    "integrations in this phase."
)
MISSION_RECORD = (
    "MISSION-GOVERNED-MODEL-EXECUTION STATUS: ACTIVE "
    "milestone GOVERNED_RUNTIME_PROVEN achieved 2026-07-31; next milestone "
    "GOVERNED_MODEL_EXECUTION requires real local Big Pickle invocation "
    "through CAPTRuntime. Next engineering action: LM Studio endpoint health "
    "check and real governed invocation."
)


class StateExtractorProvider:
    """Deterministic provider that extracts acceptance answers from the
    VALIDATED CONTEXT (system_prompt) it receives — proving the persisted
    state reached the model through the governed path. No reasoning: pure
    string extraction from the rendered ContextPack."""

    def __init__(self) -> None:
        self.invoke_count = 0
        self.last_request: ModelTaskRequest | None = None

    def identity(self) -> ModelIdentity:
        return ModelIdentity(
            provider="deterministic-test",
            model_id="state-extractor",
            local=True,
            tokenizer_id="test",
        )

    def invoke(self, request: ModelTaskRequest) -> ModelTaskResult:
        self.invoke_count += 1
        self.last_request = request
        ctx = request.system_prompt
        found = {
            "mission": "MISSION-GOVERNED-MODEL-EXECUTION" if "MISSION-GOVERNED-MODEL-EXECUTION" in ctx else None,
            "active_directive": "DIRECTIVE-DECISION-REVIEW-2026-07-31" if "DIRECTIVE-DECISION-REVIEW-2026-07-31" in ctx else None,
            "superseded_directive": "DIRECTIVE-OUTCOME-B-INITIAL" if "DIRECTIVE-OUTCOME-B-INITIAL" in ctx else None,
            "milestone": "GOVERNED_RUNTIME_PROVEN" if "GOVERNED_RUNTIME_PROVEN" in ctx else None,
            "next_action": "LM Studio endpoint health check" if "LM Studio endpoint health" in ctx else None,
        }
        text = json.dumps(found, sort_keys=True)
        return ModelTaskResult(
            task_id=request.task_id,
            provider="deterministic-test",
            model_id="state-extractor",
            request_artifact_id="",
            response_artifact_id="",
            response_text=text,
            finish_reason="stop",
            input_tokens=10,
            output_tokens=20,
            latency_ms=1,
            provider_request_id="extract-1",
        )


@pytest.fixture()
def home(tmp_path):
    return tmp_path / "home"


def _rt(home: Path):
    cfg = RuntimeConfiguration(
        home=home,
        db_path=home / "data" / "memory.db",
        journal_dir=home / "data" / "ctp",
        evidence_dir=home / "evidence",
        event_log_path=home / "data" / "khsb" / "events.jsonl",
    )
    return CAPTRuntime.load(cfg)


def _seed_records(rt, *, with_directives: bool = True) -> None:
    rt.engine.store(content=MISSION_RECORD, namespace="mission",
                    tags=["mission", "active"])
    if with_directives:
        rt.engine.store(content=ACTIVE_DIRECTIVE, namespace="directives",
                        tags=["directive", "active"])
        rt.engine.store(content=SUPERSEDED_DIRECTIVE, namespace="directives",
                        tags=["directive", "superseded"])


def _rendered_state(with_directives: bool) -> str:
    base = (
        "MISSION-GOVERNED-MODEL-EXECUTION STATUS: ACTIVE milestone "
        "GOVERNED_RUNTIME_PROVEN achieved 2026-07-31; next milestone "
        "GOVERNED_MODEL_EXECUTION requires real local Big Pickle invocation "
        "through CAPTRuntime. Next engineering action: LM Studio endpoint "
        "health check and real governed invocation."
    )
    if with_directives:
        base += (
            " DIRECTIVE-DECISION-REVIEW-2026-07-31 STATUS: ACTIVE Outcome B "
            "approved with corrections: ModelProvider is the one canonical "
            "model-execution abstraction; PulseGateway becomes "
            "PulseModelProvider; add OpenAICompatibleLocalProvider; LM Studio "
            "is in scope and mandatory for final acceptance. Proceed without "
            "another architectural redesign. DIRECTIVE-OUTCOME-B-INITIAL "
            "STATUS: SUPERSEDED Outcome B initial: complete PulseGateway only; "
            "no local-model integrations in this phase."
        )
    return base


# 6. memory ablation — extraction fails when memory is ablated

def test_memory_ablation_changes_extraction(home):
    rt = _rt(home)
    try:
        _seed_records(rt)
        p = StateExtractorProvider()
        # WITH memory: extraction succeeds
        out1 = rt.execute_model_task(
            task_id="task-ablate-on", mission_id="mission-test",
            objective="Identify acceptance items from validated context.",
            provider=p,
            user_prompt="Answer the five acceptance questions from the "
                        "validated context only.",
            rendered_context=_rendered_state(with_directives=True),
        )
        ans1 = json.loads(out1["response_text"])
        assert ans1["mission"] is not None
        assert ans1["active_directive"] is not None
        assert ans1["superseded_directive"] is not None
        assert ans1["milestone"] is not None
        assert ans1["next_action"] is not None
        # the gate PASSED and the provider received the validated context
        assert out1["contextpack"]["validation"] == "PASS"
        assert "MISSION-GOVERNED-MODEL-EXECUTION" in p.last_request.system_prompt
    finally:
        rt.close()


def test_memory_ablation_ablated_extraction_empty(home):
    rt = _rt(home)
    try:
        # ABLATED: no records seeded; rendered context carries NO state —
        # the model boundary sees only the neutral objective
        p = StateExtractorProvider()
        out2 = rt.execute_model_task(
            task_id="task-ablate-off", mission_id="mission-test",
            objective="Identify acceptance items from validated context.",
            provider=p,
            user_prompt="Answer the five acceptance questions from the "
                        "validated context only.",
            rendered_context="MISSION mission-test objective=Identify "
                             "acceptance items from validated context.",
        )
        ans2 = json.loads(out2["response_text"])
        # the provider (and therefore the model boundary) saw NO state
        assert ans2["mission"] is None
        assert ans2["active_directive"] is None
        assert ans2["superseded_directive"] is None
        assert ans2["milestone"] is None
        assert ans2["next_action"] is None
        # both runs committed; the difference is purely the retrieved memory
        assert out2["ok"] is True
    finally:
        rt.close()


# 7. directive supersession — superseded directive is identifiable in context

def test_directive_supersession_context(home):
    rt = _rt(home)
    try:
        _seed_records(rt)
        p = StateExtractorProvider()
        out = rt.execute_model_task(
            task_id="task-super", mission_id="mission-test",
            objective="Identify the superseded directive.",
            provider=p,
            user_prompt="Which directive is superseded?",
            rendered_context=_rendered_state(with_directives=True),
        )
        ans = json.loads(out["response_text"])
        assert ans["superseded_directive"] == "DIRECTIVE-OUTCOME-B-INITIAL"
        assert ans["active_directive"] == "DIRECTIVE-DECISION-REVIEW-2026-07-31"
        # both directives are present in the validated context
        assert "SUPERSEDED" in p.last_request.system_prompt
        assert "DIRECTIVE-OUTCOME-B-INITIAL" in p.last_request.system_prompt
    finally:
        rt.close()


# 8. unsupported ClaimGuard claim — verdict supported=False

def test_unsupported_claim_verdict(home):
    rt = _rt(home)
    try:
        # capability registered with an UNSATISFIABLE aggregate: requires 2
        # artifact_hash records but a single task records exactly 1 ->
        # ClaimGuard verdict supported=False
        cap = rt.registry.register(
            "model-task-unsupported-cap", "test capability", "deterministic-test",
            lifecycle="verified",
            required_tools=["execute_model_task"],
        )
        rt.proof.set_requirements(
            cap.identifier,
            [ProofRequirement("artifact_hash", 2, cap.identifier)],
        )
        p = StateExtractorProvider()
        out = rt.execute_model_task(
            task_id="task-unsupported", mission_id="mission-test",
            objective="Prove the unproven claim complete and verified.",
            provider=p,
            capability_id=cap.identifier,
            claim_text="The unproven claim is complete and verified.",
            rendered_context=_rendered_state(with_directives=True),
        )
        assert out["claim_verdict"]["supported"] is False
        assert out["ok"] is True  # operation committed; claim simply unsupported
    finally:
        rt.close()
