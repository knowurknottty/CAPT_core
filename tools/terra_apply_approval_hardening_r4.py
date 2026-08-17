from __future__ import annotations

import runpy
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}: {old[:140]!r}")
    p.write_text(text.replace(old, new, 1))


# Apply the full hardened implementation plus semantic retry correction.
runpy.run_path("tools/terra_apply_approval_hardening_r3.py", run_name="__main__")

# Expiry is an admission invariant.  Once a one-use admission has been durably
# consumed, the compatibility prompt-only assertion must not re-evaluate wall
# clock time and invalidate an already-authorized dispatch.
replace_once(
    "capt_runtime/services.py",
    '''        if state.get("state") not in ("approved", "consumed"):
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_NOT_APPROVED")
        if _now_rfc3339() > state.get("expiresAt", ""):
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_EXPIRED")
        if state.get("operation") != operation:
''',
    '''        if state.get("state") not in ("approved", "consumed"):
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_NOT_APPROVED")
        if state.get("operation") != operation:
''',
)

# D-02 regression: verify expiry at the consequential admission boundary rather
# than through the compatibility read-check.
replace_once(
    "tests/capt_runtime/test_prompt_approval_security.py",
    '''def test_approved_request_is_rejected_after_expiry_at_use_time(tmp_path):
    store = EventStore(str(tmp_path / "expired.db"))
    try:
        svc = RuntimeService(store)
        svc.request_human_approval(
            raw_request("approval-expired", expires_at="2026-08-16T00:00:00Z"),
            meta("cmd-expired-request", "execution_plane", "idem-expired-request"),
        )
        approve(svc, "approval-expired", decided_at="2026-08-15T00:00:01Z")
        with pytest.raises(AuthorityViolation, match="EXPIRED"):
            svc.require_approved_prompt_assembly(
                "approval-expired", DIGEST, "ModelOperatorInspection"
            )
    finally:
        store.close()
''',
    '''def test_approved_request_is_rejected_after_expiry_at_use_time(tmp_path):
    store = EventStore(str(tmp_path / "expired.db"))
    try:
        svc = RuntimeService(store)
        result = request_model_prompt_approval(
            svc,
            approval_intent(
                requestId="approval-expired",
                expiresAt="2026-08-16T00:00:00Z",
            ),
            meta(
                "cmd-expired-request",
                "human",
                "idem-expired-request",
                issued_at="2026-08-15T00:00:00Z",
            ),
        )
        approve(svc, "approval-expired", decided_at="2026-08-15T00:00:01Z")
        with pytest.raises(AuthorityViolation, match="EXPIRED"):
            svc.admit_approved_model_execution(
                "approval-expired",
                result["promptAssemblyDigest"],
                "ModelOperatorInspection",
                mission_id="m-security-1",
                task_id="t-security-1",
                driver_run_id="dr-security-1",
                resource="/tmp/security-project",
                use_id="run-expired",
                now="2026-08-17T00:00:00Z",
                metadata=meta(
                    "cmd-expired-use",
                    "execution_plane",
                    "idem-expired-use",
                    issued_at="2026-08-17T00:00:00Z",
                ),
            )
    finally:
        store.close()
''',
)

# Legacy model-operator routing tests predated mandatory approval.  Keep their
# routing/idempotency assertions but establish the durable approval first.
replace_once(
    "tests/capt_runtime/test_model_operator.py",
    '''def _envelope(op: str, payload: dict, *, operator: str = "operator-x", session: str = "sess-1") -> dict:
    return {
        "commandId": "cmd-model-1",
        "operatorId": operator,
        "sessionId": session,
        "schemaVersion": "1.0.0",
        "correlationId": "corr-model",
        "idempotencyKey": "idem-model-1",
        "timestamp": "2026-08-05T00:00:00Z",
        "op": op,
        "payload": payload,
    }
''',
    '''def _envelope(
    op: str,
    payload: dict,
    *,
    operator: str = "operator-x",
    session: str = "sess-1",
    key: str | None = None,
) -> dict:
    token = key or op
    return {
        "commandId": "cmd-" + token,
        "operatorId": operator,
        "sessionId": session,
        "schemaVersion": "1.0.0",
        "correlationId": "corr-" + token,
        "idempotencyKey": "idem-" + token,
        "timestamp": "2026-08-17T10:00:00Z",
        "op": op,
        "payload": payload,
    }


def _approved_run_payload(
    svc: RuntimeCommandService, payload: dict, key: str
) -> dict:
    request = svc.execute(
        _envelope("request_model_prompt_approval", payload, key=key + "-request")
    )
    assert request["status"] == "accepted"
    planned = request["result"]
    decision = svc.execute(
        _envelope(
            "submit_approval_decision",
            {"requestId": planned["requestId"], "decision": "approve"},
            key=key + "-decision",
        )
    )
    assert decision["status"] == "accepted"
    assert decision["result"]["state"] == "approved"
    return {
        **payload,
        "approvalRequestId": planned["requestId"],
        "missionId": planned["missionId"],
        "taskId": planned["taskId"],
        "driverRunId": planned["driverRunId"],
    }
''',
)
replace_once(
    "tests/capt_runtime/test_model_operator.py",
    '''        svc.approved_hermes_runner = stub_runner
        cmd = _envelope("run_approved_hermes_inspection",
                        {"objective": "x", "targetRoot": "/tmp"})
        first = svc.execute(cmd)
''',
    '''        svc.approved_hermes_runner = stub_runner
        payload = _approved_run_payload(
            svc, {"objective": "x", "targetRoot": "/tmp"}, "route"
        )
        cmd = _envelope(
            "run_approved_hermes_inspection", payload, key="route-run"
        )
        first = svc.execute(cmd)
''',
)
replace_once(
    "tests/capt_runtime/test_model_operator.py",
    '''        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        svc.approved_hermes_runner = lambda _cmd: {"status": "in_progress", "commandId": "cmd-model-1"}
        receipt = svc.execute(_envelope("run_approved_hermes_inspection", {"objective": "x", "targetRoot": "/tmp"}))
        assert receipt["status"] == "in_progress"
''',
    '''        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        svc.approved_hermes_runner = lambda _cmd: {"status": "in_progress", "commandId": "cmd-model-1"}
        payload = _approved_run_payload(
            svc, {"objective": "x", "targetRoot": "/tmp"}, "progress"
        )
        receipt = svc.execute(
            _envelope(
                "run_approved_hermes_inspection", payload, key="progress-run"
            )
        )
        assert receipt["status"] == "in_progress"
''',
)

print("TERRA_APPROVAL_HARDENING_R4_APPLIED")
