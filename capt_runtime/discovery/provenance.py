"""Discovery provenance (v0.7).

Builds a deterministic provenance envelope for a discovery run so that output can
answer: who/what requested discovery, which strategy produced each observation,
which root was searched, what policy applied, what was rejected and why, and what
redactions occurred.

This is intentionally thin: it does NOT create a parallel mini-provenance system.
It emits a JSON-serializable envelope consumed by the governed runtime operation,
which then maps it onto CAPT's canonical EvidenceRecord (see __init__.py
``to_evidence``). Provenance here never carries authority.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional


def new_run_id(prefix: str = "disc") -> str:
    return "%s-%s" % (prefix, uuid.uuid4().hex[:12])


def build_run_provenance(*, requester: str, request_id: str,
                         allowed_roots: List[str], limits: Dict[str, Any],
                         policy_name: str,
                         extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Provenance envelope for a discovery run."""
    env = dict(extra or {})
    return {
        "run_id": new_run_id(),
        "request_id": request_id,
        "requester": requester,
        "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "allowed_roots": [str(r) for r in allowed_roots],
        "limits": dict(limits),
        "policy": policy_name,
        "strategy_ladder": "capt_runtime.discovery.policy.ESCALATION_LADDER",
        "three_guess_rule": "after 3 failed direct guesses force enumeration",
        "no_capability_grant": True,
        "remote_export": "disabled",
        **env,
    }


def observation_provenance(*, run_id: str, strategy: str, root: str,
                           classification: str, confidence: str,
                           redactions: List[str],
                           accepted: bool) -> Dict[str, Any]:
    """Per-observation provenance (which strategy/root produced it)."""
    return {
        "run_id": run_id,
        "strategy": strategy,
        "root": root,
        "classification": classification,
        "confidence": confidence,
        "redactions": list(redactions),
        "accepted": accepted,
    }
