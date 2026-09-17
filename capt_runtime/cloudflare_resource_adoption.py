"""Cloudflare resource adoption proposals bound to provider discovery evidence."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

from .contracts import require
from .errors import AuthorityViolation, IntegrityViolation
from .tools.backends.cloudflare_resource_inventory import (
    CloudflareResourceInventorySnapshot,
    CloudflareResourceKind,
)

_ALIAS_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_OPERATION = "CloudflareResourceAdoption"
_CAPABILITY = "cloudflare.resource.adopt"


def _sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CloudflareResourceAdoptionProposal:
    proposal_id: str
    mission_id: str
    task_id: str
    account_id: str
    resource_kind: CloudflareResourceKind
    resource_id: str
    resource_name: str
    target_alias: str
    inventory_digest: str
    inventory_fetched_at: str
    created_at: str
    target_endpoint: str | None
    proposal_digest: str

    @classmethod
    def from_inventory(
        cls,
        inventory: CloudflareResourceInventorySnapshot,
        *,
        proposal_id: str,
        mission_id: str,
        task_id: str,
        kind: CloudflareResourceKind,
        resource_id: str,
        resource_name: str,
        target_alias: str,
        created_at: str,
        target_endpoint: str | None = None,
    ) -> "CloudflareResourceAdoptionProposal":
        inventory.require_exact(kind, resource_id, resource_name)
        if not _ALIAS_RE.fullmatch(target_alias):
            raise ValueError("cloudflare_resource_target_alias_invalid")
        if not proposal_id or not mission_id or not task_id:
            raise ValueError("cloudflare_resource_adoption_identity_required")
        if kind is CloudflareResourceKind.WORKER_SCRIPT:
            if not isinstance(target_endpoint, str) or not target_endpoint:
                raise ValueError("cloudflare_worker_target_endpoint_required")
            parsed = urlparse(target_endpoint)
            if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment or parsed.username or parsed.password:
                raise ValueError("cloudflare_worker_target_endpoint_invalid")
            target_endpoint = target_endpoint.rstrip("/")
        elif target_endpoint is not None:
            raise ValueError("cloudflare_resource_target_endpoint_not_applicable")
        base = {
            "proposalId": proposal_id,
            "missionId": mission_id,
            "taskId": task_id,
            "accountId": inventory.account_id,
            "resourceKind": kind.value,
            "resourceId": resource_id,
            "resourceName": resource_name,
            "targetAlias": target_alias,
            "inventoryDigest": inventory.source_digest,
            "inventoryFetchedAt": inventory.fetched_at.isoformat().replace("+00:00", "Z"),
            "createdAt": created_at,
            "targetEndpoint": target_endpoint,
        }
        return cls(
            proposal_id=proposal_id,
            mission_id=mission_id,
            task_id=task_id,
            account_id=inventory.account_id,
            resource_kind=kind,
            resource_id=resource_id,
            resource_name=resource_name,
            target_alias=target_alias,
            inventory_digest=inventory.source_digest,
            inventory_fetched_at=inventory.fetched_at.isoformat().replace("+00:00", "Z"),
            created_at=created_at,
            target_endpoint=target_endpoint,
            proposal_digest=_sha256(base),
        )

    def resource_uri(self) -> str:
        return (
            f"cloudflare://{self.account_id}/{self.resource_kind.value}/"
            f"{self.resource_id}"
        )

    def approval_binding(self) -> dict[str, str]:
        return {
            "proposalId": self.proposal_id,
            "proposalDigest": self.proposal_digest,
            "accountId": self.account_id,
            "resourceKind": self.resource_kind.value,
            "resourceId": self.resource_id,
            "resourceName": self.resource_name,
            "targetAlias": self.target_alias,
            "inventoryDigest": self.inventory_digest,
            "inventoryFetchedAt": self.inventory_fetched_at,
            "targetEndpoint": self.target_endpoint,
        }

    def human_approval_request(
        self,
        *,
        request_id: str,
        requested_by: Mapping[str, Any],
        expires_at: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        return {
            "schemaVersion": "1.0.0",
            "requestId": request_id,
            "missionId": self.mission_id,
            "taskId": self.task_id,
            "requestedCapability": _CAPABILITY,
            "resource": self.resource_uri(),
            "operation": _OPERATION,
            "scope": {"adoptionBinding": self.approval_binding()},
            "riskClassification": "consequential",
            "policyReason": (
                "Adopting an existing Cloudflare resource can enable future "
                "execution against that exact provider resource."
            ),
            "requestedBy": dict(requested_by),
            "expiresAt": expires_at,
            "remainingUses": 1,
            "correlationId": correlation_id,
            "createdAt": self.created_at,
        }



def _verify_binding_digest(binding: Mapping[str, Any]) -> None:
    require("CloudflareResourceBinding", dict(binding))
    material = dict(binding)
    offered = material.pop("bindingDigest")
    if _sha256(material) != offered:
        raise IntegrityViolation("CLOUDFLARE_RESOURCE_BINDING_DIGEST_MISMATCH")


class CloudflareResourceBindingRegistry:
    """Resolve only durable active Cloudflare bindings from CAPT EventStore state."""

    KIND = "cloudflare_resource_binding"

    def __init__(self, store: Any) -> None:
        self.store = store

    def resolve(
        self,
        account_id: str,
        kind: CloudflareResourceKind,
        target_alias: str,
    ) -> dict[str, Any]:
        if not isinstance(kind, CloudflareResourceKind):
            raise AuthorityViolation("CLOUDFLARE_RESOURCE_BINDING_KIND_INVALID")
        matches: list[dict[str, Any]] = []
        for stream_id, aggregate_kind, _version in self.store.all_aggregates():
            if aggregate_kind != self.KIND:
                continue
            state = self.store.load_state(stream_id)
            if not state or state.get("state") != "active":
                continue
            if state.get("accountId") != account_id:
                continue
            if state.get("resourceKind") != kind.value:
                continue
            if state.get("targetAlias") != target_alias:
                continue
            _verify_binding_digest(state)
            matches.append(dict(state))
        if not matches:
            raise AuthorityViolation("CLOUDFLARE_RESOURCE_BINDING_NOT_FOUND")
        if len(matches) != 1:
            raise IntegrityViolation("CLOUDFLARE_RESOURCE_BINDING_AMBIGUOUS")
        return matches[0]

def build_cloudflare_resource_binding(
    proposal: CloudflareResourceAdoptionProposal,
    *,
    binding_id: str,
    approval_request_id: str,
    approved_by: str,
    approved_at: str,
    bound_at: str,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "bindingId": binding_id,
        "proposalId": proposal.proposal_id,
        "accountId": proposal.account_id,
        "resourceKind": proposal.resource_kind.value,
        "resourceId": proposal.resource_id,
        "resourceName": proposal.resource_name,
        "targetAlias": proposal.target_alias,
        "inventoryDigest": proposal.inventory_digest,
        "inventoryFetchedAt": proposal.inventory_fetched_at,
        "proposalDigest": proposal.proposal_digest,
        "approvalRequestId": approval_request_id,
        "approvedBy": approved_by,
        "approvedAt": approved_at,
        "boundAt": bound_at,
        "targetEndpoint": proposal.target_endpoint,
        "state": "active",
    }
    base["bindingDigest"] = _sha256(base)
    return base
