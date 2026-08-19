"""CAPT operator CLI (UI Foundation).

A thin CLI surface over the SHARED operator layer, so CLI, TUI, Desktop, and
future Web all consume the same abstractions. No duplicated business/provider/
runtime logic.

Commands:
  capt ui onramp               run the first-run onboarding flow
  capt ui status               runtime status + active model
  capt ui dashboard            full operator dashboard
  capt ui providers            list / test / activate providers
  capt ui models               list models, set default/active
  capt ui verbosity            get/set CaveCAPT verbosity
"""

from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from capt_ui.operator.bootstrap import resolve_runtime  # noqa: E402
from capt_ui.operator.contract import Verbosity  # noqa: E402
from capt_ui.operator.models import ModelManager  # noqa: E402
from capt_ui.operator.onramp import run_onboarding  # noqa: E402
from capt_ui.operator.providers import ProviderManager  # noqa: E402
from capt_ui.operator.runtime import Operator  # noqa: E402
from capt_ui.operator.verbosity import CaveCAPT  # noqa: E402


def _op() -> Operator:
    sock, token = resolve_runtime()
    if not (sock and token):
        raise SystemExit("error: CAPT runtime not running (no socket/token). Start it first.")
    op = Operator(sock, token)
    op.connect()
    return op


def _cfg() -> Path:
    import os
    override = os.environ.get("CAPT_SOLO_HOME") or os.environ.get("CAPT_STATE_DIR")
    return (Path(override).expanduser() / "ui") if override else (Path.home() / ".capt" / "ui")


def _out(obj: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(obj, default=str, indent=2))
    else:
        if isinstance(obj, dict):
            for k, v in obj.items():
                print("%-20s %s" % (k + ":", v if not isinstance(v, (dict, list)) else json.dumps(v, default=str)))
        else:
            print(obj)


def cmd_status(args) -> int:
    op = _op()
    st = op.status()
    pm = ProviderManager(_cfg())
    mm = ModelManager(_cfg(), providers=pm)
    active = mm.active()
    d = op.dashboard()
    data = {
        "runtime": st.health.value, "integrity": st.integrity,
        "version": st.runtime_version, "model": active.model_id,
        "provider": active.provider_name, "kind": active.kind,
        "context_used": d.status.context_used, "approvals": d.status.approvals_pending,
        "head": d.status.head_sequence,
    }
    _out(data, args.json)
    return 0


def cmd_dashboard(args) -> int:
    op = _op()
    d = op.dashboard()
    _out({"missions": len(d.missions), "approvals": len(d.approvals),
          "events": len(d.events), "driver_runs": len(d.driver_runs),
          "verification": d.verification.get("status", {}).get("kind")}, args.json)
    return 0


def cmd_providers(args) -> int:
    pm = ProviderManager(_cfg())
    if args.key_ref:
        p = pm.update(args.key_ref[0], {"key_ref": args.key_ref[1]})
        _out({"provider": p.id if p else "", "key_ref": "configured" if p else ""}, args.json)
        return 0
    if args.prewarm:
        res = pm.prewarm(args.prewarm, args.model or "")
        _out(res, args.json)
        return 0
    if args.test:
        res = pm.test(args.test)
        _out(res.to_dict(), args.json)
        return 0
    if args.activate:
        target = pm.get(args.activate)
        if target is not None and target.models:
            mm = ModelManager(_cfg(), providers=pm)
            current_default = mm.summary().get("default") or {}
            model_id = current_default.get("model")
            if current_default.get("provider") != target.id or model_id not in target.models:
                model_id = target.models[0]
            mm.set_default(target.id, model_id)
        p = pm.activate(args.activate)
        _out({"activated": args.activate, "kind": pm.label(p) if p else "?"}, args.json)
        return 0
    from .secrets import safe_to_dict
    rows = [safe_to_dict(p) for p in pm.list()]
    _out(rows, args.json)
    return 0


def cmd_capabilities(args) -> int:
    from .provider_support import full_matrix
    _out(full_matrix(), args.json)
    return 0


def cmd_models(args) -> int:
    pm = ProviderManager(_cfg())
    mm = ModelManager(_cfg(), providers=pm)
    if args.set:
        # capt ui models --set provider/model
        prov, _, model = args.set.partition("/")
        mm.set_default(prov, model)
        _out({"default": {"provider": prov, "model": model}}, args.json)
        return 0
    active = mm.active()
    data = {"active": active.model_id, "provider": active.provider_name,
            "kind": active.kind, "default": mm.summary().get("default"),
            "available": [m.model_id for m in mm.available()],
            "favorites": mm.summary().get("favorites")}
    _out(data, args.json)
    return 0


def cmd_verbosity(args) -> int:
    v = CaveCAPT(_cfg())
    if args.set:
        v.set(Verbosity(args.set.lower()))
    _out({"verbosity": v.value.value}, args.json)
    return 0


def cmd_memory(args) -> int:
    op = _op()
    if args.store:
        res = op.store_memory(args.store, provenance="cli")
        _out(res, args.json)
        return 0 if res.get("ok") else 1
    if args.list:
        _out({"note": "use the capt_solo memory API for search/list; runtime exposes policy/state"},
             args.json)
        return 0
    _out({"policy": op.memory_policy(), "state": op.memory_state()}, args.json)
    return 0


def cmd_onramp(args) -> int:
    op = _op()
    res = run_onboarding(op, _cfg())
    if args.json:
        print(json.dumps(res, default=str, indent=2))
    else:
        print("onboarding trace:")
        for line in res["trace"]:
            print("  " + line)
    return 0 if res.get("ok") else 1


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="capt ui", description="CAPT operator surface")
    sub = p.add_subparsers(dest="cmd", required=True)
    p.add_argument("--json", action="store_true")

    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    d = sub.add_parser("dashboard")
    d.add_argument("--json", action="store_true")

    pr = sub.add_parser("providers")
    pr.add_argument("--test")
    pr.add_argument("--prewarm")
    pr.add_argument("--model")
    pr.add_argument("--activate")
    pr.add_argument("--key-ref", nargs=2, metavar=("PROVIDER", "REF"))
    pr.add_argument("--json", action="store_true")

    cap = sub.add_parser("capabilities")
    cap.add_argument("--json", action="store_true")

    mo = sub.add_parser("models")
    mo.add_argument("--set", metavar="provider/model")
    mo.add_argument("--json", action="store_true")

    vb = sub.add_parser("verbosity")
    vb.add_argument("--set", choices=[v.value for v in Verbosity.all()])
    vb.add_argument("--json", action="store_true")

    mem = sub.add_parser("memory")
    mem.add_argument("--store", metavar="TEXT")
    mem.add_argument("--list", action="store_true")
    mem.add_argument("--json", action="store_true")

    on = sub.add_parser("onramp")
    on.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    handlers = {
        "status": cmd_status, "dashboard": cmd_dashboard,
        "providers": cmd_providers, "capabilities": cmd_capabilities,
        "models": cmd_models,
        "verbosity": cmd_verbosity, "memory": cmd_memory, "onramp": cmd_onramp,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
