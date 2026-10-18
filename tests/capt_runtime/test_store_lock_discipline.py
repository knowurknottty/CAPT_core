"""CAPT-UPG-028: EventStore shares one SQLite connection across threads.

Every use of that connection must be serialized by ``self._lock`` (directly or
through ``self.transaction()``); otherwise a reader on another thread executes
inside a writer's open ``BEGIN IMMEDIATE`` and observes uncommitted rows.
"""
from __future__ import annotations

import ast
import threading
from pathlib import Path

import pytest

from capt_runtime.store import EventStore

STORE_SOURCE = Path(__file__).resolve().parents[2] / "capt_runtime" / "store.py"
# Construction and teardown happen before/after the object is shared.
_EXEMPT_METHODS = frozenset({"__init__"})
_LOCK_CONTEXTS = frozenset({"self._lock", "self.transaction()"})


def _unlocked_connection_uses() -> list[str]:
    tree = ast.parse(STORE_SOURCE.read_text(encoding="utf-8"))
    store_cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "EventStore"
    )
    violations: list[str] = []

    def visit(node: ast.AST, locked: bool, method: str) -> None:
        if isinstance(node, ast.With) and any(
            ast.unparse(item.context_expr) in _LOCK_CONTEXTS for item in node.items
        ):
            locked = True
        if (
            isinstance(node, ast.Attribute)
            and ast.unparse(node) == "self._conn"
            and not locked
        ):
            violations.append(f"{method}:{node.lineno}")
        for child in ast.iter_child_nodes(node):
            visit(child, locked, method)

    for item in store_cls.body:
        if isinstance(item, ast.FunctionDef) and item.name not in _EXEMPT_METHODS:
            visit(item, False, item.name)
    return violations


def test_every_shared_connection_use_is_lexically_locked() -> None:
    assert _unlocked_connection_uses() == []


def test_recent_events_never_observe_an_uncommitted_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAPT_STATE_KEY_B64", "A" * 43 + "=")
    store = EventStore(str(tmp_path / "rt.db"))
    try:
        sealed = store._seal_json(  # noqa: SLF001 - fixture builds a raw row
            {"eventId": "ev-phantom", "payload": {}},
            table="events", column="envelope_json", key="ev-phantom",
        )
        inside = threading.Event()
        release = threading.Event()
        observed: list[list[str]] = []

        def writer() -> None:
            try:
                with store.transaction() as conn:
                    conn.execute(
                        "INSERT INTO events (event_id, stream_id, stream_version, event_type,"
                        " schema_version, envelope_json, payload_digest, chain_digest)"
                        " VALUES ('ev-phantom', 's', 1, 'X', '1', ?, 'd', 'c')",
                        (sealed,),
                    )
                    inside.set()
                    release.wait(timeout=5)
                    raise RuntimeError("abort -> ROLLBACK")
            except RuntimeError:
                pass

        def reader() -> None:
            observed.append([e["eventId"] for e in store.read_recent_events()])

        w = threading.Thread(target=writer)
        w.start()
        assert inside.wait(timeout=5)
        r = threading.Thread(target=reader)
        r.start()
        # A locked reader blocks until the writer finishes; give it a chance
        # to (incorrectly) run inside the open transaction first.
        r.join(timeout=0.3)
        release.set()
        w.join(timeout=5)
        r.join(timeout=5)
        assert not w.is_alive() and not r.is_alive()
        assert observed == [[]], "reader observed rows from a transaction that rolled back"
    finally:
        store.close()
