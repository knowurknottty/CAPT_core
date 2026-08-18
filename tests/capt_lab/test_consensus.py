import math
import pytest

from capt_lab.contracts import LabEngineRequest, LabInputError
from capt_lab.engines.consensus import execute_consensus
from capt_lab.registry import build_default_registry


def request(value):
    return LabEngineRequest.from_mapping({
        "engineId": "lab.consensus", "operation": "aggregate_beliefs", "input": value,
        "missionId": "m-c", "taskId": "m-c-task-1",
    })


def test_consensus_is_advisory_and_probability_normalized():
    out = execute_consensus(request({"beliefs": [0.2, 0.8, 0.7]}), {"driverRunId": "dr-c"})
    obs = out.observation
    assert out.epistemic_class == "advisory"
    assert obs["probabilityTrue"] + obs["probabilityFalse"] == pytest.approx(1.0)
    assert 0.0 <= obs["confidence"] <= 1.0
    assert obs["mostLikely"] in {"true", "false"}
    assert "verified" not in obs


def test_consensus_unanimous_true_has_full_confidence():
    obs = execute_consensus(request({"beliefs": [1.0, 1.0, 1.0]}), {}).observation
    assert obs["probabilityTrue"] == pytest.approx(1.0)
    assert obs["probabilityFalse"] == pytest.approx(0.0)
    assert obs["confidence"] == pytest.approx(1.0)
    assert obs["mostLikely"] == "true"


def test_consensus_is_deterministic():
    value = {"beliefs": [0.1, 0.4, 0.9, 0.6]}
    one = execute_consensus(request(value), {}).to_mapping()
    two = execute_consensus(request(value), {}).to_mapping()
    assert one == two


@pytest.mark.parametrize("beliefs", [[], [0.5], [math.nan, 0.2], [-0.1, 0.2], [1.1, 0.2], [0.5] * 65])
def test_consensus_rejects_invalid_or_unbounded_beliefs(beliefs):
    with pytest.raises((LabInputError, ValueError)):
        execute_consensus(request({"beliefs": beliefs}), {})


def test_registry_marks_consensus_available():
    item = next(x for x in build_default_registry().describe() if x["engineId"] == "lab.consensus")
    assert item["available"] is True
