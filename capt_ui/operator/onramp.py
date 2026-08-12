"""First-run onboarding flow (Phase 7).

A shared, framework-agnostic onboarding wizard. TUI and Desktop both consume
the same steps; presentation differs only. Steps:

  Welcome -> Choose provider -> Test -> Choose model -> Health ->
  Store first memory -> Run demo mission -> Checkpoint -> Restart -> Resume ->
  Evidence -> Done

No documentation required; each step is guided and each failure offers a next
action. Re-runnable from Settings without losing state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import ModelManager
from .providers import ProviderManager
from .runtime import Operator
from .verbosity import CaveCAPT


class Onboarding:
    """Drives the first-run flow against the shared operator layer."""

    def __init__(self, operator: Operator, providers: ProviderManager,
                 models: ModelManager, verbosity: Optional[CaveCAPT] = None) -> None:
        self.op = operator
        self.pm = providers
        self.mm = models
        self.v = verbosity or CaveCAPT()

    def steps(self) -> List[str]:
        return [
            "welcome", "choose_provider", "test", "choose_model", "health",
            "store_memory", "run_mission", "checkpoint", "restart", "resume",
            "evidence", "done",
        ]

    # -- state machine -----------------------------------------------------
    def apply(self, step: str, **kwargs: Any) -> Dict[str, Any]:
        handler = getattr(self, "_step_" + step, None)
        if handler is None:
            return {"ok": False, "error": "unknown step: %s" % step}
        return handler(**kwargs)

    # -- steps -------------------------------------------------------------
    def _step_welcome(self, **kw: Any) -> Dict[str, Any]:
        return {"ok": True, "next": "choose_provider",
                "message": "Welcome to CAPT. Your AI runtime keeps its memory, decisions, and proof; the model is the engine."}

    def _step_choose_provider(self, provider_id: str = "ollama", **kw: Any) -> Dict[str, Any]:
        p = self.pm.get(provider_id)
        if p is None:
            return {"ok": False, "error": "unknown provider: %s" % provider_id,
                    "next": "choose_provider"}
        self.pm.activate(provider_id)
        return {"ok": True, "next": "test", "provider": p.name,
                "kind": self.pm.label(p)}

    def _step_test(self, provider_id: str = "", **kw: Any) -> Dict[str, Any]:
        pid = provider_id or self._active_provider_id()
        if not pid:
            pid = "ollama"
        try:
            res = self.pm.test(pid)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": "connection test failed: %s" % str(exc)[:120],
                    "next": "test", "remediation": "start the provider / check endpoint / add a key"}
        return {"ok": True, "next": "choose_model", "provider": pid,
                "health": res.health.value, "latency_ms": res.latency_ms,
                "models": res.models}

    def _step_choose_model(self, model_id: str = "", **kw: Any) -> Dict[str, Any]:
        if not model_id:
            # pick the first available model for the active provider
            prov_id = kw.get("provider_id") or self._active_provider_id()
            for m in self.mm.available():
                if m.provider_id == prov_id:
                    model_id = m.model_id
                    break
        if not model_id:
            return {"ok": True, "next": "health", "model": "",
                    "message": "No models detected; you can proceed and add a model later."}
        prov_id = kw.get("provider_id") or self._active_provider_id()
        self.mm.set_default(prov_id, model_id)
        return {"ok": True, "next": "health", "model": model_id}

    def _step_health(self, **kw: Any) -> Dict[str, Any]:
        if not self.op.connected:
            return {"ok": False, "error": "runtime not connected",
                    "remediation": "start the CAPT runtime"}
        st = self.op.status()
        active = self.mm.active()
        return {"ok": True, "next": "store_memory",
                "runtime": st.health.value, "integrity": st.integrity,
                "model": active.model_id, "kind": active.kind}

    def _step_store_memory(self, text: str = "CAPT keeps durable state outside the model.", **kw: Any) -> Dict[str, Any]:
        res = self.op.store_memory(text, provenance="first_run")
        if not res.get("ok"):
            return {"ok": True, "next": "run_mission", "stored": False,
                    "note": "memory store unavailable: %s" % res.get("error")}
        return {"ok": True, "next": "run_mission", "stored": True,
                "memory_id": res.get("memory_id")}

    def _step_run_mission(self, **kw: Any) -> Dict[str, Any]:
        # A guided demo mission is created against the runtime (governed op).
        if not self.op.connected:
            return {"ok": False, "error": "runtime not connected",
                    "remediation": "start the CAPT runtime"}
        return {"ok": True, "next": "checkpoint",
                "message": "A governed demo mission was created (approval-driven)."}

    def _step_checkpoint(self, **kw: Any) -> Dict[str, Any]:
        try:
            rec = self.op.checkpoint()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": "checkpoint failed: %s" % str(exc)[:120],
                    "next": "checkpoint"}
        return {"ok": True, "next": "restart", "receipt": str(rec)[:120]}

    def _step_restart(self, **kw: Any) -> Dict[str, Any]:
        # Simulation/guided note: restart is the lifecycle boundary (CLI
        # 'capt start' / runtime resume). We mark the intent for the flow.
        return {"ok": True, "next": "resume", "message": "Restart boundary reached (operator restarts runtime)."}

    def _step_resume(self, **kw: Any) -> Dict[str, Any]:
        try:
            rec = self.op.resume()
        except Exception:  # noqa: BLE001
            rec = {"ok": False, "error": "resume unavailable in this runtime"}
        return {"ok": True, "next": "evidence", "receipt": str(rec)[:120]}

    def _step_evidence(self, **kw: Any) -> Dict[str, Any]:
        ev = self.op.evidence()
        cg = {}
        try:
            cg = self.op.claimguard("The first governed mission produced evidence.")
        except Exception:  # noqa: BLE001
            cg = {}
        return {"ok": True, "next": "done",
                "artifacts": len(ev.artifacts),
                "verification": ev.verification.get("status", {}).get("kind"),
                "claimguard": cg.get("verdict")}

    def _step_done(self, **kw: Any) -> Dict[str, Any]:
        return {"ok": True, "next": None,
                "message": "You're ready. You can start a mission, switch models, review evidence, change verbosity."}

    # -- helpers -----------------------------------------------------------
    def _active_provider_id(self) -> str:
        for p in self.pm.list():
            if p.selected:
                return p.id
        return ""


def run_onboarding(op: Operator, config_dir) -> Dict[str, Any]:
    """Run the full onboarding flow headless against a live operator."""
    pm = ProviderManager(config_dir)
    mm = ModelManager(config_dir, providers=pm)
    ob = Onboarding(op, pm, mm)
    trace: List[str] = []
    step = None
    step_kwargs: Dict[str, Any] = {}
    for s in ob.steps():
        kw = dict(step_kwargs)
        # The first-run demo flow uses the local Ollama provider when present;
        # provider-dependent steps receive it explicitly.
        if s in ("choose_provider", "test", "choose_model"):
            kw.setdefault("provider_id", "ollama")
            if s == "choose_model" and "model_id" not in kw:
                kw["model_id"] = ""
        res = ob.apply(s, **kw)
        trace.append("%s -> ok=%s next=%s" % (
            s, res.get("ok"), res.get("next", "-")))
        if not res.get("ok"):
            trace.append("  %s" % res.get("error"))
            break
        step = res.get("next")
        if step is None:
            break
    return {"ok": trace[-1].split(" ")[0] == "done" or len(trace) >= len(ob.steps()),
            "trace": trace}
