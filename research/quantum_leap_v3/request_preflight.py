"""Offline structural handoff checker against CAPT's *actual* ToolRequest contract.

It imports CAPT's real tool_request_fingerprint and schema validator; it does
NOT use ToolBroker.build_execution or any live grant/lease/authority API.
The output is an advisory identity check, never an authorization to dispatch.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from capt_runtime.contracts import require
from capt_runtime.errors import ContractViolation
from capt_runtime.tool_broker import tool_request_fingerprint
from research.quantum_leap_v3.finite_decision import assess_proposal

def _result(reason:str,request:Mapping[str,Any]|None=None)->dict:
    return {
        "structural_match":reason=="IDENTITY_MATCH_ONLY",
        "reason":reason,
        "request_fingerprint":request.get("operationFingerprint") if request else None,
        "runtime_authority_verified":False,
        "fresh_grant_verified":False,
        "effect_verified":False,
        "completion_verified":False,
        "dispatch_allowed":False,
    }

def check_request_identity(
    offering,
    assessment,
    *,
    selected_parameters:Mapping[str,Any],
    decision_probabilities:Mapping[str,Any],
    advisory_thresholds:Mapping[str,Any],
    request:Mapping[str,Any],
    expected_tool_id:str,
    expected_operation:str,
    fresh_world_digest:str,
    fresh_policy_digest:str,
)->dict:
    """Return only whether proposal and tool request have matching structural identities.

    expected_tool_id/operation and fresh_* digests must come from an external
    trusted operator/runtime boundary. This function cannot authenticate those
    inputs and must never claim it does.
    """
    if assessment.status!="proposal_ready_for_runtime_review" or assessment.dispatch_allowed or assessment.completed:
        return _result("PROPOSAL_NOT_REVIEWABLE")
    if assessment.offered_digest!=offering.digest or offering.dispatch_allowed:
        return _result("PROPOSAL_OFFERING_MISMATCH")
    # Recompute against the offered scope rather than trusting a serialized
    # assessment supplied by the model. Values/probabilities remain untrusted.
    try:
        independent_assessment = assess_proposal(
            offering, selected=assessment.selected,
            parameters=selected_parameters,
            probabilities=decision_probabilities,
            declared_offering_digest=offering.digest,
            thresholds=advisory_thresholds,
        )
    except (TypeError, ValueError, KeyError):
        return _result("ASSESSMENT_INPUT_INVALID")
    if independent_assessment.to_dict()!=assessment.to_dict():
        return _result("ASSESSMENT_RECOMPUTATION_MISMATCH")
    if fresh_world_digest!=offering.world_digest or fresh_policy_digest!=offering.policy_digest:
        return _result("SOURCE_SNAPSHOT_OR_POLICY_CHANGED")
    action=assessment.selected
    if action not in offering.actions:
        return _result("ACTION_NOT_OFFERED")
    if not isinstance(selected_parameters,Mapping) or not isinstance(request,Mapping):
        return _result("INVALID_REQUEST_SHAPE")
    declared=offering.actions[action]["params"]
    if selected_parameters.keys()!=declared.keys():
        return _result("DECLARED_PARAMETERS_MISMATCH")
    if request.get("toolId")!=expected_tool_id or request.get("operation")!=expected_operation:
        return _result("ROUTING_IDENTITY_MISMATCH")
    expected=[]
    for name in sorted(declared):
        param=declared[name]
        value=selected_parameters[name]
        if param["kind"]=="boolean":
            if type(value) is not bool:
                return _result("PARAMETER_TYPE_MISMATCH")
            expected.append({"kind":"boolean","name":name,"value":value})
        else:
            if not isinstance(value,str) or value not in param["values"]:
                return _result("PARAMETER_NOT_OFFERED")
            expected.append({"kind":"string","name":name,"value":value})
    # Strict equality: no extra parameters, implicit transformations or
    # policy-omitted argument escapes. CAPT can subsequently resolve handles.
    incoming=request.get("arguments")
    if not isinstance(incoming,list):
        return _result("INVALID_ARGUMENTS")
    if sorted(incoming,key=lambda x:x.get("name","") if isinstance(x,dict) else "")!=expected:
        return _result("EXACT_ARGUMENTS_MISMATCH")
    try:
        require("ToolRequest",dict(request))
        if tool_request_fingerprint(dict(request))!=request["operationFingerprint"]:
            return _result("BROKER_FINGERPRINT_MISMATCH")
    except (ContractViolation,ValueError,KeyError,TypeError,RuntimeError,AssertionError):
        return _result("TOOLREQUEST_SCHEMA_OR_FINGERPRINT_REJECTED")
    # Caller supplies both routing and freshness inputs; this code cannot
    # verify their custody, genuine operator approval, a capability, or the world.
    return _result("IDENTITY_MATCH_ONLY",request)
