"""System-One-inspired finite decision proposals for CAPT Quantum Leap.

Research-only. Never dispatches a tool, grants authority or verifies completion.
Original CAPT implementation informed by Apache-2.0 donor:
HarnessRouter/SystemOneHarness @ ab8e8f08b4a6268c0633a474423d556599ee06a4
See systemone_cherrypick.md for source and licensing details.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

_VALID_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_KINDS = frozenset({"enum", "candidate", "boolean", "levels"})
_RISKS = frozenset({"read", "write", "destructive"})
_MAX_OPTIONS = 64

class InvalidDecisionContract(ValueError):
    pass

@dataclass(frozen=True)
class Offering:
    actions: Mapping[str, Any]
    omissions: Mapping[str, str]
    digest: str
    world_digest: str
    policy_digest: str
    # Observe mode may propose but never execute or conclude completion.
    dispatch_allowed: bool = False

@dataclass(frozen=True)
class Assessment:
    status: str
    reason: str
    selected: str | None
    weakest_probability: float | None
    required_probability: float | None
    offered_digest: str
    dispatch_allowed: bool = False
    completed: bool = False
    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status, "reason": self.reason, "selected": self.selected,
            "weakest_probability": self.weakest_probability,
            "required_probability": self.required_probability, "offered_digest": self.offered_digest,
            "dispatch_allowed": False, "completed": False,
        }

def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

def _allowed_values(spec: Mapping[str, Any], observation: Mapping[str, Any]) -> tuple[list[str] | None, str | None]:
    kind = spec.get("kind")
    if kind not in _KINDS:
        return None, "unsupported_parameter_kind"
    if kind == "boolean":
        if set(spec) - {"kind"}:
            return None, "unsupported_boolean_options"
        return ["false", "true"], None
    if kind == "candidate":
        src = spec.get("source")
        if not isinstance(src, str) or not _VALID_NAME.fullmatch(src):
            return None, "invalid_candidate_source"
        if set(spec) - {"kind", "source"}:
            return None, "unsupported_candidate_options"
        raw = observation.get(src)
    else:
        if set(spec) - {"kind", "values"}:
            return None, "unsupported_parameter_options"
        raw = spec.get("values")
    if not isinstance(raw, list) or not raw:
        return None, "missing_finite_options"
    if len(raw) > _MAX_OPTIONS:
        return None, "option_budget_exceeded"
    if not all(isinstance(s, str) and 0 < len(s) <= 128 for s in raw):
        return None, "invalid_option"
    if len(set(raw)) != len(raw):
        return None, "duplicate_option"
    if kind == "candidate" and not all(re.fullmatch(r"h_[0-9a-f]{32}", item) for item in raw):
        return None, "nonopaque_candidate"
    if kind == "levels" and len(raw) < 2:
        return None, "insufficient_levels"
    return list(raw), None

def compile_offering(
    registered: Mapping[str, Any],
    candidates: Mapping[str, Any],
    *,
    allowed_actions: frozenset[str],
    world_digest: str,
    policy_digest: str,
) -> Offering:
    """Compile registered, policy-supplied declarations, not model-supplied schemas.

    The allowed_actions list is a *read-only filter*, not a CAPT grant.
    """
    if not all(isinstance(x, str) and re.fullmatch(r"[0-9a-f]{64}", x) for x in (world_digest, policy_digest)):
        raise InvalidDecisionContract("world and policy require canonical SHA-256 digests")
    if not isinstance(registered, Mapping) or not isinstance(candidates, Mapping):
        raise InvalidDecisionContract("actions and candidates must be mappings")
    if not isinstance(allowed_actions, frozenset):
        raise InvalidDecisionContract("allowed_actions must be an explicit frozen set")
    actions: dict[str, Any] = {}
    omissions: dict[str, str] = {}
    for name, raw in sorted(registered.items()):
        if not isinstance(name, str) or not _VALID_NAME.fullmatch(name) or name in ("finish", "escalate"):
            omissions[str(name)] = "reserved_or_invalid_name"
            continue
        if name not in allowed_actions:
            omissions[name] = "not_in_observation_scope"
            continue
        if not isinstance(raw, dict) or set(raw) - {"risk", "params"}:
            omissions[name] = "invalid_declaration_shape"
            continue
        risk = raw.get("risk")
        if risk not in _RISKS:
            omissions[name] = "missing_or_invalid_risk"
            continue
        params = raw.get("params", {})
        if not isinstance(params, dict) or len(params) > 16:
            omissions[name] = "invalid_parameter_map"
            continue
        compiled_params: dict[str, Any] = {}
        reason = None
        for pname, pspec in sorted(params.items()):
            if not isinstance(pname,str) or not _VALID_NAME.fullmatch(pname) or not isinstance(pspec,dict):
                reason = "invalid_parameter_shape"
                break
            values, err = _allowed_values(pspec, candidates)
            if err:
                reason = f"{pname}:{err}"
                break
            compiled_params[pname] = {"kind": pspec["kind"], "values": values}
        if reason:
            omissions[name] = reason
            continue
        actions[name] = {"risk":risk, "params":compiled_params}
    payload = {"actions":actions, "omissions":omissions, "world_digest":world_digest, "policy_digest":policy_digest}
    try:
        digest = hashlib.sha256(_canonical(payload).encode()).hexdigest()
    except (TypeError,ValueError) as exc:
        raise InvalidDecisionContract("unserializable decision scope") from exc
    return Offering(actions, omissions, digest, world_digest, policy_digest)

def _confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        f = float(value)
    except (ValueError,OverflowError):
        return None
    return f if math.isfinite(f) and 0 <= f <= 1 else None

def assess_proposal(
    offering: Offering,
    *,
    selected: str,
    parameters: Mapping[str, Any],
    probabilities: Mapping[str, Any],
    declared_offering_digest: str,
    thresholds: Mapping[str, float],
) -> Assessment:
    """Check a proposal's shape and discrimination, not its authority.

    A successful result is 'proposal_ready_for_runtime_review', never execute.
    """
    def result(status: str, reason: str, weakest: float | None = None, required: float | None = None) -> Assessment:
        return Assessment(status,reason,selected,weakest,required,offering.digest)
    if declared_offering_digest != offering.digest:
        return result("refused","decision_scope_digest_mismatch")
    if selected == "escalate":
        return result("escalation_requested","model_abstained")
    if selected == "finish":
        return result("verification_required","model_finish_not_completion_evidence")
    if not isinstance(selected,str) or selected not in offering.actions:
        return result("refused","unoffered_action")
    if not isinstance(parameters,Mapping) or not isinstance(probabilities,Mapping):
        return result("refused","invalid_decision_shape")
    spec = offering.actions[selected]
    risk = spec["risk"]
    floor = _confidence(thresholds.get(risk))
    if floor is None:
        return result("refused","invalid_risk_threshold")
    if set(parameters)!=set(spec["params"]):
        return result("refused","parameter_names_mismatch")
    expected_prob_keys = {"action"} | set(spec["params"])
    if set(probabilities)!=expected_prob_keys:
        return result("refused","probability_evidence_missing_or_extra")
    conf: list[float] = []
    for pname,pdef in spec["params"].items():
        val = parameters[pname]
        if pdef["kind"]=="boolean":
            if type(val) is not bool:
                return result("refused",f"{pname}:not_boolean")
        elif not isinstance(val,str) or val not in pdef["values"]:
            return result("refused",f"{pname}:not_in_offered_values")
        v = _confidence(probabilities[pname])
        if v is None:
            return result("refused",f"{pname}:invalid_probability")
        conf.append(v)
    action_probability = _confidence(probabilities["action"])
    if action_probability is None:
        return result("refused","invalid_action_probability")
    conf.append(action_probability)
    weakest = min(conf)
    if weakest < floor:
        return result("needs_escalation","confidence_below_advisory_floor",weakest,floor)
    return result("proposal_ready_for_runtime_review","no_capability_or_outcome_authority",weakest,floor)
