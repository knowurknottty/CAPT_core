"""VerificationEngine — orchestrates VSI-based verification decisions.

Flow:
1. Build current VSI for (repo, scope, command, environment).
2. Compare against most recent compatible record.
3. If equivalent and policy allows reuse -> VERIFICATION_CURRENT (reuse evidence,
   do NOT rerun). Report that confidence does not increase from re-running.
4. If different -> identify exact reasons -> select targeted scope -> run only
   the necessary verification -> store a new record (mark prior superseded).
"""
from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .identity import VerifiedStateIdentity, build_vsi, diff_vsi, VsiDiffReason
from .record import (
    VerificationRecord, VerificationEvidence, VerificationStatus, VerificationPolicy,
)
from .scope import (
    VerificationScope, map_paths_to_scopes, select_scope_for_changes, command_for_scope,
)
from .store import VerificationStore


# Default runner: executes the pytest command for a scope and writes evidence.
def _default_runner(repo: str, scope: VerificationScope, evidence_dir: str) -> VerificationEvidence:
    os.makedirs(evidence_dir, exist_ok=True)
    cmd = command_for_scope(scope)
    if cmd.startswith("no-op"):
        # documentation-only: no test run; evidence is the doc state.
        ev = VerificationEvidence(
            location=os.path.join(evidence_dir, f"{scope.value}.docstate.txt"),
            summary="documentation-only change; no test suite run required",
            passed=None, failed=None, command=cmd)
        with open(ev.location, "w") as f:
            f.write("documentation-only; verification reused/skipped per policy\n")
        return ev
    args = cmd.split()[2:]  # drop "python3 -m pytest"
    try:
        proc = subprocess.run(
            ["python3", "-m", "pytest", *args],
            cwd=repo, capture_output=True, text=True, timeout=600)
        out = proc.stdout + proc.stderr
        passed = failed = None
        for line in out.splitlines():
            if "passed" in line and "failed" not in line.split(" passed")[0]:
                # crude parse: "586 passed"
                if "passed" in line:
                    try:
                        passed = int(line.split(" passed")[0].strip().split()[-1])
                    except Exception:
                        passed = None
            if "failed" in line:
                try:
                    failed = int(line.split(" failed")[0].strip().split()[-1])
                except Exception:
                    failed = None
        ev_path = os.path.join(evidence_dir, f"{scope.value}.evidence.txt")
        with open(ev_path, "w") as f:
            f.write(out)
        return VerificationEvidence(
            location=ev_path, summary=f"exit={proc.returncode}",
            passed=passed, failed=failed, command=cmd)
    except Exception as exc:  # pragma: no cover
        ev_path = os.path.join(evidence_dir, f"{scope.value}.error.txt")
        with open(ev_path, "w") as f:
            f.write(f"runner error: {exc}\n")
        return VerificationEvidence(location=ev_path, summary=f"error: {exc}",
                                    passed=0, failed=None, command=cmd)


@dataclass
class VerifyResult:
    status: VerificationStatus
    vsi: VerifiedStateIdentity
    reused_record_id: Optional[str] = None
    reused_evidence: Optional[VerificationEvidence] = None
    ran_scope: Optional[VerificationScope] = None
    diff_reasons: List[Dict[str, str]] = field(default_factory=list)
    new_record_id: Optional[str] = None
    confidence_note: str = ""
    evidence: Optional[VerificationEvidence] = None


