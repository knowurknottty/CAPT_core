"""Created DriverRuns with HTTP boundaries must survive restart as unknown outcomes."""
from types import SimpleNamespace
from desktop.capt_runtime_service import _reconcile_stranded_driver_runs


class Store:
    def __init__(self, boundary):
        self.run = {
            "driverRunId": "dr-unknown",
            "taskId": "t-unknown", "missionId": "m-unknown",
            "state": "created", "dispatchBoundary": boundary,
        }
    def all_aggregates(self):
        return [("driverrun-dr-unknown", "driverrun", 2)]
    def load_state(self, stream_id):
        return self.run if stream_id == "driverrun-dr-unknown" else None


class Service:
    def __init__(self):
        self.transitions = []
    def transition_driver_run(self, *args):
        self.transitions.append(args)
    def transition_task(self, *args):
        raise AssertionError("no linked task; must not invent one")


def test_restart_preserves_request_started_and_later_boundaries_without_replay():
    for boundary in ("request_started", "response_started", "response_completed",
                     "result_persisted", "unknown", None):
        svc = Service()
        _reconcile_stranded_driver_runs(
            SimpleNamespace(store=Store(boundary), service=svc),
            "2026-10-18T15:00:00Z",
        )
        assert svc.transitions == [], boundary


def test_restart_can_fail_created_run_only_if_proven_pre_dispatch():
    for boundary in ("not_dispatched", "prepared", "budget_rejected"):
        svc = Service()
        _reconcile_stranded_driver_runs(
            SimpleNamespace(store=Store(boundary), service=svc),
            "2026-10-18T15:00:00Z",
        )
        assert len(svc.transitions) == 1, boundary
        assert svc.transitions[0][0:2] == ("dr-unknown", "failed")
