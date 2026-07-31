"""Vendor-neutral governed deployment execution.

The adapter contract deliberately separates governance from the third-party
program that performs a deployment. CAPT owns transaction boundaries, policy,
evidence, rollback decisions, and lifecycle claims. The adapter owns only the
backend-specific invocation details.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from capt_solo.ctp.journal import CTPRuntime, Receipt


class DeploymentError(RuntimeError):
    """Raised when a governed deployment cannot safely proceed."""


@dataclass(frozen=True)
class DeploymentRequest:
    adapter: str
    target: str
    artifact: str
    command: Sequence[str]
    verify_command: Sequence[str] = field(default_factory=tuple)
    rollback_command: Sequence[str] = field(default_factory=tuple)
    working_directory: Optional[str] = None
    environment: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: int = 300
    dry_run: bool = True
    actor: str = ""
    reason: str = ""
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass(frozen=True)
class DeploymentPlan:
    adapter: str
    target: str
    artifact: str
    executable: str
    command: List[str]
    verify_command: List[str]
    rollback_command: List[str]
    working_directory: str
    timeout_seconds: int
    dry_run: bool
    digest: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeploymentEvidence:
    phase: str
    command: List[str]
    returncode: Optional[int]
    stdout_sha256: str
    stderr_sha256: str
    started_at: float
    duration_ms: float
    dry_run: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeploymentResult:
    status: str
    tx_id: str
    receipt: Receipt
    plan: DeploymentPlan
    evidence: List[DeploymentEvidence]
    rollback_attempted: bool
    rollback_succeeded: Optional[bool]
    production_proven: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "tx_id": self.tx_id,
            "receipt": self.receipt.to_dict(),
            "plan": self.plan.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "rollback_attempted": self.rollback_attempted,
            "rollback_succeeded": self.rollback_succeeded,
            "production_proven": self.production_proven,
        }


class DeploymentAdapter(ABC):
    """Backend contract for an externally implemented deployment capability."""

    name: str

    @abstractmethod
    def plan(self, request: DeploymentRequest) -> DeploymentPlan:
        raise NotImplementedError

    @abstractmethod
    def preflight(self, plan: DeploymentPlan) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def execute(self, plan: DeploymentPlan) -> DeploymentEvidence:
        raise NotImplementedError

    @abstractmethod
    def verify(self, plan: DeploymentPlan) -> DeploymentEvidence:
        raise NotImplementedError

    @abstractmethod
    def rollback(self, plan: DeploymentPlan) -> DeploymentEvidence:
        raise NotImplementedError

    def collect_evidence(self, evidence: Sequence[DeploymentEvidence]) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in evidence]


class LocalScriptDeploymentAdapter(DeploymentAdapter):
    """Reference adapter for a pre-existing local deployment CLI or script.

    This adapter never uses a shell. The executable must be explicitly allowlisted,
    arguments are passed as an argv vector, and only declared environment variables
    are inherited. It is suitable as a reference implementation and fixture target;
    successful fixture execution does not establish production deployment proof.
    """

    name = "local-script"

    def __init__(self, allowed_executables: Sequence[str]) -> None:
        if not allowed_executables:
            raise ValueError("at least one executable must be allowlisted")
        self._allowed = {str(Path(item).expanduser()) for item in allowed_executables}

    def _resolve_executable(self, command: Sequence[str]) -> str:
        if not command:
            raise DeploymentError("deployment command is empty")
        requested = str(command[0])
        resolved = shutil.which(requested) if os.path.sep not in requested else requested
        if not resolved:
            raise DeploymentError(f"executable not found: {requested}")
        resolved_path = str(Path(resolved).expanduser().resolve())
        allowed_resolved = {
            str(Path(item).expanduser().resolve())
            for item in self._allowed
            if Path(item).expanduser().exists()
        }
        allowed_names = {Path(item).name for item in self._allowed}
        if resolved_path not in allowed_resolved and Path(requested).name not in allowed_names:
            raise DeploymentError(f"executable is not allowlisted: {requested}")
        return resolved_path

    @staticmethod
    def _digest(data: Mapping[str, Any]) -> str:
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def plan(self, request: DeploymentRequest) -> DeploymentPlan:
        if not request.actor.strip():
            raise DeploymentError("deployment requires a named actor")
        if not request.reason.strip():
            raise DeploymentError("deployment requires a reason")
        if request.timeout_seconds < 1 or request.timeout_seconds > 3600:
            raise DeploymentError("timeout_seconds must be between 1 and 3600")
        executable = self._resolve_executable(request.command)
        workdir = str(Path(request.working_directory or os.getcwd()).expanduser().resolve())
        if not Path(workdir).is_dir():
            raise DeploymentError(f"working directory does not exist: {workdir}")
        payload = {
            "adapter": self.name,
            "target": request.target,
            "artifact": request.artifact,
            "command": [executable, *list(request.command[1:])],
            "verify_command": list(request.verify_command),
            "rollback_command": list(request.rollback_command),
            "working_directory": workdir,
            "timeout_seconds": request.timeout_seconds,
            "dry_run": request.dry_run,
        }
        return DeploymentPlan(digest=self._digest(payload), executable=executable, **payload)

    def preflight(self, plan: DeploymentPlan) -> Dict[str, Any]:
        artifact = Path(plan.artifact).expanduser()
        return {
            "ok": bool(plan.target.strip()) and artifact.exists(),
            "target_present": bool(plan.target.strip()),
            "artifact_exists": artifact.exists(),
            "working_directory_exists": Path(plan.working_directory).is_dir(),
            "executable": plan.executable,
            "plan_digest": plan.digest,
        }

    def _run(self, phase: str, command: Sequence[str], plan: DeploymentPlan) -> DeploymentEvidence:
        started = time.time()
        if not command:
            return DeploymentEvidence(
                phase=phase,
                command=[],
                returncode=0,
                stdout_sha256=hashlib.sha256(b"").hexdigest(),
                stderr_sha256=hashlib.sha256(b"").hexdigest(),
                started_at=started,
                duration_ms=0.0,
                dry_run=plan.dry_run,
            )
        resolved = self._resolve_executable(command)
        argv = [resolved, *list(command[1:])]
        if plan.dry_run:
            return DeploymentEvidence(
                phase=phase,
                command=argv,
                returncode=None,
                stdout_sha256=hashlib.sha256(b"").hexdigest(),
                stderr_sha256=hashlib.sha256(b"").hexdigest(),
                started_at=started,
                duration_ms=round((time.time() - started) * 1000, 2),
                dry_run=True,
            )
        env = {"PATH": os.environ.get("PATH", ""), "LANG": os.environ.get("LANG", "C")}
        proc = subprocess.run(
            argv,
            cwd=plan.working_directory,
            env=env,
            capture_output=True,
            text=False,
            shell=False,
            timeout=plan.timeout_seconds,
            check=False,
        )
        return DeploymentEvidence(
            phase=phase,
            command=argv,
            returncode=proc.returncode,
            stdout_sha256=hashlib.sha256(proc.stdout).hexdigest(),
            stderr_sha256=hashlib.sha256(proc.stderr).hexdigest(),
            started_at=started,
            duration_ms=round((time.time() - started) * 1000, 2),
            dry_run=False,
        )

    def execute(self, plan: DeploymentPlan) -> DeploymentEvidence:
        return self._run("execute", plan.command, plan)

    def verify(self, plan: DeploymentPlan) -> DeploymentEvidence:
        return self._run("verify", plan.verify_command, plan)

    def rollback(self, plan: DeploymentPlan) -> DeploymentEvidence:
        return self._run("rollback", plan.rollback_command, plan)


class GovernedDeploymentExecutor:
    """Run one deployment inside a CTP transaction and preserve failure truthfully."""

    def __init__(self, ctp: CTPRuntime) -> None:
        self._ctp = ctp

    def run(self, adapter: DeploymentAdapter, request: DeploymentRequest) -> DeploymentResult:
        plan = adapter.plan(request)
        tx_id = self._ctp.begin(
            correlation_id=request.correlation_id,
            idempotency_key=request.idempotency_key,
            meta={
                "kind": "deployment",
                "adapter": adapter.name,
                "target": request.target,
                "artifact": request.artifact,
                "actor": request.actor,
                "reason": request.reason,
                "plan_digest": plan.digest,
                "dry_run": request.dry_run,
            },
        )
        evidence: List[DeploymentEvidence] = []
        rollback_attempted = False
        rollback_succeeded: Optional[bool] = None
        try:
            preflight = adapter.preflight(plan)
            self._ctp.note(tx_id, json.dumps({"phase": "preflight", **preflight}, sort_keys=True))
            if not self._ctp.validate(tx_id, preflight):
                raise DeploymentError("deployment preflight failed")

            execution = adapter.execute(plan)
            evidence.append(execution)
            execution_ok = execution.returncode in (0, None)
            self._ctp.note(tx_id, json.dumps(execution.to_dict(), sort_keys=True))
            if not self._ctp.validate(tx_id, {"ok": execution_ok}):
                raise DeploymentError("deployment execution failed")

            verification = adapter.verify(plan)
            evidence.append(verification)
            verification_ok = verification.returncode in (0, None)
            self._ctp.note(tx_id, json.dumps(verification.to_dict(), sort_keys=True))
            if not self._ctp.validate(tx_id, {"ok": verification_ok}):
                raise DeploymentError("deployment verification failed")

            receipt = self._ctp.commit(tx_id)
            return DeploymentResult(
                status="dry_run" if request.dry_run else "committed",
                tx_id=tx_id,
                receipt=receipt,
                plan=plan,
                evidence=evidence,
                rollback_attempted=False,
                rollback_succeeded=None,
                production_proven=False,
            )
        except Exception as exc:
            if plan.rollback_command:
                rollback_attempted = True
                try:
                    rollback_evidence = adapter.rollback(plan)
                    evidence.append(rollback_evidence)
                    rollback_succeeded = rollback_evidence.returncode in (0, None)
                    self._ctp.note(tx_id, json.dumps(rollback_evidence.to_dict(), sort_keys=True))
                except Exception as rollback_exc:
                    rollback_succeeded = False
                    self._ctp.note(tx_id, f"rollback_error:{type(rollback_exc).__name__}:{rollback_exc}")
            self._ctp.note(tx_id, f"deployment_error:{type(exc).__name__}:{exc}")
            receipt = self._ctp.abort(tx_id)
            return DeploymentResult(
                status="aborted",
                tx_id=tx_id,
                receipt=receipt,
                plan=plan,
                evidence=evidence,
                rollback_attempted=rollback_attempted,
                rollback_succeeded=rollback_succeeded,
                production_proven=False,
            )
