"""CAPT Solo v0.2 — normalization stage.

Deterministic text normalization used by the pipeline before storage,
deduplication, and AntiToken extraction. No LLM, no network.
"""

from __future__ import annotations

import hashlib
import re
from typing import List

from capt_solo.memory.models import StageResult

# Whitespace collapse and control-char stripping are deterministic.
_WS = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Return a canonical form: trimmed, whitespace-collapsed, control-stripped."""
    if not text:
        return ""
    # remove control chars except newline/tab
    cleaned = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    cleaned = _WS.sub(" ", cleaned)
    return cleaned.strip()


def normalize_content_hash(content: str, namespace: str = "", tags: tuple = ()) -> str:
    """Stable content hash for exact/near duplicate detection.

    Includes namespace and a sorted tag tuple so the same text in different
    partitions is not treated as a duplicate.
    """
    norm = normalize_text(content).lower()
    key = "|".join([norm, namespace, ",".join(sorted(tags))])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def sentence_segment(text: str) -> List[str]:
    """Split into sentences on period/exclamation/question boundaries.

    Deterministic rule-based segmentation; keeps sentence-ending punctuation
    off but preserves the text. Used by AntiToken key-sentence selection.
    """
    if not text:
        return []
    # protect common abbreviations minimally (Mr. Dr. etc.) — keep simple
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    out = []
    for p in parts:
        p = p.strip()
        if p:
            out.append(p)
    return out


def extract_headings(text: str) -> List[str]:
    """Extract markdown-style headings (lines starting with #)."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") and len(line) <= 120:
            out.append(line.lstrip("#").strip())
    return out


def normalize_stage(content: str, namespace: str = "default",
                    tags: tuple = ()) -> StageResult:
    """Pipeline stage: normalize raw input and compute its content hash."""
    norm = normalize_text(content)
    if not norm:
        res = StageResult(stage="normalize", ok=False, value=None)
        res.add_rejection("empty content after normalization")
        return res
    h = normalize_content_hash(norm, namespace, tags)
    res = StageResult(
        stage="normalize", ok=True, value={"content": norm, "content_hash": h},
        metrics={"chars": len(norm)},
    )
    return res
