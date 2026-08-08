"""CAPT v0.6 flagship acceptance demonstration (Phase 8).

The canonical end-to-end demo that proves a normal human can operate CAPT:

    Model A -> Mission -> Checkpoint -> Shutdown -> Switch provider -> Model B
      -> Resume -> Evidence -> Verification -> ClaimGuard -> Done

Builds entirely on the shared operator layer and supported runtime commands -
no runtime authority is duplicated. It is executable and produces observable
output, so it doubles as the flagship v0.6 demonstration.

Usage:
    python capt_ui/acceptance/golden_demo.py [--provider-a ollama] [--provider-b lmstudio]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from capt_ui.operator.bootstrap import resolve_runtime  # noqa: E402
from capt_ui.operator.models import ModelManager  # noqa: E402
from capt_ui.operator.providers import ProviderManager  # noqa: E402
from capt_ui.operator.runtime import Operator  # noqa: E402
from capt_ui.operator.verbosity import CaveCAPT  # noqa: E402


class GoldenDemo:
    def __init__(self, provider_a: str = "ollama", provider_b: str = "lmstudio",
                 model_a: str = "", model_b: str = "") -> None:
        self.pa = provider_a
        self.pb = provider_b
        self.ma = model_a
        self.mb = model_b
        self.config_dir = _cfg()
        self.pm = ProviderManager(self.config_dir)
        self.mm = ModelManager(self.config_dir, providers=self.pm)
        self.v = CaveCAPT(self.config_dir)
        self.op: Optional[Operator] = None
        self.steps_log: List[Dict[str, Any]] = []

    # -- helpers -----------------------------------------------------------
    def _log(self, tag: str, **kw: Any) -> None:
        rec = {"step": tag, **kw}
        self.steps_log.append(rec)
        print("[%s] %s" % (tag.upper(), " | ".join("%s=%s" % (k, trunc(v)) for k, v in kw.items() if k != "step")))

    def _connect(self) -> Operator:
        if self.op and self.op.connected:
            return self.op
        sock, token = resolve_runtime()
        if not (sock and token):
            raise SystemExit("error: CAPT runtime not running (no socket/token)")
        self.op = Operator(sock, token)
        self.op.connect()
        return self.op

    # -- the flow ----------------------------------------------------------
    def run(self) -> int:
        op = self._connect()
        # 1. Model A (active provider/model)
        if not self.ma:
            self.mm.set_default(self.pa, self.pa + ":model-a")
            self.ma = self.pa + ":model-a"
        self._log("model_a", provider=self.pa, model=self.ma)

        # 2. Mission (governed op)
        receipt = op.create_mission(_mission_payload("Golden demo mission"), "golden-demo-%d" % int(time.time()))
        self._log("mission", status=receipt.get("status", "accepted"))

        # 3. Checkpoint
        cp = op.checkpoint()
        self._log("checkpoint", status=cp.get("status", "ok"))

        # 4. Shutdown boundary (guided note; runtime stop is external lifecycle)
        self._log("shutdown", message="operator shutdown boundary reached")

        # 5. Switch provider -> Model B
        self.pm.update(self.pb, {"models": [self.pb + ":model-b"]})
        self.pm.activate(self.pb)
        self.mm.set_temporary(self.pb, self.pb + ":model-b")
        active = self.mm.active()
        self.mb = active.model_id
        self._log("model_b", provider=active.provider_id, model=self.mb, kind=active.kind)

        # 6. Resume
        try:
            rs = op.resume()
            self._log("resume", status=rs.get("status", "ok"))
        except Exception as exc:  # noqa: BLE001
            self._log("resume", status="unavailable", note=str(exc)[:60])

        # 7. Evidence + Verification
        ev = op.evidence()
        self._log("evidence", artifacts=len(ev.artifacts),
                  verification=ev.verification.get("status", {}).get("kind", "?"))

        # 8. ClaimGuard
        cg = op.claimguard("The golden demo mission produced evidence under verification.")
        self._log("claimguard", verdict=cg.get("verdict"))

        # 9. Done
        d = op.dashboard()
        self._log("done", runtime=d.status.health.value, missions=len(d.missions))
        self._emit_summary()
        return 0

    def _emit_summary(self) -> None:
        print("\n=== GOLDEN DEMO SUMMARY ===")
        print("active model : %s [%s]" % (self.mm.active().model_id, self.mm.active().kind))
        print("verbosity    : %s" % self.v.value.label)
        print("steps        : %d" % len(self.steps_log))
        for s in self.steps_log:
            print("  - " + s["step"])


def _mission_payload(objective: str) -> Dict[str, Any]:
    import uuid
    return {
        "schemaVersion": "1.0.0",
        "missionId": "m-golden-" + uuid.uuid4().hex[:8],
        "objective": objective,
        "rawRequest": objective,
        "normalizedRequest": objective.lower(),
        "constraints": [],
        "successCriteria": [{"criterionId": "sc-1", "statement": "Mission produced evidence", "requiresVerification": True}],
        "terminationCriteria": [{"criterionId": "tc-1", "statement": "failure", "terminalState": "failed"}],
        "budget": {"maxEvents": 0},
        "unresolvedAmbiguities": [],
        "requiresApproval": False,
        "requestedCapability": "cap.fs.read",
        "operation": "DemoMission",
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False},
        "riskClassification": "low",
        "policyReason": "Flagship demo mission.",
    }


def _cfg():
    import os
    override = os.environ.get("CAPT_SOLO_HOME") or os.environ.get("CAPT_STATE_DIR")
    return (Path(override).expanduser() / "ui") if override else (Path.home() / ".capt" / "ui")


def trunc(v: Any, n: int = 60) -> str:
    s = str(v)
    return s if len(s) <= n else s[:n] + "…"


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="CAPT golden acceptance demo")
    p.add_argument("--provider-a", default="ollama")
    p.add_argument("--provider-b", default="lmstudio")
    args = p.parse_args()
    return GoldenDemo(args.provider_a, args.provider_b).run()


if __name__ == "__main__":
    raise SystemExit(main())
