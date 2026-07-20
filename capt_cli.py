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
import sys
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
    sub = parser.add_subparsers(dest="group")

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

    args = parser.parse_args(argv)
    if not args.group:
        parser.print_help()
        return 1

    as_json = args.json
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
