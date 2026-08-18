"""Bounded deterministic QIPC-inspired consensus diagnostics."""

from __future__ import annotations

import math
from typing import Any, Mapping

from capt_lab.contracts import LabEngineRequest, LabEngineResult, LabInputError

_ENGINE_ID = "lab.consensus"
_ENGINE_VERSION = "0.1.0"
_MIN_BELIEFS = 2
_MAX_BELIEFS = 64


def _validate_beliefs(raw: Any):
    if not isinstance(raw, list) or not _MIN_BELIEFS <= len(raw) <= _MAX_BELIEFS:
        raise LabInputError("beliefs must contain %d..%d probabilities" % (_MIN_BELIEFS, _MAX_BELIEFS))
    values = []
    for index, item in enumerate(raw):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise LabInputError("beliefs[%d] must be a finite probability" % index)
        value = float(item)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise LabInputError("beliefs[%d] must be in [0, 1]" % index)
        values.append(value)
    return values


def _aggregate(value: Mapping[str, Any]) -> LabEngineResult:
    if set(value) != {"beliefs"}:
        missing = {"beliefs"} - set(value)
        unknown = set(value) - {"beliefs"}
        if missing:
            raise LabInputError("missing input field beliefs")
        raise LabInputError("unknown input field(s): %s" % ", ".join(sorted(unknown)))
    beliefs = _validate_beliefs(value["beliefs"])

    false_amp = sum(math.sqrt(1.0 - p) for p in beliefs)
    true_amp = sum(math.sqrt(p) for p in beliefs)
    norm2 = false_amp * false_amp + true_amp * true_amp
    if norm2 <= 0.0 or not math.isfinite(norm2):
        raise LabInputError("consensus amplitude normalization failed")
    p_false = (false_amp * false_amp) / norm2
    p_true = (true_amp * true_amp) / norm2
    entropy = -sum(p * math.log2(p) for p in (p_false, p_true) if p > 0.0)
    confidence = max(0.0, min(1.0, 1.0 - entropy))
    most_likely = "true" if p_true >= p_false else "false"
    return LabEngineResult(
        engine_id=_ENGINE_ID,
        engine_version=_ENGINE_VERSION,
        operation="aggregate_beliefs",
        epistemic_class="advisory",
        observation={
            "beliefCount": len(beliefs),
            "meanInputProbability": sum(beliefs) / len(beliefs),
            "probabilityFalse": p_false,
            "probabilityTrue": p_true,
            "entropyBits": entropy,
            "confidence": confidence,
            "mostLikely": most_likely,
        },
        limitations=(
            "This is a deterministic quantum-inspired probability aggregator, not distributed-consensus proof.",
            "Consensus confidence does not verify a claim and cannot override CAPT evidence or verification authority.",
        ),
    )


def execute_consensus(request: LabEngineRequest, context: Mapping[str, Any]) -> LabEngineResult:
    if request.engine_id != _ENGINE_ID:
        raise LabInputError("consensus adapter received wrong engineId")
    if request.operation == "aggregate_beliefs":
        return _aggregate(request.input)
    raise LabInputError("unsupported consensus operation %s" % request.operation)
