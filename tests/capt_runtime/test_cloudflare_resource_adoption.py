from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from capt_runtime import commands
from capt_runtime.cloudflare_resource_adoption import (
    CloudflareResourceAdoptionProposal,
    CloudflareResourceBindingRegistry,
)
from capt_runtime.errors import AuthorityViolation
from capt_runtime.governed_service import GovernedRuntimeService
from capt_runtime.replay import full_replay
from capt_runtime.store import EventStore
from capt_runtime.tools.backends.cloudflare_resource_inventory import (
    CloudflareResourceKind,
    parse_cloudflare_resource_inventory,
)

CREATED = "2026-09-09T05:20:00Z"
APPROVED = "2026-09-09T05:20:01Z"
BOUND = "2026-09-09T05:20:02Z"
EXPIRES = "2026-09-09T05:30:00Z"


def meta(command_id: str, actor_kind: str, *, issued_at: str = CREATED):
    return commands.command(
        command_id=command_id,
        idempotency_key=command_id + "-idem",
        operation_fingerprint="sha256:" + "f" * 64,
        correlation_id="corr-cloudflare-adoption",
        actor_id="operator-1" if actor_kind == "human" else "exec-1",
        actor_kind=actor_kind,
        issued_at=issued_at,
    )


def inventory():
    return parse_cloudflare_resource_inventory(
        account_id="acct-1",
        d1_rows=[{"uuid": "db-1", "name": "capt-state"}],
        queue_rows=[{"queue_id": "q-1", "queue_name": "capt-delegates"}],
        worker_rows=[],
        fetched_at=datetime(2026, 9, 9, 5, 19, tzinfo=timezone.utc),
    )


def proposal():
    return CloudflareResourceAdoptionProposal.from_inventory(
        inventory(),
        proposal_id="cf-adopt-1",
        mission_id="m-1",
        task_id="t-1",
        kind=CloudflareResourceKind.D1_DATABASE,
        resource_id="db-1",
        resource_name="capt-state",
        target_alias="capt-state",
        created_at=CREATED,
    )


def request_and_approve(svc: GovernedRuntimeService, prop: CloudflareResourceAdoptionProposal):
    request = prop.human_approval_request(
        request_id="cf-adopt-approval-1",
        requested_by={"actorId": "exec-1", "kind": "execution_plane"},
        expires_at=EXPIRES,
        correlation_id="corr-cloudflare-adoption",
    )
    svc.request_human_approval(request, meta("cf-adopt-request-1", "execution_plane"))
    svc.submit_human_approval_decision(
        {
            "schemaVersion": "1.0.0",
            "requestId": "cf-adopt-approval-1",
            "decision": "approve",
            "operatorId": "operator-1",
            "decidedAt": APPROVED,
            "note": None,
            "idempotencyKey": "cf-adopt-decision-1",
            "correlationId": "corr-cloudflare-adoption",
            "sessionId": "sess-1",
        },
        meta("cf-adopt-decision-1", "human", issued_at=APPROVED),
        now=APPROVED,
    )
    return request


def test_proposal_is_exactly_bound_to_inventory_identity():
    prop = proposal()
    assert prop.inventory_digest == inventory().source_digest
    assert prop.proposal_digest.startswith("sha256:")
    request = prop.human_approval_request(
        request_id="cf-adopt-approval-1",
        requested_by={"actorId": "exec-1", "kind": "execution_plane"},
        expires_at=EXPIRES,
        correlation_id="corr-cloudflare-adoption",
    )
    binding = request["scope"]["adoptionBinding"]
    assert request["remainingUses"] == 1
    assert request["operation"] == "CloudflareResourceAdoption"
    assert binding["proposalDigest"] == prop.proposal_digest
    assert binding["inventoryDigest"] == inventory().source_digest
    assert binding["resourceId"] == "db-1"


def test_bind_requires_approved_one_use_exact_scope_and_is_atomic(tmp_path):
    store = EventStore(str(tmp_path / "ledger.db"))
    svc = GovernedRuntimeService(store)
    prop = proposal()

    with pytest.raises(
        AuthorityViolation, match="CLOUDFLARE_RESOURCE_ADOPTION_NOT_APPROVED"
    ):
        svc.bind_cloudflare_resource_adoption(
            prop,
            request_id="cf-adopt-approval-1",
            binding_id="cf-binding-1",
            use_id="cf-adopt-use-1",
            now=BOUND,
            metadata=meta("cf-adopt-bind-0", "execution_plane", issued_at=BOUND),
        )

    request_and_approve(svc, prop)
    result = svc.bind_cloudflare_resource_adoption(
        prop,
        request_id="cf-adopt-approval-1",
        binding_id="cf-binding-1",
        use_id="cf-adopt-use-1",
        now=BOUND,
        metadata=meta("cf-adopt-bind-1", "execution_plane", issued_at=BOUND),
    )
    binding = result["binding"]
    assert binding["resourceId"] == "db-1"
    assert binding["inventoryDigest"] == prop.inventory_digest
    assert binding["proposalDigest"] == prop.proposal_digest
    assert binding["approvalRequestId"] == "cf-adopt-approval-1"
    assert binding["approvedBy"] == "operator-1"
    assert store.require_state("human_approval-cf-adopt-approval-1")["state"] == "consumed"
    assert store.require_state("cloudflare_resource_binding-cf-binding-1") == binding
    store.close()


