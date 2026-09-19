from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.cloudflare_ai_catalog import (
    CloudflareAIModelCatalogSnapshot,
    parse_cloudflare_ai_model_catalog,
)

NOW = datetime(2026, 9, 9, 4, 15, tzinfo=timezone.utc)


def _rows():
    return [
        {
            "name": "@cf/meta/llama-3.1-8b-instruct",
            "properties": [
                {"property_id": "context_window", "value": "32000"},
            ],
        },
        {
            "name": "@cf/zai-org/glm-5.3-flash",
            "properties": [
                {"property_id": "require_workers_paid", "value": "true"},
            ],
        },
    ]


def test_catalog_snapshot_binds_provider_metadata_and_digest():
    snapshot = parse_cloudflare_ai_model_catalog(_rows(), fetched_at=NOW)
    assert snapshot.source == "cloudflare_ai_models_search"
    assert snapshot.catalog_models == frozenset(
        {"@cf/meta/llama-3.1-8b-instruct", "@cf/zai-org/glm-5.3-flash"}
    )
    assert snapshot.paid_required_models == frozenset({"@cf/zai-org/glm-5.3-flash"})
    assert snapshot.source_digest.startswith("sha256:")


def test_fresh_catalog_allows_unmarked_model_and_blocks_paid_required_model():
    snapshot = parse_cloudflare_ai_model_catalog(_rows(), fetched_at=NOW)
    snapshot.require_free("@cf/meta/llama-3.1-8b-instruct", at=NOW + timedelta(minutes=1))
    with pytest.raises(
        AuthorityViolation, match="CLOUDFLARE_AI_MODEL_REQUIRES_PAID_AUTHORITY"
    ):
        snapshot.require_free("@cf/zai-org/glm-5.3-flash", at=NOW + timedelta(minutes=1))


def test_catalog_fails_closed_when_stale_or_model_missing():
    snapshot = parse_cloudflare_ai_model_catalog(_rows(), fetched_at=NOW)
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_AI_MODEL_CATALOG_STALE"):
        snapshot.require_free(
            "@cf/meta/llama-3.1-8b-instruct",
            at=NOW + timedelta(minutes=16),
        )
    with pytest.raises(
        AuthorityViolation, match="CLOUDFLARE_AI_MODEL_BILLING_STATUS_UNKNOWN"
    ):
        snapshot.require_free("@cf/unknown/model", at=NOW + timedelta(minutes=1))


def test_catalog_rejects_ambiguous_paid_metadata():
    rows = [
        {
            "name": "@cf/example/model",
            "properties": [
                {"property_id": "require_workers_paid", "value": "sometimes"},
            ],
        }
    ]
    with pytest.raises(ValueError, match="cloudflare_ai_catalog_paid_metadata_invalid"):
        parse_cloudflare_ai_model_catalog(rows, fetched_at=NOW)


def test_snapshot_requires_timezone_aware_provider_timestamp():
    with pytest.raises(ValueError, match="cloudflare_ai_catalog_timestamp_unaware"):
        CloudflareAIModelCatalogSnapshot(
            fetched_at=datetime(2026, 9, 9, 4, 15),
            source_digest="sha256:" + "0" * 64,
            catalog_models=frozenset({"@cf/example/model"}),
            paid_required_models=frozenset(),
        )
