"""Authoritative CAPT Bot identity/policy composition.

A Bot aggregate owns durable identity and declared policy only. Live secrets,
capability grants, leases, and execution state remain owned by their existing
CAPT authority planes.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from ..errors import AuthorityViolation


class BotAggregate(object):
    KIND = "bot"
    OWNED_FIELDS = frozenset({
        "bot.displayName", "bot.roleKind", "bot.role", "bot.missionId",
        "bot.modelStrategy", "bot.cognitionPolicy", "bot.localityPolicy",
        "bot.collaboration", "bot.authorityTemplateRef", "bot.createdBy",
        "bot.createdAt",
    })
    REFERENCE_FIELDS = frozenset({"botId"})

    @staticmethod
    def stream_id(bot_id: str) -> str:
        if not bot_id:
            raise ValueError("BOT_ID_REQUIRED")
        return "bot-" + bot_id

    @staticmethod
    def create(spec: Mapping[str, Any]) -> Dict[str, Any]:
        if spec.get("roleKind") == "delegate" and not spec.get("missionId"):
            raise AuthorityViolation("DELEGATE_MISSION_REQUIRED")
        return {
            "botId": str(spec["botId"]),
            "displayName": str(spec["displayName"]),
            "roleKind": str(spec["roleKind"]),
            "role": str(spec["role"]),
            "missionId": spec.get("missionId"),
            "modelStrategy": dict(spec.get("modelStrategy") or {}),
            "cognitionPolicy": dict(spec.get("cognitionPolicy") or {}),
            "localityPolicy": dict(spec.get("localityPolicy") or {}),
            "collaboration": dict(spec.get("collaboration") or {}),
            "authorityTemplateRef": spec.get("authorityTemplateRef"),
            "createdBy": dict(spec["createdBy"]),
            "createdAt": str(spec["createdAt"]),
        }
