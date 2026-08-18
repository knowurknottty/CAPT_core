import pytest

from capt_lab.contracts import LabEngineRequest
from capt_lab.registry import (
    LabEngineDescriptor,
    LabEngineRegistry,
    LabOperationDescriptor,
    LabRegistryError,
    build_default_registry,
)


def test_default_registry_is_deterministic_and_provenanced():
    one = build_default_registry().describe()
    two = build_default_registry().describe()
    assert one == two
    assert [item["engineId"] for item in one] == sorted(item["engineId"] for item in one)
    assert {item["engineId"] for item in one} == {
        "lab.analogy", "lab.consensus", "lab.forge", "lab.math"
    }
    for item in one:
        assert item["operations"]
        assert item["provenance"]["donorRepository"]
        assert item["provenance"]["donorCommit"]
        assert all(op["epistemicClass"] in {
            "calculation", "heuristic", "simulation", "advisory"
        } for op in item["operations"])


def test_registry_rejects_unknown_engine_and_operation_before_dispatch():
    registry = build_default_registry()
    request = LabEngineRequest.from_mapping({
        "engineId": "lab.nope", "operation": "noop", "input": {},
        "missionId": "m-1", "taskId": "t-1",
    })
    with pytest.raises(LabRegistryError, match="unknown engine"):
        registry.execute(request, {"driverRunId": "dr-1"})

    request = LabEngineRequest.from_mapping({
        "engineId": "lab.math", "operation": "not_real", "input": {},
        "missionId": "m-1", "taskId": "t-1",
    })
    with pytest.raises(LabRegistryError, match="unknown operation"):
        registry.execute(request, {"driverRunId": "dr-1"})


def test_duplicate_engine_registration_fails_closed():
    registry = LabEngineRegistry()
    descriptor = LabEngineDescriptor(
        engine_id="lab.test", engine_version="0.1.0", display_name="Test",
        description="test engine",
        operations=(LabOperationDescriptor("inspect", "advisory", "Inspect input"),),
        provenance={"donorRepository": "example/repo", "donorCommit": "abc"},
    )
    registry.register(descriptor, lambda request, context: None)
    with pytest.raises(LabRegistryError, match="already registered"):
        registry.register(descriptor, lambda request, context: None)
