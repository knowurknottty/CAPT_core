"""Process-boundary tests for Model-A -> process death -> Model-B restart continuity (CAPT-UPG-007)."""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from capt_runtime.composition import create_runtime
from desktop.desktop_runtime_client import RuntimeClient


def _seed_approval(ledger_path: Path, req_id: str, objective: str) -> None:
    from capt_runtime import commands, contracts
    from capt_runtime.store import EventStore
    from capt_runtime.services import RuntimeService
    from capt_runtime.operator_provenance import build_prompt_assembly
    prompt_assembly = build_prompt_assembly(
        human_prompt=str(objective),
        response_mode="SPOCK",
        enhancement_engine="OFF",
        context_pack_digest=contracts.digest({"context": "not-selected-at-admission"}),
        tool_schema_digest=contracts.digest({"operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"]}),
    )
    digest = prompt_assembly.get("promptAssemblyDigest") or prompt_assembly.get("assemblyDigest", "")
    req = {
        "schemaVersion": "1.0.0",
        "requestId": req_id,
        "missionId": "m-cross-" + req_id,
        "taskId": "t-cross-" + req_id,
        "requestedCapability": "cap.fs.read",
        "resource": "/tmp",
        "operation": "ModelOperatorInspection",
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": True},
        "riskClassification": "low",
        "policyReason": "Approve exact model-visible prompt.",
        "requestedBy": {"actorId": "exec-1", "kind": "execution_plane"},
        "expiresAt": "2030-01-01T00:00:00Z",
        "correlationId": "corr-" + req_id,
        "createdAt": "2026-08-16T00:00:00Z",
        "promptAssemblyDigest": digest,
    }
    def _meta(name: str, kind: str):
        return commands.command(
            command_id="cmd-" + req_id + "-" + name,
            idempotency_key="idem-" + req_id + "-" + name,
            operation_fingerprint=commands.fingerprint(name, {"requestId": req_id}),
            correlation_id="corr-" + req_id,
            actor_id="operator",
            actor_kind=kind,
            issued_at="2026-08-16T00:00:00Z",
        )
    store = EventStore(str(ledger_path))
    svc = RuntimeService(store)
    svc.request_human_approval(req, _meta("req", "execution_plane"))
    decision = {
        "schemaVersion": "1.0.0",
        "requestId": req_id,
        "decision": "approve",
        "operatorId": "operator",
        "decidedAt": "2026-08-16T00:00:00Z",
        "note": "Approved for cross-model test lifecycle.",
        "idempotencyKey": "approve-" + req_id,
        "correlationId": "corr-" + req_id,
        "sessionId": "sess-cross",
    }
    svc.submit_human_approval_decision(decision, _meta("dec", "human"))
    store.close()


