"""Deterministic provenance DAG projection for CAPT operator surfaces.

The graph is presentation/read-model data only. Nodes and edges are created
only from explicit identifiers/relationships present in CAPT projections or
recorded event payloads. Missing links remain missing.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from capt_runtime.contracts import digest
from capt_runtime.errors import IntegrityViolation

GRAPH_SCHEMA_VERSION = "1.0.0"


def _node_id(kind: str, identity: str) -> str:
    return "%s:%s" % (kind, identity)


class ProvenanceGraphBuilder(object):
    def __init__(self) -> None:
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    def add_node(self, kind: str, identity: str, data: Optional[Mapping[str, Any]] = None) -> str:
        node_id = _node_id(kind, str(identity))
        payload = dict(data or {})
        existing = self.nodes.get(node_id)
        if existing is None:
            self.nodes[node_id] = {
                "id": node_id,
                "kind": kind,
                "identity": str(identity),
                "data": payload,
            }
        elif payload:
            merged = dict(existing.get("data") or {})
            for key, value in payload.items():
                if key not in merged:
                    merged[key] = value
                    continue
                prior = merged[key]
                if prior == value:
                    continue
                prior_empty = prior is None or prior == "" or prior == [] or prior == {}
                value_empty = value is None or value == "" or value == [] or value == {}
                if prior_empty and not value_empty:
                    merged[key] = value
                    continue
                if value_empty:
                    continue
                raise IntegrityViolation(
                    "PROVENANCE_NODE_CONFLICT %s field %s" % (node_id, key)
                )
            existing["data"] = merged
        return node_id

    def add_edge(self, source: str, target: str, relation: str, data: Optional[Mapping[str, Any]] = None) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise IntegrityViolation("provenance edge endpoint is missing from graph")
        key = (source, target, relation)
        self.edges[key] = {
            "source": source,
            "target": target,
            "relation": relation,
            "data": dict(data or {}),
        }

    def build(self) -> Dict[str, Any]:
        nodes = [self.nodes[key] for key in sorted(self.nodes)]
        edges = [self.edges[key] for key in sorted(self.edges)]
        graph = {
            "schemaVersion": GRAPH_SCHEMA_VERSION,
            "kind": "CAPTProvenanceDAG",
            "authority": "projection_only",
            "nodes": nodes,
            "edges": edges,
        }
        graph["graphDigest"] = digest(graph)
        graph["topologicalOrder"] = topological_order(graph)
        return graph


def _verification_id(claim_id: str, verification: Mapping[str, Any]) -> str:
    return str(verification.get("verificationId") or (claim_id + ":verification"))


def _approval_prompt_digest(approval: Mapping[str, Any]) -> Optional[str]:
    value = approval.get("promptAssemblyDigest") or approval.get("assemblyDigest")
    return str(value) if value else None


def _event_payload(event: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def build_provenance_graph(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a graph from the shared authoritative/read-model projection."""
    b = ProvenanceGraphBuilder()

    mission_nodes: Dict[str, str] = {}
    task_nodes: Dict[str, str] = {}
    driver_nodes: Dict[str, str] = {}
    claim_nodes: Dict[str, str] = {}
    approval_nodes: Dict[str, str] = {}
    verification_nodes: Dict[str, str] = {}

    for mission in state.get("missions", []) or []:
        mission_id = mission.get("missionId")
        if not mission_id:
            continue
        mission_nodes[str(mission_id)] = b.add_node(
            "mission", str(mission_id),
            {"state": mission.get("state"), "rawRequest": mission.get("rawRequest")},
        )

    for task in state.get("tasks", []) or []:
        task_id = task.get("taskId")
        if not task_id:
            continue
        task_node = b.add_node("task", str(task_id), {"state": task.get("state"), "title": task.get("title")})
        task_nodes[str(task_id)] = task_node
        mission_id = task.get("missionId")
        if mission_id and str(mission_id) in mission_nodes:
            b.add_edge(mission_nodes[str(mission_id)], task_node, "contains_task")

    for approval in state.get("approvals", []) or []:
        request_id = approval.get("requestId")
        if not request_id:
            continue
        approval_node = b.add_node(
            "approval", str(request_id),
            {"state": approval.get("state"), "operation": approval.get("operation")},
        )
        approval_nodes[str(request_id)] = approval_node
        task_id = approval.get("taskId")
        if task_id and str(task_id) in task_nodes:
            b.add_edge(task_nodes[str(task_id)], approval_node, "requires_approval")
        prompt_digest = _approval_prompt_digest(approval)
        if prompt_digest:
            prompt_node = b.add_node("prompt_assembly", prompt_digest, {"digest": prompt_digest})
            b.add_edge(prompt_node, approval_node, "approval_binds_prompt")
        decision = approval.get("decision")
        if decision:
            decision_identity = "%s:%s" % (request_id, decision)
            decision_node = b.add_node(
                "approval_decision",
                decision_identity,
                {
                    "decision": decision,
                    "operatorId": approval.get("operatorId"),
                    "decidedAt": approval.get("decidedAt"),
                    "note": approval.get("note"),
                },
            )
            b.add_edge(approval_node, decision_node, "resolved_by")

    for run in state.get("driverRuns", []) or []:
        run_id = run.get("driverRunId")
        if not run_id:
            continue
        run_node = b.add_node(
            "driver_run", str(run_id),
            {
                "state": run.get("state"),
                "driverId": run.get("driverId"),
                "externalRunId": run.get("externalRunId"),
            },
        )
        driver_nodes[str(run_id)] = run_node
        task_id = run.get("taskId")
        if task_id and str(task_id) in task_nodes:
            b.add_edge(task_nodes[str(task_id)], run_node, "executes_as")

    verifications = state.get("verificationsByClaim") or {}
    for claim in state.get("claims", []) or []:
        claim_id = claim.get("claimId")
        if not claim_id:
            continue
        claim_node = b.add_node(
            "claim", str(claim_id),
            {
                "kind": claim.get("kind"),
                "statement": claim.get("statement"),
                "promotionState": claim.get("promotionState"),
            },
        )
        claim_nodes[str(claim_id)] = claim_node
        task_id = claim.get("taskId")
        mission_id = claim.get("missionId")
        if task_id and str(task_id) in task_nodes:
            b.add_edge(task_nodes[str(task_id)], claim_node, "produces_claim")
        elif mission_id and str(mission_id) in mission_nodes:
            b.add_edge(mission_nodes[str(mission_id)], claim_node, "produces_claim")

        for evidence_id in claim.get("evidenceIds") or []:
            evidence_node = b.add_node("evidence", str(evidence_id), {"evidenceId": str(evidence_id)})
            b.add_edge(evidence_node, claim_node, "supports_claim")

        verification = verifications.get(str(claim_id)) if isinstance(verifications, Mapping) else None
        if isinstance(verification, Mapping) and verification:
            verification_id = _verification_id(str(claim_id), verification)
            verification_node = b.add_node(
                "verification", verification_id,
                {
                    "status": verification.get("status"),
                    "domain": verification.get("verificationDomain") or verification.get("domain"),
                    "committed": verification.get("committed"),
                    "advisory": verification.get("advisory"),
                },
            )
            verification_nodes[verification_id] = verification_node
            status = verification.get("status")
            status_evidence = status.get("supportingEvidenceIds") if isinstance(status, Mapping) else None
            supporting_evidence = verification.get("supportingEvidenceIds") or status_evidence or []
            for evidence_id in supporting_evidence:
                evidence_node = b.add_node("evidence", str(evidence_id), {"evidenceId": str(evidence_id)})
                b.add_edge(evidence_node, verification_node, "supports_verification")
            b.add_edge(verification_node, claim_node, "evaluates_claim")

        if claim.get("guardVerdict"):
            decision_id = "%s:%s" % (claim_id, claim.get("guardVerdict"))
            decision_node = b.add_node(
                "claim_decision", decision_id,
                {"verdict": claim.get("guardVerdict"), "qualification": claim.get("qualification")},
            )
            b.add_edge(claim_node, decision_node, "adjudicated_by")

    # Capability authority: grant and embedded lease remain separate nodes.
    for capability in state.get("capabilities", []) or []:
        grant_id = capability.get("grantId")
        if not grant_id:
            continue
        grant_node = b.add_node(
            "capability_grant",
            str(grant_id),
            {
                "capabilityId": capability.get("capabilityId"),
                "grantState": capability.get("grantState"),
                "subjectActorId": capability.get("subjectActorId"),
                "operations": capability.get("operations"),
                "scope": capability.get("scope"),
                "usesConsumed": capability.get("usesConsumed"),
                "revocation": capability.get("revocation"),
            },
        )
        policy_id = capability.get("policyDecisionId")
        if policy_id:
            policy_node = b.add_node(
                "policy_decision_ref", str(policy_id), {"referenceOnly": True}
            )
            b.add_edge(policy_node, grant_node, "authorizes_grant")
        lease = capability.get("lease")
        if isinstance(lease, Mapping) and lease.get("leaseId"):
            lease_id = str(lease["leaseId"])
            lease_node = b.add_node(
                "capability_lease",
                lease_id,
                {
                    "state": lease.get("state"),
                    "operations": lease.get("operations"),
                    "scope": lease.get("scope"),
                    "executionContextId": lease.get("executionContextId"),
                },
            )
            b.add_edge(grant_node, lease_node, "activates_lease")
            mission_id = lease.get("missionId")
            task_id = lease.get("taskId")
            if mission_id and str(mission_id) in mission_nodes:
                b.add_edge(mission_nodes[str(mission_id)], lease_node, "scopes_lease_to_mission")
            if task_id and str(task_id) in task_nodes:
                b.add_edge(task_nodes[str(task_id)], lease_node, "scopes_lease_to_task")

    # Artifact promotion is a separate authority domain from verification and ClaimGuard.
    for promotion in state.get("artifactPromotions", []) or []:
        promotion_id = promotion.get("promotionId")
        if not promotion_id:
            continue
        promotion_node = b.add_node(
            "artifact_promotion",
            str(promotion_id),
            {
                "state": promotion.get("state"),
                "candidateId": promotion.get("candidateId"),
                "workspaceId": promotion.get("workspaceId"),
                "contentDigest": promotion.get("contentDigest"),
                "destinationPath": promotion.get("destinationPath"),
            },
        )
        claim_id = promotion.get("claimId")
        if claim_id and str(claim_id) in claim_nodes:
            b.add_edge(claim_nodes[str(claim_id)], promotion_node, "governs_promotion")
        evidence_id = promotion.get("evidenceId")
        if evidence_id:
            evidence_node = b.add_node("evidence", str(evidence_id), {"evidenceId": str(evidence_id)})
            b.add_edge(evidence_node, promotion_node, "binds_promotion_evidence")
        verification_id = promotion.get("verificationId")
        if verification_id and str(verification_id) in verification_nodes:
            b.add_edge(
                verification_nodes[str(verification_id)],
                promotion_node,
                "binds_promotion_verification",
            )

    # Cohort detail remains intentionally bounded here; UPG-018 owns the deliberation chamber.
    for cohort in state.get("cohorts", []) or []:
        cohort_id = cohort.get("cohortId")
        if not cohort_id:
            continue
        cohort_node = b.add_node(
            "cohort",
            str(cohort_id),
            {
                "epoch": cohort.get("epoch"),
                "rounds": cohort.get("rounds"),
                "stoppingReason": cohort.get("stoppingReason"),
            },
        )
        mission_id = cohort.get("missionId")
        task_id = cohort.get("taskId")
        if mission_id and str(mission_id) in mission_nodes:
            b.add_edge(mission_nodes[str(mission_id)], cohort_node, "coordinates_mission")
        if task_id and str(task_id) in task_nodes:
            b.add_edge(task_nodes[str(task_id)], cohort_node, "coordinates_with")
        for evidence_id in cohort.get("evidenceIds") or []:
            evidence_node = b.add_node("evidence", str(evidence_id), {"evidenceId": str(evidence_id)})
            b.add_edge(evidence_node, cohort_node, "records_cohort_state")
        steer = cohort.get("latestSteer")
        if isinstance(steer, Mapping) and steer.get("steeredBy"):
            actor_id = str(steer["steeredBy"])
            actor_node = b.add_node("human_actor", actor_id, {"actorId": actor_id})
            b.add_edge(actor_node, cohort_node, "steered_cohort")

    # Replay fork source identity is explicit provenance; it does not reactivate source authority.
    for fork in state.get("replayForks", []) or []:
        fork_id = fork.get("forkId")
        if not fork_id:
            continue
        fork_node = b.add_node(
            "replay_fork",
            str(fork_id),
            {
                "state": fork.get("state"),
                "reason": fork.get("reason"),
                "historicalAuthorityReactivated": fork.get("historicalAuthorityReactivated"),
            },
        )
        source_sequence = fork.get("sourceSequence")
        source_chain = fork.get("sourceChainDigest")
        if source_sequence is not None and source_chain:
            source_identity = "%s:%s" % (source_sequence, source_chain)
            source_node = b.add_node(
                "replay_source",
                source_identity,
                {
                    "globalSequence": source_sequence,
                    "eventId": fork.get("sourceEventId"),
                    "stateDigest": fork.get("sourceStateDigest"),
                    "chainDigest": source_chain,
                },
            )
            b.add_edge(source_node, fork_node, "forked_from")
        new_mission_id = fork.get("newMissionId")
        if new_mission_id and str(new_mission_id) in mission_nodes:
            b.add_edge(fork_node, mission_nodes[str(new_mission_id)], "creates_mission")

    # Recorded event payloads may carry richer evidence and cognitive
    # provenance than aggregate snapshots. Add only explicit identities.
    for event in state.get("eventTimeline", []) or []:
        payload = _event_payload(event)
        evidence = payload.get("evidence")
        if isinstance(evidence, Mapping) and evidence.get("evidenceId"):
            evidence_id = str(evidence["evidenceId"])
            b.add_node("evidence", evidence_id, dict(evidence))

        provenance = payload.get("cognitiveProvenance")
        if isinstance(provenance, Mapping) and provenance:
            provenance_id = str(provenance.get("provenanceId") or digest(dict(provenance)))
            provenance_node = b.add_node("cognitive_provenance", provenance_id, dict(provenance))
            correlation = provenance.get("correlation")
            if isinstance(correlation, Mapping):
                run_id = correlation.get("driverRunId")
                if run_id and str(run_id) in driver_nodes:
                    b.add_edge(provenance_node, driver_nodes[str(run_id)], "describes_driver_run")
            prompt_digest = provenance.get("promptAssemblyDigest") or provenance.get("assemblyDigest")
            if prompt_digest:
                prompt_node = b.add_node("prompt_assembly", str(prompt_digest), {"digest": str(prompt_digest)})
                b.add_edge(prompt_node, provenance_node, "included_in_provenance")
            provider = provenance.get("provider") or provenance.get("providerId")
            model = provenance.get("model")
            if provider or model:
                target_identity = "%s/%s" % (provider or "unknown-provider", model or "unknown-model")
                target_node = b.add_node(
                    "model_target", target_identity,
                    {"provider": provider, "model": model},
                )
                b.add_edge(target_node, provenance_node, "identified_by")

    return b.build()


