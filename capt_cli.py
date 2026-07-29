#!/usr/bin/env python3
"""CAPT Solo — unified local-first cognitive runtime CLI.

Groups: memory, session, procedure, prospective, retrieval, canon, foundry,
architecture, workspace, release. All commands support --json for machine-readable output
and return nonzero exit codes on failure. No raw SQL is exposed. No credentials
are printed. The CLI is local-first and performs no network I/O.

Usage:
    python3 capt_cli.py workspace validate
    python3 capt_cli.py architecture validate
    python3 capt_cli.py foundry list-skills
    python3 capt_cli.py memory list --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make the package importable when run as a script.
_SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SRC))

# Runtime public surface. Guarded so the CLI loads even when an optional
# subsystem (e.g. CTP) is missing from the tree — architecture commands must
# still run. Runtime commands report a clear error instead of crashing import.
try:  # noqa: E402
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
    _RUNTIME_OK = True
except Exception as _runtime_err:  # noqa: E402, BLE001
    _RUNTIME_OK = False
    _runtime_err = _runtime_err
    # Stand-ins so module-level references don't NameError at import time.
    # Runtime commands check _RUNTIME_OK and fail with a clear message.
    class CaptSoloError(Exception):  # type: ignore
        pass
    LifecycleManager = MemoryEngine = None  # type: ignore
    ProofEngine = ProofRequirement = CapabilityRegistry = None  # type: ignore
    ClaimGuard = SkillFoundry = ValidationHarness = None  # type: ignore
    KnowledgeBubbleRuntime = Governance = SkillCurator = None  # type: ignore
    CompositionEngine = CTPRuntime = None  # type: ignore


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
    parser = argparse.ArgumentParser(
        prog="capt",
        description="CAPT Solo local-first verification and cognitive runtime CLI",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="group")

    sub.add_parser(
        "doctor",
        help="inspect the installed runtime without creating persistent state",
    )

    # release validation is read-only and independent of runtime persistence.
    rel = sub.add_parser("release", help="release semantic and artifact validation")
    rels = rel.add_subparsers(dest="action")
    p = rels.add_parser("validate", help="fail closed on stale release claims")
    p.add_argument("--root", default=".", help="source checkout to validate")
    p.add_argument("--dist-dir", default=None, help="optional wheel/sdist directory")
    p.add_argument("--final", action="store_true", help="enforce frozen candidate checks")
    p.add_argument("--candidate-sha", default=None)

    # memory
    m = sub.add_parser("memory")
    ms = m.add_subparsers(dest="action")
    p = ms.add_parser("list"); p.add_argument("--namespace", default=None)
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

    # architecture (Phase 3A enforcement)
    arch = sub.add_parser("architecture", help="canonical architecture registry + fitness")
    archs = arch.add_subparsers(dest="action")
    archs.add_parser("validate", help="validate architecture/registry.yaml")
    archs.add_parser("list", help="list canonical subsystems")
    _show = archs.add_parser("show", help="show a subsystem by id")
    _show.add_argument("id")

    # canon (Phase 3L — hardened external surface over canonical subsystems)
    cn = sub.add_parser("canon", help="canonical subsystem operations (episodes/knowledge/evidence/...)")
    cns = cn.add_subparsers(dest="action")
    p = cns.add_parser("episodes"); p.add_argument("--limit", type=int, default=20)
    p = cns.add_parser("knowledge"); p.add_argument("--status", default=None)
    p = cns.add_parser("evidence"); p.add_argument("--status", default=None)
    p = cns.add_parser("autobiographical"); p.add_argument("--subject", default=None)
    p = cns.add_parser("engrams"); p.add_argument("--state", default=None)
    p = cns.add_parser("research-health")
    p = cns.add_parser("self-check")

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

    # workspace (Universal Workspace layer — additive, local-first)
    ws = sub.add_parser("workspace", help="universal workspace operations (status/validate/bootstrap/checkpoint/tasks/next/capabilities)")
    wss = ws.add_subparsers(dest="action")
    wss.add_parser("status")
    wss.add_parser("validate")
    wss.add_parser("bootstrap")
    wss.add_parser("tasks")
    p = wss.add_parser("next")
    p.add_argument("--capabilities", default=None, help="JSON dict of capability->bool (default: local-agent manifest)")
    wss.add_parser("capabilities")
    p = wss.add_parser("checkpoint")
    p.add_argument("--task", default=None)
    p.add_argument("--next", dest="next_cmd", default="")
    p.add_argument("--files", default=None)
    p.add_argument("--in-progress", dest="in_progress", default="")
    wss.add_parser("archive-checkpoint")

    # verify (Verified State Identity — independent of runtime; local-first)
    vf = sub.add_parser("verify", help="Verified State Identity verification (reuse prior evidence when state unchanged)")
    vfs = vf.add_subparsers(dest="action")
    p = vfs.add_parser("run", help="verify a scope; reuse prior evidence if VSI unchanged")
    p.add_argument("--scope", default="full",
                   choices=[s.value for s in __import__("capt_solo.verification.scope", fromlist=["VerificationScope"]).VerificationScope])
    p.add_argument("--force", action="store_true", help="ignore VSI reuse and re-run")
    p.add_argument("--command", default=None, help="override verification command")
    p.add_argument("--store", default=None, help="path to verification records JSONL")
    vfs.add_parser("status", help="show latest verification record")

    # evidence (governed evidence engine — independent of runtime; local-first)
    ef = sub.add_parser("evidence", help="governed evidence engine (status/show/trace/invalidate/reuse-decision/conflicts)")
    efs = ef.add_subparsers(dest="action")
    efs.add_parser("status", help="summary of evidence store")
    p = efs.add_parser("show", help="show an evidence record by id")
    p.add_argument("record_id")
    p = efs.add_parser("trace", help="trace what supports a claim")
    p.add_argument("claim_id")
    p = efs.add_parser("invalidate", help="record an invalidation event")
    p.add_argument("--reason", required=True)
    p.add_argument("--path", action="append", default=[], help="changed path (repeatable)")
    p.add_argument("--claim", default=None, help="optional claim id to scope")
    p = efs.add_parser("reuse-decision", help="structured guard decision for a claim")
    p.add_argument("claim_id")
    p.add_argument("--vsi", default="equivalent", choices=["equivalent", "changed", "unknown"])
    p.add_argument("--user-fresh", action="store_true")
    efs.add_parser("conflicts", help="list conflicted evidence")

    # continuity (CVE v0.2 — policy evaluation only; no production actions)
    cv = sub.add_parser("continuity", help="CVE v0.2 operational-continuity evidence runtime")
    cvs = cv.add_subparsers(dest="action")
    p = cvs.add_parser("validate-policy", help="validate a CSL v0.2 policy")
    p.add_argument("--policy", default=None)
    p = cvs.add_parser("validate-pack", help="validate a continuity evidence pack")
    p.add_argument("pack")
    p.add_argument("--policy", default=None)
    p = cvs.add_parser("evaluate", help="evaluate a pack; BLOCK exits nonzero")
    p.add_argument("pack")
    p.add_argument("--policy", default=None)
    p = cvs.add_parser("receipt-verify", help="verify a receipt against pack and policy digests")
    p.add_argument("receipt")
    p.add_argument("pack")
    p.add_argument("--policy", default=None)
    p = cvs.add_parser("plan-drill", help="produce a safe, non-executing sandbox drill plan")
    p.add_argument("pack")
    p.add_argument("--environment", default="sandbox")
    p = cvs.add_parser("collect", help="build an inspectable pack from local provider snapshots")
    p.add_argument("--pack-id", default="local-continuity")
    p.add_argument("--component", default="capt-solo")
    p.add_argument("--tier", default="C1", choices=["C0", "C1", "C2", "C3"])
    p.add_argument("--scope", default="local runtime snapshot")
    p.add_argument("--roles", required=True, help="JSON role list")
    p.add_argument("--claims", required=True, help="JSON claim list")
    p.add_argument("--mission-id", default=None)
    p.add_argument("--include-memory", action="store_true")
    p.add_argument("--output", default=None, help="explicit local JSON output path")
    p = cvs.add_parser("receipt-append", help="append a receipt to an explicit local chain")
    p.add_argument("receipt")
    p.add_argument("--chain", required=True)

    # mission (checkpoint / resume / status)
    mf = sub.add_parser("mission", help="mission checkpoint and restart recovery")
    mfs = mf.add_subparsers(dest="action")
    p = mfs.add_parser("checkpoint", help="save a mission checkpoint")
    p.add_argument("--mission-id", required=True)
    p.add_argument("--project-id", default="capt-solo")
    p.add_argument("--objective", default="")
    p.add_argument("--phase", default="0")
    p.add_argument("--next", dest="next_action", default="")
    p.add_argument("--head", default="")
    mfs.add_parser("status", help="list checkpoints")
    p = mfs.add_parser("resume", help="resume plan for a checkpoint")
    p.add_argument("mission_id")

    # selfmod (self-modification governance)
    sf = sub.add_parser("selfmod", help="self-modification governance (status/propose/diff/rollback)")
    sfs = sf.add_subparsers(dest="action")
    sfs.add_parser("status", help="list self-modification records")
    p = sfs.add_parser("propose", help="propose a governed self-modification")
    p.add_argument("--mission-id", default="cli")
    p.add_argument("--change", required=True)
    p.add_argument("--rationale", default="")
    p.add_argument("--scope", default="project_local", choices=["project_local", "global_policy", "skill", "prompt"])
    p.add_argument("--diff", default="")
    p.add_argument("--rollback", default="")
    p = sfs.add_parser("diff", help="show a self-modification diff")
    p.add_argument("record_id")
    p.add_argument("--mission-id", default="cli")
    p = sfs.add_parser("rollback", help="roll back a self-modification")
    p.add_argument("record_id")
    p.add_argument("--mission-id", default="cli")

    args = parser.parse_args(argv)
    if not args.group:
        parser.print_help()
        return 1

    as_json = args.json

    if args.group == "doctor":
        return _cmd_doctor(as_json)
    if args.group == "release":
        return _cmd_release(args, as_json)

    # verify group is independent of the memory runtime.
    if args.group == "verify":
        return _cmd_verify(args, as_json)
    # evidence / mission / selfmod groups are independent of the memory runtime.
    if args.group == "evidence":
        return _cmd_evidence(args, as_json)
    if args.group == "continuity":
        return _cmd_continuity(args, as_json)
    if args.group == "mission":
        return _cmd_mission(args, as_json)
    if args.group == "selfmod":
        return _cmd_selfmod(args, as_json)

    # Architecture commands are independent of the runtime and must work even
    # when optional subsystems (e.g. CTP) are missing from the tree.
    if args.group == "architecture":
        return _cmd_architecture(args, as_json)

    if args.group == "canon":
        return _cmd_canon(args, as_json)

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
        if args.group == "workspace":
            return _cmd_workspace(args, as_json)
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


def _cmd_doctor(as_json: bool) -> int:
    """Inspect the installed package without hidden persistence or network I/O."""
    from importlib import metadata, resources

    checks = []

    def check(check_id: str, operation) -> None:
        try:
            evidence = operation()
            if evidence is False:
                raise RuntimeError("check returned false")
            checks.append({
                "id": check_id,
                "status": "pass",
                "evidence": str(evidence),
            })
        except Exception as exc:  # diagnostic boundary: preserve exact failure
            checks.append({
                "id": check_id,
                "status": "fail",
                "evidence": f"{type(exc).__name__}: {exc}",
            })

    check("package.version", lambda: metadata.version("capt-solo"))
    check("profile.evidence", lambda: __import__("capt_solo.evidence").evidence.__name__)
    check("profile.verification", lambda: __import__("capt_solo.verification").verification.__name__)
    check("profile.context", lambda: __import__("capt_solo.contextpack").contextpack.__name__)
    check("profile.transaction", lambda: __import__("capt_solo.ctp").ctp.__name__)
    check("profile.workspace", lambda: __import__("capt_solo.workspace").workspace.__name__)
    check("profile.runtime", lambda: __import__("capt_solo.api").api.__name__)
    check(
        "data.plugin_manifest",
        lambda: resources.files("capt_solo").joinpath("plugin/plugin.json").is_file(),
    )
    check(
        "data.bundled_skills",
        lambda: len(list(resources.files("capt_solo").joinpath("skills").glob("*/SKILL.md"))) == 8,
    )

    def _pulse_disabled() -> bool:
        from capt_solo.pulse import default_gateway
        return default_gateway().enabled is False

    check("network.default_disabled", _pulse_disabled)
    failed = [item for item in checks if item["status"] == "fail"]
    result = {
        "ok": not failed,
        "checks": checks,
        "side_effects": "none",
        "network": "not used",
        "persistence": "not created",
    }
    if failed:
        print(_json_or_human(result, as_json))
        return 1
    return _ok(result, as_json)


def _cmd_release(args, as_json: bool) -> int:
    if args.action != "validate":
        return _fail("unknown release action (expected validate)")
    from capt_solo.release_validation import result_document, validate_release

    result = result_document(validate_release(
        Path(args.root),
        dist_dir=Path(args.dist_dir) if args.dist_dir else None,
        final=args.final,
        candidate_sha=args.candidate_sha,
    ))
    print(_json_or_human(result, as_json))
    return 0 if result["ok"] else 1


def _cmd_architecture(args, as_json) -> int:
    from architecture.validate_registry import validate, load_registry, REGISTRY_PATH
    if args.action == "validate":
        try:
            reg = load_registry()
        except Exception as e:
            return _fail(f"registry load failed: {e}")
        checks = validate(reg)
        fails = [c for c in checks if c.status == "fail"]
        out = {
            "ok": not fails,
            "checks": len(checks),
            "fail": len(fails),
            "details": [
                {"id": c.cid, "status": c.status, "severity": c.severity, "summary": c.summary}
                for c in checks
            ],
        }
        return _ok(out, as_json) if not fails else _fail(str(out))
    if args.action == "list":
        reg = load_registry()
        return _ok([
            {"id": s["canonical_id"], "name": s["canonical_name"], "layer": s["architectural_layer"],
             "maturity": s["maturity"], "target": s["public_release_target"]}
            for s in reg["subsystems"]
        ], as_json)
    if args.action == "show":
        reg = load_registry()
        sub = next((s for s in reg["subsystems"] if s["canonical_id"] == args.id), None)
        if sub is None:
            return _fail(f"subsystem not found: {args.id}")
        return _ok(sub, as_json)
    return _fail("unknown architecture action")


def _cmd_canon(args, as_json) -> int:
    """Hardened external surface over canonical subsystems (Phase 3L)."""
    from capt_solo.capt_facade import CAPT
    try:
        capt = CAPT()  # local-first in-memory by default; explicit, no silent IO
    except Exception as e:
        return _fail(f"CAPT init failed: {type(e).__name__}: {e}")
    try:
        if args.action == "episodes":
            items = capt.episodic.list_episodes(limit=args.limit)
            return _ok([e.__dict__ for e in items], as_json)
        if args.action == "knowledge":
            items = capt.knowledge.list_knowledge(status=args.status)
            return _ok([k.__dict__ for k in items], as_json)
        if args.action == "evidence":
            items = capt.evidence.list_evidence(status=args.status)
            return _ok([e.__dict__ for e in items], as_json)
        if args.action == "autobiographical":
            items = capt.autobiographical.list_entries(subject_identity=args.subject)
            return _ok([a.__dict__ for a in items], as_json)
        if args.action == "engrams":
            items = capt.engram.list_engrams(state=args.state)
            return _ok([e.__dict__ for e in items], as_json)
        if args.action == "research-health":
            return _ok(capt.research.health(), as_json)
        if args.action == "self-check":
            return _ok({"ok": capt.verify_runtime()}, as_json)
        return _fail("unknown canon action")
    except Exception as e:  # surface as structured error, never silent
        return _fail(f"{type(e).__name__}: {e}")
    finally:
        try:
            capt.close()
        except Exception:
            pass


def _cmd_workspace(args, as_json) -> int:
    """Universal Workspace commands (local-first; no network I/O)."""
    from capt_solo.workspace import run_command
    caps = None
    if getattr(args, "capabilities", None):
        try:
            caps = json.loads(args.capabilities)
        except Exception as e:
            return _fail(f"--capabilities must be JSON: {e}")
    action = args.action
    cargs = {}
    if action == "next":
        cargs["capabilities"] = caps
    if action == "capabilities":
        cargs["agent"] = "cli"
    if action == "checkpoint":
        cargs = {
            "task": getattr(args, "task", None),
            "next": getattr(args, "next_cmd", ""),
            "files": getattr(args, "files", None),
            "in_progress": getattr(args, "in_progress", ""),
        }
    code, data = run_command(action, cargs)
    if code != 0:
        return _fail(json.dumps(data, default=str))
    return _ok(data, as_json)


def _cmd_verify(args, as_json) -> int:
    """Verified State Identity verification (local-first; no network I/O)."""
    from capt_solo.verification import (
        VerificationEngine, VerificationStore, VerificationScope,
    )
    repo = os.path.abspath(os.path.dirname(__file__))  # capt_cli.py lives at repo root
    if args.action == "status":
        store = VerificationStore(os.path.join(repo, ".capt_verify", "records.jsonl"))
        latest = store.latest()
        if latest is None:
            return _ok({"status": "no_verification_recorded"}, as_json)
        return _ok({
            "record_id": latest.get("record_id"),
            "status": latest.get("status"),
            "scope": latest.get("vsi", {}).get("verification_scope"),
            "head": latest.get("vsi", {}).get("head_commit", "")[:12],
            "evidence": latest.get("evidence", {}).get("location"),
            "created_at": latest.get("created_at"),
        }, as_json)
    if args.action != "run":
        return _fail("unknown verify action (expected run|status)")
    scope = VerificationScope(args.scope)
    store = VerificationStore(args.store) if args.store else None
    engine = VerificationEngine(repo, store=store)
    result = engine.verify(scope, command=args.command, force=args.force)
    out = {
        "status": result.status.value,
        "scope": scope.value,
        "ran_scope": result.ran_scope.value if result.ran_scope else None,
        "reused_record_id": result.reused_record_id,
        "new_record_id": result.new_record_id,
        "diff_reasons": result.diff_reasons,
        "confidence_note": result.confidence_note,
        "evidence": result.evidence.location if result.evidence else None,
    }
    return _ok(out, as_json)


def _cmd_continuity(args, as_json) -> int:
    """Local CVE v0.2 policy evaluation.  It never executes a drill."""
    from capt_solo.continuity import (
        ContinuityError, ContinuityPack, ReceiptChain, build_pack_from_providers,
        evaluate_pack, load_policy, plan_drill,
        validate_pack, verify_receipt,
    )
    repo = Path(__file__).resolve().parent
    policy_path = getattr(args, "policy", None) or repo / "architecture" / "cve" / "continuity-v0.2.yaml"
    try:
        policy = load_policy(policy_path)
        if args.action == "validate-policy":
            return _ok({"valid": True, "policy_id": policy["policy_id"],
                        "clauses": [a["id"] for a in policy["articles"]]}, as_json)
        if args.action == "collect":
            from capt_solo.evidence import CheckpointStore
            from capt_solo.evidence.providers import MemoryProvider, MissionProvider
            providers = [MissionProvider(CheckpointStore(str(repo), create=False), args.mission_id or "")]
            if args.include_memory:
                if not _RUNTIME_OK:
                    return _fail("memory provider unavailable: runtime imports failed")
                providers.append(MemoryProvider(MemoryEngine()))
            try:
                roles, claims = json.loads(args.roles), json.loads(args.claims)
            except json.JSONDecodeError as exc:
                return _fail("--roles and --claims must be JSON: " + str(exc))
            pack = build_pack_from_providers(
                pack_id=args.pack_id, component=args.component,
                tier=args.tier, scope=args.scope, roles=roles, claims=claims,
                policy_id=policy["policy_id"], providers=providers)
            data = pack.to_dict()
            if args.output:
                Path(args.output).write_text(json.dumps(data, indent=2), encoding="utf-8")
                data = {"saved": str(args.output), "pack": data}
            return _ok(data, as_json)
        if args.action == "receipt-append":
            receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
            return _ok(ReceiptChain(Path(args.chain)).append(receipt), as_json)
        pack_raw = json.loads(Path(args.pack).read_text(encoding="utf-8"))
        pack = ContinuityPack.from_dict(pack_raw)
        if args.action == "validate-pack":
            findings = validate_pack(pack, policy)
            result = {"valid": not any(x["status"] == "BLOCK" for x in findings),
                      "findings": findings}
            if not result["valid"]:
                print(_json_or_human(result, as_json))
                return 2
            return _ok(result, as_json)
        if args.action == "evaluate":
            result = evaluate_pack(pack, policy)
            if result["status"] == "BLOCK":
                print(_json_or_human(result, as_json))
                return 2
            return _ok(result, as_json)
        if args.action == "receipt-verify":
            receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
            result = verify_receipt(receipt, pack, policy)
            if not result["valid"]:
                print(_json_or_human(result, as_json))
                return 2
            return _ok(result, as_json)
        if args.action == "plan-drill":
            return _ok(plan_drill(pack, args.environment), as_json)
        return _fail("unknown continuity action")
    except (OSError, json.JSONDecodeError, ContinuityError) as exc:
        return _fail(str(exc))


def _evidence_store_path(repo):
    return os.path.join(repo, ".capt", "evidence", "evidence.jsonl")


def _evidence_load(repo):
    from capt_solo.evidence.core import EvidenceRecord
    path = _evidence_store_path(repo)
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(EvidenceRecord.from_dict(json.loads(line)))
    return out


def _evidence_save(repo, records):
    from capt_solo.evidence.core import EvidenceRecord
    path = _evidence_store_path(repo)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r.to_dict()) + "\n")


def _cmd_evidence(args, as_json) -> int:
    from capt_solo.evidence import (
        EvidenceRecord, EvidenceClaim, EvidenceSource, EvidenceClass, EvidenceStatus,
        ProofGraph,
    )
    from capt_solo.evidence.guard import build_guard_decision
    from capt_solo.evidence.invalidation import scan_invalidation, InvalidationReason
    repo = os.path.abspath(os.path.dirname(__file__))
    action = args.action
    if action == "status":
        recs = _evidence_load(repo)
        by_status = {}
        for r in recs:
            by_status[r.status] = by_status.get(r.status, 0) + 1
        return _ok({"total": len(recs), "by_status": by_status}, as_json)
    if action == "show":
        recs = _evidence_load(repo)
        rec = next((r for r in recs if r.record_id == args.record_id), None)
        if rec is None:
            return _fail(f"evidence not found: {args.record_id}")
        return _ok(rec.to_dict(), as_json)
    if action == "trace":
        recs = _evidence_load(repo)
        g = ProofGraph()
        for r in recs:
            g.add_node(r.record_id, "evidence", r.record_id)
            g.link(r.record_id, r.claim.claim_id)
        supporters = g.what_supports_claim(args.claim_id)
        return _ok({"claim_id": args.claim_id if hasattr(args, "claim_id") else args.claim_id,
                    "supporting_evidence": supporters}, as_json)
    if action == "invalidate":
        recs = _evidence_load(repo)
        ev = scan_invalidation(args.reason, args.path, recs)
        # apply status change to affected records
        for r in recs:
            if r.record_id in ev.affected_evidence_ids:
                r.status = EvidenceStatus.INVALIDATED.value
                r.invalidation_links.append(ev.event_id)
        _evidence_save(repo, recs)
        return _ok({"event_id": ev.event_id, "affected": ev.affected_evidence_ids,
                    "unaffected": ev.unaffected_evidence_ids,
                    "invalidation_scope": ev.invalidation_scope}, as_json)
    if action == "reuse-decision":
        recs = _evidence_load(repo)
        decision = build_guard_decision(claim_id=args.claim_id, vsi_state=args.vsi,
                                        evidence=recs, user_fresh=args.user_fresh)
        return _ok(decision, as_json)
    if action == "conflicts":
        recs = _evidence_load(repo)
        conflicts = [r.record_id for r in recs if r.status == EvidenceStatus.CONFLICTED.value]
        return _ok({"conflicts": conflicts}, as_json)
    return _fail("unknown evidence action (expected status|show|trace|invalidate|reuse-decision|conflicts)")


def _cmd_mission(args, as_json) -> int:
    from capt_solo.evidence import MissionCheckpoint, CheckpointStore, detect_divergence, resume_plan
    repo = os.path.abspath(os.path.dirname(__file__))
    action = args.action
    store = CheckpointStore(repo)
    if action == "checkpoint":
        cp = MissionCheckpoint(
            mission_id=args.mission_id, project_id=args.project_id,
            objective=args.objective, current_phase=args.phase,
            next_safe_action=args.next_action, latest_verified_state=args.head)
        store.save(cp)
        return _ok({"saved": args.mission_id, "path": os.path.join(repo, ".capt", "checkpoints", f"{args.mission_id}.json")}, as_json)
    if action == "status":
        ids = store.list_ids()
        return _ok({"checkpoints": ids}, as_json)
    if action == "resume":
        cp = store.load(args.mission_id)
        if cp is None:
            return _fail(f"checkpoint not found: {args.mission_id}")
        div = detect_divergence(cp, current_head=cp.latest_verified_state or "",
                                current_branch="", current_files=cp.files_changed)
        plan = resume_plan(cp, div)
        store.record_event(args.mission_id, "resumed")
        return _ok({"mission_id": args.mission_id, **plan}, as_json)
    return _fail("unknown mission action (expected checkpoint|status|resume)")


def _cmd_selfmod(args, as_json) -> int:
    from capt_solo.evidence import SelfModificationGovernor, SelfModState
    repo = os.path.abspath(os.path.dirname(__file__))
    # Persist governors per mission in .capt/selfmod/<mission>.json
    import tempfile
    gov_dir = os.path.join(repo, ".capt", "selfmod")
    os.makedirs(gov_dir, exist_ok=True)
    mission = getattr(args, "mission_id", "cli") if hasattr(args, "mission_id") else "cli"
    gov_path = os.path.join(gov_dir, f"{mission}.json")
    gov = SelfModificationGovernor(mission_id=mission)
    if os.path.exists(gov_path):
        import json as _json
        data = _json.load(open(gov_path))
        for rd in data.get("records", []):
            from capt_solo.evidence import SelfModificationRecord
            gov._records.append(SelfModificationRecord(**rd))
    action = args.action
    if action == "status":
        return _ok({"mission": mission, "records": [r.to_dict() for r in gov.records()]}, as_json)
    if action == "propose":
        rec = gov.propose(
            proposed_change=args.change, rationale=args.rationale,
            triggering_evidence="cli", original_behavior="", expected_improvement="",
            risk_analysis="cli-proposed", affected_scope=args.scope,
            diff=args.diff, tests_or_validation="", rollback_path=args.rollback,
            approval_requirement="global_approval" if args.scope == "global_policy" else "project_local")
        _json_dump(gov, gov_path)
        return _ok({"record_id": rec.record_id, "status": rec.status}, as_json)
    if action == "diff":
        rec = next((r for r in gov.records() if r.record_id == args.record_id), None)
        if rec is None:
            return _fail(f"record not found: {args.record_id}")
        return _ok({"record_id": rec.record_id, "diff": rec.diff, "status": rec.status}, as_json)
    if action == "rollback":
        try:
            rec = gov.rollback(args.record_id)
        except Exception as e:
            return _fail(str(e))
        _json_dump(gov, gov_path)
        return _ok({"record_id": rec.record_id, "status": rec.status}, as_json)
    return _fail("unknown selfmod action (expected status|propose|diff|rollback)")


def _json_dump(gov, path):
    import json as _json
    _json.dump({"records": [r.to_dict() for r in gov.records()]}, open(path, "w"), indent=2)


def _cmd_memory(mgr, args, as_json) -> int:
    lc = mgr.lifecycle
    if args.action == "list":
        rows = mgr._eng.list()
        return _ok([r.to_dict() for r in rows], as_json)
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
    if not _RUNTIME_OK:
        return _fail(f"runtime unavailable: {_runtime_err}")
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
