"""Provider-metadata authority for Workers AI free-only admission."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from capt_runtime.errors import AuthorityViolation

CLOUDFLARE_AI_CATALOG_SOURCE = "cloudflare_ai_models_search"
CLOUDFLARE_AI_CATALOG_MAX_AGE_SECONDS = 15 * 60


@dataclass(frozen=True)
class CloudflareAIModelCatalogSnapshot:
    fetched_at: datetime
    source_digest: str
    catalog_models: frozenset[str]
    paid_required_models: frozenset[str]
    source: str = CLOUDFLARE_AI_CATALOG_SOURCE

    def __post_init__(self) -> None:
        if self.fetched_at.tzinfo is None or self.fetched_at.utcoffset() is None:
            raise ValueError("cloudflare_ai_catalog_timestamp_unaware")
        if not self.source_digest.startswith("sha256:") or len(self.source_digest) != 71:
            raise ValueError("cloudflare_ai_catalog_digest_invalid")
        if not self.catalog_models:
            raise ValueError("cloudflare_ai_catalog_empty")
        if not self.paid_required_models.issubset(self.catalog_models):
            raise ValueError("cloudflare_ai_catalog_paid_subset_invalid")
        if self.source != CLOUDFLARE_AI_CATALOG_SOURCE:
            raise ValueError("cloudflare_ai_catalog_source_invalid")

    def require_free(
        self,
        model: str,
        *,
        at: datetime,
        max_age_seconds: int = CLOUDFLARE_AI_CATALOG_MAX_AGE_SECONDS,
    ) -> None:
        if not isinstance(model, str) or not model:
            raise ValueError("cloudflare_ai_model_invalid")
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("cloudflare_ai_catalog_check_time_unaware")
        age = (at - self.fetched_at).total_seconds()
        if age < 0:
            raise AuthorityViolation("CLOUDFLARE_AI_MODEL_CATALOG_CLOCK_INCONSISTENT")
        if age > max_age_seconds:
            raise AuthorityViolation("CLOUDFLARE_AI_MODEL_CATALOG_STALE")
        if model not in self.catalog_models:
            raise AuthorityViolation("CLOUDFLARE_AI_MODEL_BILLING_STATUS_UNKNOWN")
        if model in self.paid_required_models:
            raise AuthorityViolation("CLOUDFLARE_AI_MODEL_REQUIRES_PAID_AUTHORITY")


def _paid_required(properties: Any) -> bool:
    if not isinstance(properties, list):
        raise ValueError("cloudflare_ai_catalog_properties_invalid")
    values: list[Any] = []
    for item in properties:
        if not isinstance(item, dict):
            raise ValueError("cloudflare_ai_catalog_property_invalid")
        if item.get("property_id") == "require_workers_paid":
            values.append(item.get("value"))
    if len(values) > 1:
        raise ValueError("cloudflare_ai_catalog_paid_metadata_duplicated")
    if not values:
        return False
    value = values[0]
    if value is True or value == "true":
        return True
    if value is False or value == "false":
        return False
    raise ValueError("cloudflare_ai_catalog_paid_metadata_invalid")


def parse_cloudflare_ai_model_catalog(
    rows: Any,
    *,
    fetched_at: datetime,
) -> CloudflareAIModelCatalogSnapshot:
    if not isinstance(rows, list) or not rows:
        raise ValueError("cloudflare_ai_catalog_result_invalid")
    names: set[str] = set()
    paid: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("cloudflare_ai_catalog_row_invalid")
        name = row.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("cloudflare_ai_catalog_model_name_invalid")
        if name in names:
            raise ValueError("cloudflare_ai_catalog_duplicate_model")
        names.add(name)
        if _paid_required(row.get("properties")):
            paid.add(name)
    encoded = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return CloudflareAIModelCatalogSnapshot(
        fetched_at=fetched_at,
        source_digest="sha256:" + hashlib.sha256(encoded).hexdigest(),
        catalog_models=frozenset(names),
        paid_required_models=frozenset(paid),
    )
