"""Temporal model (Gate 13) and control/data-plane (Gate 12) tests."""

import pytest

from capt_runtime import temporal as T
from capt_runtime import control_data_plane as C
from capt_runtime.errors import AuthorityViolation


def test_temporal_context_valid():
    ctx = T.build_temporal_context(monotonic=1.0, logical=1, causal="c0", mission_relative=0.0)
    assert ctx["wallClock"]
    assert ctx["logical"] == 1


def test_stale_approval_after_restart_expired():
    # An approval with an expiration in the past is expired even after restart.
    assert T.is_expired("2020-01-01T00:00:00Z", now="2026-08-03T00:00:00Z") is True


def test_valid_lease_not_expired():
    assert T.is_expired("2099-01-01T00:00:00Z", now="2026-08-03T00:00:00Z") is False


def test_causal_replay_ordering():
    assert T.causal_order_ok("c0", "c0.1") is True
    assert T.causal_order_ok("c0", "cX") is False


def test_observation_before_verification():
    assert T.observation_before_verification("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z") is True
    assert T.observation_before_verification("2026-01-02T00:00:00Z", "2026-01-01T00:00:00Z") is False


def test_future_information_leak_rejected():
    assert T.no_future_leak_into_history("2026-01-01T00:00:00Z", "2026-06-01T00:00:00Z") is False
    assert T.no_future_leak_into_history("2026-01-01T00:00:00Z", "2025-12-01T00:00:00Z") is True


def test_control_plane_classification():
    assert C.classify("CreateMission") == "control"
    assert C.classify("UpdatePolicy") == "control"
    assert C.classify("RevokeIdentity") == "control"


def test_data_plane_classification():
    assert C.classify("RepositoryRead") == "data"
    assert C.classify("RetrieveMemory") == "data"
    assert C.classify("Inference") == "data"


def test_unknown_op_fails_closed_to_control():
    # Unknown operations must not silently gain data-plane privileges.
    assert C.classify("MysteryOp") == "control"


def test_tag_command():
    tagged = C.tag_command({"operation": "CancelTask"})
    assert tagged["plane"] == "control"


def test_control_not_on_permissive_channel():
    with pytest.raises(AuthorityViolation):
        C.assert_control_not_on_permissive_channel("CreateMission", "event-stream")
    # data-plane op on permissive channel is allowed
    C.assert_control_not_on_permissive_channel("RepositoryRead", "event-stream")
