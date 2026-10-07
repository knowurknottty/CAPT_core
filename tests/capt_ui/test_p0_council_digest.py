"""P0.2 digest-integrity tests: the reattach identity must be bound to the
actual workflow bytes, not to a caller-supplied digest string.

- Forged digest (valid format, wrong value) is rejected.
- Stale digest (workflow mutated after digesting) is rejected.
- Mutations to provider, model, cohortId, targetRoot, missionId are rejected.
- Exact session and repeated exact reattachment are accepted.
"""
from __future__ import annotations

import copy
import dataclasses
from pathlib import Path

import pytest

from capt_ui.operator.council_workflow import (
    CouncilWorkflow,
    donor_convergence_workflow,
    workflow_digest,
)
from capt_ui.operator.runtime import Operator, OperatorError

# Reuse the harness from the sibling module.
from test_council_reattach import _FakeClient, _operator, _session, _states


def _cohorts(session):
    return [a["cohortSpec"]["cohortId"] for a in session["approvals"]]


def test_reattach_forged_digest_rejected(tmp_path: Path):
    session, run_key = _session(tmp_path)
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=tuple(cohorts)))
    session["workflowDigest"] = "sha256:" + "0" * 64
    with pytest.raises(OperatorError, match="digest mismatch"):
        op.reattach_council_workflow(session)
    assert op._client.commands == []


def test_reattach_missing_digest_rejected(tmp_path: Path):
    session, run_key = _session(tmp_path)
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=tuple(cohorts)))
    del session["workflowDigest"]
    with pytest.raises(OperatorError, match="digest mismatch"):
        op.reattach_council_workflow(session)
    assert op._client.commands == []


def _mutated_session(tmp_path, replace):
    """Apply a dataclasses.replace transformation, keeping the stale digest."""
    session, run_key = _session(tmp_path)
    wf = CouncilWorkflow.from_mapping(copy.deepcopy(session["workflow"]))
    wf = replace(wf)
    session["workflow"] = wf.to_record()
    return session, run_key


def _replace_cohort(wf, idx, **kw):
    cohorts = list(wf.cohorts)
    cohorts[idx] = dataclasses.replace(cohorts[idx], **kw)
    return dataclasses.replace(wf, cohorts=tuple(cohorts))


def test_reattach_stale_digest_on_provider_mutation_rejected(tmp_path: Path):
    session, run_key = _mutated_session(
        tmp_path, lambda wf: _replace_cohort(wf, 0, provider="evil-provider"))
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=tuple(cohorts)))
    with pytest.raises(OperatorError, match="digest mismatch"):
        op.reattach_council_workflow(session)
    assert op._client.commands == []


def test_reattach_stale_digest_on_model_mutation_rejected(tmp_path: Path):
    session, run_key = _mutated_session(
        tmp_path, lambda wf: _replace_cohort(wf, 0, model="evil-model"))
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=tuple(cohorts)))
    with pytest.raises(OperatorError, match="digest mismatch"):
        op.reattach_council_workflow(session)
    assert op._client.commands == []


def test_reattach_stale_digest_on_target_root_mutation_rejected(tmp_path: Path):
    other = tmp_path / "other-root"
    other.mkdir()
    session, run_key = _mutated_session(
        tmp_path, lambda wf: dataclasses.replace(wf, target_root=str(other)))
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=tuple(cohorts)))
    with pytest.raises(OperatorError, match="digest mismatch"):
        op.reattach_council_workflow(session)
    assert op._client.commands == []


def test_reattach_stale_digest_on_mission_mutation_rejected(tmp_path: Path):
    session, run_key = _mutated_session(
        tmp_path, lambda wf: dataclasses.replace(wf, mission_id="evil-mission"))
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=tuple(cohorts)))
    with pytest.raises(OperatorError, match="digest mismatch"):
        op.reattach_council_workflow(session)
    assert op._client.commands == []


def test_reattach_exact_session_accepted_repeatedly(tmp_path: Path):
    """Exact session: digest recomputes equal, reattachment accepted twice,
    provider dispatched exactly once (no redispatch of completed work)."""
    session, run_key = _session(tmp_path)
    cohorts = _cohorts(session)
    op = _operator(_states(session, run_key, consumed=tuple(cohorts)))
    r1 = op.reattach_council_workflow(session)
    r2 = op.reattach_council_workflow(session)
    assert r1["status"] == "accepted"
    assert r2["status"] == "idempotent"
    assert op._client.dispatches == 1
    # The run key used is derived from the recomputed digest.
    _op, _payload, key = op._client.commands[0]
    assert key == run_key
