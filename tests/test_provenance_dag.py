"""CAPT-UPG-017 tests for deterministic truthful provenance DAG projection."""

from copy import deepcopy

import pytest

from capt_runtime.errors import IntegrityViolation
from capt_ui.operator.provenance import (
    build_provenance_graph,
    topological_order,
)


def _state():
    return {
        "missions": [{"missionId": "m-1", "state": "active", "rawRequest": "inspect"}],
        "tasks": [{"taskId": "t-1", "missionId": "m-1", "state": "running", "title": "inspect repo"}],
        "approvals": [{
            "requestId": "ap-1",
            "missionId": "m-1",
            "taskId": "t-1",
            "state": "approved",
            "operation": "ModelOperatorInspection",
            "promptAssemblyDigest": "sha256:" + "a" * 64,
        }],
        "driverRuns": [{"driverRunId": "dr-1", "taskId": "t-1", "state": "completed", "driverId": "provider"}],
        "claims": [{
            "claimId": "cl-1",
            "missionId": "m-1",
            "taskId": "t-1",
            "kind": "completion",
            "statement": "inspection completed",
            "evidenceIds": ["ev-1"],
            "promotionState": "accepted",
            "guardVerdict": "accept",
        }],
        "verificationsByClaim": {
            "cl-1": {
                "verificationId": "ver-1",
                "status": {"kind": "verified"},
                "verificationDomain": "artifact_correctness",
                "supportingEvidenceIds": ["ev-1"],
                "committed": True,
            }
        },
        "eventTimeline": [{
            "eventId": "event-evidence",
            "payload": {
                "eventType": "EvidenceRecorded",
                "evidence": {
                    "evidenceId": "ev-1",
                    "evidence": {"kind": "artifact_hash", "artifactDigest": "sha256:" + "1" * 64},
                },
            },
        }],
    }


def _edge_set(graph):
    return {(e["source"], e["target"], e["relation"]) for e in graph["edges"]}


def test_graph_preserves_claim_evidence_verification_and_decision_separation():
    graph = build_provenance_graph(_state())
    edges = _edge_set(graph)

    assert ("mission:m-1", "task:t-1", "contains_task") in edges
    assert ("task:t-1", "approval:ap-1", "requires_approval") in edges
    assert ("task:t-1", "driver_run:dr-1", "executes_as") in edges
    assert ("evidence:ev-1", "claim:cl-1", "supports_claim") in edges
    assert ("evidence:ev-1", "verification:ver-1", "supports_verification") in edges
    assert ("verification:ver-1", "claim:cl-1", "evaluates_claim") in edges
    assert ("claim:cl-1", "claim_decision:cl-1:accept", "adjudicated_by") in edges
    assert graph["authority"] == "projection_only"
    assert len(graph["topologicalOrder"]) == len(graph["nodes"])


def test_unrelated_claim_does_not_receive_fabricated_evidence_edge():
    state = _state()
    state["claims"].append({
        "claimId": "cl-2",
        "missionId": "m-1",
        "statement": "unrelated",
        "evidenceIds": [],
        "promotionState": "proposed",
    })
    graph = build_provenance_graph(state)
    edges = _edge_set(graph)
    assert ("evidence:ev-1", "claim:cl-2", "supports_claim") not in edges


def test_graph_is_deterministic_for_equivalent_projection():
    first = build_provenance_graph(_state())
    second = build_provenance_graph(deepcopy(_state()))
    assert first["graphDigest"] == second["graphDigest"]
    assert first["nodes"] == second["nodes"]
    assert first["edges"] == second["edges"]


def test_cycle_is_reported_not_hidden():
    graph = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [
            {"source": "a", "target": "b", "relation": "x"},
            {"source": "b", "target": "a", "relation": "y"},
        ],
    }
    with pytest.raises(IntegrityViolation, match="contains cycle"):
        topological_order(graph)
