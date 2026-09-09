import time

from capt_runtime.prompt_compiler import BoundedPromptCompilerRunner, CompilerProvider, PromptCompiler
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from desktop.capt_runtime_service import RuntimeQueryService
from desktop.m1_command_service import RuntimeCommandService
from desktop.operator_control import OperatorControlStore


def _cmd(op: str, payload: dict, cid: str) -> dict:
    return {
        "commandId": cid,
        "operatorId": "operator",
        "sessionId": "session",
        "schemaVersion": "1.0.0",
        "correlationId": "corr-" + cid,
        "idempotencyKey": "idem-" + cid,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "op": op,
        "payload": payload,
    }


def _compiler() -> PromptCompiler:
    return PromptCompiler(
        runner=BoundedPromptCompilerRunner(lambda payload: {
            "stage": payload["stage"], "outcome": "enhanced", "scope": "prompt",
            "inputs": [], "outputs": ["x"], "constraints": [],
            "successCriteria": ["exact"], "ambiguities": [], "requestedCapabilities": [],
        }),
        provider=CompilerProvider("mtplx", "qwen", "local"),
    )

def _harness(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    store = EventStore(str(tmp_path / "runtime.db"))
    control = OperatorControlStore(tmp_path / "operator-control.json", {
        "provider": "ollama", "model": "qwen3.5-defiant-fable:latest",
        "targetRoot": str(root), "promptIntelligence": "AUTO",
    })
    relay = RuntimeCommandService(
        store, "operator", "session", runtime_service=RuntimeService(store),
        prompt_compiler=_compiler(), operator_control=control,
    )
    query = RuntimeQueryService(store, operator_control=control)
    return root, store, control, relay, query


def test_capabilities_advertise_operator_control_surface(tmp_path):
    _root, store, _control, _relay, query = _harness(tmp_path)
    caps = query.handle({"op": "capabilities"})["result"]
    assert "operator_control_snapshot" in caps["queryOperations"]
    assert "operator_prompt_submit" in caps["commandOperations"]
    assert "operator_proposal_select" in caps["commandOperations"]
    store.close()


def test_operator_prompt_submit_uses_exact_effective_configuration(tmp_path):
    root, store, _control, relay, query = _harness(tmp_path)
    chat = relay.execute(_cmd("operator_chat_new", {"expectedRevision": 0}, "chat"))["result"]
    cfg = relay.execute(_cmd("operator_execution_config_set", {
        "expectedRevision": chat["revision"],
        "targetRoot": str(root), "provider": "ollama",
        "model": "qwen3.5-defiant-fable:latest", "promptIntelligence": "OFF",
    }, "cfg"))["result"]
    submitted = relay.execute(_cmd("operator_prompt_submit", {
        "text": "Return exactly MCP_CONTROL_GOLDEN and no other text.",
        "controlRevision": cfg["revision"],
        "configurationDigest": cfg["configurationDigest"],
    }, "submit"))
    assert submitted["status"] == "accepted"
    proposal = submitted["result"]["proposal"]
    control = submitted["result"]["control"]
    assert proposal["targetRoot"] == str(root)
    assert proposal["provider"] == "ollama"
    assert proposal["model"] == "qwen3.5-defiant-fable:latest"
    assert proposal["stageChain"] == []
    assert proposal["stageRecords"] == []
    assert proposal["proposedPrompt"] == proposal["originalPrompt"]
    assert control["proposalId"] == proposal["proposalId"]
    projected = query.handle({"op": "operator_proposal_get"})["result"]
    assert projected["configurationDigest"] == cfg["configurationDigest"]
    assert projected["proposal"]["proposalId"] == proposal["proposalId"]
    store.close()


def test_operator_proposal_select_binds_original_and_approval_scope(tmp_path):
    root, store, _control, relay, _query = _harness(tmp_path)
    chat = relay.execute(_cmd("operator_chat_new", {"expectedRevision": 0}, "chat2"))["result"]
    cfg = relay.execute(_cmd("operator_execution_config_set", {
        "expectedRevision": chat["revision"], "promptIntelligence": "OFF",
    }, "cfg2"))["result"]
    submitted = relay.execute(_cmd("operator_prompt_submit", {
        "text": "Return exactly CONTROL_APPROVAL_GOLDEN and no other text.",
        "controlRevision": cfg["revision"],
        "configurationDigest": cfg["configurationDigest"],
    }, "submit2"))["result"]
    control = submitted["control"]
    proposal = submitted["proposal"]
    selected = relay.execute(_cmd("operator_proposal_select", {
        "proposalId": proposal["proposalId"], "basis": "original",
        "controlRevision": control["revision"],
        "configurationDigest": control["configurationDigest"],
    }, "select2"))
    assert selected["status"] == "accepted"
    approval = selected["result"]["approval"]
    bound = selected["result"]["control"]
    assert bound["proposalSelection"] == "original"
    assert bound["approvalRequestId"] == approval["requestId"]
    state = store.require_state("human_approval-" + approval["requestId"])
    assert state["scope"]["rootPath"] == str(root)
    assert state["scope"]["approvalBinding"]["selectedPromptKind"] == "original"
    assert state["scope"]["approvalBinding"]["authorityProfile"]["filesystemRoot"] == str(root)
    store.close()


def test_stale_control_revision_rejects_prompt_before_proposal_creation(tmp_path):
    _root, store, _control, relay, _query = _harness(tmp_path)
    chat = relay.execute(_cmd("operator_chat_new", {"expectedRevision": 0}, "chat3"))["result"]
    cfg = relay.execute(_cmd("operator_execution_config_set", {
        "expectedRevision": chat["revision"], "promptIntelligence": "OFF",
    }, "cfg3"))["result"]
    _winner = relay.execute(_cmd("operator_execution_config_set", {
        "expectedRevision": cfg["revision"], "promptIntelligence": "AUTO",
    }, "cfg4"))["result"]
    before = len([x for x in store.all_aggregates() if x[1] == "prompt_proposal"])
    rejected = relay.execute(_cmd("operator_prompt_submit", {
        "text": "must not compile", "controlRevision": cfg["revision"],
        "configurationDigest": cfg["configurationDigest"],
    }, "stale"))
    after = len([x for x in store.all_aggregates() if x[1] == "prompt_proposal"])
    assert rejected["status"] == "rejected"
    assert rejected["error"]["code"] == "E_OPERATOR_CONTROL_STALE"
    assert after == before
    store.close()
