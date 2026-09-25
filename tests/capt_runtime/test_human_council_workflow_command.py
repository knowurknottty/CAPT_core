from __future__ import annotations

from pathlib import Path

from capt_runtime.composition import create_runtime
from desktop.m1_command_service import RuntimeCommandService


def _envelope(op: str, payload: dict, key: str = "human-council-r1") -> dict:
    return {
        "commandId": "cmd-human-council-r1",
        "operatorId": "operator-human",
        "sessionId": "sess-human",
        "schemaVersion": "1.0.0",
        "correlationId": "corr-human-council-r1",
        "idempotencyKey": key,
        "timestamp": "2026-09-25T16:00:00Z",
        "op": op,
        "payload": payload,
    }


class _CouncilHarness(RuntimeCommandService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subcalls = []

    def execute(self, cmd):
        if cmd.get("op") == "run_approved_hermes_inspection":
            payload = dict(cmd["payload"])
            self.subcalls.append(payload)
            return {
                "status": "accepted",
                "classification": "accepted",
                "result": {
                    "driverRunId": payload["driverRunId"],
                    "cohortSpec": payload["cohortSpec"],
                    "provider": payload["provider"],
                    "model": payload["model"],
                },
            }
        return super().execute(cmd)


def _execution(root: Path, cohort: str, model: str) -> dict:
    return {
        "objective": "Inspect, integrate, test, and report.",
        "targetRoot": str(root),
        "provider": "openrouter",
        "model": model,
        "missionId": "m-human-parity",
        "taskId": "t-human-" + cohort,
        "driverRunId": "dr-human-" + cohort,
        "approvalRequestId": "approval-" + cohort,
        "requestedContextBudget": 128000,
        "requestedExecutionSeconds": 1800,
        "humanVerificationRequired": True,
        "responseMode": "SPOCK",
        "promptEnhancement": "OFF",
        "cohortSpec": {
            "cohortId": cohort,
            "vesselsPerCohort": 11,
            "configurationId": "human-parity-r1",
            "vesselCharterPolicy": {"schemaVersion": "2.0.0"},
        },
        "authorityProfile": {
            "filesystemScope": "project",
            "filesystemRoot": str(root),
            "fileMutationAllowed": True,
            "shellAccessAllowed": True,
            "providerNetworkPolicy": "remote_allowed",
        },
    }


def test_human_configured_three_by_eleven_scheduler_is_exact_and_sequential(tmp_path):
    runtime = create_runtime(str(tmp_path / "runtime.db"))
    try:
        svc = _CouncilHarness(
            runtime.store,
            "operator-human",
            "sess-human",
            runtime_service=runtime.service,
        )
        executions = [
            _execution(tmp_path, "qwen38-flash", "qwen/qwen3.8-flash"),
            _execution(tmp_path, "mimo26-flash", "xiaomi/mimo-v2.6-flash"),
            _execution(tmp_path, "glm53-flash", "z-ai/glm-5.3-flash"),
        ]
        receipt = svc.execute(_envelope(
            "run_approved_council_inspection",
            {
                "councilId": "council-human-parity",
                "maxConcurrentCohorts": 1,
                "executions": executions,
            },
        ))
        assert receipt["status"] == "accepted"
        result = receipt["result"]
        assert result["cohortCount"] == 3
        assert result["vesselsPerCohort"] == 11
        assert result["logicalVessels"] == 33
        assert result["maxConcurrentCohorts"] == 1
        assert result["peakConcurrentCohortExecutions"] == 1
        assert result["providerCallInvariant"] == "one_call_per_cohort"
        assert len(svc.subcalls) == 3
        assert [x["model"] for x in svc.subcalls] == [
            "qwen/qwen3.8-flash",
            "xiaomi/mimo-v2.6-flash",
            "z-ai/glm-5.3-flash",
        ]
    finally:
        runtime.close()
