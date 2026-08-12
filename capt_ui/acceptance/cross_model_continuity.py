"""REAL cross-model continuity acceptance scaffold (Phase 8 / flagship).

This is the SCAFFOLD for the v0.6 flagship proof. It does NOT yet pass — it
requires REAL model execution through two distinct providers (e.g. LM Studio ->
Ollama) and actual process-boundary shutdown/restart. It is gated so it
SKIPS cleanly (never fabricates success) until real providers are connected.

Acceptance contract (what the real proof must demonstrate):
    Provider A -> real model A selected
    -> governed mission
    -> actual model-generated work
    -> artifact/evidence persisted
    -> checkpoint
    -> runtime shutdown, process exits
    Provider B -> runtime restarted against same authoritative state
    -> real model B selected
    -> bounded ContextPack/state recovered
    -> previous completed work inspected
    -> NO completed work repeated
    -> new model-generated work
    -> new evidence persisted
    -> verification
    -> ClaimGuard
    -> complete provenance chain

Continuity must belong to CAPT (EventStore/checkpoint/replay), not to either
model's transcript. At least one local-first combination must be demonstrated.

Do NOT fabricate model responses for this proof.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from capt_ui.operator.bootstrap import resolve_runtime  # noqa: E402
from capt_ui.operator.providers import ProviderManager  # noqa: E402


# Which transport adapters support REAL model execution today.
# Until model_execution=True and a real endpoint is reachable, the flagship
# proof is NOT runnable and must not be claimed.
def _ready_providers() -> Dict[str, List[str]]:
    """Return {provider_id: [models]} for providers with a reachable real
    execution path. Empty unless a real server is up."""
    pm = ProviderManager()
    ready: Dict[str, List[str]] = {}
    for pid in ("ollama", "lmstudio"):
        p = pm.get(pid)
        if not p:
            continue
        # only count providers whose transport has a real model list
        try:
            from capt_ui.operator.adapters import list_models_via_adapter
            models = list_models_via_adapter(p)
            if models:
                ready[pid] = models
        except Exception:  # noqa: BLE001
            continue
    return ready


def real_provider_available() -> bool:
    """True only if a real local-first model provider is reachable with models."""
    return bool(_ready_providers())


def run_real_cross_model_demo(provider_a: str, model_a: str,
                              provider_b: str, model_b: str) -> Dict[str, Any]:
    """Executes the real cross-model continuity proof. Raises if any step cannot
    be genuinely performed (no fabricated success)."""
    evidence_chain: List[str] = []

    # 0. connectivity to real providers
    ready = _ready_providers()
    if provider_a not in ready or provider_b not in ready:
        raise RuntimeError(
            "real cross-model proof requires two reachable model providers; "
            "ready=%s" % sorted(ready))

    # 1. Provider A -> model A selected
    evidence_chain.append("model_A_selected=%s/%s" % (provider_a, model_a))
    print("[MODEL A] %s/%s" % (provider_a, model_a))

    # 2. governed mission + real model-generated work
    #    (REQUIRES a governed execution driver wired to a real model; not yet)
    raise NotImplementedError(
        "REAL cross-model proof cannot run yet: governed model execution "
        "driver (real model A -> artifact -> checkpoint -> process exit -> "
        "model B -> no-repeat recovery) is not implemented. "
        "This is the flagship v0.6 release-gate item, NOT the UI continuity demo.")


def main() -> int:
    pm = ProviderManager()
    ready = _ready_providers()

    # Word-of-warning to the operator: if this ends in NotImplementedError, that
    # is the CORRECT honest outcome, not a failure to paper over.
    print("=== REAL CROSS-MODEL CONTINUITY ACCEPTANCE ===")
    print("ready real providers: %s" % (sorted(ready) or "NONE"))
    if not ready:
        print("No real model provider reachable. Proof cannot run and is NOT claimed.")
        print("Status: PENDING (requires real provider/model execution).")
        return 2

    # pick first two ready providers as A and B
    ids = sorted(ready)
    pa, pb = ids[0], ids[1] if len(ids) > 1 else ids[0]
    try:
        run_real_cross_model_demo(pa, ready[pa][0], pb, ready[pb][0])
    except NotImplementedError as exc:
        print("[STOP] %s" % str(exc)[:200])
        print("Status: PENDING (real model execution not yet wired).")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
