"""End-to-end governed proof: real Hermes runtime as an external ExecutionDriver.

Runs the complete frozen M0-B path with the Hermes driver substituted for the
reference driver, and records the full model-turn ownership trace.

    MissionCreated -> PolicyEvaluated -> CapabilityGranted -> LeaseActivated
    -> TaskTransitioned -> DriverRunCreated -> ContextSliceBuilt
    -> LeaseRevalidated -> HermesInvoked (real process)
    -> UntrustedObservationReturned -> ObservationValidated
    -> ArtifactValidated -> VerificationCompleted -> ClaimGuardDecision
    -> CheckpointCreated -> ProcessRestart(separate process) -> Replay
    -> Reconciled

No repository mutation. Staging-only artifact. Read-only capability grants.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "contracts" / "generated" / "python"))

from capt_runtime.capability import verify_lease  # noqa: E402
from capt_runtime.checkpoint import create_checkpoint  # noqa: E402
from capt_runtime.driver_host import DriverHost, tree_digest  # noqa: E402
from capt_runtime.driver_run import DriverRunAggregate  # noqa: E402
from capt_runtime.drivers.hermes import (  # noqa: E402
    DESCRIPTOR as HERMES_DESCRIPTOR,
    HermesDriver,
    probe_hermes_identity,
    resolve_hermes_executable,
)
from capt_runtime.drivers.openharness import (  # noqa: E402
    DESCRIPTOR as REF_DESCRIPTOR,
    OpenHarnessDriver,
)
from capt_runtime.drivers.registry import DriverRegistry  # noqa: E402
from capt_runtime.reconciliation import reconcile  # noqa: E402
from capt_runtime.replay import (  # noqa: E402
    checkpoint_replay,
    full_replay,
    replay_equivalent,
)
from capt_runtime.scenario import build_scenario  # noqa: E402
from capt_runtime.store import EventStore  # noqa: E402

TRACE: list = []


def step(name: str, **fields) -> None:
    TRACE.append({"step": name, "at": _now(), **fields})


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _lease(repo: str, lease_id: str = "l-hermes-1"):
    return {
        "leaseId": lease_id,
        "grantId": "g-hermes-1",
        "driverId": "hermes",
        "missionId": "m-hermes-1",
        "taskId": "t-hermes-1",
        "operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate",
                       "AnalysisOnly"],
        "scope": {"kind": "filesystem", "rootPath": repo, "recursive": True,
                  "allowedPaths": [repo]},
        "budget": {"maxSeconds": 600},
        "validFrom": "2026-01-01T00:00:00Z",
        "validUntil": "2030-01-01T00:00:00Z",
        "status": "active",
        "revoked": False,
    }


def _context_lease(lease):
    return {
        "leaseId": lease["leaseId"],
        "operations": lease["operations"],
        "scope": lease["scope"],
        "validFrom": lease["validFrom"],
        "validUntil": lease["validUntil"],
    }


def make_fixture(root: Path) -> Path:
    repo = root / "fixture-repo"
    (repo / "src").mkdir(parents=True)
    (repo / "README.md").write_text("# fixture\n\nA tiny fixture repository.\n")
    (repo / "src" / "app.py").write_text(
        "def handler(event):\n    return {'ok': True}\n"
    )
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.0.1"\n'
    )
    return repo


def run_driver(driver, driver_id: str, descriptor, repo: Path, staging: Path,
               run_id: str, store: EventStore) -> dict:
    reg = DriverRegistry()
    reg.register(descriptor)
    step("DriverRegistered", driverId=driver_id,
         registered=reg.is_registered(driver_id))

    host = DriverHost(reg, str(staging), str(repo))
    host.select_driver(driver)

    before = tree_digest(str(repo))
    step("TargetHashedBefore", digest=before)

    lease = _lease(str(repo))
    lease["driverId"] = driver_id
    step("CapabilityLeaseIssued", leaseId=lease["leaseId"],
         operations=lease["operations"], scope=lease["scope"]["kind"])

    ctx = host.build_context(
        _context_lease(lease),
        ["terminal"],
        {"maxSeconds": 240, "maxArtifacts": 1, "maxObservations": 10},
        [{"artifactPath": str(staging / ("x-%s.md" % run_id)),
          "artifactKind": "report"}],
        {"onUnexpectedWrite": "fail"},
    )
    step("ContextSliceBuilt", keys=sorted(ctx.keys()),
         writesAllowed=ctx["filesystemPolicy"]["writesAllowed"],
         egressAllowed=ctx.get("networkPolicy", {}).get("egressAllowed"))

    wo = {
        "schemaVersion": "1.0.0",
        "driverRunId": run_id,
        "driverId": driver_id,
        "missionId": "m-hermes-1",
        "taskId": "t-hermes-1",
        "workOrderVersion": 1,
        "contextSlice": ctx,
        "operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate",
                       "AnalysisOnly"],
    }
    step("DriverWorkOrderCreated", driverRunId=run_id, operations=wo["operations"])

    state = DriverRunAggregate.create(
        {"driverRunId": run_id, "driverId": driver_id,
         "missionId": "m-hermes-1", "taskId": "t-hermes-1"}
    )
    state = DriverRunAggregate.transition(state, "queued")
    state = DriverRunAggregate.transition(state, "running")
    step("DriverRunTransitioned", state=state["state"])

    verify_lease(
        lease, now=_now(), driver_id=driver_id, mission_id="m-hermes-1",
        task_id="t-hermes-1", operations=wo["operations"],
        resource_path=str(repo),
    )
    step("CapabilityRevalidatedBeforeDispatch", ok=True)

    t0 = time.time()
    out = host.dispatch(wo, ctx, state, now=_now(), lease=lease)
    elapsed = time.time() - t0
    diag = out.get("diagnostics", {})
    step("DriverInvoked", driverId=driver_id, externalRunId=out.get("externalRunId"),
         externalPid=diag.get("externalPid"), exitCode=diag.get("exitCode"),
         elapsedSeconds=round(elapsed, 2), envKeys=diag.get("envKeys"))

    seen: dict = {}
    ing = host.ingest(out, run_id, "m-hermes-1", "t-hermes-1", seen,
                      expected_observed_by=driver_id)
    step("UntrustedObservationIngested",
         observations=len(ing["observations"]),
         artifacts=len(ing["artifacts"]),
         trust=ing["observations"][0]["trust"] if ing["observations"] else None)

    vr = host.verify(before, ing["artifacts"][0]["path"],
                     ing["artifacts"][0]["digest"], driver_id)
    step("VerificationCompleted", status=vr["status"]["kind"],
         checks=vr["_view"]["checks"], trust=vr["_view"]["trust"])

    claim = host.propose_bounded_claim("Repository inspected in read-only mode.")
    step("ClaimGuardDecision", accepted=True, statement=claim)

    overclaim_rejected = False
    try:
        host.propose_bounded_claim("The issue was fixed.")
    except Exception as exc:
        overclaim_rejected = True
        step("ClaimGuardOverclaimRejected", error=type(exc).__name__)
    assert overclaim_rejected, "ClaimGuard failed to reject an overclaim"

    after = tree_digest(str(repo))
    step("TargetHashedAfter", digest=after, unchanged=(before == after))
    assert before == after, "target repository mutated during read-only proof"

    rec = reconcile(
        state,
        [{"eventType": "DriverRunStateChanged", "payload": {"toState": "completed"}}],
        ing["observations"], artifact_present=True, lease_valid=True,
        budget_valid=True,
    )
    step("Reconciled", result=rec["result"])

    return {
        "driverId": driver_id,
        "observationSummary": ing["observations"][0]["summary"],
        "artifactPath": ing["artifacts"][0]["path"],
        "artifactDigest": ing["artifacts"][0]["digest"],
        "verification": vr,
        "claim": claim,
        "reconcile": rec,
        "before": before,
        "after": after,
        "diagnostics": diag,
    }


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="capt-hermes-proof-"))
    repo = make_fixture(root)
    staging = root / "staging"
    staging.mkdir()
    db = str(root / "ledger.db")

    exe = resolve_hermes_executable()
    ident = probe_hermes_identity(exe)
    step("HermesRuntimeIdentified", executable=exe,
         version=ident["stdout"].splitlines()[0] if ident["stdout"] else None,
         exitCode=ident["exitCode"])

    # --- governed mission/policy/capability/task path (frozen M0-A scenario) ---
    scenario = build_scenario(db)
    step("MissionAndCapabilityPathExecuted",
         eventTypes=scenario["eventTypes"],
         headSequence=scenario["headSequence"],
         checkpointId=scenario["checkpointId"])

    store = EventStore(db)

    # --- real Hermes as external ExecutionDriver ---
    hermes_result = run_driver(
        HermesDriver(str(staging), toolsets="terminal"),
        "hermes", HERMES_DESCRIPTOR, repo, staging, "dr-hermes-1", store,
    )

    # --- checkpoint + separate-process replay ---
    full = full_replay(store)
    manifest = create_checkpoint(store, "cp-hermes", _now(), "sha256:" + "0" * 64)
    partial = checkpoint_replay(store, manifest)
    step("CheckpointCreated", checkpointId=manifest.get("checkpointId"),
         replayEquivalent=replay_equivalent(full, partial),
         fullApplied=full.applied, tailApplied=partial.applied)
    store.close()

    restart = subprocess.run(
        [sys.executable, "-m", "tests.capt_runtime.restart_process", db],
        capture_output=True, text=True, cwd=str(REPO),
        env={**os.environ, "PYTHONPATH": str(REPO)},
    )
    step("SeparateProcessRestartReplay", exitCode=restart.returncode,
         stdout=restart.stdout.strip()[:400],
         stderr=restart.stderr.strip()[-300:] if restart.returncode else "")
    if restart.returncode != 0:
        raise SystemExit("restart/replay proof failed")

    # --- swap proof: same bounded work order through the reference driver ---
    ref_result = run_driver(
        OpenHarnessDriver(str(staging)),
        "openharness", REF_DESCRIPTOR, repo, staging, "dr-ref-1",
        EventStore(db),
    )

    semantics = {
        "bothVerified": (hermes_result["verification"]["status"]["kind"]
                         == ref_result["verification"]["status"]["kind"]
                         == "verified"),
        "bothRepoUnchanged": (hermes_result["before"] == hermes_result["after"]
                              and ref_result["before"] == ref_result["after"]),
        "bothSameBoundedClaim": hermes_result["claim"] == ref_result["claim"],
        "bothReconciledCompleted": (hermes_result["reconcile"]["result"]
                                    == ref_result["reconcile"]["result"]
                                    == "reconciled_completed"),
        "artifactsDistinct": (hermes_result["artifactPath"]
                              != ref_result["artifactPath"]),
    }
    step("SwapProofCompleted", **semantics)
    if not all(semantics.values()):
        raise SystemExit("swap proof semantics mismatch")

    report = {
        "hermesRuntime": ident,
        "hermes": hermes_result,
        "reference": ref_result,
        "swapSemantics": semantics,
        "trace": TRACE,
        "fixtureRoot": str(root),
    }
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
