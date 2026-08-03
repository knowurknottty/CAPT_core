"""ContextSlice construction (M0-B, ADR-0125).

ContextSlice is a deliberately minimal, read-only projection built by CAPT
(`DriverHost`), never by the driver. It MUST NOT contain governance, policy,
claim, capability-graph, ledger, or aggregate references. Over-disclosure is a
build-time contract violation: constructing a ContextSlice with any forbidden
object reference raises.
"""

from __future__ import annotations

from typing import Any, Dict

from .contracts import require

# Objects that must NEVER appear inside a ContextSlice. Their mere presence is an
# authority-escalation surface. We check by type name so we don't need imports.
_FORBIDDEN_TYPE_NAMES = frozenset(
    {
        "GovernanceKernel",
        "PolicyEngine",
        "ClaimGuard",
        "CapabilityAggregate",
        "EventLedger",
        "EventStore",
        "MissionAggregate",
        "TaskAggregate",
        "ClaimAggregate",
        "DriverRegistry",
    }
)


class ContextOverDisclosure(Exception):
    pass


def _scan_forbidden(obj: Any, path: str = "$") -> None:
    """Recursively reject any forbidden authority object by type name."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _scan_forbidden(v, "%s.%s" % (path, k))
        return
    if isinstance(obj, (list, tuple, set)):
        for i, v in enumerate(obj):
            _scan_forbidden(v, "%s[%d]" % (path, i))
        return
    # It's some object instance.
    type_name = type(obj).__name__
    if type_name in _FORBIDDEN_TYPE_NAMES:
        raise ContextOverDisclosure(
            "ContextSlice must not contain %s (found at %s)" % (type_name, path)
        )


def build_context_slice(
    lease: Dict[str, Any],
    filesystem_policy: Dict[str, Any],
    permitted_tools: list,
    budgets: Dict[str, Any],
    expected_artifacts: list,
    termination_conditions: Dict[str, Any],
    network_policy: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Construct a validated ContextSlice. Forbidden objects are rejected."""
    # Guard against accidental leakage of authority objects.
    _scan_forbidden(lease)
    _scan_forbidden(filesystem_policy)
    _scan_forbidden(budgets)
    _scan_forbidden(permitted_tools)
    _scan_forbidden(expected_artifacts)
    _scan_forbidden(termination_conditions)

    slice_: Dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "lease": lease,
        "filesystemPolicy": filesystem_policy,
        "permittedTools": list(permitted_tools),
        "budgets": budgets,
        "expectedArtifacts": list(expected_artifacts),
        "terminationConditions": termination_conditions,
    }
    if network_policy is not None:
        slice_["networkPolicy"] = network_policy
    return require("ContextSlice", slice_)
