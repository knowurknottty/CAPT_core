#!/usr/bin/env python3
"""CAPT Solo v0.3 — Memory Review CLI.

Local CLI for inspecting and controlling memory, sessions, procedures,
prospective memory, and retrieval feedback.

Usage:
    capt memory list [--namespace NS] [--json]
    capt memory inspect <id> [--json]
    capt memory search <query> [--json]
    capt memory candidates [--json]
    capt memory conflicts [--json]
    capt memory pending [--json]
    capt memory promote <id> --state <state> --evidence <e1,e2> [--actor user]
    capt memory pin <id>
    capt memory archive <id>
    capt memory restore <id>
    capt memory explain <id> [--json]
    capt session list [--json]
    capt session status <id> [--json]
    capt session checkpoint <id> --next-action <text>
    capt session resume <id> [--json]
    capt session consolidate <id>
    capt session close <id>
    capt procedure list [--json]
    capt procedure inspect <id> [--json]
    capt procedure runs <id> [--json]
    capt prospective list [--json]
    capt prospective ready [--json]
    capt prospective resolve <id>
    capt retrieval feedback [--json]
    capt retrieval adaptation [--json]
    capt retrieval reset [--namespace NS]

All commands support --json for machine-readable output and return
nonzero exit codes on failure. No raw SQL is exposed. No credentials
are printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make the package importable when run as a script.
_SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SRC))

from capt_solo.api import (  # noqa: E402
    LifecycleManager,
    MemoryEngine,
)
from capt_solo.core.errors import CaptSoloError  # noqa: E402
from capt_solo.foundry import (  # noqa: E402
    ProofEngine, ProofRequirement, CapabilityRegistry, ClaimGuard, SkillFoundry,
    ValidationHarness, KnowledgeBubbleRuntime, Governance,
    SkillCurator, CompositionEngine,
)
from capt_solo.ctp.journal import CTPRuntime  # noqa: E402
from capt_runtime.composition import create_runtime  # noqa: E402
from capt_runtime import commands as runtime_commands  # noqa: E402
from capt_runtime.cli_ramp import default_state_dir  # noqa: E402
from capt_runtime.authored_skills import (  # noqa: E402
    AuthoredSkillPackViolation, load_capt_skills_lock, verify_skill_pack,
)
from capt_runtime.managed_skills import (  # noqa: E402
    ManagedSkillPackViolation, default_managed_skill_root,
    import_managed_skill_pack, verify_managed_skill_pack,
)


def _json_or_human(data: Any, as_json: bool) -> str:
    if as_json:
        return json.dumps(data, indent=2, default=str)
    return _humanize(data)


def _humanize(data: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(data, dict):
        lines = []
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}:")
                lines.append(_humanize(v, indent + 1))
            else:
                lines.append(f"{pad}{k}: {v}")
        return "\n".join(lines)
    if isinstance(data, list):
        if not data:
            return f"{pad}(empty)"
        return "\n".join(_humanize(x, indent) for x in data)
    return f"{pad}{data}"


def _ok(data: Any, as_json: bool) -> int:
    print(_json_or_human(data, as_json))
    return 0


def _fail(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="capt", description="CAPT Solo memory review CLI")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--version", action="version", version="capt-solo 0.5.0")
    sub = parser.add_subparsers(dest="group")

    # memory
    m = sub.add_parser("memory")
    ms = m.add_subparsers(dest="action")
    p = ms.add_parser("list"); p.add_argument("--namespace", default=None)
    p = ms.add_parser("store"); p.add_argument("text"); p.add_argument("--namespace", default="default"); p.add_argument("--tag", action="append", default=None); p.add_argument("--provenance", default="cli")
    p = ms.add_parser("inspect"); p.add_argument("id")
    p = ms.add_parser("search"); p.add_argument("query")
    ms.add_parser("candidates")
    ms.add_parser("conflicts")
    ms.add_parser("pending")
    p = ms.add_parser("promote"); p.add_argument("id")
    p.add_argument("--state", required=True)
    p.add_argument("--evidence", default="")
    p.add_argument("--actor", default="user")
    p.add_argument("--reason", default="cli promote")
    p = ms.add_parser("pin"); p.add_argument("id"); p.add_argument("--reason", default="cli pin")
    p = ms.add_parser("archive"); p.add_argument("id"); p.add_argument("--reason", default="cli archive")
    p = ms.add_parser("restore"); p.add_argument("id"); p.add_argument("--reason", default="cli restore")
    p = ms.add_parser("explain"); p.add_argument("id")

    # session
    s = sub.add_parser("session")
    ss = s.add_subparsers(dest="action")
    ss.add_parser("list")
    p = ss.add_parser("begin"); p.add_argument("project_namespace"); p.add_argument("--objective", default="")
    p = ss.add_parser("status"); p.add_argument("id")
    p = ss.add_parser("checkpoint"); p.add_argument("id")
    p.add_argument("--objective", default="")
    p.add_argument("--progress", default="")
    p.add_argument("--next-action", default="")
    p = ss.add_parser("resume"); p.add_argument("id")
    p = ss.add_parser("consolidate"); p.add_argument("id")
    p = ss.add_parser("close"); p.add_argument("id"); p.add_argument("--outcome", default="completed")

    # procedure
    pr = sub.add_parser("procedure")
    prs = pr.add_subparsers(dest="action")
    prs.add_parser("list")
    p = prs.add_parser("inspect"); p.add_argument("id")
    p = prs.add_parser("runs"); p.add_argument("id")

    # prospective
    pv = sub.add_parser("prospective")
    pvs = pv.add_subparsers(dest="action")
    pvs.add_parser("list")
    pvs.add_parser("ready")
    p = pvs.add_parser("resolve"); p.add_argument("id")

    # retrieval
    rt = sub.add_parser("retrieval")
    rts = rt.add_subparsers(dest="action")
    rts.add_parser("feedback")
    rts.add_parser("adaptation")
    p = rts.add_parser("reset"); p.add_argument("--namespace", default="default")

    # foundry (v0.4)
    fw = sub.add_parser("foundry", help="proof-governed skill/capability/bubble ops")
    fws = fw.add_subparsers(dest="action")
    fws.add_parser("list-skills")
    p = fws.add_parser("skill"); p.add_argument("id")
    p = fws.add_parser("candidates")
    p = fws.add_parser("validate"); p.add_argument("id")
    p = fws.add_parser("review"); p.add_argument("id")
    p = fws.add_parser("approve"); p.add_argument("id"); p.add_argument("--reviewer", default="cli")
    p = fws.add_parser("publish"); p.add_argument("id"); p.add_argument("--ctp", default=None)
    fws.add_parser("list-caps")
    p = fws.add_parser("cap"); p.add_argument("id")
    p = fws.add_parser("verify-cap"); p.add_argument("id")
    p = fws.add_parser("prove-cap"); p.add_argument("id")
    p = fws.add_parser("govern-cap"); p.add_argument("id"); p.add_argument("--approver", default="cli")
    p = fws.add_parser("list-bubbles")
    p = fws.add_parser("bubble-validate"); p.add_argument("id")
    p = fws.add_parser("bubble-approve"); p.add_argument("id"); p.add_argument("--approver", default="cli")
    p = fws.add_parser("bubble-install"); p.add_argument("id"); p.add_argument("--ctp", default=None)
    fws.add_parser("curate")
    fws.add_parser("audit")

    # authored skills: pinned external prompt/context guidance, not Foundry procedures
    sk = sub.add_parser("skills", help="verify and inspect pinned external authored skills")
    sks = sk.add_subparsers(dest="action")
    p = sks.add_parser("status"); p.add_argument("--root", required=True)
    p = sks.add_parser("list"); p.add_argument("--root", required=True)
    p = sks.add_parser("show"); p.add_argument("name"); p.add_argument("--root", required=True)
    p = sks.add_parser("import", help="import a managed local Agent Skills pack")
    p.add_argument("--source", required=True)
    p.add_argument("--name", default="ultimate")
    p.add_argument("--state-dir", default=None)
    p = sks.add_parser("verify", help="verify an installed managed local skill pack")
    p.add_argument("--name", default="ultimate")
    p.add_argument("--state-dir", default=None)

    # One canonical bounded CAPT Core transaction, constructed via create_runtime().
    rr = sub.add_parser("runtime", help="canonical CAPT Core runtime operations")
    rrs = rr.add_subparsers(dest="action")
    p = rrs.add_parser("mission-begin")
    p.add_argument("--ledger", required=True)
    p.add_argument("--objective", required=True)
    p.add_argument("--operator", default="cli-operator")

    harness = sub.add_parser("harness", help="headless canonical CAPT runtime service (expert/debug surface)")
    hs = harness.add_subparsers(dest="action")
    p = hs.add_parser("start")
    p.add_argument("--ledger", required=True)
    p.add_argument("--sock", required=True)
    p.add_argument("--token-file", required=True)
    p.add_argument("--seed", action="store_true")
    for name in ("health", "capabilities"):
        p = hs.add_parser(name)
        p.add_argument("--sock", required=True)
        p.add_argument("--token-file", required=True)
    p = hs.add_parser("checkpoint")
    p.add_argument("--sock", required=True)
    p.add_argument("--token-file", required=True)
    p.add_argument("--idempotency-key", required=True)
    p = hs.add_parser("resume")
    p.add_argument("--sock", required=True)
    p.add_argument("--token-file", required=True)
    p.add_argument("--idempotency-key", required=True)
    p = hs.add_parser("stop")
    p.add_argument("--sock", required=True)
    p.add_argument("--token-file", required=True)
    p.add_argument("--idempotency-key", required=True)
    p = hs.add_parser("command", help="send an existing governed runtime command")
    p.add_argument("operation")
    p.add_argument("--payload-json", required=True)
    p.add_argument("--idempotency-key")
    p.add_argument("--sock", required=True)
    p.add_argument("--token-file", required=True)

    # --- P0 normal-human on-ramp (thin convenience over the harness) -----
    # `capt start` / `capt status` / `capt stop` allocate default local state
    # (~/.capt by default) so a new user does not need socket/token/ledger
    # paths. `capt harness ...` remains the full expert surface.
    p = sub.add_parser("start", help="start the governed runtime with sensible defaults")
    p.add_argument("--state-dir", default=None, help="state directory (default: ~/.capt or $CAPT_STATE_DIR)")
    p.add_argument("--seed", action="store_true", help="seed a demo mission (for first-run demonstration)")

    p = sub.add_parser("status", help="report runtime health and version")
    p.add_argument("--state-dir", default=None)

    p = sub.add_parser("stop", help="stop the running runtime")
    p.add_argument("--state-dir", default=None)

    p = sub.add_parser("checkpoint", help="checkpoint the running runtime")
    p.add_argument("--state-dir", default=None)
    p.add_argument("--idempotency-key", default=None)

    p = sub.add_parser("resume", help="resume a check-pointed runtime")
    p.add_argument("--state-dir", default=None)
    p.add_argument("--idempotency-key", default=None)

    p = sub.add_parser("doctor", help="diagnose the local environment")

    p = sub.add_parser("evidence", help="show a human-readable evidence/verification view")
    p.add_argument("--state-dir", default=None)
    p.add_argument("--mission", default=None, help="mission id to inspect (default: most recent)")

    p = sub.add_parser("run", help="run a governed provider inference")
    p.add_argument("--provider", required=True, help="registered CAPT provider id")
    p.add_argument("--model", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--state-dir", default=None)
    p.add_argument("--idempotency-key", default=None)
    sub.add_parser("tui", help="launch the interactive CAPT operator console")

    args = parser.parse_args(argv)
    if not args.group:
        parser.print_help()
        return 1

    as_json = args.json
    if args.group == "run":
        return _cmd_run(args, as_json)
    if args.group == "tui":
        from capt_runtime.cli_ramp import default_paths
        if _cmd_ramp_start(args, default_paths(), False) != 0:
            return 1
        from capt_ui.surfaces.tui.app import main as tui_main
        return tui_main()
    if args.group in ("start", "status", "stop", "checkpoint", "resume", "doctor", "evidence"):
        return _cmd_ramp(args, as_json)
    if args.group == "runtime":
        return _cmd_runtime(args, as_json)
    if args.group == "harness":
        return _cmd_harness(args)
    if args.group == "skills":
        return _cmd_authored_skills(args, as_json)
    try:
        eng = MemoryEngine()
        mgr = LifecycleManager(eng)
        if args.group == "memory":
            return _cmd_memory(mgr, args, as_json)
        if args.group == "session":
            return _cmd_session(mgr, args, as_json)
        if args.group == "procedure":
            return _cmd_procedure(mgr, args, as_json)
        if args.group == "prospective":
            return _cmd_prospective(mgr, args, as_json)
        if args.group == "retrieval":
            return _cmd_retrieval(mgr, args, as_json)
        if args.group == "foundry":
            return _cmd_foundry(mgr, args, as_json)
    except CaptSoloError as e:
        return _fail(str(e))
    except Exception as e:  # surface as structured error
        return _fail(f"{type(e).__name__}: {e}")
    finally:
        try:
            eng.close()
        except Exception:
            pass
    return 1


def _cmd_authored_skills(args, as_json: bool) -> int:
    """Inspect pinned packs or import/verify managed local authored skills."""
    if args.action in {"import", "verify"}:
        state_root = (
            Path(args.state_dir).expanduser() if args.state_dir else default_state_dir()
        )
        root = default_managed_skill_root(state_root, args.name)
        try:
            if args.action == "import":
                verified = import_managed_skill_pack(args.source, root, pack_name=args.name)
                status = "IMPORTED"
            else:
                verified = verify_managed_skill_pack(root)
                status = "VERIFIED"
        except ManagedSkillPackViolation as exc:
            return _fail(str(exc))
        return _ok({
            "status": status,
            "trust": verified["trust"],
            "packName": verified["packName"],
            "packVersion": verified["packVersion"],
            "manifestDigest": verified["manifestDigest"],
            "skillCount": verified["skillCount"],
            "root": str(root),
        }, as_json)

    try:
        verified = verify_skill_pack(args.root, load_capt_skills_lock())
    except AuthoredSkillPackViolation as exc:
        return _fail(str(exc))

    if args.action == "status":
        return _ok({
            "status": "VERIFIED",
            "trust": "pinned_external",
            "packName": verified["packName"],
            "packVersion": verified["packVersion"],
            "repository": verified["repository"],
            "ref": verified["ref"],
            "commit": verified["commit"],
            "tree": verified["tree"],
            "manifestDigest": verified["manifestDigest"],
            "skillCount": len(verified["skills"]),
        }, as_json)
    if args.action == "list":
        return _ok([
            {"name": item["name"], "version": item["version"],
             "contentDigest": item["contentDigest"]}
            for item in verified["skills"]
        ], as_json)
    if args.action == "show":
        for item in verified["skills"]:
            if item["name"] == args.name:
                return _ok(item, as_json)
        return _fail(f"authored skill not found: {args.name}")
    return _fail("skills action required")


def _cmd_harness(args) -> int:
    if args.action == "start":
        argv = [sys.executable, "-m", "desktop.capt_runtime_service", "--ledger", args.ledger,
                "--sock", args.sock, "--token-file", args.token_file]
        if args.seed:
            argv.append("--seed")
        return subprocess.call(argv)
    if args.action == "health" or args.action == "capabilities":
        from desktop.desktop_runtime_client import RuntimeClient
        client = RuntimeClient(args.sock, args.token_file)
        try:
            identity = client.connect()
            result = client.capabilities() if args.action == "capabilities" else {"status": "HEALTHY" if identity.get("integrity") == "ok" else "UNHEALTHY", "identity": identity}
            print(_json_or_human(result, args.json))
            return 0 if result.get("status", "HEALTHY") == "HEALTHY" else 1
        finally:
            client.disconnect()
    if args.action in ("checkpoint", "stop", "resume"):
        from desktop.desktop_runtime_client import RuntimeClient
        client = RuntimeClient(args.sock, args.token_file)
        try:
            client.connect()
            operation = {"checkpoint": "checkpoint_runtime", "stop": "shutdown", "resume": "resume_runtime"}[args.action]
            receipt = client.command(operation, {}, args.idempotency_key)
            print(_json_or_human(receipt, args.json))
            return 0 if receipt.get("status") in ("accepted", "idempotent") else 1
        finally:
            client.disconnect()
    if args.action == "command":
        from desktop.desktop_runtime_client import RuntimeClient
        try:
            payload = json.loads(args.payload_json)
        except json.JSONDecodeError as exc:
            return _fail("invalid --payload-json: %s" % exc)
        client = RuntimeClient(args.sock, args.token_file)
        try:
            client.connect()
            receipt = client.command(args.operation, payload, args.idempotency_key)
            print(_json_or_human(receipt, args.json))
            return 0 if receipt.get("status") in ("accepted", "idempotent") else 1
        finally:
            client.disconnect()
    return _fail("harness action required")


def _cmd_run(args, as_json: bool) -> int:
    from capt_runtime.cli_ramp import default_paths, is_running
    from desktop.desktop_runtime_client import RuntimeClient
    paths=default_paths()
    if args.state_dir:
        base=Path(args.state_dir).expanduser(); paths={"state_dir":base,"ledger":base/"runtime.db","sock":base/"runtime.sock","token":base/"runtime.token","pid":base/"runtime.pid"}
    if not paths["sock"].exists() or not is_running(paths["sock"]):
        return _fail("CAPT runtime is not running. Run: capt start")
    client=RuntimeClient(str(paths["sock"]),str(paths["token"]))
    try:
        client.connect()
        receipt=client.command("run_approved_hermes_inspection", {"provider":args.provider,"model":args.model,"objective":args.prompt,"targetRoot":str(Path.cwd())}, args.idempotency_key)
        print(_json_or_human(receipt,as_json))
        return 0 if receipt.get("status") in ("accepted","idempotent") else 1
    finally: client.disconnect()


def _cmd_ramp(args, as_json) -> int:
    """P0 normal-human on-ramp: capt start/status/stop/checkpoint/resume/doctor/evidence.

    Simple convenience wrappers that allocate default local state so a new
    user does not need socket/token/ledger paths. Authority remains in
    RuntimeService; these are caller-side conveniences only.
    """
    from capt_runtime.cli_ramp import default_paths
    from desktop.desktop_runtime_client import RuntimeClient

    group = args.group

    if group == "doctor":
        return _cmd_doctor()

    paths = default_paths()
    if getattr(args, "state_dir", None):
        base = Path(args.state_dir).expanduser()
        paths = {
            "state_dir": base,
            "ledger": base / "runtime.db",
            "sock": base / "runtime.sock",
            "token": base / "runtime.token",
            "pid": base / "runtime.pid",
        }

    if group == "start":
        return _cmd_ramp_start(args, paths, as_json)

    # status / stop / evidence all need a running service
    from capt_runtime.cli_ramp import is_running
    if not paths["sock"].exists() or not is_running(paths["sock"]):
        return _fail(
            "CAPT runtime is not running. Start it first with: capt start\n"
            f"  (expected socket: {paths['sock']})"
        )
    if not paths["token"].exists():
        return _fail("token file missing: %s" % paths["token"])

    client = RuntimeClient(str(paths["sock"]), str(paths["token"]))
    try:
        identity = client.connect()
        if group == "status":
            result = _status_view(client, identity)
            print(_json_or_human(result, as_json))
            return 0 if identity.get("integrity") == "ok" else 1
        if group == "checkpoint":
            idek = getattr(args, "idempotency_key", None) or "cli-checkpoint-" + uuid.uuid4().hex
            receipt = client.command("checkpoint_runtime", {}, idek)
            print(_json_or_human(receipt, as_json))
            return 0 if receipt.get("status") in ("accepted", "idempotent") else 1
        if group == "resume":
            idek = getattr(args, "idempotency_key", None) or "cli-resume-" + uuid.uuid4().hex
            receipt = client.command("resume_runtime", {}, idek)
            print(_json_or_human(receipt, as_json))
            return 0 if receipt.get("status") in ("accepted", "idempotent") else 1
        if group == "stop":
            receipt = client.command("shutdown", {}, "cli-stop-" + uuid.uuid4().hex)
            print(_json_or_human(receipt, as_json))
            return 0 if receipt.get("status") in ("accepted", "idempotent") else 1
        if group == "evidence":
            result = _evidence_view(client, getattr(args, "mission", None))
            print(_json_or_human(result, as_json))
            return 0
    except Exception as exc:
        return _fail(f"{type(exc).__name__}: {exc}")
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
    return 1


def _cmd_ramp_start(args, paths, as_json) -> int:
    """Start the runtime service with default local state (background)."""
    from capt_runtime.cli_ramp import is_running
    base = paths["state_dir"]
    base.mkdir(parents=True, exist_ok=True)
    # If already running, just report status.
    if paths["sock"].exists() and is_running(paths["sock"]):
        from desktop.desktop_runtime_client import RuntimeClient
        client = RuntimeClient(str(paths["sock"]), str(paths["token"]))
        try:
            identity = client.connect()
            print(_json_or_human(_status_view(client, identity), as_json))
            return 0
        finally:
            client.disconnect()
    argv = [sys.executable, "-m", "desktop.capt_runtime_service",
            "--ledger", str(paths["ledger"]),
            "--sock", str(paths["sock"]),
            "--token-file", str(paths["token"])]
    if getattr(args, "seed", False):
        argv.append("--seed")
    # Launch detached so `capt start` returns and the runtime keeps running.
    # The parent closes its copies of the redirected handles after Popen; the
    # child process inherits and owns its own descriptors.
    devnull = open(os.devnull, "wb")
    logf = open(base / "start.log", "ab")
    try:
        proc = subprocess.Popen(argv, stdout=devnull, stderr=logf, start_new_session=True)
    finally:
        devnull.close()
        logf.close()
    try:
        paths["pid"].write_text(str(proc.pid))
    except OSError:
        pass
    # Wait for the service to become healthy (bounded).
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if paths["sock"].exists() and is_running(paths["sock"]):
            from desktop.desktop_runtime_client import RuntimeClient
            client = RuntimeClient(str(paths["sock"]), str(paths["token"]))
            try:
                identity = client.connect()
                print(_json_or_human(_status_view(client, identity), as_json))
                return 0
            finally:
                client.disconnect()
        time.sleep(0.25)
    return _fail("runtime start timed out before becoming healthy")


def _status_view(client, identity) -> dict:
    """Small human/operator status projection."""
    caps = client.capabilities()
    return {
        "status": "HEALTHY" if identity.get("integrity") == "ok" else "UNHEALTHY",
        "runtimeVersion": identity.get("runtimeVersion"),
        "ledgerPath": identity.get("ledgerPath"),
        "headSequence": identity.get("headSequence"),
        "ledgerDigest": identity.get("ledgerChainDigest"),
        "capabilities": {
            "queryOperations": caps.get("queryOperations", [])[:5],
            "commandOperations": caps.get("commandOperations", [])[:8],
        },
    }


def _evidence_view(client, mission_id) -> dict:
    """Human-readable evidence/verification projection."""
    from desktop.desktop_runtime_client import (
        project_evidence, project_claimguard, project_mission_spec,
    )
    missions = client.list_aggregates()
    mission = mission_id
    if mission is None:
        # pick the first mission aggregate stream to inspect
        for agg in missions:
            if agg["kind"] == "mission":
                sid = agg["streamId"]
                mission = sid[len("mission-"):] if sid.startswith("mission-") else sid
                break
    evidence = []
    verification = client.verification()
    claimguard = None
    claim_statement = None
    spec = None
    if mission:
        evidence = project_evidence(client, mission)
        spec = project_mission_spec(client, mission)
        # Calculate ClaimGuard only against a real claim statement if a claim
        # aggregate exists; do not fabricate a statement.
        for agg in missions:
            if agg["kind"] == "claim":
                st = client.get_state(agg["streamId"])
                if st and st.get("statement"):
                    claim_statement = st["statement"]
                    break
        if claim_statement:
            try:
                claimguard = project_claimguard(client, claim_statement)
            except Exception:
                claimguard = None
    return {
        "mission": mission,
        "missionSpec": spec,
        "evidence": evidence,
        "verification": verification,
        "claimGuardDisposition": claimguard,
        "hint": "Evidence and verification are authoritative CAPT state; run `capt --json evidence` for the full record.",
    }


def _cmd_doctor() -> int:
    """First-class diagnostics surface (works from source and installed wheel).

    Pure-Python checks so `capt doctor` is a normal-human support surface that
    does not depend on repo-relative shell scripts.
    """
    import sys as _sys
    from capt_runtime.cli_ramp import default_paths, is_running
    checks = []

    def add(cid, status, summary, evidence=""):
        checks.append((cid, status, summary, evidence))

    paths = {}
    # environment
    add("env.python3", "pass" if _sys.executable else "warn",
        "python interpreter", _sys.version.split()[0])
    try:
        import sqlite3  # noqa: F401
        add("env.sqlite3", "pass", "sqlite3 stdlib importable")
    except Exception:
        add("env.sqlite3", "fail", "sqlite3 stdlib missing")

    # package importability
    try:
        import capt_solo  # noqa: F401
        add("env.package", "pass", "CAPT Solo package importable")
    except Exception as exc:
        add("env.package", "fail", "CAPT Solo package not importable", str(exc)[:120])

    # runtime state dir
    try:
        paths = default_paths()
        add("runtime.state_dir", "pass" if paths["state_dir"].exists() else "warn",
            "runtime state dir", str(paths["state_dir"]))
    except Exception as exc:
        add("runtime.state_dir", "fail", "could not resolve state dir", str(exc)[:120])

    # running runtime?
    try:
        running = bool(paths) and paths["sock"].exists() and is_running(paths["sock"])
        add("runtime.service", "pass" if running else "warn",
            "runtime service", "running" if running else "not running (start with `capt start`)")
    except Exception as exc:
        add("runtime.service", "fail", "could not check runtime", str(exc)[:120])

    rows = []
    for cid, status, summary, evidence in checks:
        tag = status.upper()
        line = f"[{tag:4}] {cid:<22} {summary}"
        if evidence:
            line += f"  ({evidence})"
        rows.append(line)
    print("== CAPT doctor ==")
    print("\n".join(rows))
    # `warn` is not a hard failure for this surface; only the sys.exit code
    # reflects hard failures (fail). Warnings still print but return 0-ish.
    hard_fail = any(c[1] == "fail" for c in checks)
    print("\nDoctor complete: %d checks, %d pass, %d warn, %d fail." % (
        len(checks),
        sum(c[1] == "pass" for c in checks),
        sum(c[1] == "warn" for c in checks),
        sum(c[1] == "fail" for c in checks),
    ))
    return 1 if hard_fail else 0


def _cmd_runtime(args, as_json) -> int:
    """Run one persisted CAPT Core mission transaction and close deterministically."""
    mission_id = "mission-" + uuid.uuid4().hex
    command_id = "cmd-" + uuid.uuid4().hex
    metadata = runtime_commands.command(
        command_id=command_id,
        idempotency_key="idem-" + command_id,
        operation_fingerprint=runtime_commands.fingerprint(
            "create_mission", {"missionId": mission_id, "objective": args.objective}
        ),
        correlation_id="runtime-mission-begin:" + mission_id,
        actor_id=args.operator,
        actor_kind="human",
        issued_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        replay_policy="never",
    )
    runtime = create_runtime(args.ledger)
    try:
        result = runtime.service.create_mission_with_approval(
            {
                "schemaVersion": "1.0.0", "missionId": mission_id,
                "objective": args.objective,
                "rawRequest": args.objective, "normalizedRequest": args.objective,
                "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False},
                "requiresApproval": False,
            }, metadata
        )
        return _ok({"ok": True, "ledger": args.ledger, **result}, as_json)
    except Exception as exc:
        return _fail(f"{type(exc).__name__}: {exc}")
    finally:
        runtime.close()


def _cmd_memory(mgr, args, as_json) -> int:
    lc = mgr.lifecycle
    if args.action == "list":
        rows = mgr._eng.list()
        return _ok([r.to_dict() for r in rows], as_json)
    if args.action == "store":
        record = mgr._eng.store(
            args.text,
            namespace=args.namespace,
            provenance=args.provenance,
            tags=args.tag,
        )
        return _ok({"memory_id": record.memory_id, "namespace": args.namespace}, as_json)
    if args.action == "inspect":
        m = mgr._eng.get(args.id)
        if m is None:
            return _fail(f"memory not found: {args.id}")
        return _ok(m.to_dict(), as_json)
    if args.action == "search":
        rows = mgr._eng.search(args.query)
        return _ok([r.to_dict() for r in rows], as_json)
    if args.action == "candidates":
        rows = [r for r in mgr._eng.list() if r.lifecycle_state == "candidate"]
        return _ok([r.to_dict() for r in rows], as_json)
    if args.action == "conflicts":
        return _ok(mgr._eng.list_conflicts(unresolved_only=True), as_json)
    if args.action == "pending":
        intents = mgr.prospective.list(status="pending")
        return _ok([i.to_dict() for i in intents], as_json)
    if args.action == "promote":
        ev = [e for e in args.evidence.split(",") if e]
        r = mgr.promote_with_ctp(args.id, args.state, actor=args.actor,
                                evidence=ev or None, reason=args.reason)
        return _ok(r, as_json)
    if args.action == "pin":
        r = lc.pin(args.id, reason=args.reason)
        return _ok({"ok": True, "transition_id": r}, as_json)
    if args.action == "archive":
        r = mgr.archive_with_ctp(args.id, reason=args.reason)
        return _ok(r, as_json)
    if args.action == "restore":
        r = mgr.restore_with_ctp(args.id, reason=args.reason)
        return _ok(r, as_json)
    if args.action == "explain":
        hist = lc.transition_history(args.id)
        ev = lc.evaluate_promotion(args.id)
        return _ok({"transition_history": hist, "promotion_evaluation": ev.to_dict()}, as_json)
    return _fail("unknown memory action")


def _cmd_session(mgr, args, as_json) -> int:
    sr = mgr.sessions
    if args.action == "begin":
        r = mgr.session_begin_with_ctp(args.project_namespace, objective=args.objective)
        return _ok(r, as_json)
    if args.action == "list":
        return _ok(sr.list(), as_json)
    if args.action == "status":
        return _ok(sr.status(args.id), as_json)
    if args.action == "checkpoint":
        cid = sr.checkpoint(args.id, objective=args.objective,
                          progress=args.progress, next_action=args.next_action)
        return _ok({"ok": True, "checkpoint_id": cid}, as_json)
    if args.action == "resume":
        pkt = sr.resume(args.id)
        return _ok(pkt.to_dict(), as_json)
    if args.action == "consolidate":
        cid = mgr.session_consolidate_with_ctp(args.id)
        return _ok({"ok": True, "consolidation_id": cid}, as_json)
    if args.action == "close":
        sr.close(args.id, outcome=args.outcome)
        return _ok({"ok": True}, as_json)
    return _fail("unknown session action")


def _cmd_procedure(mgr, args, as_json) -> int:
    ps = mgr.procedures
    if args.action == "list":
        return _ok([p.to_dict() for p in ps.list()], as_json)
    if args.action == "inspect":
        p = ps.get(args.id)
        if p is None:
            return _fail(f"procedure not found: {args.id}")
        return _ok(p.to_dict(), as_json)
    if args.action == "runs":
        return _ok(ps.get_runs(args.id), as_json)
    return _fail("unknown procedure action")


def _cmd_prospective(mgr, args, as_json) -> int:
    pv = mgr.prospective
    if args.action == "list":
        return _ok([i.to_dict() for i in pv.list()], as_json)
    if args.action == "ready":
        return _ok([i.to_dict() for i in pv.list(status="ready")], as_json)
    if args.action == "resolve":
        ok = pv.resolve(args.id)
        return _ok({"ok": ok}, as_json)
    return _fail("unknown prospective action")


def _cmd_retrieval(mgr, args, as_json) -> int:
    fb = mgr.feedback
    if args.action == "feedback":
        return _ok(fb.list_feedback(), as_json)
    if args.action == "adaptation":
        return _ok(fb.get_adaptation_state(), as_json)
    if args.action == "reset":
        fb.reset_adaptation(args.namespace)
        return _ok({"ok": True, "namespace": args.namespace}, as_json)
    return _fail("unknown retrieval action")


def _cmd_foundry(mgr, args, as_json) -> int:
    """v0.4 foundry CLI — uses public foundry APIs only (no direct SQL)."""
    eng = mgr._eng
    pe = ProofEngine(eng._conn)
    reg = CapabilityRegistry(eng._conn, pe)
    cg = ClaimGuard(reg, pe)
    ps = mgr.procedures
    sf = SkillFoundry(eng._conn, pe, ps)
    ctp = CTPRuntime()
    kb = KnowledgeBubbleRuntime(eng._conn, sf)
    gov = Governance(eng._conn, ctp, foundry=sf, registry=reg, bubbles=kb)
    a = args.action

    if a == "list-skills":
        return _ok([s.to_dict() for s in sf.list()], as_json)
    if a == "skill":
        s = sf.get(args.id)
        if s is None:
            return _fail(f"skill not found: {args.id}")
        return _ok(s.to_dict(), as_json)
    if a == "candidates":
        return _ok([c for c in sf.list_candidates()], as_json)
    if a == "validate":
        rep = sf.validate(args.id, ValidationHarness(pe))
        return _ok(rep.to_dict(), as_json)
    if a == "review":
        sf.submit_for_review(args.id)
        return _ok({"ok": True, "lifecycle": "reviewing"}, as_json)
    if a == "approve":
        sf.approve(args.id, reviewer=args.reviewer)
        return _ok({"ok": True, "lifecycle": "approved"}, as_json)
    if a == "publish":
        sf.publish(args.id, ctp_tx_id=args.ctp)
        return _ok({"ok": True, "lifecycle": "published"}, as_json)
    if a == "list-caps":
        return _ok([c.to_dict() for c in reg.list()], as_json)
    if a == "cap":
        c = reg.get(args.id)
        if c is None:
            return _fail(f"capability not found: {args.id}")
        d = c.to_dict()
        try:
            d["degradations"] = reg.get_degradations(args.id)
        except Exception:
            d["degradations"] = []
        return _ok(d, as_json)
    if a == "verify-cap":
        # use a default requirement set: 1 test_pass + 1 static_analysis
        r = reg.verify(args.id, pe, [
            ProofRequirement("test_pass", 1, args.id),
            ProofRequirement("static_analysis", 1, args.id),
        ])
        return _ok(r, as_json)
    if a == "prove-cap":
        r = reg.mark_proven(args.id)
        return _ok(r, as_json)
    if a == "govern-cap":
        r = reg.govern_approve(args.id, args.approver)
        return _ok(r, as_json)
    if a == "list-bubbles":
        return _ok(kb.list(), as_json)
    if a == "bubble-validate":
        rep = kb.validate_bubble(args.id)
        return _ok(rep.to_dict(), as_json)
    if a == "bubble-approve":
        kb.approve_bubble(args.id, args.approver)
        return _ok({"ok": True, "lifecycle": "approved"}, as_json)
    if a == "bubble-install":
        res = kb.install_bubble(args.id, ctp_tx_id=args.ctp)
        return _ok(res, as_json)
    if a == "curate":
        cur = SkillCurator(sf)
        return _ok(cur.recommend(), as_json)
    if a == "audit":
        return _ok(gov.audit_trail(), as_json)
    return _fail("unknown foundry action")


if __name__ == "__main__":
    sys.exit(main())
