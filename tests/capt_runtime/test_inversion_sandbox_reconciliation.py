from __future__ import annotations

from pathlib import Path

from capt_runtime import commands
from capt_runtime.aggregates import SandboxLeaseAggregate
from capt_runtime.contracts import digest
from capt_runtime.errors import AuthorityViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from capt_runtime.tools.backends.inversion_sandbox import (
    InversionSandboxProcessBackend,
    InversionSandboxProfile,
    InversionSandboxProfileRegistry,
    SandboxRuntimeIdentity,
)

NOW = "2026-09-09T12:00:00Z"
IMAGE = "sha256:" + "a" * 64
CONTAINER = "b" * 64


def _profile() -> InversionSandboxProfile:
    return InversionSandboxProfile(
        profile_id="reconcile-profile",
        context_name="desktop-linux",
        image_ref="python:3.13-slim",
        persistent_entrypoint_argv=("/usr/local/bin/python3", "-c", "import time; time.sleep(3600)"),
    )


def _identity(profile: InversionSandboxProfile) -> SandboxRuntimeIdentity:
    return SandboxRuntimeIdentity(
        sandbox_lease_id="sandbox-reconcile-1",
        profile_id=profile.profile_id,
        profile_digest=profile.profile_digest(),
        context_endpoint="unix:///tmp/docker.sock",
        daemon_identity_digest=digest({"daemon": "reconcile"}),
        workload_container_id=CONTAINER,
        workload_image_id=IMAGE,
        security_profile_digest="sha256:" + profile.security_profile_digest(),
        network_policy_digest="sha256:" + profile.network_policy.digest(),
        filesystem_scope_digest="sha256:" + profile.filesystem_scope_digest(),
        persistent_entrypoint_digest=profile.persistent_entrypoint_digest(),
        creation_attestation_digest=digest({"attestation": "reconcile"}),
    )


def _meta(name: str) -> dict:
    return commands.command(
        command_id=name,
        idempotency_key=name,
        operation_fingerprint=commands.fingerprint(name, {"name": name}),
        correlation_id="corr-reconcile",
        actor_id="sandbox-reconciler",
        actor_kind="system",
        issued_at=NOW,
    )


def _seed(store: EventStore, service: RuntimeService, profile: InversionSandboxProfile, state: str) -> dict:
    identity = _identity(profile)
    lease = {
        "schemaVersion": "1.0.0",
        "sandboxLeaseId": identity.sandbox_lease_id,
        "profileId": profile.profile_id,
        "operatorId": "operator-1",
        "sessionId": "session-1",
        "executionContextId": "ctx-reconcile",
        "creationToolExecutionId": "create-reconcile-1",
        "profileDigest": profile.profile_digest(),
        "imageId": IMAGE,
        "securityProfileDigest": identity.security_profile_digest,
        "networkPolicyDigest": identity.network_policy_digest,
        "filesystemScopeDigest": identity.filesystem_scope_digest,
        "persistentEntrypointDigest": identity.persistent_entrypoint_digest,
        "daemonIdentityDigest": identity.daemon_identity_digest,
        "dockerEndpoint": identity.context_endpoint,
        "createdAt": NOW,
        "expiresAt": "2026-09-09T12:30:00Z",
        "ttlSeconds": 1800,
        "state": "reserved",
    }
    service.reserve_sandbox_lease(lease, _meta("reserve-reconcile"))
    if state == "reserved":
        return store.require_state(SandboxLeaseAggregate.stream_id(identity.sandbox_lease_id))
    service.recover_reserved_sandbox_created(
        identity.sandbox_lease_id,
        {
            "containerId": identity.workload_container_id,
            "creationAttestationDigest": identity.creation_attestation_digest,
            "sideEffectIdentity": identity.digest(),
        },
        _meta("recover-created"),
    )
    if state == "created":
        return store.require_state(SandboxLeaseAggregate.stream_id(identity.sandbox_lease_id))
    service.record_sandbox_running(identity.sandbox_lease_id, {}, _meta("recover-running"))
    if state == "running":
        return store.require_state(SandboxLeaseAggregate.stream_id(identity.sandbox_lease_id))
    if state == "closing":
        service.begin_sandbox_close(
            identity.sandbox_lease_id, {"closeReason": "operator_requested"}, _meta("begin-close")
        )
    elif state == "indeterminate":
        service.mark_sandbox_indeterminate(
            identity.sandbox_lease_id,
            {"reconciliationReason": "runtime_state_unknown"},
            _meta("mark-indeterminate"),
        )
    else:
        raise AssertionError(state)
    return store.require_state(SandboxLeaseAggregate.stream_id(identity.sandbox_lease_id))


