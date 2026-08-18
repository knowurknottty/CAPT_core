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


def test_current_runtime_shapes_include_authority_effect_cohort_and_replay_provenance():
    state = _state()
    # Real VerificationResult shape: supporting evidence belongs to status.
    state["verificationsByClaim"]["cl-1"] = {
        "verificationId": "ver-1",
        "claimId": "cl-1",
        "strategy": "artifact_hashing",
        "status": {"kind": "verified", "supportingEvidenceIds": ["ev-1"]},
        "verifiedBy": {"actorId": "verification_pipeline", "kind": "verification_plane"},
        "verifiedAt": "2026-08-18T08:00:00Z",
        "committed": True,
        "advisory": False,
    }
    state["approvals"][0].update({
        "decision": "approve",
        "operatorId": "captain",
        "decidedAt": "2026-08-18T08:00:00Z",
    })
    state["capabilities"] = [{
        "grantId": "g-1",
        "grantState": "leased",
        "capabilityId": "cap.fs.read",
        "subjectActorId": "exec-1",
        "operations": ["repository.read"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/repo", "recursive": True},
        "policyDecisionId": "pd-1",
        "policyBundleDigest": "sha256:" + "b" * 64,
        "usesConsumed": 0,
        "lease": {
            "leaseId": "l-1",
            "missionId": "m-1",
            "taskId": "t-1",
            "executionContextId": "ec-1",
            "operations": ["repository.read"],
            "scope": {"kind": "filesystem", "rootPath": "/tmp/repo", "recursive": False},
            "state": "active",
        },
        "reservations": [],
        "consumptions": [],
        "revocation": None,
    }]
    state["artifactPromotions"] = [{
        "promotionId": "p-1",
        "candidateId": "cand-1",
        "workspaceId": "ws-1",
        "contentDigest": "sha256:" + "c" * 64,
        "claimId": "cl-1",
        "verificationId": "ver-1",
        "evidenceId": "ev-1",
        "state": "adopted",
    }]
    state["cohorts"] = [{
        "cohortId": "coh-1",
        "missionId": "m-1",
        "taskId": "t-1",
        "epoch": 1,
        "rounds": 1,
        "stoppingReason": "SILENCE_QUORUM",
        "evidenceIds": ["ev-cohort-1"],
        "latestSteer": {
            "directive": "inspect alternate evidence",
            "reason": "operator steering",
            "steeredBy": "captain",
            "steeredAt": "2026-08-18T08:00:00Z",
            "epoch": 1,
        },
    }]
    state["replayForks"] = [{
        "forkId": "fork-1",
        "sourceSequence": 12,
        "sourceEventId": "ev-source-12",
        "sourceStateDigest": "sha256:" + "d" * 64,
        "sourceChainDigest": "sha256:" + "e" * 64,
        "newMissionId": "m-1",
        "reason": "alternate continuation",
        "createdBy": {"actorId": "captain", "kind": "human"},
        "createdAt": "2026-08-18T08:00:00Z",
        "historicalAuthorityReactivated": False,
        "state": "created",
    }]

    graph = build_provenance_graph(state)
    edges = _edge_set(graph)
    node_ids = {node["id"] for node in graph["nodes"]}

    # Real VerificationResult nested evidence relation.
    assert ("evidence:ev-1", "verification:ver-1", "supports_verification") in edges

    # Approval request and operator decision remain distinct.
    assert "approval_decision:ap-1:approve" in node_ids
    assert ("approval:ap-1", "approval_decision:ap-1:approve", "resolved_by") in edges

    # Capability grant/lease authority is visible but remains projection-only.
    assert "capability_grant:g-1" in node_ids
    assert "capability_lease:l-1" in node_ids
    assert ("capability_grant:g-1", "capability_lease:l-1", "activates_lease") in edges
    assert ("task:t-1", "capability_lease:l-1", "scopes_lease_to_task") in edges

    # Verified artifact promotion binds distinct claim/evidence/verification identities.
    assert "artifact_promotion:p-1" in node_ids
    assert ("claim:cl-1", "artifact_promotion:p-1", "governs_promotion") in edges
    assert ("verification:ver-1", "artifact_promotion:p-1", "binds_promotion_verification") in edges
    assert ("evidence:ev-1", "artifact_promotion:p-1", "binds_promotion_evidence") in edges

    # Cohort and steering provenance are explicit without inventing model identities.
    assert "cohort:coh-1" in node_ids
    assert ("task:t-1", "cohort:coh-1", "coordinates_with") in edges
    assert ("human_actor:captain", "cohort:coh-1", "steered_cohort") in edges

    # Replay fork points from an explicit historical source identity into new history.
    assert "replay_fork:fork-1" in node_ids
    replay_sources = [node["id"] for node in graph["nodes"] if node["kind"] == "replay_source"]
    assert len(replay_sources) == 1
    assert (replay_sources[0], "replay_fork:fork-1", "forked_from") in edges
    assert ("replay_fork:fork-1", "mission:m-1", "creates_mission") in edges
    assert graph["authority"] == "projection_only"


def test_later_authoritative_event_enriches_placeholder_node_without_losing_identity():
    state = _state()
    # Remove the original full EvidenceRecorded event so claim/verification
    # references create only the identity placeholder before authoritative
    # event detail arrives.
    state["eventTimeline"] = []
    state["eventTimeline"].append({
        "globalSequence": 9,
        "eventId": "evt-evidence-rich",
        "payload": {
            "eventType": "EvidenceRecorded",
            "evidence": {
                "schemaVersion": "1.0.0",
                "evidenceId": "ev-1",
                "missionId": "m-1",
                "evidence": {
                    "kind": "artifact_hash",
                    "artifactPath": "/tmp/report.md",
                    "artifactDigest": "sha256:" + "9" * 64,
                },
                "collectedBy": {"actorId": "verification_pipeline", "kind": "verification_plane"},
                "collectedAt": "2026-08-18T08:05:00Z",
                "trust": "capt_authoritative",
            },
        },
    })

    graph = build_provenance_graph(state)
    evidence = next(node for node in graph["nodes"] if node["id"] == "evidence:ev-1")
    assert evidence["data"]["evidenceId"] == "ev-1"
    assert evidence["data"]["collectedAt"] == "2026-08-18T08:05:00Z"
    assert evidence["data"]["evidence"]["artifactDigest"] == "sha256:" + "9" * 64


def test_conflicting_explicit_data_for_same_provenance_identity_fails_visible():
    from capt_ui.operator.provenance import ProvenanceGraphBuilder

    builder = ProvenanceGraphBuilder()
    builder.add_node("evidence", "ev-conflict", {"evidenceId": "ev-conflict", "trust": "a"})
    with pytest.raises(IntegrityViolation, match="PROVENANCE_NODE_CONFLICT"):
        builder.add_node("evidence", "ev-conflict", {"evidenceId": "ev-conflict", "trust": "b"})