def topological_order(graph: Mapping[str, Any]) -> List[str]:
    """Return deterministic topological order or fail visibly on a cycle."""
    node_ids = [str(node["id"]) for node in graph.get("nodes", [])]
    indegree: Dict[str, int] = {node_id: 0 for node_id in node_ids}
    outgoing: Dict[str, Set[str]] = {node_id: set() for node_id in node_ids}
    for edge in graph.get("edges", []) or []:
        source = str(edge["source"])
        target = str(edge["target"])
        if source not in indegree or target not in indegree:
            raise IntegrityViolation("provenance graph edge references missing node")
        if target not in outgoing[source]:
            outgoing[source].add(target)
            indegree[target] += 1

    ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
    order: List[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for target in sorted(outgoing[node_id]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()

    if len(order) != len(node_ids):
        cyclic = sorted(node_id for node_id, degree in indegree.items() if degree > 0)
        raise IntegrityViolation("provenance graph contains cycle involving %s" % cyclic)
    return order


def render_provenance_summary(graph: Mapping[str, Any], max_nodes: int = 20) -> str:
    nodes = list(graph.get("nodes", []) or [])
    edges = list(graph.get("edges", []) or [])
    lines = [
        "CAPT Provenance Lens (projection only)",
        "nodes=%d edges=%d digest=%s" % (len(nodes), len(edges), graph.get("graphDigest", "unknown")),
    ]
    for node in nodes[:max_nodes]:
        lines.append("- %s [%s]" % (node.get("identity"), node.get("kind")))
    if len(nodes) > max_nodes:
        lines.append("... %d more node(s)" % (len(nodes) - max_nodes))
    return "\n".join(lines)
