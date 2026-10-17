
from capt_runtime.mission_steward import (
    MODE_READ_ONLY_DIAGNOSIS,
    READ_ONLY_QUERY_OPS,
    build_decision_report,
    build_steward_bot_manifest,
    classify_mission,
    fetch_inventory,
)


class FakeClient:
    def __init__(self, data):
        self.data = data
        self.ops = []

    def query(self, op, payload=None):
        assert op in READ_ONLY_QUERY_OPS
        self.ops.append(op)
        return self.data[op]

    def command(self, *args, **kwargs):  # must never be used by the steward
        raise AssertionError("read-only steward attempted a command")


def mission(mid, state="authorized", spec=None):
    return {"missionId": mid, "state": state, "spec": spec or {}, "createdAt": "2026-10-01T00:00:00Z"}


def test_completed_driver_run_awaiting_verification_is_verify_not_replay():
    row = classify_mission(
        mission("m-model-38d83d663de535e73d0703f9", spec={"objective": "run model"}),
        [{"missionId": "m-model-38d83d663de535e73d0703f9", "state": "awaiting_verification", "title": "t"}],
        [{"missionId": "m-model-38d83d663de535e73d0703f9", "state": "consumed"}],
        [{"missionId": "m-model-38d83d663de535e73d0703f9", "status": "completed", "reconciliationStatus": "not_required"}],
    )
    assert row["disposition"] == "VERIFY"
    assert row["storedState"] == "authorized"  # stored state never reinterpreted


def test_lost_driver_run_is_investigate_never_blind_retry():
    row = classify_mission(
        mission("m-lost"),
        [{"missionId": "m-lost", "state": "pending"}],
        [],
        [{"missionId": "m-lost", "status": "lost", "reconciliationStatus": "required"}],
    )
    assert row["disposition"] == "INVESTIGATE"
    assert "never blind-retried" in row["reason"]


def test_pending_without_runs_is_run_but_terminal_completed_retains():
    row = classify_mission(mission("m-new"), [{"missionId": "m-new", "state": "pending"}], [], [])
    assert row["disposition"] == "RUN"
    done = classify_mission(mission("m-done", state="completed"), [], [], [])
    assert done["disposition"] == "RETAIN"


def test_manifest_is_registration_payload_ready():
    manifest = build_steward_bot_manifest()
    assert "createdBy" not in manifest and "createdAt" not in manifest
    assert manifest["botId"] == "capt-mission-steward"
    assert manifest["collaboration"] == {"mayDelegate": False, "maxSpawnDepth": 0}
    assert manifest["cognitionPolicy"] == {"promotionMode": "locked"}


def test_fetch_inventory_and_report_are_read_only():
    client = FakeClient({
        "list_aggregates": [
            {"kind": "mission", "streamId": "mission-m1"},
            {"kind": "driverrun", "streamId": "driverrun-r1"},
        ],
        "missions": {"missions": [mission("m1", spec={"objective": "x"})], "count": 1},
        "tasks": {"tasks": [{"missionId": "m1", "state": "awaiting_verification", "title": "t"}], "count": 1},
        "approvals": {"approvals": [], "count": 0},
        "bots": {"bots": [], "count": 0},
        "get_state": {"missionId": "m1", "status": "completed", "reconciliationStatus": "not_required"},
    })
    inventory = fetch_inventory(client)
    report = build_decision_report(inventory)
    assert report["mode"] == MODE_READ_ONLY_DIAGNOSIS
    assert report["totalMissions"] == 1
    assert report["byDisposition"] == {"VERIFY": 1}
