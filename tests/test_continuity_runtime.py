import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capt_solo.continuity import (  # noqa: E402
    ContinuityError, ContinuityPack, evaluate_pack, load_policy, plan_drill,
    verify_receipt,
)
import capt_cli  # noqa: E402


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = os.path.join(ROOT, "architecture", "cve", "continuity-v0.2.yaml")


def _raw(tier="C1", status="verified", expires_at="", roles=None):
    return {
        "pack_id": "memory-continuity-1", "component": "capt-solo-memory", "tier": tier,
        "scope": "local test only", "policy_id": "capt-cve-continuity-v0.2",
        "created_at": "2026-07-28T00:00:00+00:00",
        "roles": roles or [{"role": "operator", "identity": "op-a"}, {"role": "reviewer", "identity": "reviewer-b"}],
        "claims": [{"claim_id": "memory-export", "statement": "export can be inspected"}],
        "evidence": [{"evidence_id": "ev-1", "kind": "test_result", "status": status,
                      "source": "tests/test_memory.py", "collected_at": "2026-07-28T00:00:00+00:00",
                      "verifier": "pytest", "expires_at": expires_at}],
    }


def test_policy_has_exactly_nine_clauses():
    policy = load_policy(POLICY)
    assert len(policy["articles"]) == 9


def test_current_evidence_and_independent_roles_pass():
    result = evaluate_pack(ContinuityPack.from_dict(_raw()), load_policy(POLICY))
    assert result["status"] == "PASS"
    assert result["receipt"]["pack_digest"].startswith("sha256:")


def test_missing_evidence_blocks_instead_of_assuming_compliance():
    raw = _raw(); raw["evidence"] = []
    result = evaluate_pack(ContinuityPack.from_dict(raw), load_policy(POLICY))
    assert result["status"] == "BLOCK"
    assert any(x["code"] == "evidence_missing" for x in result["findings"])


def test_expired_and_invalid_evidence_block():
    expired = _raw(expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
    assert evaluate_pack(ContinuityPack.from_dict(expired), load_policy(POLICY))["status"] == "BLOCK"
    assert evaluate_pack(ContinuityPack.from_dict(_raw(status="invalidated")), load_policy(POLICY))["status"] == "BLOCK"


def test_role_concentration_blocks_independence_claim():
    raw = _raw(roles=[{"role": "operator", "identity": "same"}, {"role": "reviewer", "identity": "same"}])
    result = evaluate_pack(ContinuityPack.from_dict(raw), load_policy(POLICY))
    assert result["status"] == "BLOCK"
    assert any(x["code"] == "role_independence_failed" for x in result["findings"])


def test_pack_secret_screening_rejects_token_values():
    raw = _raw(); raw["metadata"] = {"token": "sk_abcdefghijklmnop"}
    with pytest.raises(ContinuityError):
        ContinuityPack.from_dict(raw)


def test_receipt_verification_detects_pack_mutation():
    policy = load_policy(POLICY); pack = ContinuityPack.from_dict(_raw())
    receipt = evaluate_pack(pack, policy)["receipt"]
    assert verify_receipt(receipt, pack, policy)["valid"]
    changed = _raw(); changed["claims"][0]["statement"] = "different"
    assert not verify_receipt(receipt, ContinuityPack.from_dict(changed), policy)["valid"]


def test_drills_are_plan_only_and_production_is_refused():
    pack = ContinuityPack.from_dict(_raw())
    assert plan_drill(pack)["status"] == "NOT_RUN"
    with pytest.raises(ContinuityError):
        plan_drill(pack, "production")


def test_cli_blocks_a_pack_without_evidence(tmp_path):
    raw = _raw(); raw["evidence"] = []
    path = tmp_path / "blocked.json"; path.write_text(json.dumps(raw))
    assert capt_cli.main(["continuity", "evaluate", str(path)]) == 2
