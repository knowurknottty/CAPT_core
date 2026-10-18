"""Durable claim-once donor-adaptation tests. No live CAPT ledger touched."""
import concurrent.futures
from pathlib import Path
import sqlite3
import threading

import pytest

from capt_runtime.memory.claim_once_handoff import (
    ClaimOnceHandoffStore,
    HandoffRefused,
)

D1 = "sha256:" + "a" * 64
D2 = "sha256:" + "b" * 64


@pytest.fixture
def inbox(tmp_path):
    now = [1_000_000.0]
    store = ClaimOnceHandoffStore(tmp_path / "handoffs.sqlite", clock=lambda: now[0])
    return store, now


def offer(store, handoff_id="h-1", target="session-b", digest=D1, ttl=3600):
    return store.offer(
        handoff_id=handoff_id, issuer="session-a", target_principal=target,
        source_digest=digest, ttl_seconds=ttl,
    )


def claim(store, key="claim-1", principal="session-b", digest=D1, hid="h-1"):
    return store.claim(
        handoff_id=hid, principal=principal, claim_key=key,
        expected_source_digest=digest,
    )


def test_claim_once_and_replay_are_distinct(inbox):
    store, _ = inbox
    assert offer(store) == "created"
    a = claim(store)
    assert a.replayed is False
    assert claim(store).replayed is True
    with pytest.raises(HandoffRefused, match="ALREADY_CLAIMED"):
        claim(store, key="claim-again")
    assert store.inspect("h-1")["status"] == "claimed"


def test_survives_new_connection_and_fresh_instance(inbox):
    store, now = inbox
    offer(store)
    other = ClaimOnceHandoffStore(store.path, clock=lambda: now[0])
    assert claim(other).replayed is False
    assert claim(store).replayed is True


def test_single_winner_under_concurrency(inbox):
    store, now = inbox
    offer(store)
    barrier = threading.Barrier(6)
    def contender(i):
        other=ClaimOnceHandoffStore(store.path,clock=lambda:now[0])
        barrier.wait()
        try:
            return (True,claim(other,key=f"key-{i}"))
        except HandoffRefused:
            return (False,None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        rows=list(pool.map(contender,range(6)))
    assert sum(s for s,_ in rows) == 1
    assert store.inspect("h-1")["status"] == "claimed"


def test_claim_wrong_owner_or_digest_does_not_consume(inbox):
    store, _ = inbox
    offer(store)
    with pytest.raises(HandoffRefused,match="WRONG_PRINCIPAL"):
        claim(store,principal="session-c")
    with pytest.raises(HandoffRefused,match="SOURCE_CHANGED"):
        claim(store,digest=D2)
    assert store.inspect("h-1")["status"]=="open"
    assert claim(store).claimed_by=="session-b"


def test_offer_id_is_immutable_and_idempotent(inbox):
    store, _=inbox
    assert offer(store)=="created"
    assert offer(store)=="already_exists"
    with pytest.raises(HandoffRefused,match="ID_CONFLICT"):
        offer(store,target="session-c")
    with pytest.raises(HandoffRefused,match="ID_CONFLICT"):
        offer(store,digest=D2)


def test_expired_offer_cannot_be_claimed(inbox):
    store, clock=inbox
    offer(store,ttl=60)
    clock[0]+=61
    with pytest.raises(HandoffRefused,match="EXPIRED"):
        claim(store)
    assert store.inspect("h-1")["status"]=="open"


def test_revocation_denies_claim_and_uses_issuer(inbox):
    store, _=inbox
    offer(store)
    with pytest.raises(HandoffRefused,match="ISSUER_MISMATCH"):
        store.revoke(handoff_id="h-1",issuer="session-c")
    assert store.revoke(handoff_id="h-1",issuer="session-a")
    assert not store.revoke(handoff_id="h-1",issuer="session-a")
    with pytest.raises(HandoffRefused,match="REVOKED"):
        claim(store)


def test_claimed_handoff_cannot_be_revoked(inbox):
    store,_=inbox
    offer(store)
    claim(store)
    with pytest.raises(HandoffRefused,match="ALREADY_CLAIMED"):
        store.revoke(handoff_id="h-1",issuer="session-a")


@pytest.mark.parametrize("bad",["","../escape","a b","_starts","x"*128,"💣"])
def test_malformed_owner_or_handoff_refused(inbox,bad):
    store,_=inbox
    with pytest.raises(HandoffRefused):
        offer(store,handoff_id=bad)


@pytest.mark.parametrize("digest",["","sha256:xyz","md5:"+"0"*32,"sha256:"+"A"*64])
def test_unsigned_unstructured_source_denied(inbox,digest):
    store,_=inbox
    with pytest.raises(HandoffRefused,match="INVALID_SOURCE_DIGEST"):
        offer(store,digest=digest)


def test_ledger_does_not_store_raw_memory_text(inbox):
    store,_=inbox
    offer(store)
    con=sqlite3.connect(store.path)
    columns={x[1] for x in con.execute("PRAGMA table_info(handoff)")}
    con.close()
    assert "body" not in columns
    assert "prompt" not in columns
    assert "source_digest" in columns


def test_database_file_is_private(inbox):
    store,_=inbox
    assert store.path.stat().st_mode & 0o077 == 0
