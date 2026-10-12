"""Bounded Tk semantic accessibility supplement for the CAPT Council UI.

Tk 9.0 on macOS does not expose ttk form widgets through the AX tree.
This surface acts on the *actual Tk widgets* on the UI thread, never on
RuntimeService, ToolBroker, approvals or arbitrary desktop input.

The external TIA client MUST first authenticate the exact native AXWindow,
PID and title, and then bind the returned PID to this owner's 0600 socket.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import queue
import socket
import socketserver
import stat
import struct
import sys
import threading
from typing import Any, Callable

WINDOW_TITLE = "CAPT · Model Council — Recovery R3"
MAX_FRAME = 8192
MAX_VALUE = 512


def socket_path(pid: int, home: Path | None = None) -> Path:
    if not isinstance(pid, int) or pid < 2:
        raise ValueError("PID required")
    return (home or Path.home()) / ".capt" / "tia" / ("council-%d.sock" % pid)


def peer_uid(sock: socket.socket) -> int:
    if sys.platform == "darwin":
        libc = ctypes.CDLL(None)
        uid = ctypes.c_uint()
        gid = ctypes.c_uint()
        if libc.getpeereid(sock.fileno(), ctypes.byref(uid), ctypes.byref(gid)) != 0:
            raise PermissionError("PEER_CREDENTIALS_UNAVAILABLE")
        return uid.value
    if hasattr(socket, "SO_PEERCRED"):
        return struct.unpack("3i", sock.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
        ))[1]
    raise PermissionError("PEER_CREDENTIALS_UNAVAILABLE")


class _SocketHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        surface: CouncilSemanticSurface = self.server.surface  # type: ignore[attr-defined]
        try:
            if peer_uid(self.connection) != os.getuid():
                raise PermissionError("WRONG_LOCAL_USER")
            raw = self.rfile.readline(MAX_FRAME + 1)
            if not raw.endswith(b"\n") or len(raw) > MAX_FRAME:
                raise ValueError("INVALID_OR_OVERSIZED_FRAME")
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError("INVALID_SEMANTIC_REQUEST")
            if surface.closing:
                raise RuntimeError("COUNCIL_CLOSING")
            done = threading.Event()
            response: list[dict[str, Any]] = []
            surface.inbox.put((request, response, done))
            if not done.wait(timeout=4):
                raise TimeoutError("UI_THREAD_NOT_RESPONDING")
            result = response[0]
        except Exception as exc:
            result = {"ok": False, "error": str(exc)[:120]}
        self.wfile.write((json.dumps(result, separators=(",", ":")) + "\n").encode())


class _Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False


class CouncilSemanticSurface:
    """Allowlisted named Tk widgets; one GUI root, one per-PID socket."""

    def __init__(self, root: Any, home: Path | None = None) -> None:
        self.root = root
        self.path = socket_path(os.getpid(), home)
        self.fields: dict[str, tuple[Any, Any, str]] = {}
        self.buttons: dict[str, Any] = {}
        self.inbox: queue.Queue[tuple[dict[str, Any], list[dict[str, Any]], threading.Event]] = queue.Queue()
        self.closing = False
        self.server: _Server | None = None
        self.thread: threading.Thread | None = None
        self.timer_id: Any = None

    def register_field(self, name: str, var: Any, widget: Any, role: str = "AXTextField") -> None:
        if name in self.fields or name in self.buttons:
            raise ValueError("DUPLICATE_SEMANTIC_NAME")
        if role not in ("AXTextField", "AXComboBox"):
            raise ValueError("DISALLOWED_SEMANTIC_ROLE")
        self.fields[name] = (var, widget, role)

    def register_safe_button(self, name: str, button: Any) -> None:
        if name not in ("Refresh models", "Refresh", "Reconnect"):
            raise ValueError("UNSAFE_SEMANTIC_BUTTON")
        if name in self.fields or name in self.buttons:
            raise ValueError("DUPLICATE_SEMANTIC_NAME")
        self.buttons[name] = button

    def snapshot(self) -> dict[str, Any]:
        nodes = [
            {"role": role, "name": name, "value": "[REDACTED]"}
            for name, (_var, _widget, role) in sorted(self.fields.items())
        ] + [{"role": "AXButton", "name": name} for name in sorted(self.buttons)]
        return {"ok": True, "pid": os.getpid(), "windowTitle": WINDOW_TITLE,
                "nodes": nodes, "source": "tk-semantic-widget-supplement"}

    def handle_ui(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.closing or self.root.title() != WINDOW_TITLE:
            return {"ok": False, "error": "WINDOW_PROFILE_CHANGED"}
        if request.get("pid") != os.getpid() or request.get("windowTitle") != WINDOW_TITLE:
            return {"ok": False, "error": "WINDOW_IDENTITY_MISMATCH"}
        operation = request.get("op")
        if operation == "snapshot":
            return self.snapshot()
        name = request.get("name")
        role = request.get("role")
        if type(name) is not str or len(name) > 90:
            return {"ok": False, "error": "SELECTOR_INVALID"}
        if operation == "set_value":
            spec = self.fields.get(name)
            if spec is None or role != spec[2]:
                return {"ok": False, "error": "UNLISTED_FIELD"}
            value = request.get("value")
            if type(value) is not str or len(value.encode()) > MAX_VALUE:
                return {"ok": False, "error": "VALUE_LIMIT"}
            var = spec[0]
            before = hashlib.sha256(str(var.get()).encode()).hexdigest()
            var.set(value)
            verified = str(var.get()) == value
            after = hashlib.sha256(str(var.get()).encode()).hexdigest()
            return {"ok": verified, "op": operation, "role": role, "name": name,
                    "beforeDigest": "sha256:" + before, "afterDigest": "sha256:" + after}
        if operation == "focus":
            spec = self.fields.get(name)
            if spec is None or role != spec[2]:
                return {"ok": False, "error": "UNLISTED_FIELD"}
            spec[1].focus_set()
            return {"ok": True, "op": operation, "role": role, "name": name}
        if operation == "press":
            button = self.buttons.get(name)
            if button is None or role != "AXButton":
                return {"ok": False, "error": "UNSAFE_BUTTON"}
            if "disabled" in button.state():
                return {"ok": False, "error": "BUTTON_DISABLED"}
            button.invoke()  # Actual human-facing Tk button; never RuntimeService.
            return {"ok": True, "op": operation, "role": role, "name": name}
        return {"ok": False, "error": "OPERATION_NOT_ALLOWED"}

    def _drain(self) -> None:
        if self.closing:
            return
        for _ in range(20):
            try:
                request, response, done = self.inbox.get_nowait()
            except queue.Empty:
                break
            try:
                reply = self.handle_ui(request)
                reply.setdefault("pid", os.getpid())
                reply.setdefault("windowTitle", WINDOW_TITLE)
                response.append(reply)
            except Exception as exc:
                response.append({"ok": False, "error": type(exc).__name__})
            finally:
                done.set()
        self.timer_id = self.root.after(40, self._drain)

    def start(self) -> None:
        directory = self.path.parent
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if directory.is_symlink() or directory.stat().st_uid != os.getuid():
            raise PermissionError("UNSAFE_SOCKET_DIRECTORY")
        directory.chmod(0o700)
        if self.path.exists() or self.path.is_symlink():
            raise FileExistsError("COUNCIL_SEMANTIC_SOCKET_ALREADY_EXISTS")
        self.server = _Server(str(self.path), _SocketHandler)
        self.server.surface = self
        self.path.chmod(0o600)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.timer_id = self.root.after(40, self._drain)

    def stop(self) -> None:
        self.closing = True
        if self.timer_id is not None:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        self.path.unlink(missing_ok=True)
