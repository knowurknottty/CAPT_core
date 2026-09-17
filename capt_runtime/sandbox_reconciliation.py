"""Non-destructive restart reconciliation for persistent InversionSandbox leases.

EventStore resource identity remains authoritative. Docker labels are discovery
hints only: R2 may inspect by a durable lease label, but it never adopts or
deletes an object by label alone.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable

from . import commands
from .aggregates import SandboxLeaseAggregate
from .contracts import digest, require
from .errors import AuthorityViolation
from .services import RuntimeService
from .tools.backends.docker import DockerPreparedTarget, docker_context_endpoint
from .tools.backends.inversion_sandbox import (
    InversionSandboxPreparedTarget,
    InversionSandboxProcessBackend,
    SandboxRuntimeIdentity,
    attest_created_container,
)

_FULL_ID = re.compile(r"^[0-9a-f]{64}$")


def _stable_token(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


class SandboxLeaseReconciler:
    """Reconcile durable sandbox truth against read-only Docker observations."""

    def __init__(
        self,
        runtime: RuntimeService,
        backend: InversionSandboxProcessBackend,
        *,
        now: Callable[[], str],
    ) -> None:
        self.runtime = runtime
        self.store = runtime.store
        self.backend = backend
        self._now = now

    def _metadata(self, lease_id: str, action: str, evidence: object) -> dict[str, Any]:
        evidence_digest = digest(evidence)
        material = f"{lease_id}:{action}:{evidence_digest}"
        token = _stable_token(material)
        return commands.command(
            command_id="sandbox-reconcile-" + token,
            idempotency_key="sandbox-reconcile-" + token,
            operation_fingerprint=commands.fingerprint(
                "reconcile_sandbox_lease",
                {"sandboxLeaseId": lease_id, "action": action, "evidenceDigest": evidence_digest},
            ),
            correlation_id="sandbox-reconcile-" + _stable_token(lease_id),
            actor_id="sandbox-reconciler",
            actor_kind="system",
            issued_at=self._now(),
        )

    @staticmethod
    def _identity_from_state(state: dict[str, Any]) -> SandboxRuntimeIdentity | None:
        required = ("containerId", "creationAttestationDigest", "sideEffectIdentity")
        if any(not state.get(name) for name in required):
            return None
        return SandboxRuntimeIdentity(
            sandbox_lease_id=state["sandboxLeaseId"],
            profile_id=state["profileId"],
            profile_digest=state["profileDigest"],
            context_endpoint=state["dockerEndpoint"],
            daemon_identity_digest=state["daemonIdentityDigest"],
            workload_container_id=state["containerId"],
            workload_image_id=state["imageId"],
            security_profile_digest=state["securityProfileDigest"],
            network_policy_digest=state["networkPolicyDigest"],
            filesystem_scope_digest=state["filesystemScopeDigest"],
            persistent_entrypoint_digest=state["persistentEntrypointDigest"],
            creation_attestation_digest=state["creationAttestationDigest"],
            guardian_container_id=state.get("guardianContainerId"),
            guardian_image_id=state.get("guardianImageId"),
            internal_network_name=state.get("networkName"),
            internal_network_id=state.get("networkId"),
        )

    def _mark_indeterminate(
        self, state: dict[str, Any], reason: str, evidence: object
    ) -> dict[str, Any]:
        if state["state"] == "indeterminate":
            return {
                "sandboxLeaseId": state["sandboxLeaseId"],
                "status": "indeterminate",
                "reason": state.get("reconciliationReason") or reason,
                "evidenceDigest": digest(evidence),
            }
        patch = {
            "reconciliationReason": reason[:1024],
            "reconciliationEvidenceDigest": digest(evidence),
            "lastReconciledAt": self._now(),
        }
        self.runtime.mark_sandbox_indeterminate(
            state["sandboxLeaseId"],
            patch,
            self._metadata(state["sandboxLeaseId"], "indeterminate", evidence),
        )
        return {
            "sandboxLeaseId": state["sandboxLeaseId"],
            "status": "indeterminate",
            "reason": reason,
            "evidenceDigest": patch["reconciliationEvidenceDigest"],
        }

    def _list_labeled_ids(
        self, endpoint: str, object_kind: str, sandbox_lease_id: str | None
    ) -> list[str] | None:
        label = "capt.sandboxLeaseId" + (
            "=" + sandbox_lease_id if sandbox_lease_id is not None else ""
        )
        if object_kind == "container":
            args = (
                "container", "ls", "--all", "--quiet", "--no-trunc",
                "--filter", "label=" + label,
            )
        elif object_kind == "network":
            args = (
                "network", "ls", "--quiet", "--no-trunc", "--filter", "label=" + label,
            )
        else:
            raise ValueError(object_kind)
        result = self.backend.docker_backend._run_endpoint(
            endpoint,
            args,
            timeout_seconds=5.0,
            stdout_limit_bytes=256 * 1024,
            stderr_limit_bytes=16 * 1024,
        )
        if result.exit_code != 0 or result.timed_out:
            return None
        ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if any(not _FULL_ID.fullmatch(value) for value in ids):
            return None
        return sorted(set(ids))

    def _inventory_for_lease(self, lease: dict[str, Any]) -> dict[str, Any]:
        endpoint = lease["dockerEndpoint"]
        try:
            containers = self._list_labeled_ids(
                endpoint, "container", lease["sandboxLeaseId"]
            )
            networks = self._list_labeled_ids(endpoint, "network", lease["sandboxLeaseId"])
        except Exception as exc:  # noqa: BLE001 - observation failure must become fail-closed evidence
            return {
                "available": False,
                "containers": [],
                "networks": [],
                "reason": f"{type(exc).__name__}: {exc}"[:1024],
            }
        if containers is None or networks is None:
            return {
                "available": False,
                "containers": containers or [],
                "networks": networks or [],
                "reason": "Docker labeled inventory could not be proven",
            }
        return {"available": True, "containers": containers, "networks": networks}

    def _recover_reserved_candidate(
        self, state: dict[str, Any], inventory: dict[str, Any]
    ) -> dict[str, Any] | None:
        if len(inventory["containers"]) != 1 or inventory["networks"]:
            return None
        profile = self.backend.profiles.require(state["profileId"])
        # Same label set is intentionally shared across workload/guardian/network.
        # Without role labels, allowlist discovery is ambiguous in R2.
        if profile.network_policy.mode == "allowlist":
            return None
        if profile.profile_digest() != state["profileDigest"]:
            raise AuthorityViolation("reserved recovery profile digest drifted")
        if self.backend._daemon_identity_digest(state["dockerEndpoint"]) != state["daemonIdentityDigest"]:
            raise AuthorityViolation("reserved recovery daemon identity drifted")
        container_id = inventory["containers"][0]
        record = self.backend.docker_backend._inspect_exact(state["dockerEndpoint"], container_id)
        container_state = record.get("State") or {}
        if container_state.get("Status") != "created" or container_state.get("Running") is True:
            return None
        if record.get("Image") != state["imageId"]:
            raise AuthorityViolation("reserved recovery image identity drifted")
        prepared = DockerPreparedTarget(
            self.backend.docker_profiles.require(profile.profile_id),
            state["dockerEndpoint"],
            state["imageId"],
            None,
        )
        expected_labels = self.backend.persistent_labels(
            state["sandboxLeaseId"], profile, InversionSandboxPreparedTarget(profile, prepared)
        )
        labels = (record.get("Config") or {}).get("Labels") or {}
        if not isinstance(labels, dict) or any(labels.get(k) != v for k, v in expected_labels.items()):
            raise AuthorityViolation("reserved recovery workload labels drifted")
        attestation = attest_created_container(profile, prepared, record)
        identity = SandboxRuntimeIdentity(
            sandbox_lease_id=state["sandboxLeaseId"],
            profile_id=profile.profile_id,
            profile_digest=state["profileDigest"],
            context_endpoint=state["dockerEndpoint"],
            daemon_identity_digest=state["daemonIdentityDigest"],
            workload_container_id=container_id,
            workload_image_id=state["imageId"],
            security_profile_digest=state["securityProfileDigest"],
            network_policy_digest=state["networkPolicyDigest"],
            filesystem_scope_digest=state["filesystemScopeDigest"],
            persistent_entrypoint_digest=state["persistentEntrypointDigest"],
            creation_attestation_digest="sha256:" + attestation.digest,
        )
        if identity.security_profile_digest != "sha256:" + attestation.security_profile_digest:
            raise AuthorityViolation("reserved recovery security digest drifted")
        if identity.network_policy_digest != "sha256:" + attestation.network_policy_digest:
            raise AuthorityViolation("reserved recovery network digest drifted")
        if identity.filesystem_scope_digest != "sha256:" + attestation.filesystem_scope_digest:
            raise AuthorityViolation("reserved recovery filesystem digest drifted")
        return {
            "containerId": container_id,
            "creationAttestationDigest": identity.creation_attestation_digest,
            "sideEffectIdentity": identity.digest(),
            "lastReconciledAt": self._now(),
            "reconciliationReason": "reserved_create_identity_rediscovered",
            "reconciliationEvidenceDigest": digest(
                {"inventory": inventory, "attestationDigest": identity.creation_attestation_digest}
            ),
        }

    def _identity_absent(self, identity: SandboxRuntimeIdentity) -> bool:
        try:
            if self.backend._daemon_identity_digest(identity.context_endpoint) != identity.daemon_identity_digest:
                return False
            if not self.backend._container_absent(
                identity.context_endpoint, identity.workload_container_id
            ):
                return False
            if identity.guardian_container_id is not None and not self.backend._container_absent(
                identity.context_endpoint, identity.guardian_container_id
            ):
                return False
            if identity.internal_network_id is not None and not self.backend._network_absent(
                identity.context_endpoint, identity.internal_network_id
            ):
                return False
        except Exception:  # noqa: BLE001 - inability to prove exact absence is false
            return False
        return True

    def reconcile_one(self, sandbox_lease_id: str) -> dict[str, Any]:
        stream = SandboxLeaseAggregate.stream_id(sandbox_lease_id)
        state = self.store.load_state(stream)
        if state is None:
            raise AuthorityViolation("SANDBOX_LEASE_NOT_FOUND")
        require("SandboxLease", state)
        if state["state"] == "closed":
            return {"sandboxLeaseId": sandbox_lease_id, "status": "closed"}

        if state["state"] == "reserved":
            inventory = self._inventory_for_lease(state)
            if not inventory.get("available"):
                return {
                    "sandboxLeaseId": sandbox_lease_id,
                    "status": "unproven",
                    "reason": str(inventory.get("reason") or "Docker unavailable")[:1024],
                }
            if not inventory["containers"] and not inventory["networks"]:
                receipt = digest(
                    {"sandboxLeaseId": sandbox_lease_id, "outcome": "create_failed_no_effect", "inventory": inventory}
                )
                self.runtime.record_sandbox_closed(
                    sandbox_lease_id,
                    {
                        "closeReason": "create_failed_no_effect",
                        "closedAt": self._now(),
                        "closureReceiptDigest": receipt,
                        "lastReconciledAt": self._now(),
                        "reconciliationReason": "reserved_create_no_effect_proven",
                        "reconciliationEvidenceDigest": digest(inventory),
                    },
                    self._metadata(sandbox_lease_id, "reserved-no-effect", inventory),
                )
                return {"sandboxLeaseId": sandbox_lease_id, "status": "closed_no_effect"}
            try:
                recovered = self._recover_reserved_candidate(state, inventory)
            except Exception as exc:  # noqa: BLE001 - mismatch/control failure quarantines lease
                return self._mark_indeterminate(
                    state,
                    "reserved_create_identity_mismatch",
                    {"inventory": inventory, "error": f"{type(exc).__name__}: {exc}"},
                )
            if recovered is None:
                return self._mark_indeterminate(
                    state, "reserved_create_identity_ambiguous", inventory
                )
            self.runtime.recover_reserved_sandbox_created(
                sandbox_lease_id,
                recovered,
                self._metadata(sandbox_lease_id, "recover-created", recovered),
            )
            return {"sandboxLeaseId": sandbox_lease_id, "status": "recovered_created"}

        identity = self._identity_from_state(state)
        if identity is None:
            return self._mark_indeterminate(
                state, "sandbox_runtime_identity_incomplete", {"state": state["state"]}
            )

        if state["state"] == "closing":
            if self._identity_absent(identity):
                evidence = {"identityDigest": identity.digest(), "exactAbsence": True}
                self.runtime.record_sandbox_closed(
                    sandbox_lease_id,
                    {
                        "closedAt": self._now(),
                        "closureReceiptDigest": digest(evidence),
                        "lastReconciledAt": self._now(),
                        "reconciliationReason": "close_absence_proven",
                        "reconciliationEvidenceDigest": digest(evidence),
                    },
                    self._metadata(sandbox_lease_id, "closing-absent", evidence),
                )
                return {"sandboxLeaseId": sandbox_lease_id, "status": "closed"}
            try:
                observation = self.backend.inspect_persistent(identity)
            except Exception as exc:  # noqa: BLE001 - mismatch/control failure quarantines lease
                return self._mark_indeterminate(
                    state,
                    "closing_identity_unproven",
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
            return {
                "sandboxLeaseId": sandbox_lease_id,
                "status": "cleanup_required",
                "evidenceDigest": digest(observation),
            }

        if state["state"] == "indeterminate" and state.get("reconciliationReason") == "exec_termination_unknown":
            try:
                observation = self.backend.inspect_persistent(identity)
                evidence_digest = digest(observation)
            except Exception as exc:  # noqa: BLE001 - preserve unknown exec termination as evidence
                evidence_digest = digest({"error": f"{type(exc).__name__}: {exc}"})
            return {
                "sandboxLeaseId": sandbox_lease_id,
                "status": "close_required",
                "reason": "exec_termination_unknown",
                "evidenceDigest": evidence_digest,
            }

        if self._now() >= state["expiresAt"]:
            if state["state"] == "indeterminate":
                return {
                    "sandboxLeaseId": sandbox_lease_id,
                    "status": "cleanup_required",
                    "reason": state.get("reconciliationReason") or "lease_expired_cleanup_required",
                }
            result = self._mark_indeterminate(
                state,
                "lease_expired_cleanup_required",
                {"expiresAt": state["expiresAt"], "observedAt": self._now()},
            )
            result["status"] = "cleanup_required"
            return result

        try:
            observation = self.backend.inspect_persistent(identity)
        except Exception as exc:  # noqa: BLE001 - observation failure quarantines lease
            return self._mark_indeterminate(
                state,
                "sandbox_identity_observation_failed",
                {"error": f"{type(exc).__name__}: {exc}"},
            )

        if state["state"] == "created":
            if observation.get("workloadRunning") is True:
                patch = {
                    "lastReconciledAt": self._now(),
                    "reconciliationReason": "keeper_running_recovered",
                    "reconciliationEvidenceDigest": digest(observation),
                }
                self.runtime.record_sandbox_running(
                    sandbox_lease_id,
                    patch,
                    self._metadata(sandbox_lease_id, "created-running", observation),
                )
                return {"sandboxLeaseId": sandbox_lease_id, "status": "recovered_running"}
            if observation.get("workloadState") == "created":
                return {
                    "sandboxLeaseId": sandbox_lease_id,
                    "status": "verified_created",
                    "evidenceDigest": digest(observation),
                }
            return self._mark_indeterminate(
                state, "created_resource_state_unexpected", observation
            )

        if state["state"] == "running":
            if observation.get("workloadRunning") is True:
                return {
                    "sandboxLeaseId": sandbox_lease_id,
                    "status": "verified_running",
                    "evidenceDigest": digest(observation),
                }
            return self._mark_indeterminate(
                state, "running_keeper_not_proven", observation
            )

        if state["state"] == "indeterminate":
            if observation.get("workloadRunning") is True:
                patch = {
                    "lastReconciledAt": self._now(),
                    "reconciliationReason": "resource_identity_reverified",
                    "reconciliationEvidenceDigest": digest(observation),
                }
                self.runtime.reconcile_sandbox_lease(
                    sandbox_lease_id,
                    "running",
                    patch,
                    self._metadata(sandbox_lease_id, "indeterminate-running", observation),
                )
                return {"sandboxLeaseId": sandbox_lease_id, "status": "reconciled_running"}
            return {
                "sandboxLeaseId": sandbox_lease_id,
                "status": "close_required",
                "evidenceDigest": digest(observation),
            }

        return self._mark_indeterminate(
            state, "unsupported_sandbox_reconciliation_state", {"state": state["state"]}
        )

    def reconcile_all(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for stream_id, kind, _version in self.store.all_aggregates():
            if kind != SandboxLeaseAggregate.KIND:
                continue
            state = self.store.load_state(stream_id)
            if not state or state.get("state") == "closed":
                continue
            try:
                results.append(self.reconcile_one(state["sandboxLeaseId"]))
            except Exception as exc:  # noqa: BLE001 - one bad lease must not block startup reconciliation
                results.append(
                    {
                        "sandboxLeaseId": state.get("sandboxLeaseId"),
                        "status": "unproven",
                        "reason": f"{type(exc).__name__}: {exc}"[:1024],
                    }
                )
        results.extend(self.report_orphans())
        return results

    def _inventory_all_labeled(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for profile in self.backend.profiles.values():
            try:
                endpoint = docker_context_endpoint(profile.context_name)
            except Exception:  # noqa: BLE001,S112 - unavailable profile is skipped during read-only orphan inventory
                continue
            for object_kind in ("container", "network"):
                try:
                    ids = self._list_labeled_ids(endpoint, object_kind, None)
                except Exception:  # noqa: BLE001,S112 - unavailable inventory source is non-authoritative
                    continue
                if ids is None:
                    continue
                for object_id in ids:
                    key = (object_kind, object_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        if object_kind == "container":
                            inspected = self.backend.docker_backend._inspect_exact(
                                endpoint, object_id
                            )
                        else:
                            result = self.backend.docker_backend._run_endpoint(
                                endpoint,
                                ("network", "inspect", object_id),
                                timeout_seconds=5.0,
                                stdout_limit_bytes=4 * 1024 * 1024,
                                stderr_limit_bytes=16 * 1024,
                            )
                            if result.exit_code != 0 or result.timed_out:
                                continue
                            inspected = json.loads(result.stdout)[0]
                    except Exception:  # noqa: BLE001,S112 - malformed/unavailable orphan observation is ignored
                        continue
                    labels = (
                        (inspected.get("Config") or {}).get("Labels")
                        if object_kind == "container"
                        else inspected.get("Labels")
                    ) or {}
                    lease_id = labels.get("capt.sandboxLeaseId") if isinstance(labels, dict) else None
                    if isinstance(lease_id, str) and lease_id:
                        records.append(
                            {
                                "objectKind": object_kind,
                                "objectId": object_id,
                                "sandboxLeaseId": lease_id,
                            }
                        )
        return records

    def report_orphans(self) -> list[dict[str, Any]]:
        known: set[str] = set()
        for stream_id, kind, _version in self.store.all_aggregates():
            if kind != SandboxLeaseAggregate.KIND:
                continue
            state = self.store.load_state(stream_id)
            if state and isinstance(state.get("sandboxLeaseId"), str):
                known.add(state["sandboxLeaseId"])
        orphans = []
        for item in self._inventory_all_labeled():
            if item.get("sandboxLeaseId") in known:
                continue
            record = {
                "status": "orphan",
                "objectKind": str(item.get("objectKind"))[:64],
                "objectId": str(item.get("objectId"))[:128],
                "sandboxLeaseId": str(item.get("sandboxLeaseId"))[:128],
            }
            orphans.append(record)
        return sorted(
            orphans,
            key=lambda item: (item["sandboxLeaseId"], item["objectKind"], item["objectId"]),
        )
