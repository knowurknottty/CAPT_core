"""Session lifecycle integration tests."""

import sys
sys.path.insert(0, '.')

import pytest
from capt_runtime.session import SessionLifecycle, SessionLifecycleError
from capt_solo.khsb.bus import KHSB
from capt_solo.ctp.journal import CTPRuntime


def test_register_session_returns_session_id_and_ctp_tx_id():
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    result = lifecycle.register_session("session-001", mission_id="mission-alpha")

    assert result["sessionId"] == "session-001"
    assert result["missionId"] == "mission-alpha"
    assert result["state"] == "active"
    assert "ctpTxId" in result


def test_register_session_publishes_lifecycle_event():
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    lifecycle.register_session("session-002", mission_id="mission-beta")

    events = bus.pending_messages("session.lifecycle")
    assert len(events) >= 1
    assert events[-1]["payload"]["sessionId"] == "session-002"
    assert events[-1]["payload"]["action"] == "register"


def test_checkpoint_session_requires_registered_session():
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    with pytest.raises(SessionLifecycleError) as exc_info:
        lifecycle.checkpoint_session("unknown-session", "mission-x", "do-something")

    assert exc_info.value.code == "SESSION_NOT_REGISTERED"
    assert "not registered" in str(exc_info.value)


def test_checkpoint_session_returns_ctp_tx_id():
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    lifecycle.register_session("session-003", mission_id="mission-gamma")

    result = lifecycle.checkpoint_session(
        "session-003",
        mission_id="mission-gamma",
        exact_next_action="continue-task-42",
        offload_id="offload-abc",
    )

    assert result["sessionId"] == "session-003"
    assert result["exactNextAction"] == "continue-task-42"
    assert result["offloadId"] == "offload-abc"
    assert "ctpTxId" in result


def test_resume_session_returns_exact_next_action():
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    lifecycle.register_session("session-004", mission_id="mission-delta")
    lifecycle.checkpoint_session(
        "session-004",
        mission_id="mission-delta",
        exact_next_action="resume-task-99",
        offload_id="offload-def",
    )

    result = lifecycle.resume_session("session-004")

    assert result["sessionId"] == "session-004"
    assert result["exactNextAction"] == "resume-task-99"
    assert result["offloadId"] == "offload-def"


def test_close_session_sets_state_closed():
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    lifecycle.register_session("session-005", mission_id="mission-epsilon")

    result = lifecycle.close_session("session-005", reason="completed")

    assert result["sessionId"] == "session-005"
    assert result["state"] == "closed"
    assert result["reason"] == "completed"


def test_get_session_state_returns_current_state():
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    lifecycle.register_session("session-006", mission_id="mission-zeta")

    state = lifecycle.get_session_state("session-006")

    assert state["sessionId"] == "session-006"
    assert state["state"] == "active"


def test_list_sessions_returns_all_registered():
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    lifecycle.register_session("session-007", mission_id="mission-eta")
    lifecycle.register_session("session-008", mission_id="mission-theta")

    sessions = lifecycle.list_sessions()

    assert len(sessions) == 2
    assert "session-007" in sessions
    assert "session-008" in sessions


def test_close_session_requires_registered_session():
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    with pytest.raises(SessionLifecycleError) as exc_info:
        lifecycle.close_session("unknown-session", reason="test")

    assert exc_info.value.code == "SESSION_NOT_REGISTERED"


def test_resume_session_requires_registered_session():
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    with pytest.raises(SessionLifecycleError) as exc_info:
        lifecycle.resume_session("unknown-session")

    assert exc_info.value.code == "SESSION_NOT_REGISTERED"


def test_khsb_payload_contains_only_reference_fields():
    """KHSB payloads carry references, not mission truth."""
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    lifecycle.register_session("session-khsb-ref", mission_id="mission-khsb-ref")

    events = bus.pending_messages("session.lifecycle")
    assert len(events) >= 1

    payload = events[-1]["payload"]
    # Reference-only fields: session_id, mission_id, action, ctp_tx_id
    assert "sessionId" in payload
    assert "missionId" in payload
    assert "action" in payload
    assert "ctpTxId" in payload
    # Must NOT contain mission state, task lists, or memory contents
    assert "tasks" not in payload
    assert "memory" not in payload
    assert "missionState" not in payload


def test_ctp_correlation_id_bound_to_session():
    """CTP transactions are correlated to session_id."""
    bus = KHSB()
    ctp = CTPRuntime()
    lifecycle = SessionLifecycle(bus, ctp)

    result = lifecycle.register_session("session-ctp-corr", mission_id="mission-ctp-corr")

    assert "ctpTxId" in result
    assert result["ctpTxId"] is not None


def test_restart_restores_checkpoint_and_exact_next_action(tmp_path):
    journal = tmp_path / "ctp" / "journal.jsonl"
    first_ctp = CTPRuntime(journal_path=journal)
    first = SessionLifecycle(KHSB(), first_ctp)
    first.register_session("session-restart", mission_id="mission-restart")
    checkpoint = first.checkpoint_session(
        "session-restart",
        mission_id="mission-restart",
        exact_next_action="resume-governed-work-packet",
        offload_id="offload-restart",
    )
    first_ctp.close()

    second_ctp = CTPRuntime(journal_path=journal)
    second = SessionLifecycle(KHSB(), second_ctp)
    restored = second.get_session_state("session-restart")
    assert restored is not None
    assert restored["state"] == "checkpointed"
    assert restored["exactNextAction"] == "resume-governed-work-packet"
    assert restored["offloadId"] == "offload-restart"

    resumed = second.resume_session("session-restart", checkpoint["ctpTxId"])
    assert resumed["exactNextAction"] == "resume-governed-work-packet"
    second_ctp.close()
