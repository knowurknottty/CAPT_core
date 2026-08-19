"""DriverHost (M0-B orchestration, ADR-0120/0123).

Wires the read-only proof scenario: build a ContextSlice, create the DriverRun,
dispatch the selected driver, ingest untrusted output, verify independently,
reconcile, and complete. The host is the ONLY place that touches CAPT aggregates
and the driver together; it enforces the trust boundary at every step.

It does NOT integrate multiple drivers, does NOT write to the target repository,
and does NOT grant the driver any aggregate-mutation authority.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from .context_slice import build_context_slice
from .authored_skills import (
    AuthoredSkillPackViolation, build_skill_context, load_capt_skills_lock,
    summarize_skill_context,
)
from .contracts import require
from .capability import check_work_order_operations, verify_lease
from .drivers.registry import DriverRegistry
from .ingestion import (
    validate_artifact_candidate,
    validate_observation,
    validate_receipt_candidate,
)
from .verification import build_verification_result, guard_claim


class DriverHost:
    def __init__(
        self,
        registry: DriverRegistry,
        staging_root: str,
        target_repo: str,
        memory_engine: Any = None,
        authored_skill_pack_root: Optional[str] = None,
        authored_skill_pack_lock: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.registry = registry
        self.staging_root = staging_root
        self.target_repo = target_repo
        self._driver = None  # set by select_driver
        self.memory_engine = memory_engine  # optional MemoryTriggerEngine
        self.authored_skill_pack_root = authored_skill_pack_root
        self.authored_skill_pack_lock = authored_skill_pack_lock
        self._prepared_skill_context: Optional[Dict[str, Any]] = None
        self._prepared_skill_names: tuple[str, ...] = ()

    def select_driver(self, driver) -> None:
        # driver is an ExecutionDriver instance (e.g. OpenHarnessDriver)
        self._driver = driver

    def prepare_authored_skills(self, skill_names: List[str]) -> Dict[str, Any]:
        """Verify and freeze selected authored-skill bytes before mutation.

        The returned value is provenance-only. The full verified text remains in
        memory on this host and is later copied into the governed ContextSlice;
        disk is not re-read between preflight and dispatch.
        """
        if not self.authored_skill_pack_root:
            raise AuthoredSkillPackViolation(
                "authored skill pack root is required when skills are selected"
            )
        lock = self.authored_skill_pack_lock or load_capt_skills_lock()
        context = build_skill_context(
            self.authored_skill_pack_root, lock, selected_names=skill_names
        )
        return self.bind_prepared_authored_skills(context, skill_names)

    def bind_prepared_authored_skills(
        self, context: Dict[str, Any], skill_names: List[str]
    ) -> Dict[str, Any]:
        """Bind an already verified execution snapshot without re-reading disk."""
        require("AuthoredSkillContext", context)
        actual_names = [str(item.get("name", "")) for item in context.get("skills", [])]
        if actual_names != list(skill_names):
            raise AuthoredSkillPackViolation(
                "prepared authored skill names differ from the verified snapshot"
            )
        self._prepared_skill_context = copy.deepcopy(context)
        self._prepared_skill_names = tuple(skill_names)
        summary = summarize_skill_context(context)
        assert summary is not None
        return summary

    # -- scenario steps ----------------------------------------------------

    def build_context(
        self,
        lease: Dict[str, Any],
        permitted_tools: List[str],
        budgets: Dict[str, Any],
        expected_artifacts: List[Dict[str, Any]],
        termination: Dict[str, Any],
        *,
        skill_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        fs_policy = {
            "rootPath": self.target_repo,
            "allowedPaths": [self.target_repo, self.staging_root],
            "writesAllowed": False,
        }
        net_policy = {"egressAllowed": False, "allowedHosts": []}
        skill_context = None
        if self._prepared_skill_context is not None:
            if skill_names is not None and tuple(skill_names) != self._prepared_skill_names:
                raise AuthoredSkillPackViolation(
                    "requested authored skills differ from the prepared snapshot"
                )
            skill_context = copy.deepcopy(self._prepared_skill_context)
        elif skill_names:
            # Direct/conformance callers may still request a one-shot verified
            # context. The governed model-operator path MUST preflight via
            # prepare_authored_skills() before authoritative mutation.
            if not self.authored_skill_pack_root:
                raise AuthoredSkillPackViolation(
                    "authored skill pack root is required when skills are selected"
                )
            lock = self.authored_skill_pack_lock or load_capt_skills_lock()
            skill_context = build_skill_context(
                self.authored_skill_pack_root, lock, selected_names=skill_names
            )
        return build_context_slice(
            lease=lease,
            filesystem_policy=fs_policy,
            permitted_tools=permitted_tools,
            budgets=budgets,
            expected_artifacts=expected_artifacts,
            termination_conditions=termination,
            network_policy=net_policy,
            skill_context=skill_context,
        )

    def dispatch(
        self,
        work_order: Dict[str, Any],
        context_slice: Dict[str, Any],
        driver_run_state: Dict[str, Any],
        *,
        now: str,
        lease: Dict[str, Any],
        budget: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Invoke the driver. Returns untrusted driver output.

        Before any external boundary crossing, CAPT re-validates the capability
        lease (ADR-0122): identity, scope, active status, operation coverage,
        path scope, and budget. A failed check raises CapabilityViolation and the
        driver is never contacted.
        """
        if self._driver is None:
            raise RuntimeError("no driver selected")
        # Mandatory memory gate: CAPT owns the trigger decision. Refuse dispatch
        # when memory is inactive, ContextPack missing/stale, consent/scope
        # violated, or context exceeds the hard-stop boundary.
        if self.memory_engine is not None:
            gate = self.memory_engine.require_memory_before_dispatch(
                work_order.get("missionId", ""),
                context_pack_digest=context_slice.get("contextPackRef", {}).get("contextPackDigest")
                if context_slice.get("contextPackRef") else None,
                policy_digest=work_order.get("memoryPolicyRef", {}).get("policyDigest")
                if work_order.get("memoryPolicyRef") else None,
                context_usage=context_slice.get("budgets", {}).get("maxTokens"),
                consent_ok=True,
                scope_ok=True,
            )
            # Attach the authorized slice reference the driver may consume.
            cs = dict(context_slice)
            cs["contextPackRef"] = {
                "contextPackId": gate["contextPackDigest"].replace("sha256:", "cp-"),
                "contextPackDigest": gate["contextPackDigest"],
                "selectedRecordCount": gate["selectedRecordCount"],
                "tokenBudget": context_slice.get("budgets", {}).get("maxTokens", 0),
            }
            wo = dict(work_order)
            wo["contextSlice"] = cs
            wo["memoryPolicyRef"] = {
                "policyVersion": self.memory_engine.policy.policy_version,
                "policyDigest": self.memory_engine.policy.policy_digest,
                "hardStopTriggerSteps": self.memory_engine.policy.hard_stop_trigger_steps,
            }
            # Reject structurally unsafe operations BEFORE schema validation / dispatch.
            check_work_order_operations(wo.get("operations", []))
            # Re-validate the lease immediately before the external call.
            verify_lease(
                lease,
                now=now,
                driver_id=wo.get("driverId", ""),
                mission_id=wo.get("missionId", ""),
                task_id=wo.get("taskId", ""),
                operations=wo.get("operations", []),
                resource_path=self.target_repo,
                budget=budget,
            )
            require("ExecutionDriverWorkOrder", wo)
            # Synchronous wrapper around the async driver for the conformance scenario.
            import asyncio

            return asyncio.run(self._driver.submit(wo))
        # Reject structurally unsafe operations BEFORE schema validation / dispatch.
        check_work_order_operations(work_order.get("operations", []))
        # Re-validate the lease immediately before the external call.
        verify_lease(
            lease,
            now=now,
            driver_id=work_order.get("driverId", ""),
            mission_id=work_order.get("missionId", ""),
            task_id=work_order.get("taskId", ""),
            operations=work_order.get("operations", []),
            resource_path=self.target_repo,
            budget=budget,
        )
        require("ExecutionDriverWorkOrder", work_order)
        wo = dict(work_order)
        wo["contextSlice"] = context_slice
        # Synchronous wrapper around the async driver for the conformance scenario.
        import asyncio

        return asyncio.run(self._driver.submit(wo))

    def ingest(
        self,
        driver_output: Dict[str, Any],
        driver_run_id: str,
        mission_id: str,
        task_id: str,
        seen: Dict[str, Dict[str, Any]],
        expected_observed_by: str,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {"observations": [], "artifacts": [], "receipts": []}
        for obs in driver_output.get("observations", []):
            v = validate_observation(
                obs, driver_run_id, mission_id, task_id, [self.staging_root], seen,
                expected_observed_by,
            )
            if not v.get("duplicate"):
                result["observations"].append(v["observation"])
        if "artifactCandidate" in driver_output:
            ac = validate_artifact_candidate(
                driver_output["artifactCandidate"], driver_run_id, self.staging_root
            )
            result["artifacts"].append(ac)
        for rc in driver_output.get("receipts", []):
            result["receipts"].append(
                validate_receipt_candidate(rc, driver_run_id)
            )
        return result

    def verify(
        self,
        before_digest: str,
        artifact_path: str,
        artifact_digest: str,
        observed_by: str,
        claim_id: Optional[str] = None,
        supporting_evidence_ids: Optional[list] = None,
        verified_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        return build_verification_result(
            self.target_repo, before_digest, artifact_path, artifact_digest, observed_by,
            claim_id=claim_id,
            supporting_evidence_ids=supporting_evidence_ids,
            verified_at=verified_at,
        )

    def propose_bounded_claim(self, statement: str) -> str:
        """ClaimGuard: only bounded statements accepted."""
        return guard_claim(statement)


def tree_digest(path: str) -> str:
    """Independent recursive content digest of a repository tree (before/after)."""
    root = Path(path)
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            try:
                h.update(p.resolve().as_posix().encode("utf-8"))
                h.update(p.read_bytes())
            except OSError:
                continue
    return "sha256:" + h.hexdigest()
