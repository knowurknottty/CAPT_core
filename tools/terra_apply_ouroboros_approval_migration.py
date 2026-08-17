from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}: {old[:160]!r}")
    p.write_text(text.replace(old, new, 1))


# Fifth-pass blast-radius reduction: D-06 is fixed inside the approval planner
# from the explicit outer idempotency identity.  Correlation IDs remain tracing
# identities and should not be globally redefined for every RuntimeClient op.
replace_once(
    "desktop/desktop_runtime_client.py",
    "import hashlib\nimport json\n",
    "import json\n",
)
replace_once(
    "desktop/desktop_runtime_client.py",
    '            "correlationId": "corr-" + hashlib.sha256((op + ":" + idek).encode()).hexdigest()[:24],\n',
    '            "correlationId": "corr-" + uuid.uuid4().hex,\n',
)

# Preserve the existing command-idempotency authority ordering.  A reused run
# key with a changed payload is an idempotency conflict before approval
# consumption; approval hardening must not downgrade that invariant into a
# generic authority mismatch.
replace_once(
    "desktop/m1_command_service.py",
    "from capt_runtime.errors import CaptRuntimeError\n",
    "from capt_runtime.errors import CaptRuntimeError, IdempotencyConflict\n",
)
replace_once(
    "desktop/m1_command_service.py",
    '''                p = cmd["payload"]
                approval_request_id = str(p.get("approvalRequestId", ""))
''',
    '''                p = cmd["payload"]
                run_fingerprint = commands.fingerprint(
                    "run_approved_hermes_inspection", p
                )
                prior_run_command = self.store.find_idempotent(cmd["idempotencyKey"])
                if (
                    prior_run_command is not None
                    and prior_run_command["operation_fingerprint"] != run_fingerprint
                ):
                    raise IdempotencyConflict(
                        "idempotency key %r reused with a different operation fingerprint"
                        % cmd["idempotencyKey"]
                    )
                approval_request_id = str(p.get("approvalRequestId", ""))
''',
)

# Migrate the real-process Ouroboros lifecycle suite through the new governed
# approval command path.  The tests retain their lifecycle/crash/idempotency
# assertions; only their setup now establishes durable authorization first.
replace_once(
    "tests/capt_runtime/test_ouroboros_lifecycle.py",
    '''def _state(client: RuntimeClient, prefix: str, suffix: str) -> dict:
''',
    '''def _authorize_model_run(client: RuntimeClient, payload: dict, suffix: str) -> dict:
    request = client.command(
        "request_model_prompt_approval",
        payload,
        "idem-ouro-approval-" + suffix,
    )
    assert request["status"] == "accepted", request
    planned = request["result"]
    decision = client.command(
        "submit_approval_decision",
        {"requestId": planned["requestId"], "decision": "approve"},
        "idem-ouro-approval-decision-" + suffix,
    )
    assert decision["status"] == "accepted", decision
    authoritative = client.get_state("human_approval-" + planned["requestId"])
    assert authoritative["state"] == "approved"
    assert authoritative["remainingUses"] == 1
    return {
        **payload,
        "approvalRequestId": planned["requestId"],
        "missionId": planned["missionId"],
        "taskId": planned["taskId"],
        "driverRunId": planned["driverRunId"],
    }


def _state(client: RuntimeClient, prefix: str, suffix: str) -> dict:
''',
)

replace_once(
    "tests/capt_runtime/test_ouroboros_lifecycle.py",
    '''        receipt = client.command("run_approved_hermes_inspection", _payload(repo, exe, suffix), "idem-ouro-happy")
''',
    '''        payload = _authorize_model_run(client, _payload(repo, exe, suffix), suffix)
        receipt = client.command("run_approved_hermes_inspection", payload, "idem-ouro-happy")
''',
)
replace_once(
    "tests/capt_runtime/test_ouroboros_lifecycle.py",
    '''        receipt = client.command("run_approved_hermes_inspection", _payload(repo, exe, suffix), "idem-ouro-failure")
''',
    '''        payload = _authorize_model_run(client, _payload(repo, exe, suffix), suffix)
        receipt = client.command("run_approved_hermes_inspection", payload, "idem-ouro-failure")
''',
)
replace_once(
    "tests/capt_runtime/test_ouroboros_lifecycle.py",
    '''        receipt = client.command("run_approved_hermes_inspection", _payload(repo, missing, suffix), "idem-ouro-nodispatch")
''',
    '''        payload = _authorize_model_run(client, _payload(repo, missing, suffix), suffix)
        receipt = client.command("run_approved_hermes_inspection", payload, "idem-ouro-nodispatch")
''',
)
replace_once(
    "tests/capt_runtime/test_ouroboros_lifecycle.py",
    '''    payload = _payload(repo, exe, suffix)
    try:
        first = client.command("run_approved_hermes_inspection", payload, "idem-ouro-restart")
''',
    '''    payload = _payload(repo, exe, suffix)
    try:
        payload = _authorize_model_run(client, payload, suffix)
        first = client.command("run_approved_hermes_inspection", payload, "idem-ouro-restart")
''',
)
replace_once(
    "tests/capt_runtime/test_ouroboros_lifecycle.py",
    '''        client.command("run_approved_hermes_inspection", _payload(repo, exe, suffix), "idem-ouro-projection")
''',
    '''        payload = _authorize_model_run(client, _payload(repo, exe, suffix), suffix)
        client.command("run_approved_hermes_inspection", payload, "idem-ouro-projection")
''',
)
replace_once(
    "tests/capt_runtime/test_ouroboros_lifecycle.py",
    '''        receipt = client.command("run_approved_hermes_inspection", _payload(repo, exe, suffix), "idem-ouro-indeterminate")
''',
    '''        payload = _authorize_model_run(client, _payload(repo, exe, suffix), suffix)
        receipt = client.command("run_approved_hermes_inspection", payload, "idem-ouro-indeterminate")
''',
)
replace_once(
    "tests/capt_runtime/test_ouroboros_lifecycle.py",
    '''    try:
        with pytest.raises(Exception):
            client.command("run_approved_hermes_inspection", payload, "idem-ouro-" + suffix)
''',
    '''    try:
        payload = _authorize_model_run(client, payload, suffix)
        with pytest.raises(Exception):
            client.command("run_approved_hermes_inspection", payload, "idem-ouro-" + suffix)
''',
)
replace_once(
    "tests/capt_runtime/test_ouroboros_lifecycle.py",
    '''        payload = _payload(repo, exe, suffix)
        first = client.command("run_approved_hermes_inspection", payload, "idem-ouro-durable")
''',
    '''        payload = _authorize_model_run(client, _payload(repo, exe, suffix), suffix)
        first = client.command("run_approved_hermes_inspection", payload, "idem-ouro-durable")
''',
)

print("TERRA_OUROBOROS_APPROVAL_MIGRATION_APPLIED")
