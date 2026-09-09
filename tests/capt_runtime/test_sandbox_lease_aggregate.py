"""Persistent resource lifetime facts never confer capability authority."""
import importlib
from copy import deepcopy

import pytest

from capt_runtime.errors import ContractViolation, IllegalTransition

STATES = ("reserved", "created", "running", "closing", "closed", "indeterminate")
TRANSITIONS = {
    "reserved": {"created", "closed", "indeterminate"},
    "created": {"running", "closing", "indeterminate"},
    "running": {"closing", "indeterminate"},
    "closing": {"closed", "indeterminate"},
    "indeterminate": {"running", "closing", "closed"},
    "closed": set(),
}
DIGEST_FIELDS = (
    "profileDigest", "imageId", "securityProfileDigest", "networkPolicyDigest",
    "filesystemScopeDigest", "persistentEntrypointDigest", "daemonIdentityDigest",
)
OBJECT_FIELDS = ("containerId", "guardianContainerId", "networkId")


def sandbox_lease_fixture(state="reserved"):
    record = {
        "schemaVersion": "1.0.0", "sandboxLeaseId": "sandbox-1",
        "profileId": "profile-1", "operatorId": "operator-1", "sessionId": "session-1",
        "executionContextId": "context-1", "creationToolExecutionId": "create-1",
        "dockerEndpoint": "unix:///var/run/docker.sock", "ttlSeconds": 1800,
        "createdAt": "2026-09-09T12:00:00Z", "expiresAt": "2026-09-09T12:30:00Z",
        "state": state,
        **{field: "sha256:" + "a" * 64 for field in DIGEST_FIELDS},
    }
    if state != "reserved":
        record.update(identity_patch())
    return record


def identity_patch():
    return {
        **{field: "b" * 64 for field in OBJECT_FIELDS},
        "networkName": "capt-sandbox-1", "guardianImageId": "sha256:" + "c" * 64,
        "creationAttestationDigest": "sha256:" + "d" * 64,
        "sideEffectIdentity": "sha256:" + "e" * 64,
    }


@pytest.fixture
def aggregate():
    # Import at test execution so RED also exposes contract failures.
    return importlib.import_module("capt_runtime.aggregates.sandbox_lease").SandboxLeaseAggregate


def test_registered_resource_ownership_and_stream(aggregate):
    from capt_runtime.aggregates import ALL_AGGREGATES, SandboxLeaseAggregate
    assert aggregate is SandboxLeaseAggregate
    assert aggregate in ALL_AGGREGATES
    assert aggregate.stream_id("sandbox-1") == "sandbox_lease-sandbox-1"
    assert aggregate.KIND == "sandbox_lease"
    assert "sandbox_lease.state" in aggregate.OWNED_FIELDS
    assert "leaseId" not in aggregate.OWNED_FIELDS | aggregate.REFERENCE_FIELDS


@pytest.mark.parametrize("state", STATES)
def test_reserve_only_reserved(aggregate, state):
    record = sandbox_lease_fixture(state)
    if state == "reserved":
        result = aggregate.reserve(record)
        assert result == record and result is not record
    else:
        with pytest.raises(IllegalTransition):
            aggregate.reserve(record)


@pytest.mark.parametrize("source", STATES)
@pytest.mark.parametrize("target", STATES)
def test_exact_transition_matrix(aggregate, source, target):
    state = sandbox_lease_fixture(source)
    before = deepcopy(state)
    patch = identity_patch() if target == "created" else {}
    if source == "reserved" and target == "closed":
        patch["closeReason"] = "create_failed_no_effect"
    if source == "indeterminate":
        action = lambda: aggregate.reconcile(state, target, patch)
    else:
        methods = {"created": "record_created", "running": "record_running",
                   "closing": "begin_close", "closed": "record_closed",
                   "indeterminate": "mark_indeterminate"}
        action = (lambda: aggregate.reserve(state)) if target == "reserved" else (
            lambda: getattr(aggregate, methods[target])(state, patch))
    if target in TRANSITIONS[source] or source == target == "reserved":
        result = action()
        assert result["state"] == target
        assert result is not state
    else:
        with pytest.raises(IllegalTransition):
            action()
    assert state == before


@pytest.mark.parametrize("reason", [None, "", "error", "create_failed"])
def test_reserved_close_requires_exact_no_effect_reason(aggregate, reason):
    patch = {} if reason is None else {"closeReason": reason}
    with pytest.raises(IllegalTransition):
        aggregate.record_closed(sandbox_lease_fixture(), patch)


@pytest.mark.parametrize("field", DIGEST_FIELDS + OBJECT_FIELDS + (
    "sandboxLeaseId", "profileId", "operatorId", "sessionId", "executionContextId",
    "creationToolExecutionId", "dockerEndpoint", "networkName", "guardianImageId",
    "creationAttestationDigest", "sideEffectIdentity", "createdAt", "expiresAt", "ttlSeconds",
))
@pytest.mark.parametrize("clear", [False, True])
def test_bound_identity_cannot_change_or_clear(aggregate, field, clear):
    state = sandbox_lease_fixture("running")
    value = None if clear else (3600 if field == "ttlSeconds" else "replacement")
    with pytest.raises(IllegalTransition):
        aggregate.begin_close(state, {field: value})
    state["state"] = "indeterminate"
    with pytest.raises(IllegalTransition):
        aggregate.reconcile(state, "running", {field: value})


@pytest.mark.parametrize("method", ["record_running", "begin_close", "record_closed"])
def test_indeterminate_requires_explicit_reconciliation(aggregate, method):
    with pytest.raises(IllegalTransition):
        getattr(aggregate, method)(sandbox_lease_fixture("indeterminate"), {})


@pytest.mark.parametrize("source", [s for s in STATES if s != "indeterminate"])
def test_reconciliation_requires_indeterminate(aggregate, source):
    with pytest.raises(IllegalTransition):
        aggregate.reconcile(sandbox_lease_fixture(source), "running", {})


def test_patch_cannot_smuggle_state_or_authority(aggregate):
    for patch in ({"state": "closed"}, {"leaseId": "cap-1"}):
        with pytest.raises((IllegalTransition, ContractViolation)):
            aggregate.begin_close(sandbox_lease_fixture("running"), patch)


def test_observed_identity_is_required_before_created(aggregate):
    with pytest.raises((IllegalTransition, ContractViolation)):
        aggregate.record_created(sandbox_lease_fixture(), {})


def test_reconciliation_can_bind_previously_unobserved_identity(aggregate):
    state = aggregate.mark_indeterminate(sandbox_lease_fixture(), {"reconciliationReason": "create_unknown"})
    result = aggregate.reconcile(state, "running", identity_patch())
    assert result["containerId"] == "b" * 64
    assert "containerId" not in state


def test_no_effect_close_cannot_discard_observed_objects(aggregate):
    state = sandbox_lease_fixture()
    state.update(identity_patch())
    with pytest.raises(IllegalTransition):
        aggregate.record_closed(state, {"closeReason": "create_failed_no_effect"})
