"""Actor-kind gates on mission and driver-run lifecycle transitions.

These three acts were previously UNGATED: `transition_mission`,
`create_driver_run` and `transition_driver_run` validated `CommandMetadata`
but called `require_authority()` for no act, so any authenticated actor could
move a mission or a driver run — in a deny-by-default authority model, the
ungated paths are the interesting ones.

Permitted kinds are DERIVED from actual call sites rather than invented, so
these tests pin both halves: the wrong kind is refused, and the kinds already
used in production/recovery and in the existing tests still pass. If the
second half ever breaks, this change has broken a real flow.
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

import pytest

from capt_runtime import commands
from capt_runtime.authority import known_acts, permitted_actors, require_authority
from capt_runtime.errors import AuthorityViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


def meta(command_id: str, actor_kind: str) -> dict:
    return commands.command(
        command_id=command_id,
        idempotency_key=command_id,
        operation_fingerprint="sha256:" + "b" * 64,
        correlation_id="corr",
        actor_id="actor-1",
        actor_kind=actor_kind,
        issued_at="2026-08-16T00:00:00Z",
    )


def mission_spec(mission_id: str) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "missionId": mission_id,
        "rawRequest": "test mission",
        "normalizedRequest": "test mission",
        "objectives": [{"objectiveId": "obj-1", "statement": "test", "priority": 10}],
        "constraints": [],
        "successCriteria": [
            {"criterionId": "sc-1", "statement": "done", "requiresVerification": False}
        ],
        "terminationCriteria": [],
        "unresolvedAmbiguities": [],
        "createdAt": "2026-08-16T10:00:00Z",
    }


def driver_run(run_id: str) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "driverRunId": run_id,
        "driverId": "openharness",
        "missionId": "m-auth-1",
        "taskId": "t-auth-1",
        "workOrderVersion": 1,
        "externalRunId": None,
        "state": "created",
        "reconciliationStatus": "not_required",
        "createdAt": "2026-08-16T10:00:00Z",
    }


# --------------------------------------------------------------------------
# the table itself
# --------------------------------------------------------------------------

def test_the_three_acts_are_now_known_and_carry_derived_kinds():
    acts = known_acts()
    for act in ("transition_mission", "create_driver_run", "transition_driver_run"):
        assert act in acts, act

    assert permitted_actors("transition_mission") == frozenset({"human", "system"})
    assert permitted_actors("create_driver_run") == frozenset({"execution_plane", "system"})
    # HUMAN is present because cancel_driver_run permits it and delegates here.
    assert permitted_actors("transition_driver_run") == frozenset(
        {"execution_plane", "human", "system"})


def test_driver_run_act_permits_at_least_what_its_callers_permit():
    """Delegation invariant: an act reachable from a public act must not be
    stricter than the act that routes into it, or the public path breaks one
    layer down. This was a real regression: the operator cancel
    (actor_kind="human") was refused inside transition_driver_run."""
    # cancel_driver_run routes into transition_driver_run to write 'cancelled'.
    assert permitted_actors("cancel_driver_run") <= permitted_actors("transition_driver_run")


def test_an_unknown_act_still_permits_nobody():
    """Deny-by-default is the property that makes the gates meaningful."""
    assert permitted_actors("no_such_act") == frozenset()
    with pytest.raises(AuthorityViolation) as exc:
        require_authority("no_such_act", "human")
    assert "no actor may perform it" in str(exc.value)


# --------------------------------------------------------------------------
# driver run: wrong kind refused, real kind accepted
# --------------------------------------------------------------------------

def test_create_driver_run_refuses_a_non_execution_actor():
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        with pytest.raises(AuthorityViolation) as exc:
            svc.create_driver_run(driver_run("dr-auth-1"), meta("c-dr-1", "cognitive_plane"))
        assert "create_driver_run" in str(exc.value)
        # nothing was written
        assert store.aggregate_version("driverrun-dr-auth-1") == 0
    finally:
        store.close()


def test_create_and_transition_driver_run_accept_execution_plane():
    """The kinds every production and recovery call site actually uses."""
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        svc.create_driver_run(driver_run("dr-auth-2"), meta("c-dr-2", "execution_plane"))
        assert store.aggregate_version("driverrun-dr-auth-2") == 1

        svc.transition_driver_run("dr-auth-2", "submitted", meta("t-dr-2a", "execution_plane"))
        svc.transition_driver_run("dr-auth-2", "running", meta("t-dr-2b", "execution_plane"))
        assert store.aggregate_version("driverrun-dr-auth-2") == 3

        # a system actor reconciles
        svc.transition_driver_run("dr-auth-2", "lost", meta("t-dr-2c", "system"))
        assert store.require_state("driverrun-dr-auth-2")["state"] == "lost"
    finally:
        store.close()


def test_transition_driver_run_refuses_a_non_execution_actor():
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        svc.create_driver_run(driver_run("dr-auth-3"), meta("c-dr-3", "execution_plane"))
        with pytest.raises(AuthorityViolation) as exc:
            svc.transition_driver_run("dr-auth-3", "submitted", meta("t-dr-3", "cognitive_plane"))
        assert "transition_driver_run" in str(exc.value)
        assert store.require_state("driverrun-dr-auth-3")["state"] == "created"
    finally:
        store.close()


# --------------------------------------------------------------------------
# mission transition: wrong kind refused, real kind accepted
# --------------------------------------------------------------------------

def test_transition_mission_refuses_a_non_human_actor():
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        svc.create_mission(mission_spec("m-auth-1"), meta("c-m-1", "human"))
        with pytest.raises(AuthorityViolation) as exc:
            svc.transition_mission("m-auth-1", "authorized", "nope", meta("t-m-1", "execution_plane"))
        assert "transition_mission" in str(exc.value)
        assert store.require_state("mission-m-auth-1")["state"] == "draft"
    finally:
        store.close()


def test_transition_mission_accepts_human_and_advances_lifecycle():
    """`human` is the kind the only existing caller uses."""
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        svc.create_mission(mission_spec("m-auth-2"), meta("c-m-2", "human"))
        svc.transition_mission("m-auth-2", "authorized", "approved", meta("t-m-2", "human"))
        assert store.require_state("mission-m-auth-2")["state"] == "authorized"
        svc.transition_mission("m-auth-2", "executing", "go", meta("t-m-3", "system"))
        assert store.require_state("mission-m-auth-2")["state"] == "executing"
    finally:
        store.close()


def test_operator_cancel_driver_run_survives_the_delegation():
    """The regression that the derived set missed.

    cancel_driver_run permits HUMAN and delegates to transition_driver_run. The
    M1 operator surface issues commands as actor_kind="human", so restricting
    the inner act to execution_plane broke the operator-facing cancel.
    """
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        svc.create_driver_run(driver_run("dr-auth-4"), meta("c-dr-4", "execution_plane"))
        svc.transition_driver_run("dr-auth-4", "submitted", meta("t-dr-4a", "execution_plane"))
        svc.transition_driver_run("dr-auth-4", "running", meta("t-dr-4b", "execution_plane"))

        svc.cancel_driver_run("dr-auth-4", "operator stop", meta("cancel-dr-4", "human"))
        assert store.require_state("driverrun-dr-auth-4")["state"] == "cancelled"

        # idempotent replay of the same cancel
        result = svc.cancel_driver_run("dr-auth-4", "operator stop", meta("cancel-dr-4", "human"))
        assert result["status"] == "idempotent"
    finally:
        store.close()
