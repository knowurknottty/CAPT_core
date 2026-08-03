#!/usr/bin/env python3.12
"""Gate 0 — CAPT Core runtime activation proof (evidence-bound).

Exercises every smoke required by the desktop workflow Gate 1 runtime
activation proof and emits a JSON evidence record. Read-only against a
temporary ledger; does not touch the CAPT_core worktree or any real mission.

Run:
  python3.12 desktop/gate0_activation.py
Exit 0 = runtime proven active; non-zero = CAPT_RUNTIME_NOT_ACTIVE.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "contracts" / "generated" / "python"))

EVIDENCE: dict = {"gate": "Gate0", "checks": [], "status": "CAPT_RUNTIME_NOT_ACTIVE"}


def check(name: str, ok: bool, detail: str = "") -> bool:
    EVIDENCE["checks"].append(
        {"name": name, "ok": bool(ok), "detail": str(detail)[:500]}
    )
    return ok


def main() -> int:
    try:
        import capt_runtime
        from capt_runtime.driver_host import DriverHost, tree_digest
        from capt_runtime.drivers.registry import DriverRegistry
        from capt_runtime.drivers.openharness import OpenHarnessDriver, DESCRIPTOR as REF
        from capt_runtime.drivers.hermes import (
            HermesDriver,
            DESCRIPTOR as HER,
            resolve_hermes_executable,
            probe_hermes_identity,
        )
        from capt_runtime.store import EventStore
        from capt_runtime.checkpoint import create_checkpoint
        from capt_runtime.replay import full_replay, checkpoint_replay, replay_equivalent
        from capt_runtime.scenario import build_scenario
        from capt_runtime.capability import verify_lease
        from capt_runtime.verification import build_verification_result, guard_claim
        from capt_runtime.ingestion import (
            validate_observation,
            validate_artifact_candidate,
        )
        from capt_runtime.contracts import require
    except Exception as e:  # noqa: BLE001
        check("imports_resolve", False, repr(e))
        print(json.dumps(EVIDENCE, indent=2))
        return 1

    check("imports_resolve", True, capt_runtime.__file__)

    # canonical contracts available
    try:
        from contracts.generated.python.capt_contracts import spec, validate

        check("generated_contracts_available", True, spec.__name__)
    except Exception as e:  # noqa: BLE001
        check("generated_contracts_available", False, repr(e))

    tmp = Path(tempfile.mkdtemp(prefix="capt-gate0-"))
    db = str(tmp / "ledger.db")

    # event-ledger smoke
    try:
        store = EventStore(db)
        scenario = build_scenario(db)
        check(
            "event_ledger_smoke",
            True,
            "eventTypes=%s head=%s cp=%s"
            % (
                scenario["eventTypes"],
                scenario["headSequence"],
                scenario["checkpointId"],
            ),
        )
    except Exception as e:  # noqa: BLE001
        check("event_ledger_smoke", False, repr(e))
        store = None

    # checkpoint/replay smoke
    try:
        if store is None:
            raise RuntimeError("ledger unavailable; cannot replay")
        full = full_replay(store)
        manifest = create_checkpoint(store, "cp-gate0", _now(), "sha256:" + "0" * 64)
        partial = checkpoint_replay(store, manifest)
        check(
            "checkpoint_replay_smoke",
            True,
            "fullApplied=%s tailApplied=%s equivalent=%s"
            % (full.applied, partial.applied, replay_equivalent(full, partial)),
        )
    except Exception as e:  # noqa: BLE001
        check("checkpoint_replay_smoke", False, repr(e))

    # ClaimGuard + verification reachable
    try:
        claim_ok = guard_claim("Repository inspected in read-only mode.")
        overclaim_rejected = False
        try:
            guard_claim("The issue was fixed.")
        except Exception:
            overclaim_rejected = True
        check(
            "claimguard_reachable",
            bool(claim_ok) and overclaim_rejected,
            "bounded=%r overclaimRejected=%r" % (bool(claim_ok), overclaim_rejected),
        )
    except Exception as e:  # noqa: BLE001
        check("claimguard_reachable", False, repr(e))

    # verification reachable (use a real temp target + artifact)
    try:
        vrepo = tmp / "vrepo"
        vrepo.mkdir(parents=True, exist_ok=True)
        (vrepo / "f.txt").write_text("data\n")
        vart = tmp / "vart.md"
        vart.write_text("# artifact\n")
        import hashlib
        vart_digest = "sha256:" + hashlib.sha256(vart.read_bytes()).hexdigest()
        before = tree_digest(str(vrepo))
        vr = build_verification_result(
            str(vrepo),
            before,
            str(vart),
            vart_digest,
            "openharness",
        )
        check("verification_reachable", True, "status=%s" % vr["status"]["kind"])
    except Exception as e:  # noqa: BLE001
        check("verification_reachable", False, repr(e))

    # DriverRegistry + DriverHost reachable
    try:
        reg = DriverRegistry()
        reg.register(REF)
        host = DriverHost(reg, str(tmp / "staging"), str(tmp / "repo"))
        check(
            "driver_registry_host_reachable",
            reg.is_registered("openharness") and host is not None,
            "registered=%s" % reg.is_registered("openharness"),
        )
    except Exception as e:  # noqa: BLE001
        check("driver_registry_host_reachable", False, repr(e))

    # reference driver smoke (deterministic, in-process)
    try:
        reg2 = DriverRegistry()
        reg2.register(REF)
        host2 = DriverHost(reg2, str(tmp / "staging2"), str(tmp / "repo2"))
        host2.select_driver(OpenHarnessDriver(str(tmp / "staging2")))
        repo2 = tmp / "repo2"
        repo2.mkdir(parents=True, exist_ok=True)
        (repo2 / "README.md").write_text("# fixture\n")
        lease = {
            "leaseId": "g0", "grantId": "g0", "driverId": "openharness",
            "missionId": "m0", "taskId": "t0",
            "operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"],
            "scope": {"kind": "filesystem", "rootPath": str(repo2), "recursive": True,
                      "allowedPaths": [str(repo2)]},
            "budget": {"maxSeconds": 600},
            "validFrom": "2026-01-01T00:00:00Z", "validUntil": "2030-01-01T00:00:00Z",
            "status": "active", "revoked": False,
        }
        ctx = host2.build_context(
            {"leaseId": lease["leaseId"], "operations": lease["operations"],
             "scope": lease["scope"], "validFrom": lease["validFrom"],
             "validUntil": lease["validUntil"]},
            ["terminal"], {"maxSeconds": 60, "maxArtifacts": 1, "maxObservations": 10},
            [{"artifactPath": str(tmp / "staging2" / "x.md"), "artifactKind": "report"}],
            {"onUnexpectedWrite": "fail"},
        )
        wo = {
            "schemaVersion": "1.0.0", "driverRunId": "dr-g0", "driverId": "openharness",
            "missionId": "m0", "taskId": "t0", "workOrderVersion": 1,
            "contextSlice": ctx,
            "operations": lease["operations"],
        }
        verify_lease(lease, now=_now(), driver_id="openharness", mission_id="m0",
                     task_id="t0", operations=lease["operations"], resource_path=str(repo2))
        out = host2.dispatch(wo, ctx, {"state": "running"}, now=_now(), lease=lease)
        check(
            "reference_driver_smoke",
            out.get("externalRunId") is not None,
            "externalRunId=%s" % out.get("externalRunId"),
        )
    except Exception as e:  # noqa: BLE001
        check("reference_driver_smoke", False, repr(e))

    # Hermes driver reachable when available
    try:
        exe = resolve_hermes_executable()
        ident = probe_hermes_identity(exe)
        check(
            "hermes_driver_available",
            ident["exitCode"] == 0,
            "exe=%s version=%s"
            % (exe, (ident["stdout"].splitlines()[0] if ident["stdout"] else None)),
        )
    except Exception as e:  # noqa: BLE001
        check("hermes_driver_available", False, "unavailable: %r" % e)

    store.close() if store else None

    # generated-contract drift
    try:
        proc = subprocess.run(
            [sys.executable, str(REPO / "contracts" / "tools" / "check_drift.py")],
            capture_output=True, text=True, cwd=str(REPO),
        )
        check("contract_drift_clean", proc.returncode == 0,
              (proc.stdout or proc.stderr).strip()[:400])
    except Exception as e:  # noqa: BLE001
        check("contract_drift_clean", False, repr(e))

    all_ok = all(c["ok"] for c in EVIDENCE["checks"])
    EVIDENCE["status"] = "CAPT_RUNTIME_ACTIVE" if all_ok else "CAPT_RUNTIME_NOT_ACTIVE"
    EVIDENCE["python"] = sys.version.split()[0]
    EVIDENCE["repo"] = str(REPO)
    EVIDENCE["head"] = _git_head(REPO)
    out_path = REPO / "desktop" / "gate0_evidence.json"
    out_path.write_text(json.dumps(EVIDENCE, indent=2))
    print(json.dumps(EVIDENCE, indent=2))
    return 0 if all_ok else 1


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _git_head(repo: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
