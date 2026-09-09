"""Read-only Cloudflare resource discovery with provenance-bound identity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from capt_runtime.errors import AuthorityViolation


class CloudflareResourceKind(str, Enum):
    D1_DATABASE = "d1_database"
    QUEUE = "queue"
    WORKER_SCRIPT = "worker_script"


@dataclass(frozen=True, order=True)
class CloudflareResourceCandidate:
    kind: CloudflareResourceKind
    resource_id: str
    name: str
    adoption_authority: str = "human_required"
    adopted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CloudflareResourceKind):
            raise ValueError("cloudflare_resource_kind_invalid")
        if not isinstance(self.resource_id, str) or not self.resource_id:
            raise ValueError("cloudflare_resource_id_invalid")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("cloudflare_resource_name_invalid")
        if self.adoption_authority != "human_required" or self.adopted:
            raise ValueError("cloudflare_discovery_candidate_cannot_confer_authority")


@dataclass(frozen=True)
class CloudflareResourceInventorySnapshot:
    account_id: str
    fetched_at: datetime
    source_digest: str
    resources: tuple[CloudflareResourceCandidate, ...]
    source: str = "cloudflare_account_resource_inventory"

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("cloudflare_resource_inventory_account_id_invalid")
        if self.fetched_at.tzinfo is None or self.fetched_at.utcoffset() is None:
            raise ValueError("cloudflare_resource_inventory_timestamp_unaware")
        if not self.source_digest.startswith("sha256:") or len(self.source_digest) != 71:
            raise ValueError("cloudflare_resource_inventory_digest_invalid")

    def candidates_by_name(self, kind: CloudflareResourceKind, name: str) -> tuple[CloudflareResourceCandidate, ...]:
        return tuple(r for r in self.resources if r.kind is kind and r.name == name)

    def require_unique_name(self, kind: CloudflareResourceKind, name: str) -> CloudflareResourceCandidate:
        matches = self.candidates_by_name(kind, name)
        if not matches:
            raise AuthorityViolation("CLOUDFLARE_RESOURCE_NAME_NOT_DISCOVERED")
        if len(matches) != 1:
            raise AuthorityViolation("CLOUDFLARE_RESOURCE_NAME_AMBIGUOUS")
        return matches[0]

    def require_exact(self, kind: CloudflareResourceKind, resource_id: str, name: str) -> CloudflareResourceCandidate:
        matches = [r for r in self.resources if r.kind is kind and r.resource_id == resource_id]
        if not matches:
            raise AuthorityViolation("CLOUDFLARE_RESOURCE_ID_NOT_DISCOVERED")
        resource = matches[0]
        if resource.name != name:
            raise AuthorityViolation("CLOUDFLARE_RESOURCE_ID_NAME_MISMATCH")
        return resource


def _require_rows(value: Any, code: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(code)
    if not all(isinstance(row, dict) for row in value):
        raise ValueError(code)
    return value


def parse_cloudflare_resource_inventory(
    *,
    account_id: str,
    d1_rows: Any,
    queue_rows: Any,
    worker_rows: Any,
    fetched_at: datetime,
) -> CloudflareResourceInventorySnapshot:
    resources: list[CloudflareResourceCandidate] = []
    for row in _require_rows(d1_rows, "cloudflare_d1_inventory_invalid"):
        resources.append(CloudflareResourceCandidate(CloudflareResourceKind.D1_DATABASE, row.get("uuid"), row.get("name")))
    for row in _require_rows(queue_rows, "cloudflare_queue_inventory_invalid"):
        resources.append(CloudflareResourceCandidate(CloudflareResourceKind.QUEUE, row.get("queue_id"), row.get("queue_name")))
    for row in _require_rows(worker_rows, "cloudflare_worker_inventory_invalid"):
        resources.append(CloudflareResourceCandidate(CloudflareResourceKind.WORKER_SCRIPT, row.get("id"), row.get("id")))
    seen: set[tuple[str, str]] = set()
    for resource in resources:
        key = (resource.kind.value, resource.resource_id)
        if key in seen:
            raise ValueError("cloudflare_resource_identity_duplicate")
        seen.add(key)
    canonical = {
        "accountId": account_id,
        "resources": [asdict(r) for r in sorted(resources)],
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return CloudflareResourceInventorySnapshot(
        account_id=account_id,
        fetched_at=fetched_at,
        source_digest="sha256:" + hashlib.sha256(encoded).hexdigest(),
        resources=tuple(sorted(resources)),
    )
