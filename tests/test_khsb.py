"""Tests for the KHSB in-process message bus public surface."""

import pytest

from capt_solo.khsb.bus import KHSB, Message
from capt_solo.core.errors import BusError


def test_publish_subscribe(bus):
    received = []
    bus.subscribe("t", lambda m: received.append(m.payload))
    mid = bus.publish("t", {"a": 1})
    assert received == [{"a": 1}]
    assert mid


def test_unsubscribe(bus):
    sub = bus.subscribe("t", lambda m: None)
    assert bus.unsubscribe(sub) is True
    assert bus.unsubscribe("nope") is False


def test_request_reply(bus):
    def handler(msg):
        bus.reply(msg, {"answer": 42})
    bus.subscribe("q", handler)
    rep = bus.request("q", {"q": 1}, timeout=2.0)
    assert rep == {"answer": 42}


def test_request_timeout(bus):
    with pytest.raises(BusError):
        bus.request("nobody", {"x": 1}, timeout=0.2)


def test_reply_to_non_request_raises(bus):
    msg = Message(message_id="m", topic="t", payload={}, correlation_id=None,
                   reply_to=None, ts=0.0, type="event")
    with pytest.raises(BusError):
        bus.reply(msg, {})


def test_ack(bus):
    mid = bus.publish("t", {"a": 1})
    bus.ack(mid)
    assert bus.is_acked(mid)
    assert bus.is_acked("nope") is False


def test_correlation_id_propagation(bus):
    corr = "corr-123"
    bus.publish("t", {"z": 1}, correlation_id=corr)
    last = bus.pending_messages("t")[-1]
    assert last["correlation_id"] == corr


def test_pending_messages_filter(bus):
    bus.publish("a", {"x": 1})
    bus.publish("b", {"y": 2})
    only_a = bus.pending_messages("a")
    assert all(m["topic"] == "a" for m in only_a)
    assert len(only_a) == 1


def test_message_to_dict():
    m = Message(message_id="m1", topic="t", payload={"p": 1}, correlation_id="c",
                 reply_to="r", ts=1.0, type="event")
    d = m.to_dict()
    assert d["message_id"] == "m1"
    assert d["type"] == "event"


def test_reset(bus):
    bus.subscribe("t", lambda m: None)
    bus.publish("t", {})
    bus.reset()
    assert bus.pending_messages() == []
