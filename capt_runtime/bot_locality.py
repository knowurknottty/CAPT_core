"""Compile low-friction onboarding answers into explicit locality policy.

This module selects where data may be processed. It never grants network,
filesystem, credential, or tool authority; those remain separate CAPT grants.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from .contracts import require
from .errors import AuthorityViolation

_PRIVATE_CLASSES = frozenset({"project", "user", "secret"})


def compile_onboarding_locality(answers: Mapping[str, Any]) -> Dict[str, str]:
    allow_cloud = bool(answers.get("allowCloudExecution", False))
    allow_private_cloud = bool(answers.get("allowPrivateDataInCloud", False))
    preferred = answers.get("preferredRuntime")

    if allow_private_cloud and not allow_cloud:
        raise AuthorityViolation("PRIVATE_CLOUD_REQUIRES_CLOUD_EXECUTION")
    if preferred not in {None, "local", "cloud", "either"}:
        raise AuthorityViolation("LOCALITY_RUNTIME_INVALID")
    if preferred in {"cloud", "either"} and not allow_cloud:
        raise AuthorityViolation("CLOUD_RUNTIME_NOT_ALLOWED")

    if not allow_cloud:
        runtime = "local"
    else:
        runtime = str(preferred or "either")
    policy = {
        "defaultRuntime": runtime,
        "privateData": "cloud_allowed" if allow_private_cloud else "local_only",
    }
    require("BotLocalityPolicy", policy)
    return policy


def runtime_for_data(policy: Mapping[str, str], sensitivity: str) -> str:
    require("BotLocalityPolicy", dict(policy))
    if sensitivity not in {"public", "project", "user", "secret"}:
        raise AuthorityViolation("DATA_SENSITIVITY_INVALID")
    if sensitivity in _PRIVATE_CLASSES and policy["privateData"] == "local_only":
        return "local"
    return str(policy["defaultRuntime"])
