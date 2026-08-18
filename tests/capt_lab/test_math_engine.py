import math
import pytest

from capt_lab.contracts import LabEngineRequest, LabInputError
from capt_lab.engines.math_engine import execute_math
from capt_lab.registry import build_default_registry


def run_math(operation, value):
    request = LabEngineRequest.from_mapping({
        "engineId": "lab.math", "operation": operation, "input": value,
        "missionId": "m-math", "taskId": "m-math-task-1",
    })
    return execute_math(request, {"driverRunId": "dr-math"})


def test_cyclotomic_summary_matches_donor_for_fifth_roots():
    out = run_math("cyclotomic_summary", {"conductor": 5})
    assert out.epistemic_class == "calculation"
    assert out.observation == {
        "conductor": 5,
        "degree": 4,
        "discriminant": "125",
        "unitRank": 1,
        "torsionOrder": 10,
    }
    assert any("class-group" in item for item in out.limitations)


def test_cyclotomic_summary_preserves_negative_discriminant():
    out = run_math("cyclotomic_summary", {"conductor": 7})
    assert out.observation["degree"] == 6
    assert out.observation["discriminant"] == "-16807"


@pytest.mark.parametrize("bad", [0, -1, True, 100001, 2.5, "5"])
def test_cyclotomic_summary_rejects_unbounded_or_non_integer_conductor(bad):
    with pytest.raises(LabInputError, match="conductor"):
        run_math("cyclotomic_summary", {"conductor": bad})


def test_mcmillan_tc_matches_donor_fixture():
    out = run_math("mcmillan_tc", {"lambda": 1.0, "omegaLog": 300.0, "muStar": 0.1})
    assert out.epistemic_class == "calculation"
    assert out.observation["tcKelvin"] == pytest.approx(20.8918823496387, rel=1e-13)
    assert out.observation["formula"] == "McMillan"


def test_mcmillan_tc_preserves_donor_zero_branch():
    out = run_math("mcmillan_tc", {"lambda": 0.1, "omegaLog": 300.0, "muStar": 0.5})
    assert out.observation["tcKelvin"] == 0.0


@pytest.mark.parametrize("payload", [
    {"lambda": math.nan, "omegaLog": 300.0, "muStar": 0.1},
    {"lambda": 1.0, "omegaLog": 0.0, "muStar": 0.1},
    {"lambda": -0.1, "omegaLog": 300.0, "muStar": 0.1},
    {"lambda": 1.0, "omegaLog": 300.0, "muStar": -0.1},
])
def test_mcmillan_tc_rejects_invalid_numeric_domain(payload):
    with pytest.raises((LabInputError, ValueError)):
        run_math("mcmillan_tc", payload)


def test_default_registry_marks_only_implemented_math_operations_available():
    item = next(x for x in build_default_registry().describe() if x["engineId"] == "lab.math")
    assert item["available"] is True
    assert [op["name"] for op in item["operations"]] == ["cyclotomic_summary", "mcmillan_tc"]
