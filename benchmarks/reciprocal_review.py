#!/usr/bin/env python3
"""CAPT-UPG-020 reciprocal-review benchmark scorer.

This harness scores *observed* trial records. It never invokes a model and does
not manufacture benchmark outcomes. Trial generation/execution is a separate
evidence step.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODES = (
    "self_review",
    "naive_agreement",
    "independent_reviewer",
    "deterministic_verification",
    "reviewer_plus_verification",
)


def validate_trial(trial: Mapping[str, Any]) -> None:
    required = ("trialId", "mode", "defectPresent", "flagged")
    missing = [key for key in required if key not in trial]
    if missing:
        raise ValueError("benchmark trial missing fields: %s" % missing)
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


def _safe_ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else float(numerator) / float(denominator)


def score_trials(trials: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for trial in trials:
        validate_trial(trial)
        grouped[str(trial["mode"])].append(trial)

    results: Dict[str, Any] = {}
    for mode in MODES:
        rows = grouped.get(mode, [])
        tp = sum(1 for r in rows if r["defectPresent"] and r["flagged"])
        fp = sum(1 for r in rows if not r["defectPresent"] and r["flagged"])
        fn = sum(1 for r in rows if r["defectPresent"] and not r["flagged"])
        tn = sum(1 for r in rows if not r["defectPresent"] and not r["flagged"])
        precision = _safe_ratio(tp, tp + fp)
        recall = _safe_ratio(tp, tp + fn)
        f1 = 0.0 if precision + recall == 0 else 2.0 * precision * recall / (precision + recall)
        clean_cases = fp + tn
        results[mode] = {
            "trialCount": len(rows),
            "truePositives": tp,
            "falsePositives": fp,
            "falseNegatives": fn,
            "trueNegatives": tn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "falseRejectionRate": _safe_ratio(fp, clean_cases),
            "meanTokens": _safe_ratio(sum(int(r.get("tokens") or 0) for r in rows), len(rows)),
            "meanCostUsd": _safe_ratio(sum(float(r.get("costUsd") or 0.0) for r in rows), len(rows)),
            "meanLatencyMs": _safe_ratio(sum(float(r.get("latencyMs") or 0.0) for r in rows), len(rows)),
        }

    populated = [mode for mode, result in results.items() if result["trialCount"] > 0]
    return {
        "schemaVersion": "1.0.0",
        "kind": "ReciprocalReviewBenchmarkResult",
        "modes": results,
        "populatedModes": populated,
        "allRequiredModesPopulated": len(populated) == len(MODES),
        "claimStatus": "empirical_result_only" if populated else "no_observed_trials",
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
    return 0 if result["allRequiredModesPopulated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