def test_cross_model_process_restart_continuity():
    import tempfile
    import shutil
    td = tempfile.mkdtemp(prefix="cpt_cnt_")
    try:
        ledger = Path(td) / "continuity.db"
        sock1 = Path(td) / "s1.sock"
        tok1 = Path(td) / "tok1.txt"
        root = Path(__file__).resolve().parents[2]

        target_dir = Path(td) / "target"
        target_dir.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=target_dir, check=True)
        (target_dir / "README.md").write_text("# target\n")
        subprocess.run(["git", "add", "README.md"], cwd=target_dir, check=True)
        subprocess.run(["git", "-c", "user.email=t@e.invalid", "-c", "user.name=t", "commit", "-qm", "init"], cwd=target_dir, check=True)

        fake_hermes1 = Path(td) / "fake_hermes1.sh"
        fake_hermes1.write_text("#!/bin/sh\nprintf 'OBSERVATION: Model A output\\n'\n")
        fake_hermes1.chmod(0o755)

        fake_hermes2 = Path(td) / "fake_hermes2.sh"
        fake_hermes2.write_text("#!/bin/sh\nprintf 'OBSERVATION: Model B output\\n'\n")
        fake_hermes2.chmod(0o755)

        _seed_approval(ledger, "req-cross-model-a", "Inspect repo with Model A")
        _seed_approval(ledger, "req-cross-model-b", "Inspect repo with Model B")

        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class _MockModelServer(BaseHTTPRequestHandler):
            calls = []
            def do_POST(self):
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                self.__class__.calls.append({
                    "path": self.path,
                    "body": json.loads(raw),
                    "auth": self.headers.get("Authorization"),
                })
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                payload = (
                    {"response": "OBSERVATION: bounded model execution completed"}
                    if self.headers.get("Host", "").endswith(str(server_a.server_port))
                    else {"choices": [{"message": {"content": "OBSERVATION: bounded model execution completed"}}]}
                )
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, format, *args):
                return

        server_a = ThreadingHTTPServer(("127.0.0.1", 0), _MockModelServer)
        server_b = ThreadingHTTPServer(("127.0.0.1", 0), _MockModelServer)
        threading.Thread(target=server_a.serve_forever, daemon=True).start()
        threading.Thread(target=server_b.serve_forever, daemon=True).start()

        ui_dir = Path(td) / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        (ui_dir / "providers.json").write_text(json.dumps({
            "providers": [
                {"id": "ollama", "name": "Model A Provider", "kind": "local", "transport": "openai_compatible", "base_url": f"http://127.0.0.1:{server_a.server_port}/v1", "context_limit": 32768, "capabilities": ["chat"]},
                {"id": "openrouter", "name": "Model B Provider", "kind": "cloud", "transport": "openai_compatible", "base_url": f"http://127.0.0.1:{server_b.server_port}/v1", "key_ref": "env:MOCK_KEY", "context_limit": 32768, "capabilities": ["chat"]}
            ]
        }))

        p1 = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import runpy; runpy.run_path('desktop/capt_runtime_service.py', run_name='__main__')",
                "--ledger", str(ledger),
                "--sock", str(sock1),
                "--token-file", str(tok1),
            ],
            cwd=root,
            env={**os.environ, "MOCK_KEY": "sk-mock-test-key-12345"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        for _ in range(50):
            if sock1.exists() and tok1.exists():
                break
            time.sleep(0.05)

        client1 = RuntimeClient(str(sock1), str(tok1))
        client1.connect()
        receipt1 = client1.command(
            "run_approved_hermes_inspection",
            {
                "objective": "Inspect repo with Model A",
                "targetRoot": str(target_dir),
                "executable": str(fake_hermes1),
                "provider": "ollama",
                "model": "llama3.2:latest",
                "approvalRequestId": "req-cross-model-a",
                "driverRunId": "dr-cross-model-a",
                "missionId": "m-cross-model-a",
                "taskId": "t-cross-model-a",
                "grantId": "g-cross-model-a",
                "leaseId": "l-cross-model-a",
                "claimId": "cl-cross-model-a",
                "policyDecisionId": "pd-cross-model-a",
            },
            idempotency_key="idem-cross-turn-1",
        )
        assert receipt1["status"] == "accepted", f"Receipt 1 error detail: {receipt1}"
        assert receipt1["result"]["cognitiveProvenance"]["model"] == "llama3.2:latest"
        assert receipt1["result"]["cognitiveProvenance"]["provider"] == "ollama"

        client1.disconnect()
        p1.terminate()
        p1.wait(timeout=5)

        sock2 = Path(td) / "s2.sock"
        tok2 = Path(td) / "tok2.txt"

        p2 = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import runpy; runpy.run_path('desktop/capt_runtime_service.py', run_name='__main__')",
                "--ledger", str(ledger),
                "--sock", str(sock2),
                "--token-file", str(tok2),
            ],
            cwd=root,
            env={**os.environ, "MOCK_KEY": "sk-mock-test-key-12345"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        for _ in range(50):
            if sock2.exists() and tok2.exists():
                break
            time.sleep(0.05)

        client2 = RuntimeClient(str(sock2), str(tok2))
        client2.connect()
        st_a = client2.get_state("driverrun-dr-cross-model-a")
        assert st_a["state"] == "completed"

        receipt2 = client2.command(
            "run_approved_hermes_inspection",
            {
                "objective": "Inspect repo with Model B",
                "targetRoot": str(target_dir),
                "executable": str(fake_hermes2),
                "provider": "openrouter",
                "model": "anthropic/claude-3-7-sonnet",
                "approvalRequestId": "req-cross-model-b",
                "driverRunId": "dr-cross-model-b",
                "missionId": "m-cross-model-b",
                "taskId": "t-cross-model-b",
                "grantId": "g-cross-model-b",
                "leaseId": "l-cross-model-b",
                "claimId": "cl-cross-model-b",
                "policyDecisionId": "pd-cross-model-b",
            },
            idempotency_key="idem-cross-turn-2",
        )
        assert receipt2["status"] == "accepted", f"Receipt 2 error detail: {receipt2}"
        assert receipt2["result"]["cognitiveProvenance"]["model"] == "anthropic/claude-3-7-sonnet"
        assert receipt2["result"]["cognitiveProvenance"]["provider"] == "openrouter"

        st_b = client2.get_state("driverrun-dr-cross-model-b")
        assert st_b["state"] == "completed"

        client2.disconnect()
        p2.terminate()
        p2.wait(timeout=5)
    finally:
        shutil.rmtree(td, ignore_errors=True)
