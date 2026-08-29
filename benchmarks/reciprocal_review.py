#!/usr/bin/env python3
"""CAPT-UPG-020 reciprocal-review benchmark scorer.

Scores observed trial records only. It never invokes a model or manufactures
benchmark outcomes; generation/execution is a separate evidence step.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

MODES = (
    "self_review",
    "naive_agreement",
    "independent_reviewer",
    "deterministic_verification",
    "reviewer_plus_verification",
)

INDEPENDENT_REVIEW_MODES = frozenset({"independent_reviewer", "reviewer_plus_verification"})
VERIFICATION_MODES = frozenset({"deterministic_verification", "reviewer_plus_verification"})

OPTIONAL_METRICS = (
    ("tokens", "meanTokens", "recordedTokensCount"),
    ("costUsd", "meanCostUsd", "recordedCostUsdCount"),
    ("latencyMs", "meanLatencyMs", "recordedLatencyMsCount"),
)


def validate_trial(trial: Mapping[str, Any]) -> None:
    required = (
        "trialId", "caseId", "caseDigest", "repeatId", "runId", "mode",
        "defectPresent", "flagged", "groundTruthRef", "protocolRef", "evidenceRef",
    )
    missing = [key for key in required if key not in trial]
    if missing:
        raise ValueError("benchmark trial missing fields: %s" % missing)
    for key in ("trialId", "caseId", "caseDigest", "repeatId", "runId", "groundTruthRef", "protocolRef", "evidenceRef"):
        if not str(trial[key]).strip():
            raise ValueError("%s must be non-empty" % key)
    if trial["mode"] not in MODES:
        raise ValueError("unknown benchmark mode: %s" % trial["mode"])
    if not isinstance(trial["defectPresent"], bool) or not isinstance(trial["flagged"], bool):
        raise ValueError("defectPresent and flagged must be booleans")
    if trial["mode"] in INDEPENDENT_REVIEW_MODES:
        generator = trial.get("generatorIdentity")
        reviewer = trial.get("reviewerIdentity")
        if not generator or not reviewer:
            raise ValueError("independent review trials require generator/reviewer identities")
        if generator == reviewer:
            raise ValueError("independent reviewer must differ from generator identity")
        if trial.get("reviewerBlindToGroundTruth") is not True:
            raise ValueError("independent review requires reviewerBlindToGroundTruth=true")
        if trial.get("reviewerBlindToOtherModes") is not True:
            raise ValueError("independent review requires reviewerBlindToOtherModes=true")
        if not str(trial.get("leakageCheckRef") or "").strip():
            raise ValueError("independent review requires leakageCheckRef")
    if trial["mode"] in VERIFICATION_MODES:
        if not trial.get("verificationDomain"):
            raise ValueError("verification mode requires explicit verificationDomain")
        if not trial.get("verificationRef"):
            raise ValueError("verification mode requires explicit verificationRef")


def _ratio_or_none(numerator: int, denominator: int) -> Optional[float]:
    return None if denominator == 0 else float(numerator) / float(denominator)


def _mean_recorded(rows: Sequence[Mapping[str, Any]], key: str) -> Optional[float]:
    values = [row[key] for row in rows if key in row and row[key] is not None]
    if not values:
        return None
    return sum(float(value) for value in values) / float(len(values))


def _recorded_count(rows: Sequence[Mapping[str, Any]], key: str) -> int:
    return sum(1 for row in rows if key in row and row[key] is not None)


def _confusion(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    tp = sum(1 for row in rows if row["defectPresent"] and row["flagged"])
    fp = sum(1 for row in rows if not row["defectPresent"] and row["flagged"])
    fn = sum(1 for row in rows if row["defectPresent"] and not row["flagged"])
    tn = sum(1 for row in rows if not row["defectPresent"] and not row["flagged"])
    precision = _ratio_or_none(tp, tp + fp)
    recall = _ratio_or_none(tp, tp + fn)
    if precision is None or recall is None or precision + recall == 0:
        f1 = None
    else:
        f1 = 2.0 * precision * recall / (precision + recall)
    return {
        "trialCount": len(rows),
        "defectPresentCount": tp + fn,
        "cleanObservationCount": fp + tn,
        "truePositives": tp,
        "falsePositives": fp,
        "falseNegatives": fn,
        "trueNegatives": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "falseRejectionRate": _ratio_or_none(fp, fp + tn),
    }


def _metric_variance(replicates: Sequence[Mapping[str, Any]], key: str) -> Dict[str, Any]:
    values = [float(row[key]) for row in replicates if row.get(key) is not None]
    return {
        "recordedReplicateCount": len(values),
        "mean": (sum(values) / len(values)) if values else None,
        "populationStdDev": statistics.pstdev(values) if len(values) >= 2 else None,
    }


def score_trials(trials: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    seen_trial_ids = set()
    case_fingerprints: Dict[str, tuple[str, bool, str]] = {}
    protocol_refs = set()
    for trial in trials:
        validate_trial(trial)
        trial_id = str(trial["trialId"])
        if trial_id in seen_trial_ids:
            raise ValueError("duplicate trialId: %s" % trial_id)
        seen_trial_ids.add(trial_id)
        case_id = str(trial["caseId"])
        fingerprint = (
            str(trial["caseDigest"]),
            bool(trial["defectPresent"]),
            str(trial["groundTruthRef"]),
        )
        existing = case_fingerprints.get(case_id)
        if existing is not None and existing != fingerprint:
            raise ValueError("case fingerprint mismatch for caseId: %s" % case_id)
        case_fingerprints[case_id] = fingerprint
        protocol_refs.add(str(trial["protocolRef"]))
        grouped[str(trial["mode"])].append(trial)

    if len(protocol_refs) > 1:
        raise ValueError("benchmark trials must use one protocolRef for cross-mode comparability")

    results: Dict[str, Any] = {}
    observation_sets: Dict[str, set] = {}
    case_sets: Dict[str, set] = {}
    for mode in MODES:
        rows = grouped.get(mode, [])
        case_sets[mode] = {str(row["caseId"]) for row in rows}
        observation_sets[mode] = {(str(row["caseId"]), str(row["repeatId"])) for row in rows}
        result = _confusion(rows)
        result["caseIds"] = sorted(case_sets[mode])
        result["repeatIds"] = sorted({str(row["repeatId"]) for row in rows})
        result["repeatCount"] = len(result["repeatIds"])
        result["defectCaseCount"] = len({str(row["caseId"]) for row in rows if row["defectPresent"]})
        result["cleanCaseCount"] = len({str(row["caseId"]) for row in rows if not row["defectPresent"]})
        for source_key, mean_key, count_key in OPTIONAL_METRICS:
            result[mean_key] = _mean_recorded(rows, source_key)
            result[count_key] = _recorded_count(rows, source_key)

        by_repeat: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
        for row in rows:
            by_repeat[str(row["repeatId"])].append(row)
        replicate_metrics = []
        for repeat_id in sorted(by_repeat):
            repeat_result = _confusion(by_repeat[repeat_id])
            repeat_result["repeatId"] = repeat_id
            replicate_metrics.append(repeat_result)
        result["replicateMetrics"] = replicate_metrics
        result["replicateVariance"] = {
            key: _metric_variance(replicate_metrics, key)
            for key in ("precision", "recall", "f1", "falseRejectionRate")
        }
        results[mode] = result

    populated = [mode for mode in MODES if results[mode]["trialCount"] > 0]
    all_populated = len(populated) == len(MODES)
    populated_observation_sets = [observation_sets[mode] for mode in populated]
    comparable = bool(populated_observation_sets) and all(
        observation_set == populated_observation_sets[0]
        for observation_set in populated_observation_sets[1:]
    )
    comparison_eligible = all_populated and comparable
    class_balance_present = all_populated and all(
        results[mode]["defectCaseCount"] > 0 and results[mode]["cleanCaseCount"] > 0
        for mode in MODES
    )
    repeated_runs_present = all_populated and all(results[mode]["repeatCount"] >= 2 for mode in MODES)
    blinding_controls_satisfied = all(
        row.get("reviewerBlindToGroundTruth") is True
        and row.get("reviewerBlindToOtherModes") is True
        and bool(str(row.get("leakageCheckRef") or "").strip())
        for mode in INDEPENDENT_REVIEW_MODES
        for row in grouped.get(mode, [])
    )
    inference_eligible = (
        comparison_eligible
        and class_balance_present
        and repeated_runs_present
        and blinding_controls_satisfied
    )

    if inference_eligible:
        claim_status = "empirical_inference_eligible"
    elif comparison_eligible:
        claim_status = "comparable_empirical_result_incomplete_controls"
    else:
        claim_status = "insufficient_for_comparison"

    return {
        "schemaVersion": "1.2.0",
        "kind": "ReciprocalReviewBenchmarkResult",
        "modes": results,
        "populatedModes": populated,
        "allRequiredModesPopulated": all_populated,
        "comparableCaseSetAndRepeats": comparable,
        "comparisonEligible": comparison_eligible,
        "classBalancePresent": class_balance_present,
        "repeatedRunsPresent": repeated_runs_present,
        "blindingControlsSatisfied": blinding_controls_satisfied,
        "empiricalInferenceEligible": inference_eligible,
        "protocolRef": next(iter(protocol_refs)) if len(protocol_refs) == 1 else None,
        "claimStatus": claim_status,
        "consensusIsVerification": False,
    }


def load_trials(path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("trials", [])
    if not isinstance(raw, list):
        raise ValueError("benchmark input must be a trial list or {'trials': [...]} object")
    return [dict(item) for item in raw]


def main() -> int:
    parser = argparse.ArgumentParser(description="Score observed CAPT reciprocal-review benchmark trials")
    parser.add_argument("trials", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = score_trials(load_trials(args.trials))
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["empiricalInferenceEligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
