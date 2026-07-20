"""KHSB — Knowledge/Hermes Signal Bus.

An in-process, networking-free message bus. All communication stays inside the
current process; no sockets, no files, no external brokers. This is the v0.1
foundation. Distributed transport (remote agents, federation) is a future
extension point and is NOT implemented here.

Public API (stable across v0.1.x):
    - publish(topic, payload, correlation_id=None)
    - subscribe(topic, handler) -> subscription_id
    - unsubscribe(subscription_id)
    - request(topic, payload, *, timeout=5.0) -> reply
    - reply(request_event, payload)
    - ack(message_id)
    - pending_messages(topic=None) -> list

Message shape (internal, but stable for the bus contract):
    {
      "message_id": str,
      "topic": str,
      "payload": Any,
      "correlation_id": str | None,
      "reply_to": str | None,
      "ts": float,
      "type": "event" | "request" | "reply"
    }

Extension point: a ``Transport`` interface can later route messages over a
network; the public methods above are unchanged and become no-ops-over-network
shims. The local bus remains the reference implementation.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from capt_solo.core.errors import BusError

Handler = Callable[["Message"], None]


@dataclass
class Message:
    message_id: str
    topic: str
    payload: Any
    correlation_id: Optional[str]
    reply_to: Optional[str]
    ts: float
    type: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "topic": self.topic,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "ts": self.ts,
            "type": self.type,
        }


class KHSB:
    """In-process publish/subscribe/request-reply bus."""

    def __init__(self) -> None:
        self._subs: Dict[str, Dict[str, Handler]] = {}
        self._lock = threading.RLock()
        self._pending_replies: Dict[str, "threading.Event"] = {}
        self._reply_store: Dict[str, Any] = {}
        self._history: List[Message] = []
        self._acked: set = set()

    # ----- publish / subscribe ------------------------------------------
    def publish(self, topic: str, payload: Any, correlation_id: Optional[str] = None) -> str:
        msg = self._make(topic, payload, correlation_id, None, "event")
        self._dispatch(msg)
        return msg.message_id

    def subscribe(self, topic: str, handler: Handler) -> str:
        sub_id = uuid.uuid4().hex
        with self._lock:
            self._subs.setdefault(topic, {})[sub_id] = handler
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        with self._lock:
            for topic, handlers in self._subs.items():
                if subscription_id in handlers:
                    del handlers[subscription_id]
                    return True
        return False

    # ----- request / reply ----------------------------------------------
    def request(self, topic: str, payload: Any, *, timeout: float = 5.0) -> Any:
        corr = uuid.uuid4().hex
        msg = self._make(topic, payload, corr, corr, "request")
        evt = threading.Event()
        with self._lock:
            self._pending_replies[corr] = evt
        # dispatch to any subscribers; they must call reply()
        self._dispatch(msg)
        if not evt.wait(timeout):
            with self._lock:
                self._pending_replies.pop(corr, None)
            raise BusError(f"request to '{topic}' timed out after {timeout}s")
        with self._lock:
            result = self._reply_store.pop(corr, None)
            self._pending_replies.pop(corr, None)
        return result

    def reply(self, request_message: Message, payload: Any) -> str:
        if request_message.reply_to is None:
            raise BusError("message is not a request (no reply_to)")
        msg = self._make(
            request_message.topic, payload,
            request_message.correlation_id, request_message.reply_to, "reply")
        with self._lock:
            self._reply_store[msg.reply_to] = payload
            evt = self._pending_replies.get(msg.reply_to)
        if evt:
            evt.set()
        return msg.message_id

    # ----- ack -----------------------------------------------------------
    def ack(self, message_id: str) -> None:
        self._acked.add(message_id)

    def is_acked(self, message_id: str) -> bool:
        return message_id in self._acked

    # ----- introspection -------------------------------------------------
    def pending_messages(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            out = [m.to_dict() for m in self._history if m.type in ("event", "request")]
        if topic:
            out = [m for m in out if m["topic"] == topic]
        return out

    def reset(self) -> None:
        with self._lock:
            self._subs.clear()
            self._pending_replies.clear()
            self._reply_store.clear()
            self._history.clear()
            self._acked.clear()

    # ----- internals ----------------------------------------------------
    def _make(self, topic, payload, corr, reply_to, mtype) -> Message:
        return Message(
            message_id=uuid.uuid4().hex,
            topic=topic,
            payload=payload,
            correlation_id=corr,
            reply_to=reply_to,
            ts=time.time(),
            type=mtype,
        )

    def _dispatch(self, msg: Message) -> None:
        with self._lock:
            self._history.append(msg)
            handlers = dict(self._subs.get(msg.topic, {}))
        for handler in handlers.values():
            try:
                handler(msg)
            except Exception as e:  # handlers must not crash the bus
                raise BusError(f"handler for '{msg.topic}' raised: {e}")