class VerificationEngine:
    def __init__(self, repo: str, store: Optional[VerificationStore] = None,
                 policy: Optional[VerificationPolicy] = None,
                 evidence_dir: Optional[str] = None,
                 runner: Optional[Callable] = None) -> None:
        self._repo = os.path.abspath(repo)
        self._store = store or VerificationStore(
            os.path.join(self._repo, ".capt_verify", "records.jsonl"))
        self._policy = policy or VerificationPolicy()
        self._evidence_dir = evidence_dir or os.path.join(self._repo, ".capt_verify", "evidence")
        self._runner = runner or (lambda scope: _default_runner(self._repo, scope, self._evidence_dir))

    def verify(self, scope: VerificationScope,
               command: Optional[str] = None,
               force: bool = False,
               environment: Optional[str] = None) -> VerifyResult:
        cmd = command or command_for_scope(scope)
        vsi = build_vsi(self._repo, scope, cmd, environment=environment)

        # 1. Try to reuse prior verification.
        if not force and self._policy.reuse_when_equivalent:
            compat = self._store.find_compatible(vsi)
            if compat is not None:
                ev = VerificationEvidence(**compat["evidence"])
                # A prior record whose evidence reports failures must never be
                # reused as current verification — that would relabel failed
                # evidence as passing. Require a clean prior result to reuse.
                if (ev.failed or 0) > 0:
                    pass
                else:
                    return VerifyResult(
                        status=VerificationStatus.VERIFICATION_CURRENT,
                        vsi=vsi,
                        reused_record_id=compat["record_id"],
                        reused_evidence=ev,
                        confidence_note=("Prior verification remains valid. Re-running the "
                                         "identical verification against an identical VSI does "
                                         "NOT increase confidence."),
                        evidence=ev,
                    )

        # 2. Not reusable -> identify why.
        latest = self._store.latest()
        diff_reasons: List[Dict[str, str]] = []
        affected_scopes = set()
        if latest is not None:
            rvsi = latest.get("vsi", {})
            old = VerifiedStateIdentity(
                repository=rvsi.get("repository", ""),
                project_id=rvsi.get("project_id", ""),
                active_branch=rvsi.get("active_branch", ""),
                head_commit=rvsi.get("head_commit", ""),
                working_tree_status=rvsi.get("working_tree_status", ""),
                scope_file_hashes=rvsi.get("scope_file_hashes", {}),
                dependency_state=rvsi.get("dependency_state", ""),
                runtime_identity=rvsi.get("runtime_identity", ""),
                operating_environment=rvsi.get("operating_environment", ""),
                verification_command=rvsi.get("verification_command", ""),
                verification_scope=rvsi.get("verification_scope", ""),
            )
            diff_reasons = diff_vsi(old, vsi)
            # Identify changed scoped files by CONTENT, not by path set. A
            # same-path in-place edit changes file content but not the set of
            # paths, so a symmetric-difference of path sets would be empty and
            # route a real code change to docs-only verification. Compare the
            # per-path content hashes instead.
            changed = {
                p for p in set(vsi.scope_file_hashes) | set(old.scope_file_hashes)
                if vsi.scope_file_hashes.get(p) != old.scope_file_hashes.get(p)
            }
            affected_scopes = map_paths_to_scopes(changed)

        if force:
            diff_reasons.append({"reason": VsiDiffReason.REQUESTED_BY_USER,
                                 "detail": "--force requested"})

        # 3. Select targeted scope to run.
        if latest is None:
            # First verification of this state: run the requested scope.
            run_scope = scope
        else:
            run_scope = self._policy.decide_scope(diff_reasons, affected_scopes)
            # If the requested scope is narrower than the selected one, prefer the
            # requested scope when the change is within it (avoid over-running).
            if run_scope == VerificationScope.SUITE and scope != VerificationScope.FULL:
                run_scope = scope

        # 4. Run only the necessary verification.
        evidence = self._runner(run_scope)
        # Failed evidence must not be recorded as a clean (re)verification.
        # When the runner reports failures, mark the record as failed so it can
        # never be reused as current verification downstream.
        if (evidence.failed or 0) > 0:
            status = VerificationStatus.VERIFICATION_INVALIDATED
            confidence = 0.0
        else:
            status = VerificationStatus.VERIFICATION_REQUIRED
            confidence = 1.0
        rec_id = f"vr-{uuid.uuid4().hex[:12]}"
        # On the run-path we always (re-)verified because the state changed or
        # this is the first verification. Reuse (CURRENT) is handled by the early
        # return above. Doc-only scopes still report REQUIRED when a change was
        # detected; they simply don't invoke the test suite (see runner).
        rec = VerificationRecord(
            record_id=rec_id, vsi=vsi, status=status.value, evidence=evidence,
            confidence=confidence)
        self._store.add(rec)
        # Mark the prior same-scope record as superseded (not the global latest,
        # which may belong to a different scope and must remain reusable).
        prior_same_scope = self._store.latest_for_scope(vsi.verification_scope)
        if prior_same_scope is not None and prior_same_scope.get("record_id") != rec_id:
            self._store.mark_superseded(prior_same_scope["record_id"], rec_id)

        return VerifyResult(
            status=status, vsi=vsi, ran_scope=run_scope,
            diff_reasons=diff_reasons, new_record_id=rec_id,
            confidence_note=("New evidence collected for changed state. Confidence "
                             "increased only because state changed and was re-verified."),
            evidence=evidence,
        )
