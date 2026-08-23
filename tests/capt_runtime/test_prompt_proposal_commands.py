from __future__ import annotations

import time

from capt_runtime.prompt_compiler import (
    BoundedPromptCompilerRunner,
    CompilerProvider,
    PromptCompiler,
)
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from desktop.m1_command_service import RuntimeCommandService


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
    def transport(payload):
        return {
            "stage": payload["stage"],
            "outcome": "produce a tested repository change",
            "scope": "approved target repository",
            "inputs": ["literal operator prompt"],
            "outputs": ["tested implementation"],
            "constraints": ["preserve CAPT authority"],
            "successCriteria": ["focused tests pass"],
            "ambiguities": [],
            "requestedCapabilities": [],
        }
    return PromptCompiler(
        runner=BoundedPromptCompilerRunner(transport),
        provider=CompilerProvider("mtplx", "qwen3.8-27b-mtplx", "local"),
    )


def _compile_payload(root: str) -> dict:
    return {
        "originalPrompt": "Implement and test the provider selection fix.",
        "targetRoot": root,
        "promptIntelligence": "AUTO",
        "mode": "normal",
        "provider": "mtplx",
        "model": "qwen3.8-27b-mtplx",
        "requestedContextBudget": 64000,
        "requestedCapabilities": ["cap.fs.read"],
    }


def test_compile_creates_durable_proposal_without_human_approval(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("provider selection\n")
    store = EventStore(str(tmp_path / "ledger.db"))
    relay = RuntimeCommandService(store, "operator", "session", runtime_service=RuntimeService(store), prompt_compiler=_compiler())

    receipt = relay.execute(_cmd("compile_prompt_proposal", _compile_payload(str(root)), "compile-1"))

    assert receipt["status"] == "accepted"
    result = receipt["result"]
    assert result["proposalId"]
    assert result["originalPrompt"] == _compile_payload(str(root))["originalPrompt"]
    assert result["proposedPrompt"] != result["originalPrompt"]
    assert result["stageChain"] == ["OMNI", "META", "FORGE", "SIGMA"]
    assert store.require_state("prompt_proposal-" + result["proposalId"])["revision"] == 0
    assert all(kind != "human_approval" for _, kind, _ in store.all_aggregates())
    store.close()


def test_upgrade_original_and_edited_selections_bind_distinct_prompt_identity(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("provider selection\n")
    store = EventStore(str(tmp_path / "ledger.db"))
    relay = RuntimeCommandService(store, "operator", "session", runtime_service=RuntimeService(store), prompt_compiler=_compiler())
    proposal = relay.execute(_cmd("compile_prompt_proposal", _compile_payload(str(root)), "compile-2"))["result"]

    base = {
        "proposalId": proposal["proposalId"],
        "proposalRevision": proposal["revision"],
        "responseMode": "SPOCK",
        "humanVerificationRequired": True,
    }
    upgrade = relay.execute(_cmd("request_prompt_proposal_approval", {**base, "selection": "upgrade"}, "approve-upgrade"))["result"]
    original = relay.execute(_cmd("request_prompt_proposal_approval", {**base, "selection": "original"}, "approve-original"))["result"]
    edited = relay.execute(_cmd("request_prompt_proposal_approval", {**base, "selection": "edited", "editedPrompt": proposal["proposedPrompt"] + "\nOnly change the provider state layer."}, "approve-edited"))["result"]

    assert len({upgrade["promptAssemblyDigest"], original["promptAssemblyDigest"], edited["promptAssemblyDigest"]}) == 3
    for receipt, kind in ((upgrade, "upgrade"), (original, "original"), (edited, "edited")):
        state = store.require_state("human_approval-" + receipt["requestId"])
        binding = state["scope"]["approvalBinding"]
        assert binding["proposalId"] == proposal["proposalId"]
        assert binding["proposalRevision"] == 0
        assert binding["selectedPromptKind"] == kind
        assert binding["originalHumanPromptDigest"] == proposal["originalPromptDigest"]
        assert binding["selectedPromptDigest"] == receipt["selectedPromptDigest"]
    store.close()


def test_revision_invalidates_old_proposal_version_for_new_approval(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("provider selection\n")
    store = EventStore(str(tmp_path / "ledger.db"))
    relay = RuntimeCommandService(store, "operator", "session", runtime_service=RuntimeService(store), prompt_compiler=_compiler())
    proposal = relay.execute(_cmd("compile_prompt_proposal", _compile_payload(str(root)), "compile-3"))["result"]

    revised = relay.execute(_cmd("revise_prompt_proposal", {
        "proposalId": proposal["proposalId"],
        "proposedPrompt": proposal["proposedPrompt"] + "\nPreserve session isolation.",
    }, "revise-3"))
    assert revised["status"] == "accepted"
    assert revised["result"]["revision"] == 1

    stale = relay.execute(_cmd("request_prompt_proposal_approval", {
        "proposalId": proposal["proposalId"],
        "proposalRevision": 0,
        "selection": "upgrade",
    }, "approve-stale"))
    assert stale["status"] == "rejected"
    assert "REVISION" in (stale.get("detail") or stale.get("error", {}).get("code", "")).upper()
    store.close()
