"""Durable provenance-bound Cloudflare resource bindings."""
from __future__ import annotations

from typing import Any, Dict, Mapping

from ..errors import AuthorityViolation


class CloudflareResourceBindingAggregate(object):
    KIND = "cloudflare_resource_binding"
    OWNED_FIELDS = frozenset(
        {
            "cloudflare_resource_binding.resourceKind",
            "cloudflare_resource_binding.resourceId",
            "cloudflare_resource_binding.resourceName",
            "cloudflare_resource_binding.targetAlias",
            "cloudflare_resource_binding.inventoryDigest",
            "cloudflare_resource_binding.proposalDigest",
            "cloudflare_resource_binding.approvalRequestId",
            "cloudflare_resource_binding.state",
        }
    )
    REFERENCE_FIELDS = frozenset({"bindingId", "proposalId", "accountId"})

    @staticmethod
    def stream_id(binding_id: str) -> str:
        if not binding_id:
            raise ValueError("CLOUDFLARE_RESOURCE_BINDING_ID_REQUIRED")
        return "cloudflare_resource_binding-" + binding_id

    @staticmethod
    def create(binding: Mapping[str, Any]) -> Dict[str, Any]:
        if binding.get("state") != "active":
            raise AuthorityViolation("CLOUDFLARE_RESOURCE_BINDING_MUST_START_ACTIVE")
        if binding.get("adopted") is False:
            raise AuthorityViolation("CLOUDFLARE_RESOURCE_BINDING_CANNOT_BE_UNADOPTED")
        return dict(binding)
