"""Component provenance experiment for ContextPack (CAPT-UPG-013).

This module is deliberately non-authoritative. A Merkle root is an internal
provenance/invalidation identity over ContextPack components; it does not
replace ``contextPackDigest`` and it does not imply provider prompt-cache hits.
Prompt prefix planning is modeled separately because provider caches depend on
exact serialized prefixes, not Merkle identity alone.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .contracts import digest

MERKLE_SCHEMA_VERSION = "1.0.0"
COMPONENT_ORDER = (
    "policy",
    "usage",
    "selection",
    "exclusions",
    "compression",
    "lineage",
)


def _component_payloads(pack: Mapping[str, Any]) -> Dict[str, Any]:
    """Project semantically meaningful ContextPack fields into stable buckets."""
    return {
        "policy": {
            "policyVersion": pack.get("policyVersion"),
            "triggerBoundary": pack.get("triggerBoundary"),
            "tokenBudget": pack.get("tokenBudget"),
        },
        "usage": {
            "contextUsageBefore": pack.get("contextUsageBefore"),
            "contextUsageAfter": pack.get("contextUsageAfter"),
            "provenanceRetained": pack.get("provenanceRetained"),
        },
        "selection": {
            "selectedRecords": [
                {
                    "recordId": rec.get("recordId"),
                    "digest": rec.get("digest"),
                    "retrievalScore": rec.get("retrievalScore"),
                    "retrievalReason": rec.get("retrievalReason"),
                }
                for rec in pack.get("selectedRecords", [])
            ],
        },
        "exclusions": {
            "excludedRecords": pack.get("excludedRecords", []),
            "unresolvedConflicts": pack.get("unresolvedConflicts", []),
            "staleRecords": pack.get("staleRecords", []),
        },
        "compression": {
            "compressionActions": pack.get("compressionActions", []),
            "summariesGenerated": pack.get("summariesGenerated", []),
            "redactions": pack.get("redactions", []),
        },
        "lineage": {
            "previousContextPackDigest": pack.get("previousContextPackDigest"),
            "missionId": pack.get("missionId"),
            "taskId": pack.get("taskId"),
            "driverRunId": pack.get("driverRunId"),
        },
    }


def _pair_digest(left: str, right: str) -> str:
    return digest({"left": left, "right": right})


def build_context_merkle(pack: Mapping[str, Any]) -> Dict[str, Any]:
    """Build fixed-order component leaves and a binary Merkle root."""
    payloads = _component_payloads(pack)
    leaves: List[Dict[str, str]] = []
    for identity in COMPONENT_ORDER:
        leaves.append(
            {
                "identity": identity,
                "digest": digest(
                    {
                        "identity": identity,
                        "payload": payloads[identity],
                    }
                ),
            }
        )

    current = [leaf["digest"] for leaf in leaves]
    levels: List[List[str]] = [list(current)]
    while len(current) > 1:
        nxt: List[str] = []
        for index in range(0, len(current), 2):
            left = current[index]
            right = current[index + 1] if index + 1 < len(current) else left
            nxt.append(_pair_digest(left, right))
        levels.append(nxt)
        current = nxt

    return {
        "schemaVersion": MERKLE_SCHEMA_VERSION,
        "kind": "ContextPackComponentMerkle",
        "contextPackDigest": pack.get("contextPackDigest"),
        "componentOrder": list(COMPONENT_ORDER),
        "leaves": leaves,
        "rootDigest": current[0],
        "treeHeight": len(levels),
        "semantics": {
            "authority": "provenance_only",
            "replacesContextPackDigest": False,
            "providerCacheHitClaim": False,
        },
    }


def diff_context_merkle(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> Dict[str, Any]:
    """Return component identities whose leaf digests changed."""
    before_leaves = {leaf["identity"]: leaf["digest"] for leaf in before.get("leaves", [])}
    after_leaves = {leaf["identity"]: leaf["digest"] for leaf in after.get("leaves", [])}
    identities = sorted(set(before_leaves).union(after_leaves))
    changed = [name for name in identities if before_leaves.get(name) != after_leaves.get(name)]
    unchanged = [name for name in identities if before_leaves.get(name) == after_leaves.get(name)]
    return {
        "changedComponents": changed,
        "unchangedComponents": unchanged,
        "changedCount": len(changed),
        "unchangedCount": len(unchanged),
        "rootChanged": before.get("rootDigest") != after.get("rootDigest"),
    }


def build_prompt_prefix_plan(
    sections: Sequence[Mapping[str, Any]],
    *,
    breakpoint_after: Optional[str] = None,
) -> Dict[str, Any]:
    """Model exact serialized-prefix identity separately from the Merkle tree.

    Sections are serialized in the supplied order as ``[identity]\ntext`` and
    separated by two newlines. The returned digest is useful for measuring
    stable-prefix behavior but makes no claim about any provider cache.
    """
    normalized: List[Dict[str, str]] = []
    found_breakpoint = breakpoint_after is None
    prefix_sections: List[Dict[str, str]] = []
    for section in sections:
        identity = str(section["identity"])
        text = str(section["text"])
        item = {"identity": identity, "text": text}
        normalized.append(item)
        if not found_breakpoint:
            prefix_sections.append(item)
            if identity == breakpoint_after:
                found_breakpoint = True
        elif breakpoint_after is None:
            prefix_sections.append(item)

    if breakpoint_after is not None and not found_breakpoint:
        raise ValueError("breakpoint identity not present: %s" % breakpoint_after)

    if breakpoint_after is not None:
        prefix_sections = []
        for item in normalized:
            prefix_sections.append(item)
            if item["identity"] == breakpoint_after:
                break

    rendered_prefix = "\n\n".join(
        "[%s]\n%s" % (item["identity"], item["text"])
        for item in prefix_sections
    )
    full_render = "\n\n".join(
        "[%s]\n%s" % (item["identity"], item["text"])
        for item in normalized
    )
    return {
        "schemaVersion": MERKLE_SCHEMA_VERSION,
        "kind": "PromptPrefixPlan",
        "sectionOrder": [item["identity"] for item in normalized],
        "breakpointAfter": breakpoint_after,
        "prefixDigest": digest(rendered_prefix),
        "fullPromptDigest": digest(full_render),
        "exactPrefixRequired": True,
        "providerCacheHitClaim": False,
    }
