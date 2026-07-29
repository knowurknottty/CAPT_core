"""Adapters from policy-neutral providers into an externally inspectable pack."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .graph import EvidenceGraph
from .runtime import ContinuityEvidence, ContinuityPack, canonical_json


def build_pack_from_providers(pack_id: str, component: str, tier: str, scope: str,
                              roles: List[Dict[str, Any]], claims: List[Dict[str, Any]],
                              policy_id: str, providers: Iterable[Any],
                              created_at: Optional[str] = None) -> ContinuityPack:
    """Build a pack from provider snapshots without reaching into components."""
    providers = list(providers)
    graph = EvidenceGraph.from_providers(providers)
    evidence = [ContinuityEvidence(
        evidence_id=node.node_id, kind=node.node_type, status=node.status,
        source=node.origin, collected_at=node.timestamp,
        verifier="provider:" + node.origin, controls=["provider_contract"],
    ) for node in graph.nodes()]
    timestamps = [node.timestamp for node in graph.nodes()]
    return ContinuityPack(
        pack_id=pack_id, component=component, tier=tier, scope=scope, roles=roles,
        claims=claims, evidence=evidence,
        created_at=created_at or (max(timestamps) if timestamps else "1970-01-01T00:00:00+00:00"), policy_id=policy_id,
        metadata={"evidence_graph": graph.to_dict(), "provider_graph_digest": graph.to_dict()["digest"],
                  "provider_versions": {
                      provider.__class__.__name__ + ":" + str(index): provider.version()
                      for index, provider in enumerate(providers)}},
    )
