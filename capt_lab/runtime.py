"""Governed RuntimeService bridge for Inversion Labs specialist advisories."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from capt_lab.contracts import LabEngineRequest, canonical_json_bytes, sha256_digest
from capt_lab.provenance import manifest_digest
from capt_lab.registry import LabEngineRegistry
from capt_runtime import commands
from capt_runtime.errors import AuthorityViolation, IntegrityViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from capt_runtime.verification import build_artifact_hash_evidence

_TASK_TERMINAL = frozenset({"succeeded", "failed", "cancelled"})
_MISSION_TERMINAL = frozenset({"completed", "failed", "cancelled"})


def _suffix(command_id: str) -> str:
    return hashlib.sha256(command_id.encode("utf-8")).hexdigest()[:24]


def _metadata(command: Mapping[str, Any], step: str, actor_id: str, actor_kind: str,
              operation: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    return commands.command(
        command_id=str(command["commandId"]) + ":" + step,
        idempotency_key=str(command["idempotencyKey"]) + ":" + step,
        operation_fingerprint=commands.fingerprint(operation, dict(payload)),
        correlation_id=str(command.get("correlationId") or "corr-lab"),
        actor_id=actor_id,
        actor_kind=actor_kind,
        issued_at=str(command.get("timestamp") or "1970-01-01T00:00:00Z"),
        replay_policy="never",
    )


def _validate_lineage(store: EventStore, request: LabEngineRequest) -> Mapping[str, Any]:
    mission = store.load_state("mission-" + request.mission_id)
    if mission is None:
        raise AuthorityViolation("Lab mission does not exist: %s" % request.mission_id)
    task = store.load_state("task-" + request.task_id)
    if task is None:
        raise AuthorityViolation("Lab task does not exist: %s" % request.task_id)
    if task.get("missionId") != request.mission_id:
        raise AuthorityViolation("Lab mission/task binding mismatch")
    if mission.get("state") in _MISSION_TERMINAL:
        raise AuthorityViolation("Lab mission is terminal: %s" % mission.get("state"))
    if task.get("state") in _TASK_TERMINAL:
        raise AuthorityViolation("Lab task is terminal: %s" % task.get("state"))
    return task


def _validate_filesystem_capability(task: Mapping[str, Any], request: LabEngineRequest) -> None:
    raw_root = request.input.get("root")
    if not isinstance(raw_root, str) or not raw_root.strip():
        raise AuthorityViolation("Lab filesystem capability requires a concrete input root")
    requested = Path(raw_root).expanduser().resolve()
    for requirement in task.get("capabilityRequirements") or []:
        if requirement.get("capabilityId") != "cap.fs.read":
            continue
        if "repository.read" not in (requirement.get("operations") or []):
            continue
        scope = requirement.get("scope") or {}
        if scope.get("kind") != "filesystem":
            continue
        allowed_raw = scope.get("rootPath")
        if not isinstance(allowed_raw, str) or not allowed_raw.strip():
            continue
        allowed = Path(allowed_raw).expanduser().resolve()
        recursive = bool(scope.get("recursive"))
        if requested == allowed or (recursive and allowed in requested.parents):
            return
    raise AuthorityViolation(
        "Lab filesystem capability does not authorize requested root: %s" % requested
    )


def _write_artifact(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def run_lab_advisory(
    store: EventStore,
    svc: RuntimeService,
    registry: LabEngineRegistry,
    staging_root: Path,
    command: Mapping[str, Any],
    *,
    post_write_hook: Optional[Callable[[Path], None]] = None,
) -> Dict[str, Any]:
    """Execute one local specialist advisory inside CAPT authority boundaries.

    Validation happens before DriverRun creation. The original command key is
    durably claimed before engine execution. Successful output becomes a
    canonical artifact, a proposed observation Claim, and artifact-hash evidence;
    no verification, claim decision, task success, or mission completion occurs.
    """
    request = LabEngineRequest.from_mapping(command.get("payload", {}))
    task = _validate_lineage(store, request)
    descriptor = registry.resolve(request)
    if descriptor.requires_filesystem:
        _validate_filesystem_capability(task, request)

    operation_fingerprint = commands.fingerprint(
        "run_lab_engine_advisory", request.to_mapping()
    )
    admission = store.claim_command(
        str(command["idempotencyKey"]), operation_fingerprint, str(command["commandId"])
    )
    if admission.get("replayed"):
        result = dict(admission)
        if result.get("status") == "idempotent":
            result.pop("status", None)
            result["_idempotent"] = True
        else:
            result["_in_progress"] = True
        return result

    suffix = _suffix(str(command["commandId"]))
    run_id = "dr-lab-" + suffix
    claim_id = "cl-lab-" + suffix
    now = str(command.get("timestamp") or "1970-01-01T00:00:00Z")
    driver_id = request.engine_id
    run = {
        "schemaVersion": "1.0.0",
        "driverRunId": run_id,
        "driverId": driver_id,
        "missionId": request.mission_id,
        "taskId": request.task_id,
        "workOrderVersion": 1,
        "externalRunId": None,
        "state": "created",
        "reconciliationStatus": "not_required",
        "createdAt": now,
    }
    svc.create_driver_run(
        run,
        _metadata(command, "driver-create", "lab-runtime", "execution_plane",
                  "create_driver_run", {"driverRunId": run_id}),
    )
    svc.transition_driver_run(
        run_id, "submitted",
        _metadata(command, "driver-submit", "lab-runtime", "execution_plane",
                  "transition_driver_run", {"driverRunId": run_id, "to": "submitted"}),
    )
    svc.transition_driver_run(
        run_id, "running",
        _metadata(command, "driver-run", "lab-runtime", "execution_plane",
                  "transition_driver_run", {"driverRunId": run_id, "to": "running"}),
    )

    try:
        engine_result = registry.execute(request, {
            "driverRunId": run_id,
            "missionId": request.mission_id,
            "taskId": request.task_id,
        })
    except Exception as exc:
        svc.transition_driver_run(
            run_id, "failed",
            _metadata(command, "driver-failed", "lab-runtime", "execution_plane",
                      "transition_driver_run", {"driverRunId": run_id, "to": "failed"}),
        )
        failure = {
            "missionId": request.mission_id, "taskId": request.task_id,
            "driverRunId": run_id, "engineId": request.engine_id,
            "operation": request.operation, "failure": type(exc).__name__,
            "claimId": None, "evidenceId": None, "verificationId": None,
        }
        store.complete_claimed_command(str(command["idempotencyKey"]), operation_fingerprint, failure)
        raise

    artifact = {
        "schemaVersion": "1.0.0",
        "engineId": engine_result.engine_id,
        "engineVersion": engine_result.engine_version,
        "operation": engine_result.operation,
        "epistemicClass": engine_result.epistemic_class,
        "requestDigest": request.request_digest,
        "observation": engine_result.observation,
        "limitations": list(engine_result.limitations),
        "driverRunId": run_id,
        "missionId": request.mission_id,
        "taskId": request.task_id,
        "provenance": {
            **dict(descriptor.provenance),
            "implementationDigest": registry.implementation_digest(request.engine_id),
            "donorManifestDigest": manifest_digest(),
        },
    }
    artifact_bytes = canonical_json_bytes(artifact)
    expected_digest = sha256_digest(artifact_bytes)
    artifact_path = Path(staging_root).resolve() / run_id / "lab-result.json"
    _write_artifact(artifact_path, artifact_bytes)
    if post_write_hook is not None:
        post_write_hook(artifact_path)
    actual_bytes = artifact_path.read_bytes()
    actual_digest = sha256_digest(actual_bytes)
    if actual_digest != expected_digest:
        svc.transition_driver_run(
            run_id, "failed",
            _metadata(command, "artifact-failed", "lab-runtime", "execution_plane",
                      "transition_driver_run", {"driverRunId": run_id, "to": "failed"}),
        )
        failure = {
            "missionId": request.mission_id, "taskId": request.task_id,
            "driverRunId": run_id, "engineId": request.engine_id,
            "operation": request.operation, "failure": "artifact_integrity",
            "claimId": None, "evidenceId": None, "verificationId": None,
        }
        store.complete_claimed_command(str(command["idempotencyKey"]), operation_fingerprint, failure)
        raise IntegrityViolation("Lab result artifact digest mismatch")

    svc.transition_driver_run(
        run_id, "completed",
        _metadata(command, "driver-complete", "lab-runtime", "execution_plane",
                  "transition_driver_run", {"driverRunId": run_id, "to": "completed"}),
    )

    statement = (
        "%s/%s produced a %s Lab advisory; result bytes were recorded as an "
        "unverified observation."
        % (request.engine_id, request.operation, engine_result.epistemic_class)
    )
    claim = {
        "schemaVersion": "1.0.0",
        "claimId": claim_id,
        "missionId": request.mission_id,
        "taskId": request.task_id,
        "kind": "observation",
        "statement": statement,
        "evidenceIds": [],
        "promotionState": "proposed",
        "proposedBy": {"actorId": "lab-cognition", "kind": "cognitive_plane"},
        "proposedAt": now,
        "sourceProposalId": None,
    }
    svc.propose_claim(
        claim,
        _metadata(command, "claim", "lab-cognition", "cognitive_plane",
                  "propose_claim", {"claimId": claim_id}),
    )
    evidence_id = "ev-lab-" + expected_digest.split(":", 1)[1][:24]
    evidence = build_artifact_hash_evidence(
        mission_id=request.mission_id,
        task_id=request.task_id,
        artifact_path=str(artifact_path),
        artifact_digest=expected_digest,
        collected_by={"actorId": "lab-runtime", "kind": "execution_plane"},
        evidence_id=evidence_id,
        collected_at=now,
    )
    svc.record_evidence(
        claim_id, evidence,
        _metadata(command, "evidence", "lab-runtime", "execution_plane",
                  "record_evidence", {"evidenceId": evidence_id}),
    )

    receipt = {
        "missionId": request.mission_id,
        "taskId": request.task_id,
        "driverRunId": run_id,
        "claimId": claim_id,
        "evidenceId": evidence_id,
        "verificationId": None,
        "promotionState": "proposed",
        "artifactPath": str(artifact_path),
        "artifactDigest": expected_digest,
        "requestDigest": request.request_digest,
        "engineId": request.engine_id,
        "operation": request.operation,
        "epistemicClass": engine_result.epistemic_class,
    }
    store.complete_claimed_command(str(command["idempotencyKey"]), operation_fingerprint, receipt)
    return receipt
