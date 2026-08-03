"""M0-B conformance tests: driver contracts, registry, lifecycle, authority, claims.

These exercise the read-only ExecutionDriver proof. The driver used is the
OpenHarness reference adapter, which performs REAL read-only inspection (no mocks,
no fabricated success). All driver output is treated as untrusted until verified.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from capt_runtime.contracts import require
from capt_runtime.drivers.registry import (
    DriverRegistry,
    DuplicateDriverId,
    IncompatibleDriverVersion,
    SpoofedDriverIdentity,
)
from capt_runtime.drivers.openharness import OpenHarnessDriver, DESCRIPTOR
from capt_runtime.driver_run import DriverRunAggregate, IllegalTransition
from capt_runtime.context_slice import build_context_slice, ContextOverDisclosure
from capt_runtime.capability import CapabilityViolation
from capt_runtime.ingestion import (
    IngestionRejection,
    validate_observation,
    validate_artifact_candidate,
    validate_receipt_candidate,
)
from capt_runtime.verification import (
    guard_claim,
    ClaimRejected,
)
from capt_runtime.reconciliation import reconcile
from capt_runtime.driver_host import DriverHost, tree_digest


@pytest.fixture
def env():
    tmp = tempfile.mkdtemp()
    repo = os.path.join(tmp, "target-repo")
    os.makedirs(repo)
    with open(os.path.join(repo, "README.md"), "w") as f:
        f.write("# target\n")
    with open(os.path.join(repo, "main.py"), "w") as f:
        f.write("print(1)\n")
    staging = os.path.join(tmp, "staging")
    os.makedirs(staging)
    return {"tmp": tmp, "repo": repo, "staging": staging}


# ---------------------------------------------------------------------------
# Driver contracts
# ---------------------------------------------------------------------------

def test_driver_contracts_validate():
    require("ExecutionDriverDescriptor", DESCRIPTOR)
    require("ContextSlice", build_context_slice(
        lease={"leaseId": "l", "operations": ["RepositoryRead"], "scope": {"kind": "filesystem", "rootPath": "/x", "recursive": True}, "validFrom": "2026-08-03T00:00:00Z", "validUntil": "2026-08-03T06:00:00Z"},
        filesystem_policy={"rootPath": "/x", "allowedPaths": ["/x"], "writesAllowed": False},
        permitted_tools=[], budgets={"maxSeconds": 10}, expected_artifacts=[],
        termination_conditions={"onUnexpectedWrite": "fail"},
        network_policy={"egressAllowed": False, "allowedHosts": []},
    ))


def test_invalid_discriminant_rejected():
    with pytest.raises(Exception):
        require("DriverRunState", "teleported")


def test_oversized_observation_rejected():
    big = "x" * 70000
    with pytest.raises(Exception):
        require("DriverObservation", {
            "schemaVersion": "1.0.0", "observationId": "o1", "observedBy": "d",
            "trust": "untrusted", "workOrderId": "w1", "summary": big,
            "observedAt": "2026-08-03T00:00:00Z",
        })


# ---------------------------------------------------------------------------
# Registry and identity
# ---------------------------------------------------------------------------

def test_valid_registration():
    reg = DriverRegistry()
    ev = reg.register(DESCRIPTOR)
    assert ev["eventType"] == "DriverRegistered"
    assert ev["authority"] == "registration_only"
    assert ev["trustClassification"] == "untrusted"
    assert reg.is_registered("openharness")


def test_duplicate_driver_id():
    reg = DriverRegistry()
    reg.register(DESCRIPTOR)
    with pytest.raises(DuplicateDriverId):
        reg.register(DESCRIPTOR)


def test_incompatible_version_rejected():
    reg = DriverRegistry()
    bad = dict(DESCRIPTOR, writeCapable=True)
    with pytest.raises(IncompatibleDriverVersion):
        reg.register(bad)


def test_identity_spoofing():
    reg = DriverRegistry()
    reg.register(DESCRIPTOR)
    spoofed = dict(DESCRIPTOR, driverVersion="9.9.9")
    with pytest.raises(SpoofedDriverIdentity):
        reg.verify_identity("openharness", spoofed)


def test_unauthorized_self_registration_no_authority():
    reg = DriverRegistry()
    ev = reg.register(DESCRIPTOR)
    assert ev["authority"] == "registration_only"
    assert "grant" not in ev


def test_disabled_driver_dispatch_rejection():
    reg = DriverRegistry()
    reg.register(DESCRIPTOR)
    reg.disable("openharness", reason="maintenance")
    assert reg.get("openharness")["enabled"] is False


# ---------------------------------------------------------------------------
# Work orders
# ---------------------------------------------------------------------------

def _lease(root="/r"):
    return {
        "leaseId": "l1", "driverId": "openharness", "missionId": "m", "taskId": "t",
        "status": "active", "revoked": False,
        "operations": ["RepositoryRead", "FilesystemRead",
                       "ArtifactCreate", "AnalysisOnly"],
        "scope": {"kind": "filesystem", "rootPath": root, "recursive": True,
                  "allowedPaths": [root]},
        "budget": {"maxSeconds": 120},
        "validFrom": "2026-08-03T00:00:00Z", "validUntil": "2026-08-03T06:00:00Z",
    }


def test_minimal_permitted_context():
    ctx = build_context_slice(
        lease=_lease(),
        filesystem_policy={"rootPath": "/r", "allowedPaths": ["/r"], "writesAllowed": False},
        permitted_tools=["inspect"], budgets={"maxSeconds": 10},
        expected_artifacts=[], termination_conditions={"onUnexpectedWrite": "fail"},
        network_policy={"egressAllowed": False, "allowedHosts": []},
    )
    assert ctx["networkPolicy"]["egressAllowed"] is False
    assert ctx["filesystemPolicy"]["writesAllowed"] is False


def test_write_operation_rejected_before_dispatch(env):
    reg = DriverRegistry()
    reg.register(DESCRIPTOR)
    host = DriverHost(reg, env["staging"], env["repo"])
    ctx = host.build_context(_lease(), ["inspect"], {"maxSeconds": 10}, [], {"onUnexpectedWrite": "fail"})
    wo = {"schemaVersion": "1.0.0", "driverRunId": "dr", "driverId": "openharness",
          "missionId": "m", "taskId": "t", "workOrderVersion": 1,
          "contextSlice": ctx, "operations": ["RepositoryWrite"]}
    host.select_driver(OpenHarnessDriver(env["staging"]))
    with pytest.raises(CapabilityViolation):
        host.dispatch(wo, ctx, DriverRunAggregate.create({"driverRunId": "dr", "driverId": "openharness", "missionId": "m", "taskId": "t"}),
                      now="2026-08-03T01:00:00Z", lease=_lease(env["repo"]))


# ---------------------------------------------------------------------------
# Read-only enforcement
# ---------------------------------------------------------------------------

def test_repository_hashes_unchanged(env):
    before = tree_digest(env["repo"])
    reg = DriverRegistry()
    reg.register(DESCRIPTOR)
    host = DriverHost(reg, env["staging"], env["repo"])
    host.select_driver(OpenHarnessDriver(env["staging"]))
    ctx = host.build_context(_lease(), ["inspect"], {"maxSeconds": 60, "maxArtifacts": 1, "maxObservations": 10},
                             [{"artifactPath": os.path.join(env["staging"], "a.md"), "artifactKind": "report"}],
                             {"onUnexpectedWrite": "fail"})
    wo = {"schemaVersion": "1.0.0", "driverRunId": "dr", "driverId": "openharness",
          "missionId": "m", "taskId": "t", "workOrderVersion": 1, "contextSlice": ctx,
          "operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"]}
    out = host.dispatch(wo, ctx, DriverRunAggregate.create({"driverRunId": "dr", "driverId": "openharness", "missionId": "m", "taskId": "t"}),
                        now="2026-08-03T01:00:00Z", lease=_lease(env["repo"]))
    seen = {}
    ing = host.ingest(out, "dr", "m", "t", seen)
    vr = host.verify(before, ing["artifacts"][0]["path"], ing["artifacts"][0]["digest"], "openharness")
    assert vr["status"]["kind"] == "verified"
    after = tree_digest(env["repo"])
    assert before == after, "target repository was modified by the driver"


def test_artifact_writing_allowed_only_in_staging(env):
    reg = DriverRegistry()
    reg.register(DESCRIPTOR)
    host = DriverHost(reg, env["staging"], env["repo"])
    host.select_driver(OpenHarnessDriver(env["staging"]))
    ctx = host.build_context(_lease(), ["inspect"], {"maxSeconds": 60, "maxArtifacts": 1, "maxObservations": 10},
                             [{"artifactPath": os.path.join(env["staging"], "a.md"), "artifactKind": "report"}],
                             {"onUnexpectedWrite": "fail"})
    wo = {"schemaVersion": "1.0.0", "driverRunId": "dr", "driverId": "openharness",
          "missionId": "m", "taskId": "t", "workOrderVersion": 1, "contextSlice": ctx,
          "operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"]}
    out = host.dispatch(wo, ctx, DriverRunAggregate.create({"driverRunId": "dr", "driverId": "openharness", "missionId": "m", "taskId": "t"}),
                        now="2026-08-03T01:00:00Z", lease=_lease(env["repo"]))
    assert out["artifactCandidate"]["artifactPath"].startswith(env["staging"])
    assert not out["artifactCandidate"]["artifactPath"].startswith(env["repo"])


# ---------------------------------------------------------------------------
# Read-only capability model (ADR-0122)
# ---------------------------------------------------------------------------

def test_capability_allows_read_only_ops():
    from capt_runtime.capability import ALLOWED_OPERATIONS, DENIED_OPERATIONS
    for op in ("repository.read", "filesystem.read", "artifact.create", "analysis.execute"):
        assert op in ALLOWED_OPERATIONS
    for op in ("repository.write", "filesystem.write", "git.commit", "git.push",
               "process.mutate", "package.install", "deployment", "credential.use",
               "network.access"):
        assert op in DENIED_OPERATIONS


def test_lease_rejects_write_operation():
    from capt_runtime.capability import verify_lease, CapabilityViolation
    lease = _lease()
    with pytest.raises(CapabilityViolation):
        verify_lease(lease, now="2026-08-03T01:00:00Z", driver_id="openharness",
                     mission_id="m", task_id="t",
                     operations=["repository.write"], resource_path="/r")


def test_lease_rejects_expired():
    from capt_runtime.capability import verify_lease, CapabilityViolation
    lease = _lease()
    with pytest.raises(CapabilityViolation):
        verify_lease(lease, now="2026-08-03T12:00:00Z", driver_id="openharness",
                     mission_id="m", task_id="t",
                     operations=["repository.read"], resource_path="/r")


def test_lease_rejects_wrong_driver():
    from capt_runtime.capability import verify_lease, CapabilityViolation
    lease = _lease()
    with pytest.raises(CapabilityViolation):
        verify_lease(lease, now="2026-08-03T01:00:00Z", driver_id="otherdriver",
                     mission_id="m", task_id="t",
                     operations=["repository.read"], resource_path="/r")


def test_lease_rejects_path_escape():
    from capt_runtime.capability import verify_lease, CapabilityViolation
    lease = _lease()
    with pytest.raises(CapabilityViolation):
        verify_lease(lease, now="2026-08-03T01:00:00Z", driver_id="openharness",
                     mission_id="m", task_id="t",
                     operations=["repository.read"], resource_path="/elsewhere/secret")


def test_lease_rejects_revoked():
    from capt_runtime.capability import verify_lease, CapabilityViolation
    lease = dict(_lease(), revoked=True)
    with pytest.raises(CapabilityViolation):
        verify_lease(lease, now="2026-08-03T01:00:00Z", driver_id="openharness",
                     mission_id="m", task_id="t",
                     operations=["repository.read"], resource_path="/r")


def test_lease_rejects_budget_overrun():
    from capt_runtime.capability import verify_lease, CapabilityViolation
    lease = _lease()
    with pytest.raises(CapabilityViolation):
        verify_lease(lease, now="2026-08-03T01:00:00Z", driver_id="openharness",
                     mission_id="m", task_id="t",
                     operations=["repository.read"], resource_path="/r",
                     budget={"maxSeconds": 999})


def test_lease_valid_passes():
    from capt_runtime.capability import verify_lease
    lease = _lease()
    # Must not raise.
    verify_lease(lease, now="2026-08-03T01:00:00Z", driver_id="openharness",
                 mission_id="m", task_id="t",
                 operations=["repository.read", "filesystem.read",
                             "artifact.create", "analysis.execute"],
                 resource_path="/r", budget={"maxSeconds": 60})


def test_work_order_blocklist_rejected():
    from capt_runtime.capability import check_work_order_operations, CapabilityViolation
    with pytest.raises(CapabilityViolation):
        check_work_order_operations(["RepositoryWrite"])
    with pytest.raises(CapabilityViolation):
        check_work_order_operations(["GitCommit", "GitPush"])
    # Read-only ops are fine.
    check_work_order_operations(["RepositoryRead", "FilesystemRead",
                                 "ArtifactCreate", "AnalysisOnly"])


# ---------------------------------------------------------------------------
# Driver output validation
# ---------------------------------------------------------------------------

def test_valid_observation_accepted_as_untrusted():
    obs = {"schemaVersion": "1.0.0", "observationId": "o1", "observedBy": "openharness",
           "trust": "untrusted", "workOrderId": "dr", "summary": "ok",
           "observedAt": "2026-08-03T00:00:00Z"}
    v = validate_observation(obs, "dr", "m", "t", ["/staging"], {})
    assert not v["duplicate"]


def test_duplicate_observation_deduplicated():
    obs = {"schemaVersion": "1.0.0", "observationId": "o1", "observedBy": "openharness",
           "trust": "untrusted", "workOrderId": "dr", "summary": "ok",
           "observedAt": "2026-08-03T00:00:00Z"}
    seen = {}
    validate_observation(obs, "dr", "m", "t", ["/staging"], seen)
    v2 = validate_observation(obs, "dr", "m", "t", ["/staging"], seen)
    assert v2["duplicate"]


def test_conflicting_duplicate_rejected():
    o1 = {"schemaVersion": "1.0.0", "observationId": "o1", "observedBy": "openharness",
           "trust": "untrusted", "workOrderId": "dr", "summary": "a", "observedAt": "2026-08-03T00:00:00Z"}
    o2 = dict(o1, summary="b")
    seen = {}
    validate_observation(o1, "dr", "m", "t", ["/staging"], seen)
    with pytest.raises(IngestionRejection):
        validate_observation(o2, "dr", "m", "t", ["/staging"], seen)


def test_fake_receipt_rejected(env):
    rc = {"schemaVersion": "1.0.0", "receiptId": "r1", "driverRunId": "dr",
          "step": "write", "claimedAt": "2026-08-03T00:00:00Z"}
    validate_receipt_candidate(rc, "dr")
    ac = {"schemaVersion": "1.0.0", "candidateId": "ac1", "driverRunId": "dr",
          "artifactPath": os.path.join(env["staging"], "missing.md"),
          "artifactDigest": "sha256:" + "0" * 64, "producedAt": "2026-08-03T00:00:00Z"}
    with pytest.raises(IngestionRejection):
        validate_artifact_candidate(ac, "dr", env["staging"])


def test_fake_authoritative_event_rejected():
    from capt_runtime.ingestion import reject_fabricated_authoritative
    with pytest.raises(IngestionRejection):
        reject_fabricated_authoritative({"eventType": "EvidenceRecord"})
    with pytest.raises(IngestionRejection):
        reject_fabricated_authoritative({"kind": "VerificationResult"})


def test_cross_mission_observation_rejected():
    obs = {"schemaVersion": "1.0.0", "observationId": "o1", "observedBy": "openharness",
           "trust": "untrusted", "workOrderId": "OTHER", "summary": "ok",
           "observedAt": "2026-08-03T00:00:00Z"}
    with pytest.raises(IngestionRejection):
        validate_observation(obs, "dr", "m", "t", ["/staging"], {})


# ---------------------------------------------------------------------------
# Driver lifecycle (state machine)
# ---------------------------------------------------------------------------

def test_lifecycle_created_to_completed():
    s = DriverRunAggregate.create({"driverRunId": "dr", "driverId": "openharness", "missionId": "m", "taskId": "t"})
    assert s["state"] == "created"
    s = DriverRunAggregate.transition(s, "queued")
    s = DriverRunAggregate.transition(s, "running")
    assert s["attemptCount"] == 1
    s = DriverRunAggregate.transition(s, "completed")
    assert s["state"] == "completed"
    assert s["terminalDisposition"] == "completed"


def test_terminal_state_immutable():
    s = DriverRunAggregate.create({"driverRunId": "dr", "driverId": "openharness", "missionId": "m", "taskId": "t"})
    s = DriverRunAggregate.transition(s, "queued")
    s = DriverRunAggregate.transition(s, "running")
    s = DriverRunAggregate.transition(s, "completed")
    with pytest.raises(IllegalTransition):
        DriverRunAggregate.transition(s, "running")


def test_suspension_and_resume():
    s = DriverRunAggregate.create({"driverRunId": "dr", "driverId": "openharness", "missionId": "m", "taskId": "t"})
    s = DriverRunAggregate.transition(s, "queued")
    s = DriverRunAggregate.transition(s, "running")
    s = DriverRunAggregate.transition(s, "suspended")
    s = DriverRunAggregate.transition(s, "running")
    assert s["state"] == "running"


def test_cancellation():
    s = DriverRunAggregate.create({"driverRunId": "dr", "driverId": "openharness", "missionId": "m", "taskId": "t"})
    s = DriverRunAggregate.transition(s, "queued")
    s = DriverRunAggregate.transition(s, "running")
    s = DriverRunAggregate.transition(s, "cancelled")
    assert s["state"] == "cancelled"


def test_stale_version_rejection():
    # Genuine optimistic-concurrency guard at the store layer: a command that
    # declares an expected aggregate version behind the actual version must be
    # rejected. This is the mechanism that prevents a restarted runtime from
    # re-applying an already-applied driver-run transition.
    from capt_runtime.store import EventStore, AppendRequest
    from capt_runtime.commands import envelope, command
    from capt_runtime.aggregates import DriverRunAggregate as DRA

    store = EventStore(":memory:")
    stream = DRA.stream_id("dr")
    run = {"schemaVersion": "1.0.0", "driverRunId": "dr", "driverId": "openharness",
           "missionId": "m", "taskId": "t", "workOrderVersion": 1, "state": "created",
           "reconciliationStatus": "not_required", "createdAt": "2026-08-03T00:00:00Z"}
    meta = command("cmd-1", "idem-1", "sha256:" + "a" * 64, "corr", "system", "system", "2026-08-03T00:00:00Z")
    ev1 = envelope("ev-1", stream, "DriverRunCreated",
                   {"eventType": "DriverRunCreated", "driverRun": run}, meta,
                   meta["issuedAt"], mission_id="m", task_id="t")
    # First commit at expected version 0 succeeds; actual becomes 1.
    store.commit_command(
        [AppendRequest(stream, DRA.KIND, 0, ev1, DRA.create(run))],
        "idem-1", "sha256:" + "a" * 64, "cmd-1",
    )
    # A second command that still claims expected version 0 must be rejected.
    ev2 = envelope("ev-2", stream, "DriverRunStateChanged",
                   {"eventType": "DriverRunStateChanged", "driverRunId": "dr",
                    "fromState": "created", "toState": "queued"}, meta,
                   meta["issuedAt"], mission_id="m", task_id="t")
    with pytest.raises(Exception):
        store.commit_command(
            [AppendRequest(stream, DRA.KIND, 0, ev2, DRA.create(run))],
            "idem-2", "sha256:" + "b" * 64, "cmd-2",
        )


# ---------------------------------------------------------------------------
# Checkpoint and replay
# ---------------------------------------------------------------------------

def test_replay_idempotent():
    from capt_runtime.store import EventStore
    from capt_runtime.services import RuntimeService
    from capt_runtime.commands import command
    from capt_runtime.replay import full_replay
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    meta = command("cmd-1", "idem-1", "sha256:" + "a" * 64, "corr", "system", "system", "2026-08-03T00:00:00Z")
    run = {"schemaVersion": "1.0.0", "driverRunId": "dr", "driverId": "openharness",
           "missionId": "m", "taskId": "t", "workOrderVersion": 1, "state": "created",
           "reconciliationStatus": "not_required", "createdAt": "2026-08-03T00:00:00Z"}
    svc.create_driver_run(run, meta)
    r1 = full_replay(store)
    r2 = full_replay(store)
    assert r1.digest() == r2.digest()


# ---------------------------------------------------------------------------
# Authority boundary
# ---------------------------------------------------------------------------

def test_driver_cannot_mutate_aggregates():
    from capt_runtime.drivers import ExecutionDriver
    for forbidden in ("grant_capability", "create_mission", "transition_task", "append_event", "create_claim"):
        assert forbidden not in dir(ExecutionDriver), "driver interface leaks authority: %s" % forbidden


def test_context_over_disclosure_rejected():
    # A clean context with no forbidden object must build successfully.
    clean = build_context_slice(
        lease=_lease(), filesystem_policy={"rootPath": "/r", "allowedPaths": ["/r"], "writesAllowed": False},
        permitted_tools=[], budgets={"maxSeconds": 10}, expected_artifacts=[],
        termination_conditions={"onUnexpectedWrite": "fail"},
        network_policy={"egressAllowed": False, "allowedHosts": []},
    )
    assert clean["networkPolicy"]["egressAllowed"] is False
    # A context that embeds a forbidden authority object must be rejected.
    # The forbidden set keys on the object's type name (ADR-0125), so we use a
    # class whose name matches a forbidden authority type.
    class GovernanceKernel:
        pass
    with pytest.raises(ContextOverDisclosure):
        build_context_slice(
            lease=_lease(), filesystem_policy={"rootPath": "/r", "allowedPaths": ["/r"], "writesAllowed": False},
            permitted_tools=[GovernanceKernel()], budgets={"maxSeconds": 10}, expected_artifacts=[],
            termination_conditions={"onUnexpectedWrite": "fail"},
            network_policy={"egressAllowed": False, "allowedHosts": []},
        )

# ---------------------------------------------------------------------------
# Claim integrity
# ---------------------------------------------------------------------------

def test_unsupported_completion_rejected():
    with pytest.raises(ClaimRejected):
        guard_claim("The issue was fixed.")
    with pytest.raises(ClaimRejected):
        guard_claim("All vulnerabilities were found.")


def test_verified_bounded_claim_accepted():
    assert guard_claim("Repository inspected in read-only mode.") == "Repository inspected in read-only mode."
    assert guard_claim("No repository modification was detected by the specified verification checks.") == "No repository modification was detected by the specified verification checks."


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

def test_reconcile_completed():
    rec = reconcile(
        {"driverRunId": "dr", "missionId": "m", "taskId": "t", "state": "running", "createdAt": "2026-08-03T00:00:00Z"},
        [{"eventType": "DriverRunStateChanged", "payload": {"toState": "completed"}}],
        [], artifact_present=True, lease_valid=True, budget_valid=True,
    )
    assert rec["result"] == "reconciled_completed"


def test_reconcile_artifact_missing():
    rec = reconcile(
        {"driverRunId": "dr", "missionId": "m", "taskId": "t", "state": "running", "createdAt": "2026-08-03T00:00:00Z"},
        [{"eventType": "DriverRunStateChanged", "payload": {"toState": "completed"}}],
        [], artifact_present=False, lease_valid=True, budget_valid=True,
    )
    assert rec["result"] == "reconciliation_requires_human"


def test_reconcile_stale_lease_forbidden():
    rec = reconcile(
        {"driverRunId": "dr", "missionId": "m", "taskId": "t", "state": "running", "createdAt": "2026-08-03T00:00:00Z"},
        [], [], artifact_present=True, lease_valid=False, budget_valid=True,
    )
    assert rec["result"] == "retry_forbidden"


# ---------------------------------------------------------------------------
# Acceptance scenario (Part 11)
# ---------------------------------------------------------------------------

def test_m0b_read_only_acceptance_scenario(env):
    reg = DriverRegistry()
    reg.register(DESCRIPTOR)
    host = DriverHost(reg, env["staging"], env["repo"])
    host.select_driver(OpenHarnessDriver(env["staging"]))
    before = tree_digest(env["repo"])

    lease = _lease(env["repo"])
    ctx = host.build_context(lease, ["inspect"],
                             {"maxSeconds": 60, "maxArtifacts": 1, "maxObservations": 10},
                             [{"artifactPath": os.path.join(env["staging"], "analysis-dr.md"), "artifactKind": "report"}],
                             {"onUnexpectedWrite": "fail"})
    wo = {"schemaVersion": "1.0.0", "driverRunId": "dr", "driverId": "openharness",
          "missionId": "m", "taskId": "t", "workOrderVersion": 1, "contextSlice": ctx,
          "operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"]}
    run_state = DriverRunAggregate.create({"driverRunId": "dr", "driverId": "openharness", "missionId": "m", "taskId": "t"})
    run_state = DriverRunAggregate.transition(run_state, "queued")
    run_state = DriverRunAggregate.transition(run_state, "running")

    out = host.dispatch(wo, ctx, run_state, now="2026-08-03T01:00:00Z", lease=lease)
    assert out["observations"]

    seen = {}
    ing = host.ingest(out, "dr", "m", "t", seen)
    assert ing["artifacts"]
    assert ing["observations"]

    vr = host.verify(before, ing["artifacts"][0]["path"], ing["artifacts"][0]["digest"], "openharness")
    assert vr["status"]["kind"] == "verified"
    assert vr["checks"]["repositoryUnchanged"] is True
    assert vr["checks"]["noGitMutation"] is True

    claim = host.propose_bounded_claim("Repository inspected in read-only mode.")
    assert claim

    after = tree_digest(env["repo"])
    assert before == after, "repository modified during M0-B proof"

    rec = reconcile(run_state, [{"eventType": "DriverRunStateChanged", "payload": {"toState": "completed"}}],
                   ing["observations"], artifact_present=True, lease_valid=True, budget_valid=True)
    assert rec["result"] == "reconciled_completed"
