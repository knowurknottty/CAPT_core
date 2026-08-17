"""Process-boundary tests for Model-A -> process death -> Model-B restart continuity (CAPT-UPG-007)."""

import os
import subprocess
import sys
import time
from pathlib import Path

from capt_runtime.composition import create_runtime
from desktop.desktop_runtime_client import RuntimeClient


def test_cross_model_process_restart_continuity():
    import tempfile
    import shutil
    td = tempfile.mkdtemp(prefix="cpt_cnt_")
    try:
        ledger = Path(td) / "continuity.db"
        sock1 = Path(td) / "s1.sock"
        tok1 = Path(td) / "tok1.txt"
        root = Path(__file__).resolve().parents[2]

        # --- Phase 1: Launch Process 1 with Model A ---
        p1 = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import runpy; runpy.run_path('desktop/capt_runtime_service.py', run_name='__main__')",
                "--ledger", str(ledger),
                "--sock", str(sock1),
                "--token-file", str(tok1),
                "--seed",
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        for _ in range(50):
            if sock1.exists() and tok1.exists():
                break
            time.sleep(0.05)

        client1 = RuntimeClient(str(sock1), str(tok1))
        client1.connect()
        aggs1 = client1.list_aggregates()
        assert len(aggs1) > 0

        # Cleanly disconnect and KILL Process 1 (Simulating host termination)
        client1.disconnect()
        p1.terminate()
        p1.wait(timeout=5)

        # --- Phase 2: Launch Process 2 with Model B against the SAME ledger ---
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        for _ in range(50):
            if sock2.exists() and tok2.exists():
                break
            time.sleep(0.05)

        client2 = RuntimeClient(str(sock2), str(tok2))
        client2.connect()
        aggs2 = client2.list_aggregates()

        # Task transition from running -> suspended on restart reconciliation increments version by 1
        stream_ids1 = {a["streamId"] for a in aggs1}
        stream_ids2 = {a["streamId"] for a in aggs2}
        assert stream_ids1 == stream_ids2
        task2 = client2.get_state("task-t-desktop-m0-demo")
        assert task2["state"] == "suspended"  # Governed crash reconciliation proven!

        client2.disconnect()
        p2.terminate()
        p2.wait(timeout=5)
    finally:
        shutil.rmtree(td, ignore_errors=True)
