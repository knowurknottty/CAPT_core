from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "capt_recover.py"
spec = importlib.util.spec_from_file_location("capt_recover", SCRIPT)
assert spec and spec.loader
capt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capt)


def test_missing_profile_is_not_provisioned(tmp_path: Path):
    assert capt.local_runtime(tmp_path)["state"] == "not_installed"


def test_local_socket_probe_checks_live_accept(tmp_path: Path):
    path = Path("/tmp") / ("capt-recover-test-%d.sock" % os.getpid())
    assert not capt.is_live(str(path))
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(1)
    try:
        assert capt.is_live(str(path))
        incoming, _ = server.accept()
        incoming.close()
    finally:
        server.close()
        path.unlink(missing_ok=True)


def test_headless_refresh_refuses_before_mutation(tmp_path: Path):
    candidate = tmp_path / "absent-config.json"
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--recover", "--config", str(candidate)],
        input="", capture_output=True, text=True, timeout=12, check=False
    )
    assert p.returncode == 2
    assert "requires physical operator terminal" in p.stderr
    assert not candidate.exists()
    assert not (tmp_path / ".capt-refresh.lock").exists()


def test_runtime_probe_authenticates_without_unauthenticated_first_connection(tmp_path: Path, monkeypatch):
    import json
    import struct
    from collections import deque
    (tmp_path / "runtime.token").write_text("fixture-secret")
    (tmp_path / "runtime.token").chmod(0o600)
    requests=[]
    class FakeSocket:
        def __init__(self):
            self.answers=deque()
            self.buffer=b""
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def settimeout(self,t):pass
        def connect(self,path):requests.append(("connect",path))
        def sendall(self,data):
            n=struct.unpack(">I",data[:4])[0]
            body=json.loads(data[4:4+n])
            requests.append(("send",body.get("op") or "authentication"))
            assert len(data)==n+4
            response={"ok":True, "authenticated":True} if "token" in body else {"ok":True}
            raw=json.dumps(response).encode()
            self.buffer+=struct.pack(">I",len(raw))+raw
        def recv(self,n):
            data,self.buffer=self.buffer[:n],self.buffer[n:]
            return data
    monkeypatch.setattr(capt.socket,"socket",lambda *a,**kw:FakeSocket())
    def rejected_probe(path):
        raise AssertionError("unauthenticated is_live socket probe must not be called")
    monkeypatch.setattr(capt,"is_live",rejected_probe)
    assert capt.local_runtime(tmp_path)["state"]=="authenticated"
    assert [x[0] for x in requests].count("connect")==1
    assert [x[1] for x in requests if x[0]=="send"]==["authentication","identity"]
