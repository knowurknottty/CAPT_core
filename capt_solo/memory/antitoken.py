"""CAPT Solo v0.2 — AntiToken extraction and compression.

AntiToken reduces prompt-token usage while preserving decision-relevant
semantic structure. The default extractor is deterministic and requires NO
LLM or network access.

Fidelity protections: compression must NOT silently remove negation,
uncertainty, contraindications, security warnings, unresolved conflicts,
numeric values, dates, versions, file paths, identifiers, test outcomes,
evidence references, or destructive-action warnings. A packet failing
fidelity validation falls back to a less compressed representation.

Token estimates: without a real tokenizer we report CHARACTER counts and an
APPROXIMATE token estimate (chars/4) clearly labeled as an estimate.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from capt_solo.memory.models import AntiTokenPacket, MemoryKind
from capt_solo.memory.normalize import extract_headings, normalize_text, sentence_segment
from capt_solo.memory.trust import trust_from_kind

# Fidelity markers that must be preserved verbatim in the assertion/constraints.
_NEG = re.compile(r"\b(not|never|no|false|incorrect|wrong|denied|cannot|won't|can't)\b", re.I)
_UNCERTAIN = re.compile(r"\b(maybe|perhaps|likely|unlikely|possibly|uncertain|approx|about|~|guess|tentative)\b", re.I)
_CONTRA = re.compile(r"\b(but|however|except|unless|despite|warning|caution|risk|danger)\b", re.I)
_SECURITY = re.compile(r"\b(secret|password|token|key|credential|private|auth|api[_-]?key)\b", re.I)
_DESTRUCTIVE = re.compile(r"\b(delete|drop|remove|purge|wipe|rm\s|truncate|overwrite|destroy)\b", re.I)
_NUM = re.compile(r"\b\d+(?:\.\d+)?\b")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_VERSION = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b")
_PATH = re.compile(r"(?:/[\w.\-]+)+|[\w.\-]+\.[a-z]{2,4}")
_IDENT = re.compile(r"\b[a-f0-9]{8,}\b")
_TEST = re.compile(r"\b(pass|fail|passed|failed|error|traceback|exit code \d+)\b", re.I)


def _estimate_tokens(text: str) -> int:
    """Approximate token estimate (chars/4). Labeled as estimate everywhere."""
    return max(1, len(text) // 4)


def extract(memory: Dict[str, Any]) -> AntiTokenPacket:
    """Deterministic AntiToken extraction from a memory dict.

    ``memory`` keys: memory_id, content, namespace, tags, provenance,
    confidence, metadata, status, ctp_refs, evidence_refs.
    """
    mid = memory["memory_id"]
    content = normalize_text(memory.get("content", ""))
    kind = MemoryKind.from_tag(str(memory.get("metadata", {}).get("kind", "fact")))

    # subject / action / object via simple heuristic on first sentence
    sentences = sentence_segment(content)
    first = sentences[0] if sentences else content
    subject, action, obj = _split_svo(first)

    # constraints: lines/headings mentioning must/should/require/constraint
    constraints = _extract_constraints(content)
    # rationale: from metadata or 'because'/'since' clauses
    rationale = _extract_rationale(content, memory.get("metadata", {}))

    negation = bool(_NEG.search(content))
    uncertainty = bool(_UNCERTAIN.search(content))
    security_warning = bool(_SECURITY.search(content))
    destructive = bool(_DESTRUCTIVE.search(content))

    # compact assertion: first sentence, trimmed to 240 chars
    assertion = first[:240]
    if len(first) > 240:
        # trim at last space if present, else hard truncate
        if " " in first[:240]:
            assertion = first[:240].rsplit(" ", 1)[0] + "…"
        else:
            assertion = first[:240] + "…"

    packet = AntiTokenPacket(
        memory_id=mid,
        kind=kind.value,
        assertion=assertion,
        subject=subject,
        action=action,
        obj=obj,
        constraints=constraints,
        rationale=rationale,
        evidence_refs=list(memory.get("evidence_refs", []) or []),
        confidence=float(memory.get("confidence", 1.0)),
        provenance_refs=[str(memory.get("provenance", "unknown"))],
        temporal_scope=memory.get("metadata", {}).get("temporal_scope", ""),
        status=str(memory.get("status", "active")),
        contradictions=list(memory.get("contradictions", []) or []),
        supersedes=list(memory.get("supersedes", []) or []),
        unresolved_questions=list(memory.get("unresolved_questions", []) or []),
        ctp_refs=list(memory.get("ctp_refs", []) or []),
        negation=negation,
        uncertainty=uncertainty,
        security_warning=security_warning,
        destructive_warning=destructive,
    )
    return packet


def extract_many(memories: List[Dict[str, Any]]) -> List[AntiTokenPacket]:
    return [extract(m) for m in memories]


def validate(packet: AntiTokenPacket, source: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Fidelity check: ensure critical semantics were not dropped.

    Returns (ok, warnings). If a fidelity-critical element is missing from the
    packet but present in source, ok=False and the caller should fall back to a
    less compressed representation.
    """
    warnings: List[str] = []
    src = normalize_text(source.get("content", ""))

    # negation preserved?
    if bool(_NEG.search(src)) and not packet.negation:
        warnings.append("negation present in source but not flagged")
    # uncertainty preserved?
    if bool(_UNCERTAIN.search(src)) and not packet.uncertainty:
        warnings.append("uncertainty present in source but not flagged")
    # security warning preserved?
    if bool(_SECURITY.search(src)) and not packet.security_warning:
        warnings.append("security warning present in source but not flagged")
    # destructive action preserved?
    if bool(_DESTRUCTIVE.search(src)) and not packet.destructive_warning:
        warnings.append("destructive-action warning present in source but not flagged")
    # numeric / date / version / path / identifier preservation
    for label, pat in (("numeric", _NUM), ("date", _DATE), ("version", _VERSION),
                       ("path", _PATH), ("identifier", _IDENT), ("test_outcome", _TEST)):
        m = pat.search(src)
        if m:
            token = m.group(0)
            # the actual value must appear verbatim in assertion or constraints
            if token.lower() not in packet.assertion.lower() and \
                    not any(token.lower() in c.lower() for c in packet.constraints):
                warnings.append(f"{label} value '{token}' in source not preserved")
    # evidence references preserved
    if source.get("evidence_refs") and not packet.evidence_refs:
        warnings.append("evidence references dropped")
    return (len(warnings) == 0, warnings)


