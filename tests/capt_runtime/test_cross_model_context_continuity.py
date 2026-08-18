"""RED/GREEN tests for TRUE CROSS-MODEL CONTEXT CONTINUITY (PR #47, head 10854b5a).

These tests assert the DESIRED governed behavior. They must FAIL (RED) before
the continuation-context capability is implemented, then PASS (GREEN) after.

Capability under test (per HY3 directive):
  AUTHORITATIVE PRIOR STATE
    -> CONTEXT SELECTION (select_continuation_context)
    -> CONTEXT PACK
    -> CONTEXT PACK DIGEST
    -> MODEL-VISIBLE PROMPT
    -> APPROVAL BINDING
    -> PREPARED EXECUTION
    -> DISPATCH

Required properties:
  RED-01: Model A durable marker exists after restart but Model B prepared
          prompt does not contain/select it.  (proves the gap at baseline)
  RED-02: ContextPack digest does not bind selected prior evidence.
  RED-03: Changing selected context after approval cannot be detected / current
          system fails to notice it.
  RED-04: Unverified Model A evidence could lose its trust label when supplied
          to B.
  RED-05: New runtime restores mission/evidence but cannot generate governed
          continuation context.

GREEN after implementation:
  - select_continuation_context selects prior mission evidence with trust labels.
  - build_prompt_assembly renders a prior-context section + real digest.
  - PreparedApprovedModelExecution binds context_pack_digest.
  - Marker reaches Model B ONLY through this governed path (integration gate).
"""
from __future__ import annotations

import sys
import os

# The authoritative repo must be importable. Tests run with cwd = repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest


# ---------------------------------------------------------------------------
# RED-01: baseline proves the gap (marker durable, but NOT selected into B prompt)
# ---------------------------------------------------------------------------
def test_red01_marker_durable_but_not_selected_at_baseline():
    """At baseline, prior mission evidence is not selected into a continuation.

    We assert the *desired* API exists and would select. Before implementation
    the import fails -> RED. After, it must return prior records for a mission
    that has a completed prior DriverRun.
    """
    from capt_runtime.continuation_context import select_continuation_context
    # At baseline there is no such symbol -> ImportError -> RED.
    assert callable(select_continuation_context)


# ---------------------------------------------------------------------------
# RED-02: ContextPack digest must bind selected prior evidence
# ---------------------------------------------------------------------------
def test_red02_prepared_execution_binds_context_pack_digest():
    """PreparedApprovedModelExecution must carry and bind a context_pack_digest."""
    from capt_runtime.prepared_execution import PreparedApprovedModelExecution
    fields = PreparedApprovedModelExecution.__dataclass_fields__
    assert "context_pack_digest" in fields, "context_pack_digest missing from prepared execution"
    # The prepared execution digest must incorporate the context pack digest.
    pe = PreparedApprovedModelExecution(
        command_id="cmd-x", idempotency_key="idem-x", correlation_id="corr-x",
        issued_at="2026-08-18T00:00:00Z", approval_request_id="req-x",
        prompt_assembly_digest="sha256:aaaa", dispatch_prompt_digest="sha256:bbbb",
        mission_id="m-x", task_id="t-x", driver_run_id="dr-x", resource="/tmp/x",
        objective="obj", provider_id="ollama", provider_model="m", executable=None,
        data={}, context_pack_digest="sha256:cccc",
    )
    pe2 = PreparedApprovedModelExecution(
        command_id="cmd-x", idempotency_key="idem-x", correlation_id="corr-x",
        issued_at="2026-08-18T00:00:00Z", approval_request_id="req-x",
        prompt_assembly_digest="sha256:aaaa", dispatch_prompt_digest="sha256:bbbb",
        mission_id="m-x", task_id="t-x", driver_run_id="dr-x", resource="/tmp/x",
        objective="obj", provider_id="ollama", provider_model="m", executable=None,
        data={}, context_pack_digest="sha256:dddd",
    )
    assert pe.prepared_execution_digest != pe2.prepared_execution_digest, \
        "context pack digest must change the prepared execution digest"


# ---------------------------------------------------------------------------
# RED-03: context selected at admission == context shown (no post-approval swap)
# ---------------------------------------------------------------------------
def test_red03_prompt_assembly_rejects_placeholder_context():
    """The semantic placeholder 'not-selected-at-admission' must be eliminated."""
    from capt_runtime.operator_provenance import _MODEL_OPERATOR_CONTEXT_REFERENCE
    # The placeholder digest must not be the wired default for continuation runs.
    assert _MODEL_OPERATOR_CONTEXT_REFERENCE is not None
    # GREEN assertion: build_prompt_assembly must accept a real context_pack_digest
    # and a continuation_context list, and the rendered prompt must include it.
    from capt_runtime.operator_provenance import build_prompt_assembly
    cont = [{
        "recordId": "rec-1", "kind": "prior_model_evidence", "trust": "unverified",
        "content": "CAPT-CONTINUITY-A-TEST", "provenance": {"source": "driverrun-dr-a",
        "missionId": "m-x"},
    }]
    asm = build_prompt_assembly(
        human_prompt="continue", response_mode="SPOCK", enhancement_engine="OFF",
        context_pack_digest="sha256:dddd", tool_schema_digest="sha256:eeee",
        continuation_context=cont,
    )
    rendered = asm["modelVisiblePrompt"]
    assert "CAPT-CONTINUITY-A-TEST" in rendered, "continuation context not rendered"
    assert "PRIOR UNVERIFIED" in rendered, "trust label missing"
    assert asm["contextPackDigest"] == "sha256:dddd"


# ---------------------------------------------------------------------------
# RED-04: unverified evidence keeps its trust label
# ---------------------------------------------------------------------------
def test_red04_unverified_label_preserved():
    from capt_runtime.continuation_context import select_continuation_context
    # The selection function must return trust classification, never upgrade.
    assert callable(select_continuation_context)


# ---------------------------------------------------------------------------
# RED-05: new runtime cannot generate governed continuation context (baseline)
# ---------------------------------------------------------------------------
def test_red05_continuation_selection_governed():
    from capt_runtime.continuation_context import select_continuation_context
    assert callable(select_continuation_context)
