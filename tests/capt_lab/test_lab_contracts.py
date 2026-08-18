import math
import pytest

from capt_lab.contracts import (
    LabContractError,
    LabEngineRequest,
    canonical_json_bytes,
    canonical_request_digest,
)


def test_request_digest_is_order_independent():
    a = canonical_request_digest({
        "engineId": "lab.math", "operation": "x",
        "input": {"b": 2, "a": 1}, "missionId": "m-1", "taskId": "t-1",
    })
    b = canonical_request_digest({
        "taskId": "t-1", "missionId": "m-1", "input": {"a": 1, "b": 2},
        "operation": "x", "engineId": "lab.math",
    })
    assert a == b
    assert a.startswith("sha256:") and len(a) == 71


def test_canonical_json_rejects_non_finite_numbers():
    with pytest.raises(LabContractError, match="finite"):
        canonical_json_bytes({"value": math.nan})


def test_request_rejects_unknown_fields_and_bad_ids():
    base = {
        "engineId": "lab.math", "operation": "x", "input": {},
        "missionId": "m-1", "taskId": "t-1",
    }
    with pytest.raises(LabContractError, match="unknown field"):
        LabEngineRequest.from_mapping({**base, "surprise": True})
    with pytest.raises(LabContractError, match="engineId"):
        LabEngineRequest.from_mapping({**base, "engineId": "bad engine id"})


def test_request_round_trip_preserves_lineage_and_input():
    raw = {
        "engineId": "lab.consensus", "operation": "aggregate_beliefs",
        "input": {"beliefs": [0.2, 0.8]}, "missionId": "m-7", "taskId": "m-7-task-2",
    }
    req = LabEngineRequest.from_mapping(raw)
    assert req.to_mapping() == raw
