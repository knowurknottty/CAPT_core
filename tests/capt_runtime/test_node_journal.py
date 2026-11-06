from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from capt_runtime.node.integrity import GenericStateViolation, OperationDigestMismatch
from capt_runtime.node.journal import NodeOperationJournal
from capt_runtime.node.types import (
    NodeOperationRequest,
    NodeOperationState,
    OperationCapability,
)

NOW = datetime(2026, 9, 8, 20, 0, tzinfo=timezone.utc)


def _request(operation_id: str = "op-1", argv: list[str] | None = None) -> NodeOperationRequest:
    cap = OperationCapability(
        capability_id="cap-1", bot_id="bot-1", mission_id="m-1", task_id="t-1",
        controller_id="controller-1", node_id="node-1",
        permitted_operations=frozenset({"shell.exec"}),
        filesystem_roots=("/tmp/capt",), issued_at=NOW, expires_at=NOW + timedelta(minutes=5),
    )
    return NodeOperationRequest(
        operation_id=operation_id, capability=cap, operation="shell.exec",
        arguments={"argv": argv or ["echo", "hi"], "cwd": "/tmp/capt"}, issued_at=NOW,
    )


def test_prepare_is_idempotent_for_same_operation_and_digest(tmp_path):
    journal = NodeOperationJournal(tmp_path / "node.sqlite")
    first = journal.prepare(_request())
    second = journal.prepare(_request())
    assert first["state"] == NodeOperationState.PREPARED.value
    assert second == first

def test_same_operation_id_with_different_digest_quarantines(tmp_path):
    journal = NodeOperationJournal(tmp_path / "node.sqlite")
    journal.prepare(_request())
    with pytest.raises(OperationDigestMismatch):
        journal.prepare(_request(argv=["echo", "different"]))
    assert journal.lookup("op-1")["state"] == NodeOperationState.QUARANTINED.value


def test_generic_state_is_rejected(tmp_path):
    journal = NodeOperationJournal(tmp_path / "node.sqlite")
    journal.prepare(_request())
    with pytest.raises(GenericStateViolation):
        journal.record_state("op-1", "error")


def test_nonterminal_entries_are_reconciliation_candidates(tmp_path):
    journal = NodeOperationJournal(tmp_path / "node.sqlite")
    journal.prepare(_request("op-1"))
    journal.record_state("op-1", NodeOperationState.EXECUTING)
    journal.prepare(_request("op-2"))
    journal.record_state("op-2", NodeOperationState.CLOSED)
    assert [row["operationId"] for row in journal.reconcile_candidates()] == ["op-1"]
