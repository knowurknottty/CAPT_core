"""Regression coverage for CAPT-UPG-014 shared Dashboard projection."""

import capt_ui.operator.runtime as runtime_module
from capt_ui.operator.runtime import Operator


class _FakeClient:
    def identity(self):
        return {
            "integrity": "ok",
            "headSequence": 42,
            "ledgerChainDigest": "sha256:" + "a" * 64,
        }


def _operator():
    op = Operator.__new__(Operator)
    op._client = _FakeClient()
    op._identity = {}
    op._connected = True
    return op


def test_dashboard_preserves_verifications_by_claim_and_builds_ladder(monkeypatch):
    claims = [
        {
            "claimId": "cl-a",
            "statement": "A",
            "evidenceIds": ["ev-a"],
            "verificationStatus": "verified",
            "promotionState": "accepted",
        },
        {
            "claimId": "cl-b",
            "statement": "B",
            "evidenceIds": ["ev-b"],
            "verificationStatus": "contradicted",
            "promotionState": "rejected",
        },
    ]
    verifications = {
        "cl-a": {"status": {"kind": "verified"}, "domain": "artifact", "committed": True},
        "cl-b": {"status": {"kind": "contradicted"}, "domain": "artifact", "committed": True},
    }

    monkeypatch.setattr(
        runtime_module,
        "project_authoritative_state",
        lambda client: {
            "missions": [],
            "tasks": [],
            "driverRuns": [],
            "claims": claims,
            "eventTimeline": [],
            "verificationsByClaim": verifications,
            "identity": client.identity(),
        },
    )
    monkeypatch.setattr(runtime_module, "project_approval_queue", lambda client: [])

    dashboard = _operator().dashboard()

    assert dashboard.verifications_by_claim == verifications
    assert [item["claimId"] for item in dashboard.epistemic_ladder] == ["cl-a", "cl-b"]
    assert dashboard.verification["status"]["kind"] == "claim_scoped"
    assert dashboard.verification["claimCount"] == 2
    assert "CLAIM_ACCEPTED" in dashboard.epistemic_ladder[0]["stages"]
    assert "CONTRADICTED:artifact" in dashboard.epistemic_ladder[1]["stages"]
