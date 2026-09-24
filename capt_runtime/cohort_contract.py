"""Typed cohort execution contract shared by approval and dispatch."""
from __future__ import annotations

from typing import Any, Dict, Optional

MAX_COHORTS = 24
MAX_VESSELS_PER_COHORT = 1000


def normalize_cohort_spec(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("COHORT_SPEC_MUST_BE_OBJECT")
    cohort_id = str(value.get("cohortId") or "").strip()
    if not cohort_id:
        raise ValueError("COHORT_ID_REQUIRED")
    vessels = value.get("vesselsPerCohort")
    if isinstance(vessels, bool) or not isinstance(vessels, int):
        raise ValueError("COHORT_VESSEL_COUNT_INVALID")
    if not 1 <= vessels <= MAX_VESSELS_PER_COHORT:
        raise ValueError("COHORT_VESSEL_COUNT_RANGE")
    configuration_id = str(value.get("configurationId") or "default").strip()
    if not configuration_id:
        raise ValueError("COHORT_CONFIGURATION_ID_REQUIRED")
    return {
        "cohortId": cohort_id,
        "vesselsPerCohort": vessels,
        "configurationId": configuration_id,
    }


def compile_cohort_objective(
    objective: str,
    *,
    provider: str,
    model: str,
    cohort_spec: Optional[Dict[str, Any]],
) -> str:
    base = str(objective or "").strip()
    if not base:
        raise ValueError("COHORT_OBJECTIVE_REQUIRED")
    spec = normalize_cohort_spec(cohort_spec)
    if spec is None:
        return base
    count = int(spec["vesselsPerCohort"])
    cohort_id = str(spec["cohortId"])
    first = f"{cohort_id}-v0001"
    last = f"{cohort_id}-v{count:04d}"
    return (
        base
        + "\n\nCAPT native cohort execution contract:\n"
        + f"- cohort_id: {cohort_id}\n"
        + f"- provider_id: {provider}\n"
        + f"- model_id: {model}\n"
        + f"- configuration_id: {spec['configurationId']}\n"
        + f"- logical_vessels: {count}\n"
        + f"- vessel_namespace: {first}..{last}\n"
        + "- this is ONE provider inference for the whole cohort; never fan "
          "logical vessels out into separate provider calls;\n"
        + f"- instantiate exactly {count} distinct internal analytical "
          "perspectives with non-redundant axes;\n"
        + "- preserve dissent, uncertainty, and counterevidence before convergence;\n"
        + "- end with a cohort synthesis covering consensus, dissent, weak spots, "
          "and next experiments.\n"
    )
