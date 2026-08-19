#!/usr/bin/env python3
"""CAPT-UPG-020 reciprocal-review benchmark scorer.

Scores observed trial records only. It never invokes a model or manufactures
benchmark outcomes; generation/execution is a separate evidence step.
"""
from __future__ import annotations

import argparse
import json
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

OPTIONAL_METRICS = (
    ("tokens", "meanTokens", "recordedTokensCount"),
    ("costUsd", "meanCostUsd", "recordedCostUsdCount"),
    ("latencyMs", "meanLatencyMs", "recordedLatencyMsCount"),
)


def validate_trial(trial: Mapping[str, Any]) -> None:
    required = (
        "trialId", "caseId", "caseDigest", "runId", "mode",
        "defectPresent", "flagged", "groundTruthRef", "evidenceRef",
    )
    missing = [key for key in required if key not in trial]
    if missing:
        raise ValueError("benchmark trial missing fields: %s" % missing)
    if not str(trial["trialId"]).strip() or not str(trial["caseId"]).strip():
        raise ValueError("trialId and caseId must be non-empty")
    if not str(trial["caseDigest"]).strip() or not str(trial["runId"]).strip():
        raise ValueError("caseDigest and runId must be non-empty")
    if not str(trial["groundTruthRef"]).strip():
        raise ValueError("observed benchmark trial requires groundTruthRef")
    if not str(trial["evidenceRef"]).strip():
        raise ValueError("observed benchmark trial requires evidenceRef")
    if trial["mode"] not in MODES:
        raise ValueError("unknown benchmark mode: %s" % trial["mode"])
    if not isinstance(trial["defectPresent"], bool) or not isinstance(trial["flagged"], bool):
        raise ValueError("defectPresent and flagged must be booleans")
    if trial["mode"] in ("independent_reviewer", "reviewer_plus_verification"):
        generator = trial.get("generatorIdentity")
        reviewer = trial.get("reviewerIdentity")
        if not generator or not reviewer:
            raise ValueError("independent review trials require generator/reviewer identities")
        if generator == reviewer:
            raise ValueError("independent reviewer must differ from generator identity")
    if trial["mode"] in ("deterministic_verification", "reviewer_plus_verification"):
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


def score_trials(trials: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    seen_trial_ids = set()
    case_fingerprints: Dict[str, tuple[str, bool, str]] = {}
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
        grouped[str(trial["mode"])].append(trial)

    results: Dict[str, Any] = {}
    case_sets: Dict[str, set] = {}
    for mode in MODES:
        rows = grouped.get(mode, [])
        case_sets[mode] = {str(row["caseId"]) for row in rows}
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
        result = {
            "trialCount": len(rows),
            "defectPresentCount": tp + fn,
            "cleanCaseCount": fp + tn,
            "truePositives": tp,
            "falsePositives": fp,
            "falseNegatives": fn,
            "trueNegatives": tn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "falseRejectionRate": _ratio_or_none(fp, fp + tn),
            "caseIds": sorted(case_sets[mode]),
        }
        for source_key, mean_key, count_key in OPTIONAL_METRICS:
            result[mean_key] = _mean_recorded(rows, source_key)
            result[count_key] = _recorded_count(rows, source_key)
        results[mode] = result

    populated = [mode for mode in MODES if results[mode]["trialCount"] > 0]
    all_populated = len(populated) == len(MODES)
    populated_sets = [case_sets[mode] for mode in populated]
    comparable = bool(populated_sets) and all(case_set == populated_sets[0] for case_set in populated_sets[1:])
    comparison_eligible = all_populated and comparable

    return {
        "schemaVersion": "1.1.0",
        "kind": "ReciprocalReviewBenchmarkResult",
        "modes": results,
        "populatedModes": populated,
        "allRequiredModesPopulated": all_populated,
        "comparableCaseSet": comparable,
        "comparisonEligible": comparison_eligible,
        "claimStatus": "comparable_empirical_result" if comparison_eligible else "insufficient_for_comparison",
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
    return 0 if result["comparisonEligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
