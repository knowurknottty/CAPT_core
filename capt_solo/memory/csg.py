"""CAPT Solo v0.2 — Context Selection Graph (CSG).

A local, SQLite-backed graph modeling relationships among memories and
selecting the most useful working context for a task. CSG is NOT a learned
neural graph; it is a deterministic, graph-assisted selector. The selection
algorithm combines configurable weighted signals (lexical relevance, namespace
match, tag match, recency, confidence, provenance quality, trust score, graph
centrality, direct graph distance, transaction linkage, and penalties for
unresolved conflicts / superseded / duplicate memories).

Storage: tables created in the same SQLite DB as memories (v0.2 migration).
No external graph database required.

Public API:
    csg.add_edge(...)
    csg.remove_edge(...)
    csg.get_neighbors(...)
    csg.find_path(...)
    csg.detect_conflicts(...)
    csg.select_context(...)
    csg.explain_selection(...)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from capt_solo.core.errors import MemoryError_
from capt_solo.memory.models import (
    EdgeType,
    MemoryKind,
    SelectionStatus,
    TrustState,
)
from capt_solo.memory.trust import base_weight, trust_from_kind


@dataclass
class CSGEdge:
    edge_id: str
    source: str
    target: str
    edge_type: str
    weight: float
    confidence: float
    provenance: str
    created_at: float
    ctp_tx_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id, "source": self.source, "target": self.target,
            "edge_type": self.edge_type, "weight": self.weight,
            "confidence": self.confidence, "provenance": self.provenance,
            "created_at": self.created_at, "ctp_tx_id": self.ctp_tx_id,
        }


# Default selection weights. Safe defaults; configurable via set_weights().
DEFAULT_WEIGHTS: Dict[str, float] = {
    "lexical_relevance": 1.0,
    "namespace_match": 1.5,
    "tag_match": 1.0,
    "recency": 0.5,
    "confidence": 1.0,
    "provenance_quality": 0.8,
    "trust_score": 1.2,
    "graph_centrality": 0.7,
    "graph_distance": 0.6,
    "transaction_linkage": 0.5,
    "unresolved_conflict_penalty": 1.0,
    "superseded_penalty": 2.0,
    "duplicate_penalty": 1.5,
    "task_intent_alignment": 1.0,
}


class CSG:
    """Local Context Selection Graph."""

    def __init__(self, conn) -> None:
        # conn is an open sqlite3.Connection owned by MemoryEngine.
        self._conn = conn
        self._weights: Dict[str, float] = dict(DEFAULT_WEIGHTS)

    # ----- configuration ----------------------------------------------
    def set_weights(self, weights: Dict[str, float]) -> None:
        for k, v in weights.items():
            if k in DEFAULT_WEIGHTS:
                self._weights[k] = float(v)

    def get_weights(self) -> Dict[str, float]:
        return dict(self._weights)

    # ----- node helpers ------------------------------------------------
    def _ensure_node(self, memory_id: str, kind: str = "fact") -> None:
        import time
        self._conn.execute(
            "INSERT OR IGNORE INTO memory_nodes (memory_id, kind, created_at) VALUES (?,?,?)",
            (memory_id, kind, time.time()),
        )

    # ----- edges -------------------------------------------------------
    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        *,
        weight: float = 1.0,
        confidence: float = 1.0,
        provenance: str = "unknown",
        ctp_tx_id: Optional[str] = None,
    ) -> str:
        if edge_type not in EdgeType.values():
            raise MemoryError_(f"unknown edge type: {edge_type}")
        self._ensure_node(source)
        self._ensure_node(target)
        edge_id = uuid.uuid4().hex
        self._conn.execute(
            """INSERT INTO memory_edges
               (edge_id, source, target, edge_type, weight, confidence,
                provenance, created_at, ctp_tx_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (edge_id, source, target, edge_type, weight, confidence,
             provenance, time.time(), ctp_tx_id),
        )
        return edge_id

    def remove_edge(self, edge_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM memory_edges WHERE edge_id=?", (edge_id,))
        return cur.rowcount > 0

    def get_neighbors(self, memory_id: str) -> List[CSGEdge]:
        rows = self._conn.execute(
            "SELECT * FROM memory_edges WHERE source=? OR target=?", (memory_id, memory_id)
        ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def find_path(self, source: str, target: str, max_depth: int = 6) -> Optional[List[str]]:
        """BFS over undirected edges, respecting max_depth. Returns path or None."""
        if source == target:
            return [source]
        adj: Dict[str, List[str]] = {}
        for r in self._conn.execute("SELECT source, target FROM memory_edges").fetchall():
            adj.setdefault(r["source"], []).append(r["target"])
            adj.setdefault(r["target"], []).append(r["source"])
        from collections import deque
        q = deque([(source, 0)])
        visited = {source: None}
        while q:
            node, depth = q.popleft()
            if depth >= max_depth:
                continue
            for nb in adj.get(node, []):
                if nb not in visited:
                    visited[nb] = node
                    if nb == target:
                        path = [nb]
                        cur = nb
                        while visited[cur] is not None:
                            cur = visited[cur]
                            path.append(cur)
                        return list(reversed(path))
                    q.append((nb, depth + 1))
        return None

    # ----- conflicts ----------------------------------------------------
    def detect_conflicts(self, memory_id: str) -> List[Dict[str, Any]]:
        """Return explicit contradiction edges touching this memory."""
        rows = self._conn.execute(
            "SELECT * FROM memory_edges WHERE (source=? OR target=?) AND edge_type=?",
            (memory_id, memory_id, EdgeType.CONTRADICTS.value),
        ).fetchall()
        out = []
        for r in rows:
            other = r["target"] if r["source"] == memory_id else r["source"]
            out.append({"edge_id": r["edge_id"], "with": other, "type": "contradicts"})
        return out

    def record_conflict(self, a: str, b: str, *, ctp_tx_id: Optional[str] = None) -> str:
        return self.add_edge(a, b, EdgeType.CONTRADICTS.value,
                            provenance="conflict_review", ctp_tx_id=ctp_tx_id)

    def resolve_conflict(self, edge_id: str) -> bool:
        # mark conflict resolved by removing the contradiction edge and adding a
        # 'resolves' style note via aliases table is overkill; we delete the edge.
        return self.remove_edge(edge_id)

    # ----- selection ----------------------------------------------------
    def select_context(
        self,
        candidates: List[Dict[str, Any]],
        *,
        query: str = "",
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_trust: float = 0.0,
        max_items: int = 10,
        include_superseded: bool = False,
        include_conflicts: bool = False,
        task_intent: Optional[str] = None,
        trust_scores: Optional[Dict[str, float]] = None,
        tx_linkage: Optional[Dict[str, str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Deterministic weighted selection.

        Returns (selected, explanations). Each explanation dict contains the
        per-signal breakdown and the final decision + reason.
        """
        w = self._weights
        explanations: List[Dict[str, Any]] = []
        scored = []

        # precompute centrality (degree) once
        centrality = self._centrality()

        q_tokens = set(query.lower().split()) if query else set()
        intent_tokens = set(task_intent.lower().split()) if task_intent else set()

        for c in candidates:
            mid = c["memory_id"]
            signals: Dict[str, float] = {}
            score = 0.0

            # lexical relevance (Jaccard vs query)
            c_tokens = set(str(c.get("content", "")).lower().split())
            if q_tokens and c_tokens:
                lex = len(q_tokens & c_tokens) / max(1, len(q_tokens | c_tokens))
            else:
                lex = 0.0
            signals["lexical_relevance"] = lex
            score += lex * w["lexical_relevance"]

            # namespace match
            ns_match = 1.0 if (namespace and c.get("namespace") == namespace) else 0.0
            signals["namespace_match"] = ns_match
            score += ns_match * w["namespace_match"]

            # tag match
            c_tags = set(c.get("tags", []) or [])
            tag_match = (len(set(tags or []) & c_tags) / max(1, len(set(tags or [])))) if tags else 0.0
            signals["tag_match"] = tag_match
            score += tag_match * w["tag_match"]

            # recency (decay over 180 days)
            age = max(0.0, time.time() - float(c.get("updated_at", time.time())))
            recency = max(0.0, 1.0 - age / (180.0 * 86400.0))
            signals["recency"] = recency
            score += recency * w["recency"]

            # confidence
            conf = float(c.get("confidence", 1.0))
            signals["confidence"] = conf
            score += conf * w["confidence"]

            # provenance quality (heuristic: tool/verified > user > unknown)
            prov = str(c.get("provenance", "unknown"))
            prov_q = 1.0 if any(k in prov for k in ("tool", "verified", "test")) else (
                0.6 if prov != "unknown" else 0.3)
            signals["provenance_quality"] = prov_q
            score += prov_q * w["provenance_quality"]

            # trust score
            trust = (trust_scores or {}).get(mid, base_weight(TrustState.USER_FACT))
            signals["trust_score"] = trust
            score += trust * w["trust_score"]

            # graph centrality
            cent = centrality.get(mid, 0.0)
            signals["graph_centrality"] = cent
            score += cent * w["graph_centrality"]

            # graph distance to query-linked nodes (baseline: 0 if no edges)
            # We approximate: if memory has any edge, distance signal = 0.5
            has_edge = mid in centrality
            dist = 0.5 if has_edge else 0.0
            signals["graph_distance"] = dist
            score += dist * w["graph_distance"]

            # transaction linkage
            linked = 1.0 if (tx_linkage or {}).get(mid) else 0.0
            signals["transaction_linkage"] = linked
            score += linked * w["transaction_linkage"]

            # task intent alignment
            if intent_tokens and c_tokens:
                align = len(intent_tokens & c_tokens) / max(1, len(intent_tokens | c_tokens))
            else:
                align = 0.0
            signals["task_intent_alignment"] = align
            score += align * w["task_intent_alignment"]

            # penalties
            conflicts = self.detect_conflicts(mid)
            if conflicts and not include_conflicts:
                score -= w["unresolved_conflict_penalty"]
                signals["unresolved_conflict_penalty"] = -w["unresolved_conflict_penalty"]
            superseded = str(c.get("status", "")) == "superseded"
            if superseded and not include_superseded:
                # hard exclude: superseded memories are not selected unless
                # the caller explicitly opts in
                score = -1.0
                signals["superseded_penalty"] = -w["superseded_penalty"]
            # duplicate penalty: flagged by caller via metadata
            if c.get("is_duplicate"):
                score -= w["duplicate_penalty"]
                signals["duplicate_penalty"] = -w["duplicate_penalty"]

            scored.append((mid, score, signals, conflicts, superseded))

        # sort by score desc, deterministic tiebreak by memory_id
        scored.sort(key=lambda t: (-round(t[1], 6), t[0]))

        selected = []
        for mid, score, signals, conflicts, superseded in scored:
            if score < 0:
                explanations.append({
                    "memory_id": mid, "decision": SelectionStatus.EXCLUDED.value,
                    "score": round(score, 6), "signals": signals,
                    "reason": "negative score after penalties",
                })
                continue
            if len(selected) >= max_items:
                explanations.append({
                    "memory_id": mid, "decision": SelectionStatus.EXCLUDED.value,
                    "score": round(score, 6), "signals": signals,
                    "reason": "exceeded max_items budget",
                })
                continue
            selected.append({
                "memory_id": mid, "score": round(score, 6),
                "confidence": float(next(c["confidence"] for c in candidates if c["memory_id"] == mid)),
            })
            explanations.append({
                "memory_id": mid, "decision": SelectionStatus.SELECTED.value,
                "score": round(score, 6), "signals": signals,
                "reason": "passed weighted threshold and within budget",
            })

        return selected, explanations

    def explain_selection(self, explanations: List[Dict[str, Any]]) -> str:
        lines = ["CSG selection explanation (deterministic, weighted):"]
        for e in explanations:
            lines.append(
                f"  - {e['memory_id'][:12]} {e['decision']} "
                f"score={e['score']} :: {e['reason']}")
        return "\n".join(lines)

    # ----- internals ----------------------------------------------------
    def _centrality(self) -> Dict[str, float]:
        rows = self._conn.execute(
            "SELECT source, target FROM memory_edges").fetchall()
        deg: Dict[str, int] = {}
        for r in rows:
            deg[r["source"]] = deg.get(r["source"], 0) + 1
            deg[r["target"]] = deg.get(r["target"], 0) + 1
        if not deg:
            return {}
        mx = max(deg.values())
        return {k: v / mx for k, v in deg.items()}

    @staticmethod
    def _row_to_edge(row) -> CSGEdge:
        return CSGEdge(
            edge_id=row["edge_id"], source=row["source"], target=row["target"],
            edge_type=row["edge_type"], weight=row["weight"],
            confidence=row["confidence"], provenance=row["provenance"],
            created_at=row["created_at"], ctp_tx_id=row["ctp_tx_id"],
        )
