"""Durable, advisory prompt proposal state.

Prompt proposals preserve literal user intent and compiler output for later
human approval binding.  This aggregate deliberately has no approval,
capability-grant, dispatch, verification, or completion transition.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet

from ..contracts import digest
from ..errors import IllegalTransition, IntegrityViolation


class PromptProposalAggregate(object):
    """Owns one revisionable prompt proposal, separate from HumanApproval."""

    KIND = "prompt_proposal"
    OWNED_FIELDS: FrozenSet[str] = frozenset(
        {
            "prompt_proposal.proposedPrompt",
            "prompt_proposal.proposedPromptDigest",
            "prompt_proposal.stageChain",
            "prompt_proposal.stageRecords",
            "prompt_proposal.provider",
            "prompt_proposal.model",
            "prompt_proposal.requestedContextBudget",
            "prompt_proposal.effectiveContextBudget",
            "prompt_proposal.capabilityRequests",
            "prompt_proposal.verificationContract",
            "prompt_proposal.state",
            "prompt_proposal.revision",
            "prompt_proposal.cancelReason",
        }
    )
    REFERENCE_FIELDS: FrozenSet[str] = frozenset(
        {"proposalId", "originalPrompt", "originalPromptDigest", "mode", "targetRoot"}
    )

    @staticmethod
    def stream_id(proposal_id: str) -> str:
        return "prompt_proposal-" + proposal_id

    @staticmethod
    def create(proposal: Dict[str, Any]) -> Dict[str, Any]:
        original = str(proposal["originalPrompt"])
        proposed = str(proposal["proposedPrompt"])
        if not original or not proposed:
            raise ValueError("prompt proposal originalPrompt and proposedPrompt are required")
        return {
            "proposalId": proposal["proposalId"],
            "originalPrompt": original,
            "originalPromptDigest": digest(original),
            "proposedPrompt": proposed,
            "proposedPromptDigest": digest(proposed),
            "mode": proposal["mode"],
            "stageChain": list(proposal["stageChain"]),
            "stageRecords": list(proposal.get("stageRecords", [])),
            "targetRoot": proposal["targetRoot"],
            "provider": proposal.get("provider"),
            "model": proposal.get("model"),
            "requestedContextBudget": int(proposal.get("requestedContextBudget", 0)),
            "effectiveContextBudget": int(proposal.get("effectiveContextBudget", 0)),
            "capabilityRequests": list(proposal.get("capabilityRequests", [])),
            "verificationContract": dict(proposal["verificationContract"]),
            "state": "active",
            "revision": 0,
            "cancelReason": None,
        }

    @staticmethod
    def revise(state: Dict[str, Any], revision: Dict[str, Any]) -> Dict[str, Any]:
        if state["state"] != "active":
            raise IllegalTransition(
                "prompt proposal %s" % state["proposalId"], state["state"], "active"
            )
        proposed = str(revision["proposedPrompt"])
        if not proposed:
            raise ValueError("revised proposedPrompt is required")
        nxt = dict(state)
        nxt["proposedPrompt"] = proposed
        nxt["proposedPromptDigest"] = digest(proposed)
        for field in (
            "stageChain",
            "stageRecords",
            "provider",
            "model",
            "requestedContextBudget",
            "effectiveContextBudget",
            "capabilityRequests",
            "verificationContract",
        ):
            if field in revision:
                value = revision[field]
                if field in ("stageChain", "stageRecords", "capabilityRequests"):
                    value = list(value)
                elif field == "verificationContract":
                    value = dict(value)
                elif field in ("requestedContextBudget", "effectiveContextBudget"):
                    value = int(value)
                nxt[field] = value
        nxt["revision"] = int(state["revision"]) + 1
        # These immutable fields are intentionally never accepted from a revision.
        return nxt

    @staticmethod
    def cancel(state: Dict[str, Any], reason: str) -> Dict[str, Any]:
        if state["state"] != "active":
            raise IllegalTransition(
                "prompt proposal %s" % state["proposalId"], state["state"], "cancelled"
            )
        if not reason:
            raise ValueError("prompt proposal cancellation reason is required")
        nxt = dict(state)
        nxt["state"] = "cancelled"
        nxt["cancelReason"] = reason
        return nxt

    @staticmethod
    def replay_create(snapshot: Dict[str, Any]) -> Dict[str, Any]:
        if snapshot.get("originalPromptDigest") != digest(snapshot.get("originalPrompt", "")):
            raise IntegrityViolation("prompt proposal original prompt digest mismatch")
        if snapshot.get("proposedPromptDigest") != digest(snapshot.get("proposedPrompt", "")):
            raise IntegrityViolation("prompt proposal proposed prompt digest mismatch")
        if snapshot.get("state") != "active" or snapshot.get("revision") != 0:
            raise IntegrityViolation("invalid prompt proposal creation snapshot")
        return dict(snapshot)
