"""Typed cohort execution contract shared by approval and dispatch."""
from __future__ import annotations

from typing import Any, Dict, Optional

MAX_COHORTS = 24
MAX_VESSELS_PER_COHORT = 1000
OUTPUT_MODALITIES = frozenset({"text", "image"})
IMAGE_OUTPUT_FORMATS = frozenset({"png", "jpeg", "webp"})

LEGACY_CHARTER_FIELDS = (
    "WHO", "WHAT", "WHY", "HOW", "AGAINST",
    "BIAS", "EVIDENCE", "INTERACTIONS", "FALSIFIER", "DELTA",
)
CHARTER_FIELDS_V2 = (
    "SOURCE", "WHO", "WHAT", "WHY", "HOW", "AGAINST",
    "BIAS", "EVIDENCE", "INTERACTIONS", "FALSIFIER", "DELTA",
)
CANDIDATE_FIELDS_V2 = ("AXIS", "MECH", "FALSIFIER", "DELTA")


def default_charter_policy(vessels: int) -> Dict[str, Any]:
    """Return the current strict deep-charter policy for text cohort runs."""
    return {
        "schemaVersion": "2.0.0",
        "mode": "deep_charters",
        "candidateMultiplier": 3,
        "coreVessels": min(int(vessels), 22),
        "adaptiveExpansion": max(0, int(vessels) - 22),
        "recursiveExpansion": True,
        "strictLedger": True,
        "candidateManifest": True,
        "candidateMaxWords": 48,
        "candidateRequiredFields": list(CANDIDATE_FIELDS_V2),
        "requiredFields": list(CHARTER_FIELDS_V2),
    }


def _legacy_charter_policy(value: Dict[str, Any], vessels: int) -> Dict[str, Any]:
    """Normalize pre-v2 policies without retroactively strengthening receipts."""
    multiplier = value.get("candidateMultiplier", 3)
    if isinstance(multiplier, bool) or not isinstance(multiplier, int):
        raise ValueError("VESSEL_CHARTER_MULTIPLIER_INVALID")
    if not 2 <= multiplier <= 8:
        raise ValueError("VESSEL_CHARTER_MULTIPLIER_RANGE")
    fields = value.get("requiredFields") or list(LEGACY_CHARTER_FIELDS)
    return {
        "schemaVersion": "1.0.0",
        "mode": "deep_charters",
        "candidateMultiplier": multiplier,
        "coreVessels": min(int(vessels), 22),
        "adaptiveExpansion": max(0, int(vessels) - 22),
        "recursiveExpansion": True,
        "strictLedger": True,
        "candidateManifest": False,
        "requiredFields": [str(x).upper() for x in fields],
    }


def normalize_charter_policy(value: Any, vessels: int) -> Dict[str, Any]:
    if value is None:
        return default_charter_policy(vessels)
    if not isinstance(value, dict):
        raise ValueError("VESSEL_CHARTER_POLICY_MUST_BE_OBJECT")

    version = str(value.get("schemaVersion") or "1.0.0").strip()
    if version in {"1", "1.0", "1.0.0"}:
        return _legacy_charter_policy(value, vessels)
    if version != "2.0.0":
        raise ValueError("VESSEL_CHARTER_POLICY_SCHEMA_INVALID")

    policy = default_charter_policy(vessels)
    mode = str(value.get("mode") or policy["mode"]).strip()
    if mode != "deep_charters":
        raise ValueError("VESSEL_CHARTER_POLICY_MODE_INVALID")
    multiplier = value.get("candidateMultiplier", policy["candidateMultiplier"])
    if isinstance(multiplier, bool) or not isinstance(multiplier, int):
        raise ValueError("VESSEL_CHARTER_MULTIPLIER_INVALID")
    if not 2 <= multiplier <= 8:
        raise ValueError("VESSEL_CHARTER_MULTIPLIER_RANGE")
    max_words = value.get("candidateMaxWords", policy["candidateMaxWords"])
    if isinstance(max_words, bool) or not isinstance(max_words, int):
        raise ValueError("VESSEL_CHARTER_CANDIDATE_WORD_LIMIT_INVALID")
    if not 16 <= max_words <= 96:
        raise ValueError("VESSEL_CHARTER_CANDIDATE_WORD_LIMIT_RANGE")
    policy["candidateMultiplier"] = multiplier
    policy["candidateMaxWords"] = max_words
    return policy


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

    normalized: Dict[str, Any] = {
        "cohortId": cohort_id,
        "vesselsPerCohort": vessels,
        "configurationId": configuration_id,
    }
    output_modality = "text"
    if "outputModality" in value or "outputFormat" in value:
        output_modality = str(value.get("outputModality") or "text").strip().lower()
        if output_modality not in OUTPUT_MODALITIES:
            raise ValueError("COHORT_OUTPUT_MODALITY_INVALID")
        normalized["outputModality"] = output_modality
        raw_format = str(value.get("outputFormat") or "").strip().lower()
        if output_modality == "image":
            output_format = raw_format or "png"
            if output_format not in IMAGE_OUTPUT_FORMATS:
                raise ValueError("COHORT_IMAGE_OUTPUT_FORMAT_INVALID")
            normalized["outputFormat"] = output_format
        elif raw_format:
            raise ValueError("COHORT_TEXT_OUTPUT_FORMAT_FORBIDDEN")

    # The deep Vessel Charter is a textual result contract. Preserve and normalize
    # it for text cohorts, but do not bind a text ledger to a binary image artifact.
    if output_modality == "text" and "vesselCharterPolicy" in value:
        normalized["vesselCharterPolicy"] = normalize_charter_policy(
            value.get("vesselCharterPolicy"), vessels
        )
    return normalized


