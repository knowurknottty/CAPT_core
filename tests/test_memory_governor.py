"""Focused unit tests for MemoryGovernor threshold enforcement and offload."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from capt_runtime.memory import MemoryGovernor, MemoryStore, MemoryTriggerEngine


def test_governor_initialization():
    """Governor initializes with correct thresholds."""
    store = MemoryStore()
    engine = MemoryTriggerEngine(store=store)
    governor = MemoryGovernor(
        store=store,
        engine=engine,
        mission_id="test-mission",
        session_id="test-session",
        effective_context_tokens=64_768,
        ladder_step=32_768,
        soft_threshold=32_768,
        hard_threshold=int(64_768 * 0.75),
        emergency_threshold=int(64_768 * 0.85),
    )

    status = governor.get_threshold_status()
    assert status["soft_threshold"] == 32_768
    assert status["hard_threshold"] == int(64_768 * 0.75)
    assert status["emergency_threshold"] == int(64_768 * 0.85)
    assert status["estimated_tokens"] == 0


def test_estimator_tracks_conversation_history():
    """Estimator tracks tokens from conversation history."""
    store = MemoryStore()
    engine = MemoryTriggerEngine(store=store)
    governor = MemoryGovernor(
        store=store,
        engine=engine,
        mission_id="test-mission",
        session_id="test-session",
        effective_context_tokens=64_768,
        ladder_step=32_768,
        soft_threshold=32_768,
        hard_threshold=int(64_768 * 0.75),
        emergency_threshold=int(64_768 * 0.85),
    )

    # Simulate conversation history
    conversation_history = []
    for i in range(50):
        conversation_history.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": "x" * 1000,  # ~250 tokens per message
        })

    status = governor.update_estimator_on_pre_call(conversation_history)
    assert status["estimated_tokens"] > 0
    assert status["estimated_tokens"] < governor.soft_threshold


def test_soft_threshold_crossing_triggers_offload():
    """Crossing soft threshold triggers offload action."""
    store = MemoryStore()
    engine = MemoryTriggerEngine(store=store)
    governor = MemoryGovernor(
        store=store,
        engine=engine,
        mission_id="test-mission",
        session_id="test-session",
        effective_context_tokens=64_768,
        ladder_step=32_768,
        soft_threshold=32_768,
        hard_threshold=int(64_768 * 0.75),
        emergency_threshold=int(64_768 * 0.85),
    )

    # Simulate crossing soft threshold
    conversation_history = []
    for i in range(150):
        conversation_history.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": "x" * 1000,
        })

    status = governor.update_estimator_on_pre_call(conversation_history)
    assert status["action_required"] == "SOFT_OFFLOAD"


def test_offload_produces_immutable_record():
    """Offload produces immutable record with digest."""
    store = MemoryStore()
    engine = MemoryTriggerEngine(store=store)
    governor = MemoryGovernor(
        store=store,
        engine=engine,
        mission_id="test-mission",
        session_id="test-session",
        effective_context_tokens=64_768,
        ladder_step=32_768,
        soft_threshold=32_768,
        hard_threshold=int(64_768 * 0.75),
        emergency_threshold=int(64_768 * 0.85),
    )

    # Update estimator before offload
    governor.update_estimator_on_pre_call([
        {"role": "user", "content": "x" * 1000},
        {"role": "assistant", "content": "x" * 1000},
    ])

    offload = governor.offload_governed_state(
        trigger_cause="SOFT_OFFLOAD",
        current_packet_id="packet-1",
        exact_next_action="continue_compiler_history_work",
        completed_packet_ids=["packet-0"],
        unresolved_state={"pending_verification": True},
        authority_state={"owner": "operator"},
    )

    assert "offload_id" in offload
    assert "digest" in offload
    assert offload["trigger_cause"] == "SOFT_OFFLOAD"
    assert offload["estimated_tokens_at_offload"] > 0


def test_context_pack_compiles_from_persisted_records():
    """ContextPack compiles from persisted records."""
    store = MemoryStore()
    engine = MemoryTriggerEngine(store=store)
    governor = MemoryGovernor(
        store=store,
        engine=engine,
        mission_id="test-mission",
        session_id="test-session",
        effective_context_tokens=64_768,
        ladder_step=32_768,
        soft_threshold=32_768,
        hard_threshold=int(64_768 * 0.75),
        emergency_threshold=int(64_768 * 0.85),
    )

    # Trigger offload first
    offload = governor.offload_governed_state(
        trigger_cause="SOFT_OFFLOAD",
        current_packet_id="packet-1",
        exact_next_action="continue_compiler_history_work",
        completed_packet_ids=["packet-0"],
        unresolved_state={"pending_verification": True},
        authority_state={"owner": "operator"},
    )

    context_pack = governor.compile_context_pack()

    assert "contextPackId" in context_pack
    assert "contextPackDigest" in context_pack
    assert len(context_pack["selectedRecords"]) > 0


def test_resume_from_checkpoints():
    """Resume capability returns persisted state."""
    store = MemoryStore()
    engine = MemoryTriggerEngine(store=store)
    governor = MemoryGovernor(
        store=store,
        engine=engine,
        mission_id="test-mission",
        session_id="test-session",
        effective_context_tokens=64_768,
        ladder_step=32_768,
        soft_threshold=32_768,
        hard_threshold=int(64_768 * 0.75),
        emergency_threshold=int(64_768 * 0.85),
    )

    # Trigger offload
    governor.offload_governed_state(
        trigger_cause="SOFT_OFFLOAD",
        current_packet_id="packet-1",
        exact_next_action="continue_compiler_history_work",
        completed_packet_ids=["packet-0"],
        unresolved_state={"pending_verification": True},
        authority_state={"owner": "operator"},
    )

    resume = governor.resume_from_checkpoints("test-mission", "test-session")

    assert resume is not None
    assert resume["mission_id"] == "test-mission"
    assert resume["session_id"] == "test-session"
    assert resume["exact_next_action"] == "continue_compiler_history_work"
    assert resume["completed_packet_ids"] == ["packet-0"]
    assert resume["unresolved_state"]["pending_verification"] is True


def test_multiple_ladder_crossings():
    """Multiple ladder crossings repeat successfully."""
    store = MemoryStore()
    engine = MemoryTriggerEngine(store=store)
    governor = MemoryGovernor(
        store=store,
        engine=engine,
        mission_id="test-mission",
        session_id="test-session",
        effective_context_tokens=64_768,
        ladder_step=32_768,
        soft_threshold=32_768,
        hard_threshold=int(64_768 * 0.75),
        emergency_threshold=int(64_768 * 0.85),
    )

    # First crossing
    conversation_history = []
    for i in range(150):
        conversation_history.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": "x" * 1000,
        })

    status = governor.update_estimator_on_pre_call(conversation_history)
    assert status["action_required"] == "SOFT_OFFLOAD"

    offload1 = governor.offload_governed_state(
        trigger_cause="SOFT_OFFLOAD",
        current_packet_id="packet-1",
        exact_next_action="continue_compiler_history_work",
        completed_packet_ids=["packet-0"],
        unresolved_state={"pending_verification": True},
        authority_state={"owner": "operator"},
    )

    # Reset thresholds for new ladder after offload
    governor.reset_thresholds_for_new_ladder()

    # Second crossing (simulate more conversation)
    conversation_history.extend([
        {"role": "user", "content": "x" * 1000},
        {"role": "assistant", "content": "x" * 1000},
    ] * 50)

    status = governor.update_estimator_on_pre_call(conversation_history)
    assert status["action_required"] in ("SOFT_OFFLOAD", "HARD_OFFLOAD", "EMERGENCY_OFFLOAD")

    offload2 = governor.offload_governed_state(
        trigger_cause=status["action_required"],
        current_packet_id="packet-2",
        exact_next_action="continue_compiler_history_work",
        completed_packet_ids=["packet-0", "packet-1"],
        unresolved_state={"pending_verification": True},
        authority_state={"owner": "operator"},
    )

    assert offload1["offload_id"] != offload2["offload_id"]


def test_store_records_exist_after_offload():
    """Store contains records after offload."""
    store = MemoryStore()
    engine = MemoryTriggerEngine(store=store)
    governor = MemoryGovernor(
        store=store,
        engine=engine,
        mission_id="test-mission",
        session_id="test-session",
        effective_context_tokens=64_768,
        ladder_step=32_768,
        soft_threshold=32_768,
        hard_threshold=int(64_768 * 0.75),
        emergency_threshold=int(64_768 * 0.85),
    )

    governor.offload_governed_state(
        trigger_cause="SOFT_OFFLOAD",
        current_packet_id="packet-1",
        exact_next_action="continue_compiler_history_work",
        completed_packet_ids=["packet-0"],
        unresolved_state={"pending_verification": True},
        authority_state={"owner": "operator"},
    )

    records = store.query(classes=["episodic"], bypass_governance=True)
    assert len(records) > 0


def test_checkpoint_session_end():
    """Session-end checkpoint produces checkpoint record."""
    store = MemoryStore()
    engine = MemoryTriggerEngine(store=store)
    governor = MemoryGovernor(
        store=store,
        engine=engine,
        mission_id="test-mission",
        session_id="test-session",
        effective_context_tokens=64_768,
        ladder_step=32_768,
        soft_threshold=32_768,
        hard_threshold=int(64_768 * 0.75),
        emergency_threshold=int(64_768 * 0.85),
    )

    # Update estimator before checkpoint
    governor.update_estimator_on_pre_call([
        {"role": "user", "content": "x" * 1000},
        {"role": "assistant", "content": "x" * 1000},
    ])

    checkpoint = governor.checkpoint_session_end(reason="session_boundary")

    assert "offload_id" in checkpoint
    assert checkpoint["trigger_cause"] == "session_boundary"
