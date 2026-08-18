"""CAPT-UPG-017 deterministic desktop DAG layout tests."""
from desktop.provenance_lens import layout_provenance_graph


def _graph():
    return {
        "nodes": [
            {"id": "mission:m", "kind": "mission", "identity": "m", "data": {}},
            {"id": "task:t", "kind": "task", "identity": "t", "data": {}},
            {"id": "claim:c", "kind": "claim", "identity": "c", "data": {}},
            {"id": "evidence:e", "kind": "evidence", "identity": "e", "data": {}},
        ],
        "edges": [
            {"source": "mission:m", "target": "task:t", "relation": "contains"},
            {"source": "task:t", "target": "claim:c", "relation": "produces_claim"},
            {"source": "evidence:e", "target": "claim:c", "relation": "supports_claim"},
        ],
        "topologicalOrder": ["evidence:e", "mission:m", "task:t", "claim:c"],
    }


def test_layout_is_deterministic_nonoverlapping_and_flows_left_to_right():
    first = layout_provenance_graph(_graph())
    second = layout_provenance_graph(_graph())
    assert first == second
    assert len(set((p["x"], p["y"]) for p in first.values())) == len(first)

    for edge in _graph()["edges"]:
        assert first[edge["source"]]["x"] < first[edge["target"]]["x"]

    assert first["mission:m"]["depth"] == 0
    assert first["task:t"]["depth"] == 1
    assert first["claim:c"]["depth"] == 2