def test_binding_survives_restart_and_digest_mismatch_does_not_consume(tmp_path):
    db = str(tmp_path / "ledger.db")
    store = EventStore(db)
    svc = GovernedRuntimeService(store)
    prop = proposal()
    request_and_approve(svc, prop)

    bad = replace(
        prop,
        target_alias="other-alias",
        proposal_digest="sha256:" + "e" * 64,
    )
    with pytest.raises(
        AuthorityViolation,
        match="CLOUDFLARE_RESOURCE_ADOPTION_PROPOSAL_DIGEST_MISMATCH",
    ):
        svc.bind_cloudflare_resource_adoption(
            bad,
            request_id="cf-adopt-approval-1",
            binding_id="cf-binding-bad",
            use_id="cf-adopt-use-bad",
            now=BOUND,
            metadata=meta("cf-adopt-bind-bad", "execution_plane", issued_at=BOUND),
        )
    assert store.require_state("human_approval-cf-adopt-approval-1")["state"] == "approved"
    assert store.load_state("cloudflare_resource_binding-cf-binding-bad") is None

    result = svc.bind_cloudflare_resource_adoption(
        prop,
        request_id="cf-adopt-approval-1",
        binding_id="cf-binding-1",
        use_id="cf-adopt-use-1",
        now=BOUND,
        metadata=meta("cf-adopt-bind-1", "execution_plane", issued_at=BOUND),
    )
    expected = result["binding"]
    store.close()

    store = EventStore(db)
    assert store.require_state("cloudflare_resource_binding-cf-binding-1") == expected
    assert store.require_state("human_approval-cf-adopt-approval-1")["state"] == "consumed"
    store.close()


def test_full_replay_reconstructs_consumed_approval_and_binding(tmp_path):
    store = EventStore(str(tmp_path / "ledger.db"))
    svc = GovernedRuntimeService(store)
    prop = proposal()
    request_and_approve(svc, prop)
    result = svc.bind_cloudflare_resource_adoption(
        prop,
        request_id="cf-adopt-approval-1",
        binding_id="cf-binding-replay",
        use_id="cf-adopt-use-replay",
        now=BOUND,
        metadata=meta("cf-adopt-bind-replay", "execution_plane", issued_at=BOUND),
    )
    replayed = full_replay(store)
    assert replayed.aggregates["human_approval-cf-adopt-approval-1"]["state"] == "consumed"
    assert replayed.aggregates["cloudflare_resource_binding-cf-binding-replay"] == result["binding"]
    store.close()


def test_binding_registry_resolves_only_durable_active_adoption(tmp_path):
    store = EventStore(str(tmp_path / "ledger.db"))
    registry = CloudflareResourceBindingRegistry(store)
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_RESOURCE_BINDING_NOT_FOUND"):
        registry.resolve("acct-1", CloudflareResourceKind.D1_DATABASE, "capt-state")

    svc = GovernedRuntimeService(store)
    prop = proposal()
    request_and_approve(svc, prop)
    result = svc.bind_cloudflare_resource_adoption(
        prop,
        request_id="cf-adopt-approval-1",
        binding_id="cf-binding-registry",
        use_id="cf-adopt-use-registry",
        now=BOUND,
        metadata=meta("cf-adopt-bind-registry", "execution_plane", issued_at=BOUND),
    )
    resolved = registry.resolve("acct-1", CloudflareResourceKind.D1_DATABASE, "capt-state")
    assert resolved == result["binding"]
    store.close()


def test_worker_adoption_binds_exact_endpoint():
    inv = parse_cloudflare_resource_inventory(
        account_id="acct-1",
        d1_rows=[], queue_rows=[],
        worker_rows=[{"id": "capt-control"}],
        fetched_at=datetime(2026, 9, 9, 5, 19, tzinfo=timezone.utc),
    )
    prop = CloudflareResourceAdoptionProposal.from_inventory(
        inv, proposal_id="cf-worker-adopt-1", mission_id="m-1", task_id="t-1",
        kind=CloudflareResourceKind.WORKER_SCRIPT, resource_id="capt-control",
        resource_name="capt-control", target_alias="capt-control", created_at=CREATED,
        target_endpoint="https://capt-control.example.workers.dev",
    )
    request = prop.human_approval_request(
        request_id="cf-worker-approval-1", requested_by={"actorId": "exec-1", "kind": "execution_plane"},
        expires_at=EXPIRES, correlation_id="corr-cloudflare-adoption",
    )
    assert request["scope"]["adoptionBinding"]["targetEndpoint"] == "https://capt-control.example.workers.dev"


def test_non_worker_adoption_rejects_target_endpoint():
    with pytest.raises(ValueError, match="cloudflare_resource_target_endpoint_not_applicable"):
        CloudflareResourceAdoptionProposal.from_inventory(
            inventory(), proposal_id="cf-bad-endpoint", mission_id="m-1", task_id="t-1",
            kind=CloudflareResourceKind.D1_DATABASE, resource_id="db-1", resource_name="capt-state",
            target_alias="capt-state", created_at=CREATED, target_endpoint="https://example.com",
        )
