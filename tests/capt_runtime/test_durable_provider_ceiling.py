import pytest
from capt_runtime.driver_run import DriverRunAggregate
from capt_runtime.errors import IllegalTransition

T = "2026-10-19T02:00:00Z"

def test_approval_bound_limit_and_inflight_guard():
    state = DriverRunAggregate.create(dict(driverRunId="dr",driverId="provider",missionId="m",taskId="t",providerHttpRequestLimit=1,providerRequestApprovalId="approval"))
    state = DriverRunAggregate.record_dispatch_boundary(state,"request_started",T)
    with pytest.raises(IllegalTransition,match="PROVIDER_REQUEST_ALREADY_STARTED"):
        DriverRunAggregate.record_dispatch_boundary(state,"request_started",T)
    state = DriverRunAggregate.record_dispatch_boundary(state,"response_started",T)
    state = DriverRunAggregate.record_dispatch_boundary(state,"response_completed",T)
    with pytest.raises(IllegalTransition,match="PROVIDER_HTTP_REQUEST_ATTEMPT_CAP_EXCEEDED"):
        DriverRunAggregate.record_dispatch_boundary(state,"request_started",T)

from capt_runtime import commands
from capt_runtime.composition import create_runtime

def _meta(rid, seq):
    return commands.command(
        command_id=f"cmd-{rid}-{seq}", idempotency_key=f"idem-{rid}-{seq}",
        operation_fingerprint=commands.fingerprint("boundary",{"run":rid,"seq":seq}),
        correlation_id="corr-budget", actor_id="exec-1",
        actor_kind="execution_plane", issued_at=T, replay_policy="never")

def _run(rid, limit):
    return dict(schemaVersion="1.0.0",driverRunId=rid,driverId="provider",
        missionId="m-budget",taskId="t-budget",workOrderVersion=1,
        externalRunId=None,state="created",reconciliationStatus="not_required",
        createdAt=T,providerHttpRequestLimit=limit,
        providerRequestApprovalId="approval-budget")

def test_restarted_eventstore_refuses_expended_budget(tmp_path):
    rid="dr-recovery-budget"
    db=str(tmp_path/"ledger.db")
    original=create_runtime(db)
    try:
        original.service.create_driver_run(_run(rid,1),_meta(rid,0))
        for seq, boundary in enumerate(("request_started","response_started","response_completed"),1):
            original.service.record_driver_dispatch_boundary(rid,boundary,_meta(rid,seq))
    finally:
        original.close()
    recovered=create_runtime(db)
    try:
        state=recovered.store.require_state("driverrun-"+rid)
        assert state["providerHttpRequestLimit"] == 1
        assert state["providerHttpRequestAttempts"] == 1
        with pytest.raises(IllegalTransition,match="PROVIDER_HTTP_REQUEST_ATTEMPT_CAP_EXCEEDED"):
            recovered.service.record_driver_dispatch_boundary(rid,"request_started",_meta(rid,4))
        assert recovered.store.require_state("driverrun-"+rid)["providerHttpRequestAttempts"] == 1
    finally:
        recovered.close()

def test_pending_request_recovery_is_not_an_extra_slot(tmp_path):
    rid="dr-recovery-pending"
    db=str(tmp_path/"pending.db")
    a=create_runtime(db)
    try:
        a.service.create_driver_run(_run(rid,2),_meta(rid,0))
        a.service.record_driver_dispatch_boundary(rid,"request_started",_meta(rid,1))
    finally:
        a.close()
    b=create_runtime(db)
    try:
        with pytest.raises(IllegalTransition,match="PROVIDER_REQUEST_ALREADY_STARTED"):
            b.service.record_driver_dispatch_boundary(rid,"request_started",_meta(rid,2))
        assert b.store.require_state("driverrun-"+rid)["providerHttpRequestAttempts"] == 1
    finally:
        b.close()


@pytest.mark.parametrize("receipt", [
    {"status": "idempotent"}, {"status": "duplicate"}, {}, "unexpected", None,
])
def test_replayed_request_boundary_never_opens_http(tmp_path, monkeypatch, receipt):
    """Even a command-idempotent EventStore replay is not a second HTTP permit."""
    import urllib.request
    from capt_runtime.drivers.provider import ProviderDriver, DispatchBoundaryError

    http_calls = []
    def never_send(*args, **kwargs):
        http_calls.append((args, kwargs))
        raise AssertionError("provider HTTP was dispatched after boundary replay")

    monkeypatch.setattr(urllib.request, "urlopen", never_send)
    driver = ProviderDriver(
        staging_root=str(tmp_path), provider_id="openrouter", model="offline-fixture",
        base_url="https://fixture.invalid", api_key="fixture",
        boundary_recorder=lambda _rid, _boundary: receipt,
    )
    with pytest.raises(DispatchBoundaryError, match="PROVIDER_REQUEST_BOUNDARY_REPLAY_FORBIDDEN"):
        driver._post_json(
            "dr-recovered", "https://fixture.invalid/chat/completions",
            {"model": "offline-fixture", "messages": [{"role": "user", "content": "fixture"}]},
            {"Authorization": "Bearer fixture"},
        )
    assert http_calls == []
