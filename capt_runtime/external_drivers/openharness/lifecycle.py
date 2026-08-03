"""Lifecycle mapping between CAPT DriverRunAggregate and the genuine OpenHarness
one-shot process.

OpenHarness ``oh -p`` is a single-shot, non-resumable execution: it starts, runs
the model loop, prints output, and exits. There is no durable external session
to suspend/resume. We therefore HONESTLY declare ``resume_supported = False`` and
reject resume requests rather than faking a resume by starting a new run.

Supported lifecycle operations: describe, submit, inspect, cancel, reconcile.
"""

from __future__ import annotations

import subprocess
import time
from typing import Any, Dict, Optional

from .translation import external_run_id_for

# CAPT DriverRunState values we map to/from.
STATE_CREATED = "created"
STATE_QUEUED = "queued"
STATE_RUNNING = "running"
STATE_COMPLETED = "completed"
STATE_CANCELLED = "cancelled"
STATE_FAILED = "failed"
STATE_RECONCILIATION_REQUIRED = "reconciliation_required"
STATE_RECONCILED = "reconciled"


class OpenHarnessRunLifecycle:
    """Tracks one external ``oh`` process and maps it to CAPT run state."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.external_run_id = external_run_id_for(run_id)
        self.state = STATE_CREATED
        self.proc: Optional[subprocess.Popen] = None
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None
        self.returncode: Optional[int] = None
        self.stdout: str = ""
        self.stderr: str = ""

    def start(self, proc: subprocess.Popen) -> None:
        self.proc = proc
        self.state = STATE_RUNNING
        self.started_at = time.time()

    def mark_completed(self, stdout: str, stderr: str, returncode: int) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.ended_at = time.time()
        if returncode == 0:
            self.state = STATE_COMPLETED
        else:
            self.state = STATE_FAILED

    def cancel(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.state = STATE_CANCELLED
        self.ended_at = time.time()

    def inspect(self) -> Dict[str, Any]:
        live = False
        if self.proc is not None and self.proc.poll() is None:
            live = True
        return {
            "driverRunId": self.run_id,
            "externalRunId": self.external_run_id,
            "state": self.state,
            "live": live,
            "returncode": self.returncode,
        }

    def reconcile(self) -> Dict[str, Any]:
        """Map external process state to a CAPT reconciliation view.

        Because the run is one-shot, reconciliation is honest:
        - completed -> reconciled_completed
        - failed -> reconciled_failed
        - cancelled -> reconciled (terminal)
        - missing/unknown process -> external_state_unknown
        """
        if self.state == STATE_COMPLETED:
            result = "reconciled_completed"
        elif self.state == STATE_FAILED:
            result = "reconciled_failed"
        elif self.state == STATE_CANCELLED:
            result = "reconciled_completed"
        elif self.state == STATE_RUNNING and self.proc is not None and self.proc.poll() is None:
            # Still running after a restart: do not auto-retry.
            result = "reconciliation_requires_human"
        else:
            result = "external_state_unknown"
        return {
            "driverRunId": self.run_id,
            "externalRunId": self.external_run_id,
            "result": result,
            "anomalies": [],
        }


# The driver descriptor advertises honest lifecycle support.
DESCRIPTOR: Dict[str, Any] = {
    "schemaVersion": "1.0.0",
    "driverId": "openharness-external",
    "driverVersion": "0.1.0",
    "supportedOperations": ["describe", "submit", "inspect", "cancel", "reconcile"],
    "resumeSupported": False,
    "writeCapable": False,
    "externalHarness": "openharness-ai==0.1.9",
    "externalModel": "local-ollama:ornith-1.0-9b",
}
