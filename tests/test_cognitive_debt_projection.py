"""CAPT-UPG-024 concrete cognitive-debt projection tests."""

from capt_ui.operator.cognitive_debt import project_cognitive_debt, render_cognitive_debt


def test_projection_reports_only_source_supported_debt_categories():
    state = {
        "claims": [
            {
                "claimId": "cl-required",
                "requiresVerification": True,
                "promotionState": "proposed",
            },
            {
                "claimId": "cl-contradicted",
                "promotionState": "proposed",
            },
            {
                "claimId": "cl-qualified",
                "promotionState": "qualified",
                "qualification": "limited evidence",
            },
        ],
        "verificationsByClaim": {
            "cl-required": {"status": {"kind": "not_tested"}, "committed": False},
            "cl-contradicted": {"status": {"kind": "contradicted"}, "committed": True},
            "cl-qualified": {"status": {"kind": "verified"}, "committed": True, "stale": True},
        },
        "approvals": [{"requestId": "ap-1", "state": "pending", "operation": "RepositoryWrite"}],
        "tasks": [{"taskId": "t-1", "recoveryState": "awaiting_reconciliation"}],
        "driverRuns": [{
            "driverRunId": "dr-1",
            "state": "lost",
            "reconciliationStatus": "unknown",
            "effectOccurrence": "indeterminate",
        }],
        "capabilities": [{
            "grantId": "g-1",
            "reservations": [{"reservationId": "r-1", "state": "awaiting_reconciliation"}],
        }],
        "cohorts": [{
            "cohortId": "coh-1",
            "epoch": 2,
            "contributions": [
                {"contributionId": "old", "epoch": 1, "outcome": "pass", "material": False},
                {"contributionId": "dissent", "epoch": 2, "outcome": "dissent", "material": True},
            ],
        }],
    }
    debt = project_cognitive_debt(state)
    categories = set(debt["categoryCounts"])
    assert {
        "required_claim_unverified",
        "unresolved_contradiction",
        "qualified_claim",
        "stale_verification_evidence",
        "pending_approval",
        "task_recovery_required",
        "driver_reconciliation_required",
        "unknown_external_effect",
        "capability_reconciliation_required",
        "stale_cohort_contribution",
        "unresolved_cohort_dissent",
    }.issubset(categories)
    assert debt["opaqueScalarScore"] is None
    assert debt["automaticHalt"] is False
    assert debt["absenceOfDebtProvesCorrectness"] is False


def test_absent_fields_do_not_create_invented_debt():
    debt = project_cognitive_debt({
        "claims": [{"claimId": "cl-clean", "promotionState": "accepted"}],
        "verificationsByClaim": {},
        "approvals": [],
        "tasks": [],
        "driverRuns": [],
    })
    assert debt["items"] == []
    assert debt["itemCount"] == 0
    assert debt["blockingItemCount"] == 0
    assert debt["absenceOfDebtProvesCorrectness"] is False


def test_identical_source_reason_is_deduplicated():
    state = {
        "approvals": [
            {"requestId": "ap-1", "state": "pending"},
            {"requestId": "ap-1", "state": "pending"},
        ]
    }
    debt = project_cognitive_debt(state)
    assert debt["categoryCounts"]["pending_approval"] == 1
    assert debt["itemCount"] == 1


def test_summary_exposes_concrete_categories_not_confidence_score():
    debt = project_cognitive_debt({"approvals": [{"requestId": "ap-1", "state": "pending"}]})
    text = render_cognitive_debt(debt)
    assert "pending_approval" in text
    assert "No opaque confidence score" in text
