"""CAPT-UPG-015 read-only capability lease inspector tests."""

from capt_ui.operator.leases import project_capability_lease, render_capability_leases


def _state():
    return {
        "grantId": "g-1",
        "grantState": "leased",
        "capabilityId": "cap.fs.read",
        "subjectActorId": "exec-1",
        "operations": ["repository.read", "filesystem.read"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/project", "recursive": True},
        "maxUses": 5,
        "usesConsumed": 2,
        "validFrom": "2026-08-18T00:00:00Z",
        "validUntil": "2026-08-19T00:00:00Z",
        "lease": {
            "leaseId": "l-1",
            "missionId": "m-1",
            "taskId": "t-1",
            "executionContextId": "ec-1",
            "operations": ["repository.read"],
            "scope": {"kind": "filesystem", "rootPath": "/tmp/project", "recursive": False},
            "maxUses": 4,
            "validFrom": "2026-08-18T00:00:00Z",
            "validUntil": "2026-08-18T12:00:00Z",
            "state": "active",
        },
        "reservations": [
            {"reservationId": "r-open", "state": "open"},
            {"reservationId": "r-unknown", "state": "awaiting_reconciliation"},
            {"reservationId": "r-done", "state": "finalized"},
        ],
        "consumptions": [{"consumptionId": "c-1"}, {"consumptionId": "c-2"}],
        "revocation": None,
    }


def test_projection_reports_effective_lease_budget_and_reconciliation_debt():
    row = project_capability_lease(_state(), now="2026-08-18T06:00:00Z")
    assert row["grantId"] == "g-1"
    assert row["leaseId"] == "l-1"
    assert row["maxUses"] == 4
    assert row["usesConsumed"] == 2
    assert row["remainingUses"] == 2
    assert row["temporalProjection"] == "within_validity_window"
    assert [r["reservationId"] for r in row["openReservations"]] == ["r-open"]
    assert [r["reservationId"] for r in row["reconciliationRequiredReservations"]] == ["r-unknown"]
    assert row["authority"] == "projection_only"


def test_projection_marks_revocation_without_inventing_authority():
    state = _state()
    state["grantState"] = "revoked"
    state["lease"]["state"] = "revoked"
    state["revocation"] = {"revocationId": "rev-1", "targetKind": "lease", "targetId": "l-1", "reason": "operator emergency stop", "revokedBy": "captain"}
    row = project_capability_lease(state)
    assert row["revoked"] is True
    assert row["leaseState"] == "revoked"
    text = render_capability_leases([row])
    assert "REVOKED: operator emergency stop" in text
    assert "projection" in text


def test_temporal_projection_is_not_expiration_authority():
    row = project_capability_lease(_state(), now="2026-08-20T00:00:00Z")
    assert row["temporalProjection"] == "expired_by_clock"
    assert row["grantState"] == "leased"
