from __future__ import annotations

from datetime import datetime, timezone

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.cloudflare_resource_inventory import (
    CloudflareResourceKind,
    parse_cloudflare_resource_inventory,
)

NOW = datetime(2026, 9, 9, 5, 10, tzinfo=timezone.utc)


def _snapshot():
    return parse_cloudflare_resource_inventory(
        account_id="acct-1",
        d1_rows=[
            {"uuid": "db-1", "name": "capt-state"},
            {"uuid": "db-2", "name": "capt-archive"},
        ],
        queue_rows=[{"queue_id": "q-1", "queue_name": "capt-delegates"}],
        worker_rows=[{"id": "capt-control"}],
        fetched_at=NOW,
    )


def test_inventory_binds_typed_identities_and_digest():
    snapshot = _snapshot()
    assert snapshot.account_id == "acct-1"
    assert snapshot.fetched_at == NOW
    assert snapshot.source_digest.startswith("sha256:")
    assert {n.resource_id for n in snapshot.resources} == {"db-1", "db-2", "q-1", "capt-control"}
    assert snapshot.require_exact(
        CloudflareResourceKind.D1_DATABASE, "db-1", "capt-state"
    ).name == "capt-state"


def test_inventory_name_lookup_is_discovery_not_authority():
    snapshot = _snapshot()
    result = snapshot.candidates_by_name(
        CloudflareResourceKind.D1_DATABASE, "capt-state"
    )
    assert len(result) == 1
    assert result[0].adoption_authority == "human_required"
    assert result[0].adopted is False


def test_inventory_rejects_ambiguous_name_or_id_mismatch():
    snapshot = parse_cloudflare_resource_inventory(
        account_id="acct-1",
        d1_rows=[
            {"uuid": "db-1", "name": "dup"},
            {"uuid": "db-2", "name": "dup"},
        ],
        queue_rows=[],
        worker_rows=[],
        fetched_at=NOW,
    )
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_RESOURCE_NAME_AMBIGUOUS"):
        snapshot.require_unique_name(CloudflareResourceKind.D1_DATABASE, "dup")
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_RESOURCE_ID_NAME_MISMATCH"):
        snapshot.require_exact(CloudflareResourceKind.D1_DATABASE, "db-1", "wrong")


def test_inventory_rejects_duplicate_typed_identity():
    with pytest.raises(ValueError, match="cloudflare_resource_identity_duplicate"):
        parse_cloudflare_resource_inventory(
            account_id="acct-1",
            d1_rows=[{"uuid": "x", "name": "a"}, {"uuid": "x", "name": "b"}],
            queue_rows=[],
            worker_rows=[],
            fetched_at=NOW,
        )