def estimate_reduction(source: str, packet: AntiTokenPacket) -> Dict[str, Any]:
    src_chars = len(source)
    pkt_chars = len(packet.assertion) + sum(len(c) for c in packet.constraints) + \
               sum(len(r) for r in packet.rationale)
    ratio = 1.0 - (pkt_chars / src_chars) if src_chars else 0.0
    return {
        "source_chars": src_chars,
        "compressed_chars": pkt_chars,
        "reduction_ratio": round(max(0.0, ratio), 4),
        "estimated_source_tokens": _estimate_tokens(source),
        "estimated_compressed_tokens": _estimate_tokens(packet.assertion),
        "token_estimate_note": "approximate (chars/4), not from a real tokenizer",
    }


def render(packet: AntiTokenPacket, format: str = "text") -> str:
    """Render an AntiToken packet.

    Supported formats: 'text' (compact plain), 'json' (structured),
    'model_neutral' (context block consumable by any model).
    """
    if format == "json":
        import json as _json
        return _json.dumps(packet.to_dict(), indent=2)
    if format == "model_neutral":
        return _render_model_neutral(packet)
    # default: compact plain text
    lines = [f"[{packet.kind}] {packet.assertion}"]
    if packet.negation:
        lines.append("  ! NEGATED")
    if packet.uncertainty:
        lines.append("  ? UNCERTAIN")
    if packet.security_warning:
        lines.append("  !! SECURITY WARNING")
    if packet.destructive_warning:
        lines.append("  !! DESTRUCTIVE ACTION")
    if packet.constraints:
        lines.append("  constraints: " + "; ".join(packet.constraints))
    if packet.rationale:
        lines.append("  rationale: " + "; ".join(packet.rationale))
    if packet.evidence_refs:
        lines.append("  evidence: " + ", ".join(packet.evidence_refs))
    if packet.contradictions:
        lines.append("  contradicts: " + ", ".join(packet.contradictions))
    if packet.supersedes:
        lines.append("  supersedes: " + ", ".join(packet.supersedes))
    if packet.unresolved_questions:
        lines.append("  open: " + "; ".join(packet.unresolved_questions))
    return "\n".join(lines)


def _render_model_neutral(packet: AntiTokenPacket) -> str:
    """Model-neutral context block. No model-specific prompt instructions."""
    parts = [
        f"kind={packet.kind}",
        f"confidence={packet.confidence}",
        f"status={packet.status}",
        f"assertion={packet.assertion}",
    ]
    if packet.negation:
        parts.append("negation=true")
    if packet.uncertainty:
        parts.append("uncertainty=true")
    if packet.security_warning:
        parts.append("security_warning=true")
    if packet.destructive_warning:
        parts.append("destructive_action=true")
    if packet.constraints:
        parts.append("constraints=" + " | ".join(packet.constraints))
    if packet.rationale:
        parts.append("rationale=" + " | ".join(packet.rationale))
    if packet.evidence_refs:
        parts.append("evidence=" + " ".join(packet.evidence_refs))
    if packet.ctp_refs:
        parts.append("ctp=" + " ".join(packet.ctp_refs))
    if packet.contradictions:
        parts.append("contradicts=" + " ".join(packet.contradictions))
    if packet.supersedes:
        parts.append("supersedes=" + " ".join(packet.supersedes))
    return "ANTITOKEN " + " ".join(parts)


# --------------------------------------------------------------------------
# Internal heuristics
# --------------------------------------------------------------------------
def _split_svo(sentence: str) -> Tuple[str, str, str]:
    # crude: split on first verb-ish 'is/are/was/should/must/use/do'
    m = re.split(r"\b(is|are|was|were|should|must|use|uses|do|does|will|has|have)\b",
                 sentence, maxsplit=1, flags=re.I)
    if len(m) >= 3:
        subject = m[0].strip().strip(".").strip()
        action = m[1].strip().lower()
        obj = m[2].strip().strip(".").strip()
        return subject[:80], action, obj[:120]
    return sentence[:80], "", ""


def _extract_constraints(content: str) -> List[str]:
    out = []
    for line in content.splitlines():
        low = line.lower()
        if any(k in low for k in ("must", "should", "require", "constraint", "only",
                                   "never", "always", "cannot")):
            t = line.strip().lstrip("#-").strip()
            if t:
                out.append(t[:160])
    # also headings
    for h in extract_headings(content):
        if any(k in h.lower() for k in ("constraint", "requirement", "rule")):
            out.append(h[:160])
    return out[:8]


def _extract_rationale(content: str, metadata: Dict[str, Any]) -> List[str]:
    out = []
    if isinstance(metadata, dict) and metadata.get("rationale"):
        r = metadata["rationale"]
        if isinstance(r, list):
            out.extend(str(x)[:160] for x in r)
        else:
            out.append(str(r)[:160])
    for sent in sentence_segment(content):
        low = sent.lower()
        if any(k in low for k in ("because", "since", "therefore", "to avoid",
                                   "to ensure", "so that")):
            out.append(sent[:160])
    return out[:6]