def _setup(tmp_path: Path, state: str = "running"):
    from capt_runtime.sandbox_reconciliation import SandboxLeaseReconciler

    store = EventStore(str(tmp_path / "runtime.db"))
    service = RuntimeService(store)
    profile = _profile()
    backend = InversionSandboxProcessBackend(InversionSandboxProfileRegistry((profile,)))
    lease = _seed(store, service, profile, state)
    reconciler = SandboxLeaseReconciler(service, backend, now=lambda: NOW)
    return store, service, backend, reconciler, profile, lease


def test_running_exact_identity_is_verified_without_lease_churn(tmp_path: Path) -> None:
    store, _service, backend, reconciler, _profile_obj, lease = _setup(tmp_path, "running")
    stream = SandboxLeaseAggregate.stream_id(lease["sandboxLeaseId"])
    version = store.aggregate_version(stream)
    backend.inspect_persistent = lambda _identity: {
        "workloadRunning": True, "workloadState": "running", "observationDigest": digest({"ok": True})
    }
    try:
        result = reconciler.reconcile_one(lease["sandboxLeaseId"])
        assert result["status"] == "verified_running"
        assert store.aggregate_version(stream) == version
        assert store.require_state(stream)["state"] == "running"
    finally:
        store.close()


def test_running_identity_drift_becomes_indeterminate_without_recreation(tmp_path: Path) -> None:
    store, _service, backend, reconciler, _profile_obj, lease = _setup(tmp_path, "running")
    backend.inspect_persistent = lambda _identity: (_ for _ in ()).throw(
        AuthorityViolation("persistent workload image identity drifted")
    )
    calls = {"create": 0, "start": 0}
    backend.create_persistent_stopped = lambda *_a, **_k: calls.__setitem__("create", 1)
    backend.start_persistent = lambda *_a, **_k: calls.__setitem__("start", 1)
    try:
        result = reconciler.reconcile_one(lease["sandboxLeaseId"])
        state = store.require_state(SandboxLeaseAggregate.stream_id(lease["sandboxLeaseId"]))
        assert result["status"] == "indeterminate"
        assert state["state"] == "indeterminate"
        assert calls == {"create": 0, "start": 0}
    finally:
        store.close()


def test_expired_running_lease_is_quarantined_without_ttl_extension(tmp_path: Path) -> None:
    store, _service, backend, reconciler, _profile_obj, lease = _setup(tmp_path, "running")
    reconciler._now = lambda: "2026-09-09T12:30:01Z"
    backend.inspect_persistent = lambda _identity: {
        "workloadRunning": True, "workloadState": "running", "observationDigest": digest({"expired": True})
    }
    try:
        result = reconciler.reconcile_one(lease["sandboxLeaseId"])
        state = store.require_state(SandboxLeaseAggregate.stream_id(lease["sandboxLeaseId"]))
        assert result["status"] == "cleanup_required"
        assert state["state"] == "indeterminate"
        assert state["reconciliationReason"] == "lease_expired_cleanup_required"
        assert state["expiresAt"] == "2026-09-09T12:30:00Z"
        assert state["ttlSeconds"] == 1800
    finally:
        store.close()


def test_exec_termination_unknown_never_auto_returns_to_running(tmp_path: Path) -> None:
    store, service, backend, reconciler, _profile_obj, lease = _setup(tmp_path, "running")
    service.mark_sandbox_indeterminate(
        lease["sandboxLeaseId"],
        {"reconciliationReason": "exec_termination_unknown"},
        _meta("timeout-unknown"),
    )
    backend.inspect_persistent = lambda _identity: {
        "workloadRunning": True, "workloadState": "running", "observationDigest": digest({"still": True})
    }
    try:
        result = reconciler.reconcile_one(lease["sandboxLeaseId"])
        state = store.require_state(SandboxLeaseAggregate.stream_id(lease["sandboxLeaseId"]))
        assert result["status"] == "close_required"
        assert state["state"] == "indeterminate"
        assert state["reconciliationReason"] == "exec_termination_unknown"
    finally:
        store.close()


