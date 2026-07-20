"""Tests for the CTP Runtime public surface."""

import pytest

from capt_solo.ctp.journal import CTPRuntime, Receipt
from capt_solo.core.errors import TransactionError, IdempotencyError


def test_begin_returns_id(ctp_runtime):
    tx = ctp_runtime.begin(correlation_id="c1", idempotency_key="k1", meta={"a": 1})
    assert tx
    assert ctp_runtime._exists(tx)


def test_validate(ctp_runtime):
    tx = ctp_runtime.begin()
    assert ctp_runtime.validate(tx, {"ok": True}) is True
    assert ctp_runtime.validate(tx, {"ok": False}) is False


def test_commit_and_receipt(ctp_runtime):
    tx = ctp_runtime.begin(correlation_id="c", idempotency_key="k")
    rcpt = ctp_runtime.commit(tx)
    assert isinstance(rcpt, Receipt)
    assert rcpt.status == "committed"
    assert rcpt.correlation_id == "c"
    assert rcpt.idempotency_key == "k"
    got = ctp_runtime.get_receipt(tx)
    assert got.status == "committed"


def test_abort(ctp_runtime):
    tx = ctp_runtime.begin()
    rcpt = ctp_runtime.abort(tx)
    assert rcpt.status == "aborted"
    assert ctp_runtime.get_receipt(tx).status == "aborted"


def test_commit_unknown_raises(ctp_runtime):
    with pytest.raises(TransactionError):
        ctp_runtime.commit("nonexistent")


def test_abort_unknown_raises(ctp_runtime):
    with pytest.raises(TransactionError):
        ctp_runtime.abort("nonexistent")


def test_double_commit_raises(ctp_runtime):
    tx = ctp_runtime.begin()
    ctp_runtime.commit(tx)
    with pytest.raises(TransactionError):
        ctp_runtime.commit(tx)


def test_double_abort_raises(ctp_runtime):
    tx = ctp_runtime.begin()
    ctp_runtime.abort(tx)
    with pytest.raises(TransactionError):
        ctp_runtime.abort(tx)


def test_idempotency_guard(ctp_runtime):
    ctp_runtime.begin(idempotency_key="dup")
    ctp_runtime.begin(idempotency_key="dup2")
    ctp_runtime.commit(ctp_runtime.begin(idempotency_key="dup2"))
    # finalized key rejected
    with pytest.raises(IdempotencyError):
        ctp_runtime.begin(idempotency_key="dup2")
    # still-open key allowed to be referenced only via its own tx
    # a brand new begin with an already-finalized key must fail
    with pytest.raises(IdempotencyError):
        ctp_runtime.begin(idempotency_key="dup2")


def test_note(ctp_runtime):
    tx = ctp_runtime.begin()
    ctp_runtime.note(tx, "doing step 1")
    trail = ctp_runtime.audit_trail(tx)
    assert any(e.get("note") == "doing step 1" for e in trail)


def test_note_unknown_raises(ctp_runtime):
    with pytest.raises(TransactionError):
        ctp_runtime.note("nope", "x")


def test_recover_no_pending_after_finalize(ctp_runtime):
    tx = ctp_runtime.begin()
    ctp_runtime.commit(tx)
    assert tx not in ctp_runtime.recover()


def test_recover_finds_pending(ctp_runtime):
    tx = ctp_runtime.begin()  # never finalized
    pending = ctp_runtime.recover()
    assert tx in pending


def test_audit_trail(ctp_runtime):
    tx = ctp_runtime.begin(correlation_id="c")
    ctp_runtime.validate(tx, {"ok": True})
    ctp_runtime.commit(tx)
    trail = ctp_runtime.audit_trail(tx)
    types = [e["type"] for e in trail]
    assert types == ["begin", "validate", "commit"]


def test_integrity_check(ctp_runtime):
    assert ctp_runtime.integrity_check() is True


def test_receipt_to_dict(ctp_runtime):
    tx = ctp_runtime.begin(correlation_id="c", idempotency_key="k")
    rcpt = ctp_runtime.commit(tx)
    d = rcpt.to_dict()
    assert d["status"] == "committed"
    assert d["correlation_id"] == "c"
