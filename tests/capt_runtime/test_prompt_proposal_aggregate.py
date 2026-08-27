"""Authority-bound durable PromptProposal contract coverage."""

from __future__ import annotations

import copy

import pytest

from capt_runtime.checkpoint import create_checkpoint
from capt_runtime import commands
from capt_runtime.contracts import digest, require
from capt_runtime.errors import IllegalTransition
from capt_runtime.aggregates.prompt_proposal import PromptProposalAggregate
from capt_runtime.replay import full_replay
from capt_runtime.store import AppendRequest, EventStore


def _proposal() -> dict:
    return {
        "proposalId": "proposal-001",
        "originalPrompt": "Build a local-first prompt review flow.",
        "proposedPrompt": "Build a local-first prompt review flow with explicit approval.",
        "mode": "normal",
        "stageChain": ["OMNI", "META"],
        "targetRoot": "/workspace/capt",
        "stageRecords": [],
        "capabilityRequests": [],
        "verificationContract": {"acceptanceCriteria": ["tests pass"]},
    }


def test_prompt_proposal_preserves_distinct_original_and_compiled_prompt_digests() -> None:
    proposal = _proposal()

    state = PromptProposalAggregate.create(proposal)

    assert state["originalPrompt"] == proposal["originalPrompt"]
    assert state["proposedPrompt"] == proposal["proposedPrompt"]
    assert state["originalPromptDigest"] == digest(proposal["originalPrompt"])
    assert state["proposedPromptDigest"] == digest(proposal["proposedPrompt"])
    assert state["originalPromptDigest"] != state["proposedPromptDigest"]


def test_prompt_proposal_revision_never_mutates_original_and_cancellation_is_terminal() -> None:
    state = PromptProposalAggregate.create(_proposal())
    original = copy.deepcopy(state)

    revised = PromptProposalAggregate.revise(
        state,
        {
            "proposedPrompt": "Build a local-first review flow with human approval and replay proof.",
            "stageChain": ["OMNI", "META", "SIGMA"],
            "stageRecords": [],
            "capabilityRequests": [],
            "verificationContract": {"acceptanceCriteria": ["tests pass", "replay passes"]},
        },
    )

    assert revised["originalPrompt"] == original["originalPrompt"]
    assert revised["originalPromptDigest"] == original["originalPromptDigest"]
    assert revised["proposedPromptDigest"] != original["proposedPromptDigest"]

    cancelled = PromptProposalAggregate.cancel(revised, "operator cancelled")
    with pytest.raises(IllegalTransition):
        PromptProposalAggregate.revise(cancelled, {"proposedPrompt": "must not apply"})


def test_prompt_proposal_stream_checkpoint_and_replay_are_authoritative() -> None:
    proposal = _proposal()
    state = PromptProposalAggregate.create(proposal)
    store = EventStore(":memory:")
    stream_id = PromptProposalAggregate.stream_id(proposal["proposalId"])
    metadata = commands.command(
        command_id="cmd-proposal-001",
        idempotency_key="idem-proposal-001",
        operation_fingerprint=commands.fingerprint("create_prompt_proposal", proposal),
        correlation_id="corr-proposal-001",
        actor_id="capt-runtime",
        actor_kind="system",
        issued_at="2026-08-23T12:00:00Z",
    )
    envelope = commands.envelope(
        event_id="event-proposal-001",
        stream_id=stream_id,
        event_type="PromptProposalCreated",
        payload={"eventType": "PromptProposalCreated", "proposal": state},
        metadata=metadata,
        occurred_at="2026-08-23T12:00:00Z",
    )
    store.commit_command(
        [AppendRequest(stream_id, PromptProposalAggregate.KIND, 0, envelope, state)],
        metadata["idempotencyKey"], metadata["operationFingerprint"], metadata["commandId"],
    )

    manifest = create_checkpoint(
        store, "checkpoint-proposal-001", "2026-08-23T12:00:01Z", digest("policy")
    )

    assert manifest["promptProposalVersions"] == [{"streamId": stream_id, "version": 1}]
    assert full_replay(store).aggregates[stream_id] == state


def test_prompt_proposal_stream_id_and_generated_bindings_are_contract_parity() -> None:
    require("StreamId", "prompt_proposal-proposal-001")
    with pytest.raises(Exception):
        require("StreamId", "prompt-proposal-001")

    from capt_contracts.types import PromptProposalSnapshot as GeneratedPromptProposalSnapshot

    required_shape = {
        "proposalId", "originalPrompt", "originalPromptDigest", "proposedPrompt",
        "proposedPromptDigest", "mode", "stageChain", "targetRoot",
    }
    assert required_shape <= set(GeneratedPromptProposalSnapshot.__annotations__)
    typescript = (
        __import__("pathlib").Path("contracts/generated/typescript/src/types.ts")
        .read_text(encoding="utf-8")
    )
    start = typescript.index("export interface PromptProposalSnapshot {")
    end = typescript.index("\n}", start)
    assert required_shape <= {
        line.strip().split(":", 1)[0].removeprefix("readonly ")
        for line in typescript[start:end].splitlines()[1:]
    }