def test_closing_positive_absence_records_closed_but_never_deletes_by_label(tmp_path: Path) -> None:
    store, _service, backend, reconciler, _profile_obj, lease = _setup(tmp_path, "closing")
    calls = {"close": 0}
    backend.close_persistent = lambda *_a, **_k: calls.__setitem__("close", 1)
    reconciler._identity_absent = lambda _identity: True
    try:
        result = reconciler.reconcile_one(lease["sandboxLeaseId"])
        state = store.require_state(SandboxLeaseAggregate.stream_id(lease["sandboxLeaseId"]))
        assert result["status"] == "closed"
        assert state["state"] == "closed"
        assert state["closureReceiptDigest"].startswith("sha256:")
        assert calls["close"] == 0
    finally:
        store.close()


def test_reserved_positive_zero_inventory_closes_as_no_effect(tmp_path: Path) -> None:
    store, _service, _backend, reconciler, _profile_obj, lease = _setup(tmp_path, "reserved")
    reconciler._inventory_for_lease = lambda _lease: {"available": True, "containers": [], "networks": []}
    try:
        result = reconciler.reconcile_one(lease["sandboxLeaseId"])
        state = store.require_state(SandboxLeaseAggregate.stream_id(lease["sandboxLeaseId"]))
        assert result["status"] == "closed_no_effect"
        assert state["state"] == "closed"
        assert state["closeReason"] == "create_failed_no_effect"
    finally:
        store.close()


def test_orphan_inventory_is_report_only(tmp_path: Path) -> None:
    store, _service, backend, reconciler, _profile_obj, _lease = _setup(tmp_path, "running")
    calls = {"cleanup": 0}
    backend.close_persistent = lambda *_a, **_k: calls.__setitem__("cleanup", 1)
    reconciler._inventory_all_labeled = lambda: [
        {"objectKind": "container", "objectId": "c" * 64, "sandboxLeaseId": "orphan-1"},
        {"objectKind": "container", "objectId": CONTAINER, "sandboxLeaseId": "sandbox-reconcile-1"},
    ]
    try:
        orphans = reconciler.report_orphans()
        assert orphans == [
            {"status": "orphan", "objectKind": "container", "objectId": "c" * 64, "sandboxLeaseId": "orphan-1"}
        ]
        assert calls["cleanup"] == 0
    finally:
        store.close()


def test_created_keeper_running_advances_to_running_from_positive_evidence(tmp_path: Path) -> None:
    store, _service, backend, reconciler, _profile_obj, lease = _setup(tmp_path, "created")
    backend.inspect_persistent = lambda _identity: {
        "workloadRunning": True,
        "workloadState": "running",
        "observationDigest": digest({"keeper": "running"}),
    }
    try:
        result = reconciler.reconcile_one(lease["sandboxLeaseId"])
        state = store.require_state(SandboxLeaseAggregate.stream_id(lease["sandboxLeaseId"]))
        assert result["status"] == "recovered_running"
        assert state["state"] == "running"
        assert state["reconciliationReason"] == "keeper_running_recovered"
    finally:
        store.close()


def test_reserved_ambiguous_inventory_never_adopts_or_starts(tmp_path: Path) -> None:
    store, _service, backend, reconciler, _profile_obj, lease = _setup(tmp_path, "reserved")
    reconciler._inventory_for_lease = lambda _lease: {
        "available": True,
        "containers": ["c" * 64, "d" * 64],
        "networks": [],
    }
    calls = {"create": 0, "start": 0}
    backend.create_persistent_stopped = lambda *_a, **_k: calls.__setitem__("create", 1)
    backend.start_persistent = lambda *_a, **_k: calls.__setitem__("start", 1)
    try:
        result = reconciler.reconcile_one(lease["sandboxLeaseId"])
        state = store.require_state(SandboxLeaseAggregate.stream_id(lease["sandboxLeaseId"]))
        assert result["status"] == "indeterminate"
        assert state["state"] == "indeterminate"
        assert calls == {"create": 0, "start": 0}
    finally:
        store.close()
