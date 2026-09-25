"""Comprehensive tests for bounded production IPC framing in CAPT Desktop Runtime."""

import socket
import threading
import time
from pathlib import Path
import pytest

from capt_runtime.ipc_framing import MAX_FRAME_BYTES, FrameProtocolError, recv_json, send_json
from desktop.capt_runtime_service import serve as serve_runtime
from desktop.desktop_runtime_client import RuntimeClient, RuntimeClientError


def test_ipc_framing_unit_boundaries():
    s1, s2 = socket.socketpair()
    try:
        # Valid send & recv
        send_json(s1, {"test": "hello", "val": 123})
        val = recv_json(s2)
        assert val == {"test": "hello", "val": 123}

        # Truncated header
        s1.sendall(b"\x00\x00")
        s1.close()
        with pytest.raises(FrameProtocolError, match="IPC_FRAME_TRUNCATED"):
            recv_json(s2)
    finally:
        s2.close()


def test_ipc_framing_oversized_frame():
    s1, s2 = socket.socketpair()
    try:
        # Send header claiming length > max_bytes
        s1.sendall((MAX_FRAME_BYTES + 10).to_bytes(4, "big") + b"x" * 10)
        with pytest.raises(FrameProtocolError, match="IPC_FRAME_TOO_LARGE"):
            recv_json(s2)
    finally:
        s1.close()
        s2.close()


def test_ipc_framing_malformed_json():
    s1, s2 = socket.socketpair()
    try:
        bad_bytes = b"not-a-json-object"
        s1.sendall(len(bad_bytes).to_bytes(4, "big") + bad_bytes)
        with pytest.raises(FrameProtocolError, match="IPC_FRAME_JSON_INVALID"):
            recv_json(s2)
    finally:
        s1.close()
        s2.close()


def test_ipc_framing_non_object_json():
    s1, s2 = socket.socketpair()
    try:
        bad_bytes = b"[1, 2, 3]"
        s1.sendall(len(bad_bytes).to_bytes(4, "big") + bad_bytes)
        with pytest.raises(FrameProtocolError, match="IPC_FRAME_OBJECT_REQUIRED"):
            recv_json(s2)
    finally:
        s1.close()
        s2.close()


def test_runtime_service_bounded_ipc_integration():
    import tempfile
    td = tempfile.mkdtemp(prefix="cpt_")
    try:
        ledger = Path(td) / "test.db"
        sock = Path(td) / "s.sock"
        token_file = Path(td) / "tok.txt"

        srv_thread = threading.Thread(
            target=serve_runtime,
            args=(str(ledger), sock, str(token_file), False),
            daemon=True,
        )
        srv_thread.start()

        for _ in range(50):
            if sock.exists() and token_file.exists():
                break
            time.sleep(0.05)

        # 1. Normal client interaction
        client = RuntimeClient(str(sock), str(token_file), connect_timeout=2.0)
        identity = client.connect()
        assert client.operator_id is not None
        assert client.session_id is not None
        aggs = client.list_aggregates()
        assert isinstance(aggs, list)
        client.disconnect()

        # 2. Malformed raw connection to service
        raw_s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        raw_s.connect(str(sock))
        # Send oversized header
        raw_s.sendall((MAX_FRAME_BYTES + 1024).to_bytes(4, "big") + b"data")
        # Service should gracefully close / reject connection
        time.sleep(0.1)
        raw_s.close()

        # 3. Service remains operational after malformed client
        client2 = RuntimeClient(str(sock), str(token_file), connect_timeout=2.0)
        identity2 = client2.connect()
        assert client2.operator_id is not None
        assert client2.session_id is not None
        aggs2 = client2.list_aggregates()
        assert isinstance(aggs2, list)
        client2.disconnect()
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_runtime_client_serializes_framed_exchanges_across_threads():
    client = RuntimeClient("/tmp/unused.sock", "/tmp/unused.token")
    client._sock = object()
    client.operator_id = "operator-test"
    client.session_id = "session-test"

    state_lock = threading.Lock()
    active = 0
    peak = 0

    def fake_send(_sock, _payload):
        nonlocal active, peak
        with state_lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)

    def fake_recv(_sock):
        nonlocal active
        time.sleep(0.03)
        with state_lock:
            active -= 1
        return {"status": "accepted"}

    client._send = fake_send
    client._recv = fake_recv
    threads = [
        threading.Thread(target=client.command, args=("noop", {}, f"idem-{i}"))
        for i in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)

    assert all(not thread.is_alive() for thread in threads)
    assert peak == 1
