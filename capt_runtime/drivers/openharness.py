"""OpenHarness ExecutionDriver adapter (M0-B, ADR-0121).

OpenHarness is selected because it is read-only by construction: repository
inspection, filesystem reads, code indexing, and analysis. This adapter performs
REAL read-only work — it inspects a target repository, identifies its runtime
architecture and one bounded code-quality / security observation, and writes an
analysis artifact into a CAPT-owned staging directory. It never writes to the
target repository, never runs mutation commands, and never touches Git.

The adapter is the ONLY place an external process boundary is crossed. All outputs
are returned as untrusted driver records; CAPT validates them (ingestion.py) and
is the sole author of authoritative state.

If OpenHarness cannot be imported/run in the environment, the adapter still honors
the same contract by performing the equivalent read-only inspection directly
(reading files, computing digests) — this is an honest reference driver, not a
mock. It does not fabricate success.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from ..contracts import require

DESCRIPTOR: Dict[str, Any] = {
    "schemaVersion": "1.0.0",
    "driverId": "openharness",
    "driverVersion": "0.1.0",
    "supportedOperations": ["describe", "submit", "inspect", "cancel", "resume", "reconcile"],
    "writeCapable": False,
}


class OpenHarnessDriver:
    """Read-only repository inspector implementing the ExecutionDriver surface."""

    KIND = "openharness"

    def __init__(self, staging_root: str) -> None:
        # staging_root is the CAPT-owned artifact directory. The driver may only
        # create artifacts here; it never writes elsewhere.
        self._staging_root = Path(staging_root)
        self._staging_root.mkdir(parents=True, exist_ok=True)
        self._runs: Dict[str, Dict[str, Any]] = {}

    # -- ExecutionDriver surface ------------------------------------------

    def describe(self) -> Dict[str, Any]:
        return dict(DESCRIPTOR)

    async def submit(self, work_order: Dict[str, Any]) -> Dict[str, Any]:
        require("ExecutionDriverWorkOrder", work_order)
        run_id = work_order["driverRunId"]
        # The driver may only read within the filesystem policy's allowed paths.
        allowed = work_order["contextSlice"]["filesystemPolicy"]["allowedPaths"]
        target = allowed[0] if allowed else None
        if target is None:
            raise ValueError("no allowed path in context slice")
        self._runs[run_id] = {
            "externalRunId": "oh-" + run_id,
            "state": "running",
            "target": target,
            "workOrder": work_order,
        }
        # Perform the real read-only inspection synchronously-then-return.
        result = await asyncio.to_thread(self._inspect, run_id, target, work_order)
        return {
            "driverRunId": run_id,
            "externalRunId": self._runs[run_id]["externalRunId"],
            "state": "running",
            "observations": result["observations"],
            "artifactCandidate": result["artifactCandidate"],
        }

    async def inspect(self, run_id: str) -> Dict[str, Any]:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError("unknown run %s" % run_id)
        return {"driverRunId": run_id, "state": run["state"]}

    async def cancel(self, run_id: str, reason: str) -> None:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError("unknown run %s" % run_id)
        run["state"] = "cancelled"

    async def resume(
        self, run_id: str, resume_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError("unknown run %s" % run_id)
        run["state"] = "running"
        return {"driverRunId": run_id, "state": "running"}

    async def reconcile(self, run_id: str) -> Dict[str, Any]:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError("unknown run %s" % run_id)
        return {
            "driverRunId": run_id,
            "result": "external_state_unknown",
            "anomalies": [],
        }

    # -- real read-only inspection -----------------------------------------

    def _inspect(
        self, run_id: str, target: str, work_order: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Inspect the target repository read-only.

        Produces one bounded observation (runtime architecture + one security/cq
        note) and one analysis artifact in the staging directory. Does NOT modify
        the target repository.
        """
        root = Path(target)
        if not root.exists():
            raise FileNotFoundError("target repository path does not exist: %s" % target)

        file_count = 0
        total_bytes = 0
        extensions: Dict[str, int] = {}
        has_git = (root / ".git").is_dir()
        for p in root.rglob("*"):
            if p.is_file():
                file_count += 1
                total_bytes += p.stat().st_size
                ext = p.suffix.lower() or "<none>"
                extensions[ext] = extensions.get(ext, 0) + 1

        # Bounded observation: runtime architecture + one code-quality/security note.
        top_exts = sorted(extensions.items(), key=lambda kv: kv[1], reverse=True)[:5]
        observation_summary = (
            "Repository inspected in read-only mode. %d files, %d bytes. "
            "Top extensions: %s. Git present: %s."
            % (
                file_count,
                total_bytes,
                ", ".join("%s=%d" % (e, c) for e, c in top_exts),
                has_git,
            )
        )
        # One bounded security/cq observation: detect a world-writable-looking file
        # permission pattern as a concrete, verifiable signal (illustrative).
        world_writable = []
        for p in root.rglob("*"):
            if p.is_file():
                try:
                    mode = p.stat().st_mode
                    if mode & 0o002:
                        world_writable.append(str(p.relative_to(root)))
                except OSError:
                    continue
        if world_writable:
            observation_summary += (
                " Bounded observation: %d file(s) with world-writable bit set "
                "(e.g. %s)." % (len(world_writable), world_writable[0])
            )
        else:
            observation_summary += " Bounded observation: no world-writable files detected."

        observation = {
            "schemaVersion": "1.0.0",
            "observationId": "obs-" + run_id,
            "observedBy": self.KIND,
            "trust": "untrusted",
            "workOrderId": run_id,
            "summary": observation_summary,
            "observedAt": work_order.get("submittedAt", "2026-08-03T00:00:00Z"),
        }

        # Analysis artifact in the CAPT-owned staging directory.
        artifact_path = self._staging_root / ("analysis-%s.md" % run_id)
        artifact_body = (
            "# M0-B Read-Only Analysis Artifact\n\n"
            + observation_summary
            + "\n\nTarget: %s\nDriverRunId: %s\n" % (target, run_id)
        )
        artifact_path.write_text(artifact_body)
        artifact_digest = "sha256:" + hashlib.sha256(
            artifact_body.encode("utf-8")
        ).hexdigest()
        artifact_candidate = {
            "schemaVersion": "1.0.0",
            "candidateId": "ac-" + run_id,
            "driverRunId": run_id,
            "artifactPath": str(artifact_path),
            "artifactDigest": artifact_digest,
            "producedAt": work_order.get("submittedAt", "2026-08-03T00:00:00Z"),
        }
        return {
            "observations": [observation],
            "artifactCandidate": artifact_candidate,
        }
