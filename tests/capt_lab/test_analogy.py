import json
import subprocess
import sys

import pytest

from capt_lab.contracts import LabEngineRequest, LabInputError
from capt_lab.engines.analogy import execute_analogy, stable_symbol_vector
from capt_lab.registry import build_default_registry


def request(operation, value):
    return LabEngineRequest.from_mapping({
        "engineId": "lab.analogy", "operation": operation, "input": value,
        "missionId": "m-a", "taskId": "m-a-task-1",
    })


def test_symbol_vectors_are_cross_process_deterministic():
    script = (
        "import json; from capt_lab.engines.analogy import stable_symbol_vector; "
        "print(json.dumps(stable_symbol_vector('CAUSE', 32)))"
    )
    one = subprocess.check_output([sys.executable, "-c", script], text=True)
    two = subprocess.check_output([sys.executable, "-c", script], text=True)
    assert one == two
    assert json.loads(one) == pytest.approx(stable_symbol_vector("CAUSE", 32))


def test_structural_map_preserves_donor_70_30_weighting_and_role_map():
    out = execute_analogy(request("structural_map", {
        "source": {"name": "fire", "roles": {"CAUSE": "fire", "EFFECT": "smoke"}},
        "target": {"name": "bug", "roles": {"CAUSE": "bug", "EFFECT": "crash"}},
    }), {"driverRunId": "dr-a"})
    obs = out.observation
    assert out.epistemic_class == "heuristic"
    assert obs["roleMapping"] == {"CAUSE": "CAUSE", "EFFECT": "EFFECT"}
    assert obs["mappedFillers"] == {"fire": "bug", "smoke": "crash"}
    expected = 0.7 * obs["structuralSimilarity"] + 0.3 * obs["surfaceSimilarity"]
    assert obs["confidence"] == pytest.approx(expected, abs=1e-12)
    assert obs["structuralSimilarity"] == pytest.approx(1.0, abs=1e-12)
    assert obs["isAnalogy"] is True


def test_schema_abstract_reports_common_roles_without_truth_claim():
    out = execute_analogy(request("schema_abstract", {"structures": [
        {"name": "one", "roles": {"CAUSE": "a", "EFFECT": "b", "CONTEXT": "x"}},
        {"name": "two", "roles": {"CAUSE": "c", "EFFECT": "d"}},
        {"name": "three", "roles": {"CAUSE": "e", "EFFECT": "f"}},
    ]}), {"driverRunId": "dr-a"})
    assert out.epistemic_class == "advisory"
    assert out.observation["commonRoles"] == ["CAUSE", "EFFECT"]
    assert out.observation["structureCount"] == 3
    assert "verified" not in out.observation


def test_analogy_rejects_oversized_structure():
    roles = {"R%03d" % i: "f%d" % i for i in range(65)}
    with pytest.raises(LabInputError, match="roles"):
        execute_analogy(request("structural_map", {
            "source": {"name": "too-big", "roles": roles},
            "target": {"name": "small", "roles": {"CAUSE": "x"}},
        }), {})


def test_registry_marks_analogy_available():
    item = next(x for x in build_default_registry().describe() if x["engineId"] == "lab.analogy")
    assert item["available"] is True