def _charter_contract(spec: Dict[str, Any]) -> str:
    policy = spec.get("vesselCharterPolicy")
    if policy is None:
        return ""
    count = int(spec["vesselsPerCohort"])
    cohort_id = str(spec["cohortId"])
    candidate_count = count * int(policy["candidateMultiplier"])
    fields = " | ".join(f"{name}=<...>" for name in policy["requiredFields"])

    if not policy.get("candidateManifest"):
        return (
            "\nCAPT deep Vessel Charter contract (legacy v1):\n"
            f"- requested_vessels: {count}; this is a design target, not a filler quota;\n"
            f"- generate at least {candidate_count} candidate deep charters before selection;\n"
            f"- select exactly {count} non-redundant vessels whenever substantively possible;\n"
            f"- persist: CAPT_CHARTER_AUDIT | generated={candidate_count} | selected={count} | "
            "deduplicated=<integer> | expansion_rounds=<integer>\n"
            f"- persist one row per vessel: CAPT_VESSEL {cohort_id}-vNNNN | {fields}\n"
        )

    candidate_fields = " | ".join(
        f"{name}=<...>" for name in policy["candidateRequiredFields"]
    )
    return (
        "\nCAPT deep Vessel Charter contract v2:\n"
        f"- requested_vessels: {count}; this is a design target, not a filler quota;\n"
        f"- produce a physically countable DEDUPLICATED candidate manifold of at least "
        f"{candidate_count} surviving candidate charters before selection;\n"
        f"- core_vessels: {policy['coreVessels']}; adaptive_challenge_vessels: "
        f"{policy['adaptiveExpansion']};\n"
        "- recursively expand shallow/redundant areas with adversarial twins, interaction "
        "specialists, unresolved-evidence specialists, implementation rivals, assumption "
        "challengers, counterexample constructors, and alternative paradigms;\n"
        "- candidate identity is causal, not cosmetic: distinguish causal question, "
        "mechanism, falsifier, and decision consequence;\n"
        f"- persist every surviving candidate compactly (<= {policy['candidateMaxWords']} "
        "words across field values) using exactly:\n"
        f"  CAPT_CANDIDATE C0001 | {candidate_fields}\n"
        "- candidate IDs must use canonical C + four digits (C0001, C0002, ...); never use CN0001. IDs must be unique and sequentially countable; CAPT independently "
        "checks count and near-duplicate signatures;\n"
        f"- select exactly {count} non-redundant vessels whenever substantively possible; "
        "never silently lower the requested count and never invent filler;\n"
        "- each selected vessel must reference its originating candidate with SOURCE=C0001-style canonical IDs; "
        "one source candidate may feed at most one selected vessel;\n"
        "- persist exactly one audit row AFTER the candidate manifest and before vessels:\n"
        f"  CAPT_CHARTER_AUDIT | candidates=<physical_candidate_row_count> | selected={count} | "
        "expansion_rounds=<integer>\n"
        f"- candidates in the audit must equal the actual physical candidate-row count and be at least {candidate_count};\n"
        "- CAPT validates candidates=physical candidate-row count and selected=physical "
        "vessel-row count; self-reported counts cannot substitute for missing rows;\n"
        "- persist one selected row per vessel using exactly:\n"
        f"  CAPT_VESSEL {cohort_id}-vNNNN | {fields}\n"
        "- every required field must be non-empty; selected charter orthogonality is "
        "independently checked;\n"
        "- keep selected rows compact (target <= 140 words each) and post-ledger synthesis "
        "bounded (target <= 1500 words);\n"
        "- CAPT, not the model, owns staging-artifact persistence. Do not claim persistence "
        "is incomplete merely because model filesystem writes are prohibited;\n"
        "- if the analytical cohort itself cannot satisfy the contract, emit the exact line "
        "CAPT_COHORT_INCOMPLETE and explain why; otherwise do not use that marker;\n"
        "- after the ledger, synthesize consensus, dissent, interactions, weak spots, "
        "vessel utility, and next falsifiable experiments.\n"
    )


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
    modality = str(spec.get("outputModality") or "text")
    common = (
        base
        + "\n\nCAPT native cohort execution contract:\n"
        + f"- cohort_id: {cohort_id}\n"
        + f"- provider_id: {provider}\n"
        + f"- model_id: {model}\n"
        + f"- configuration_id: {spec['configurationId']}\n"
        + f"- output_modality: {modality}\n"
        + f"- logical_vessels: {count}\n"
        + f"- vessel_namespace: {first}..{last}\n"
        + "- this is ONE provider inference for the whole cohort; never fan "
          "logical vessels out into separate provider calls;\n"
    )
    if modality == "image":
        return (
            common
            + f"- interpret exactly {count} logical vessels as distinct visual design "
              "lenses with non-redundant constraints;\n"
            + "- reconcile those lenses inside this single inference into ONE final "
              "visual artifact; do not emit a textual cohort report instead;\n"
            + "- preserve useful tension between lenses through composition, hierarchy, "
              "symbolism, typography, information density, and negative space;\n"
            + "- the final image is unverified provider output until CAPT records and a "
              "human accepts its verification claim.\n"
        )
    return (
        common
        + f"- instantiate exactly {count} distinct internal analytical "
          "perspectives with non-redundant axes;\n"
        + "- preserve dissent, uncertainty, and counterevidence before convergence;\n"
        + _charter_contract(spec)
        + "- end with a cohort synthesis covering consensus, dissent, weak spots, "
          "and next experiments.\n"
    )
