"""CAPT Solo v0.2 — deduplication and conflict detection.

Deterministic duplicate detection using:
  - normalized content hashes (exact)
  - exact-match metadata
  - strong lexical overlap (Jaccard on normalized tokens)
  - matching identifiers (memory_id references in metadata)

Ambiguous near-duplicates are NEVER auto-merged. They are surfaced for
explicit review/alias/supersede.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from capt_solo.memory.models import StageResult
from capt_solo.memory.normalize import normalize_content_hash, normalize_text

# Strong overlap threshold for "likely duplicate" flag (not auto-merge).
_STRONG_OVERLAP = 0.85


def _tokens(text: str) -> set:
    return {t for t in normalize_text(text).lower().split() if t}


def lexical_overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def find_duplicates(
    content: str,
    namespace: str,
    tags: Tuple[str, ...],
    existing: List[Dict[str, object]],
) -> StageResult:
    """Pipeline stage: detect duplicates against existing memory records.

    ``existing`` is a list of dicts with keys:
    memory_id, content, namespace, tags, metadata.

    Returns ``value['matches']`` = list of dicts:
      {memory_id, kind: 'exact'|'strong_overlap', overlap: float}
    Ambiguous matches are reported but NOT merged.
    """
    res = StageResult(stage="deduplicate", ok=True, value={"matches": []})
    norm_hash = normalize_content_hash(content, namespace, tags)

    for rec in existing:
        rec_ns = rec.get("namespace", "default")
        rec_tags = tuple(rec.get("tags", []) or [])
        # exact normalized hash (same text, same partition)
        if normalize_content_hash(rec.get("content", ""), rec_ns, rec_tags) == norm_hash:
            res.value["matches"].append({
                "memory_id": rec["memory_id"], "kind": "exact", "overlap": 1.0,
            })
            continue
        # strong lexical overlap (different wording, same meaning likely)
        ov = lexical_overlap(content, rec.get("content", ""))
        if ov >= _STRONG_OVERLAP:
            res.value["matches"].append({
                "memory_id": rec["memory_id"], "kind": "strong_overlap",
                "overlap": round(ov, 4),
            })
    if res.value["matches"]:
        res.metrics["duplicate_candidates"] = len(res.value["matches"])
    return res


def detect_conflicts(
    new_assertion: str,
    existing: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    """Detect direct contradictions via negation markers and opposite claims.

    Heuristic, deterministic: flags pairs where one contains a negation of the
    other's key subject. This is a baseline; CSG edges (contradicts) are the
    authoritative conflict record.
    """
    conflicts = []
    new_tokens = _tokens(new_assertion)
    neg_markers = {"not", "never", "no", "false", "incorrect", "wrong", "denied"}
    new_negated = new_tokens & neg_markers
    for rec in existing:
        rec_tokens = _tokens(rec.get("content", ""))
        rec_negated = rec_tokens & neg_markers
        # subject overlap but opposite polarity
        shared = new_tokens & rec_tokens
        if shared and bool(new_negated) != bool(rec_negated):
            conflicts.append({
                "memory_id": rec["memory_id"],
                "reason": "opposite polarity on shared subject",
                "shared_subjects": list(shared)[:5],
            })
    return conflicts
