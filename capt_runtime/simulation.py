"""Simulation Plane M0 (ADR-DT-PLANE-CONV, Gate 11).

An isolated environment for benchmarks, replay, chaos, driver/planner/memory-policy
testing, 32k trigger-policy experiments, grouped GRPO rollouts, candidate-model
evaluation, security/performance/acceptance testing.

Required properties:
- frozen initial state
- resettable environment
- isolated capabilities
- no production credentials
- no production writes
- deterministic fixtures where practical
- exact environment digest
- exact dataset digest
- no candidate cross-visibility
- reproducible receipts
- explicit simulation markers

Simulation may reproduce production contracts. Simulation may NEVER inherit
production authority. A simulation result must NEVER silently become production
evidence or production state.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from .contracts import require
from .errors import AuthorityViolation


def create_environment(
    sim_id: str,
    environment_digest: str,
    dataset_digest: str,
) -> Dict[str, Any]:
    """Create an isolated simulation environment. Authority is explicitly false."""
    env = {
        "schemaVersion": "1.0.0",
        "simId": sim_id,
        "environmentDigest": environment_digest,
        "datasetDigest": dataset_digest,
        "isSimulation": True,
        "productionAuthority": False,
    }
    return require("SimulationEnvironment", env)


def mark_simulation(marker_id: str, sim_id: str, kind: str) -> Dict[str, Any]:
    """Attach an explicit simulation marker so a result can never become production."""
    marker = {
        "schemaVersion": "1.0.0",
        "markerId": marker_id,
        "simId": sim_id,
        "kind": kind,
    }
    return require("SimulationMarker", marker)


def assert_no_production_authority(env: Dict[str, Any]) -> None:
    """Reject any simulation environment that claims production authority."""
    if env.get("productionAuthority") is not False:
        raise AuthorityViolation("simulation environment %s must not hold production authority"
                                 % env.get("simId"))
    if env.get("isSimulation") is not True:
        raise AuthorityViolation("simulation environment %s must be marked isSimulation"
                                 % env.get("simId"))


def environment_digest(snapshot: Dict[str, Any]) -> str:
    """Compute an exact, reproducible digest of the frozen initial state."""
    canon = json.dumps(snapshot, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(canon).hexdigest()


def reject_simulation_as_production(payload: Dict[str, Any]) -> None:
    """Guard: a simulation result/artifact/evidence/state must not become production.

    If the payload lacks a simulation marker while claiming to be from a sim, or
    if it carries production authority, reject it.
    """
    if payload.get("isSimulation") is True and payload.get("productionAuthority") is True:
        raise AuthorityViolation("simulation payload claims production authority; rejected")
    if payload.get("fromSimulation") is True and "simulationMarker" not in payload:
        raise AuthorityViolation("simulation result missing explicit marker; cannot enter production")
