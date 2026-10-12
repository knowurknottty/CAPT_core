from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
import socket
import tempfile
import threading
import time

from capt_ui.operator.tia_widget_surface import CouncilSemanticSurface, WINDOW_TITLE


class FakeVar:
    def __init__(self, value: str = ""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeWidget:
    def __init__(self):
        self.focused = False
        self.pressed = 0

    def focus_set(self):
        self.focused = True

    def state(self):
        return ()

    def invoke(self):
        self.pressed += 1


class FakeRoot:
    def title(self):
        return WINDOW_TITLE

    def after(self, *args):
        return 1

    def after_cancel(self, *args):
        return None


def test_semantic_surface_cannot_approve_or_launch(tmp_path):
    root = FakeRoot()
    surface = CouncilSemanticSurface(root, tmp_path)
    value = FakeVar("council-original")
    entry = FakeWidget()
    button = FakeWidget()
    surface.register_field("Council ID", value, entry)
    surface.register_safe_button("Refresh", button)
    ident = {"pid": os.getpid(), "windowTitle": WINDOW_TITLE}
    assert surface.handle_ui({**ident, "op": "set_value", "role": "AXTextField", "name": "Council ID", "value": "council-probe"})["ok"]
    assert value.get() == "council-probe"
    assert surface.handle_ui({**ident, "op": "focus", "role": "AXTextField", "name": "Council ID"})["ok"]
    assert entry.focused
    assert surface.handle_ui({**ident, "op": "press", "role": "AXButton", "name": "Refresh"})["ok"]
    assert button.pressed == 1
    assert not surface.handle_ui({**ident, "op": "press", "role": "AXButton", "name": "3 · Launch Council"})["ok"]
    assert not surface.handle_ui({**ident, "op": "press", "role": "AXButton", "name": "2 · Approve"})["ok"]
    assert not surface.handle_ui({**ident, "op": "set_value", "role": "AXTextField", "name": "API Key", "value": "secret"})["ok"]
    assert not surface.handle_ui({**ident, "op": "press", "role": "AXButton", "name": "Refresh", "pid": 9})["ok"]
    assert "[REDACTED]" in str(surface.snapshot())


def test_unix_socket_roundtrip_real_ui_queue(tmp_path):
    root = FakeRoot()
    short_home = Path(tempfile.mkdtemp(prefix="tia-sock-", dir="/tmp"))
    surface = CouncilSemanticSurface(root, short_home)
    value = FakeVar("original")
    surface.register_field("Mission ID", value, FakeWidget())
    surface.start()
    assert surface.path.stat().st_mode & 0o777 == 0o600
    results: list[dict] = []

    def client() -> None:
        for req in (
            {"op": "snapshot", "pid": os.getpid(), "windowTitle": WINDOW_TITLE},
            {"op": "set_value", "pid": os.getpid(), "windowTitle": WINDOW_TITLE,
             "role": "AXTextField", "name": "Mission ID", "value": "m-test"},
        ):
            with socket.socket(socket.AF_UNIX) as s:
                s.settimeout(3)
                s.connect(str(surface.path))
                s.sendall((json.dumps(req) + "\n").encode())
                received = bytearray()
                while not received.endswith(b"\n"):
                    received.extend(s.recv(4096))
                results.append(json.loads(received))

    thread = threading.Thread(target=client, daemon=True)
    thread.start()
    for _ in range(150):
        surface._drain()
        if len(results) == 2:
            break
        time.sleep(.01)
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert len(results) == 2
    assert all(row["ok"] and row["pid"] == os.getpid() for row in results)
    assert results[0]["nodes"][0]["value"] == "[REDACTED]"
    assert value.get() == "m-test"
    surface.stop()
    assert not surface.path.exists()
    shutil.rmtree(short_home)
