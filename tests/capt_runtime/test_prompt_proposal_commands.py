from __future__ import annotations

import time

import pytest

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



def test_execution_binding_is_recovered_from_authoritative_approval(tmp_path):
    from capt_runtime.prompt_proposals import authoritative_proposal_binding_for_execution

    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("provider selection\n")
    store = EventStore(str(tmp_path / "ledger.db"))
    relay = RuntimeCommandService(
        store, "operator", "session", runtime_service=RuntimeService(store),
        prompt_compiler=_compiler(),
    )
    proposal = relay.execute(
        _cmd("compile_prompt_proposal", _compile_payload(str(root)), "compile-bind")
    )["result"]
    approval = relay.execute(_cmd("request_prompt_proposal_approval", {
        "proposalId": proposal["proposalId"],
        "proposalRevision": proposal["revision"],
        "selection": "upgrade",
    }, "approve-bind"))["result"]

    binding = authoritative_proposal_binding_for_execution(
        store, approval["requestId"], proposal["proposedPrompt"]
    )
    assert binding["proposalId"] == proposal["proposalId"]
    assert binding["proposalRevision"] == proposal["revision"]
    assert binding["selectedPromptKind"] == "upgrade"
    assert binding["selectedPromptDigest"] == proposal["proposedPromptDigest"]
    store.close()


def test_execution_binding_rejects_tampered_selected_prompt(tmp_path):
    from capt_runtime.prompt_proposals import authoritative_proposal_binding_for_execution

    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("provider selection\n")
    store = EventStore(str(tmp_path / "ledger.db"))
    relay = RuntimeCommandService(
        store, "operator", "session", runtime_service=RuntimeService(store),
        prompt_compiler=_compiler(),
    )
    proposal = relay.execute(
        _cmd("compile_prompt_proposal", _compile_payload(str(root)), "compile-tamper")
    )["result"]
    approval = relay.execute(_cmd("request_prompt_proposal_approval", {
        "proposalId": proposal["proposalId"],
        "proposalRevision": proposal["revision"],
        "selection": "upgrade",
    }, "approve-tamper"))["result"]

    with pytest.raises(Exception, match="SELECTED_PROMPT"):
        authoritative_proposal_binding_for_execution(
            store, approval["requestId"], proposal["proposedPrompt"] + "\nTAMPERED"
        )
    store.close()


def test_execution_binding_rejects_revised_proposal_after_approval(tmp_path):
    from capt_runtime.prompt_proposals import authoritative_proposal_binding_for_execution

    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("provider selection\n")
    store = EventStore(str(tmp_path / "ledger.db"))
    relay = RuntimeCommandService(
        store, "operator", "session", runtime_service=RuntimeService(store),
        prompt_compiler=_compiler(),
    )
    proposal = relay.execute(
        _cmd("compile_prompt_proposal", _compile_payload(str(root)), "compile-revise-exec")
    )["result"]
    approval = relay.execute(_cmd("request_prompt_proposal_approval", {
        "proposalId": proposal["proposalId"],
        "proposalRevision": proposal["revision"],
        "selection": "upgrade",
    }, "approve-revise-exec"))["result"]
    revised = relay.execute(_cmd("revise_prompt_proposal", {
        "proposalId": proposal["proposalId"],
        "proposedPrompt": proposal["proposedPrompt"] + "\nNew revision.",
    }, "revise-after-approval"))
    assert revised["status"] == "accepted"

    with pytest.raises(Exception, match="REVISION"):
        authoritative_proposal_binding_for_execution(
            store, approval["requestId"], proposal["proposedPrompt"]
        )
    store.close()


def test_execution_binding_rejects_cancelled_proposal_after_approval(tmp_path):
    from capt_runtime.prompt_proposals import authoritative_proposal_binding_for_execution

    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("provider selection\n")
    store = EventStore(str(tmp_path / "ledger.db"))
    relay = RuntimeCommandService(
        store, "operator", "session", runtime_service=RuntimeService(store),
        prompt_compiler=_compiler(),
    )
    proposal = relay.execute(
        _cmd("compile_prompt_proposal", _compile_payload(str(root)), "compile-cancel-exec")
    )["result"]
    approval = relay.execute(_cmd("request_prompt_proposal_approval", {
        "proposalId": proposal["proposalId"],
        "proposalRevision": proposal["revision"],
        "selection": "upgrade",
    }, "approve-cancel-exec"))["result"]
    cancelled = relay.execute(_cmd("cancel_prompt_proposal", {
        "proposalId": proposal["proposalId"], "reason": "Operator revoked proposal."
    }, "cancel-after-approval"))
    assert cancelled["status"] == "accepted"

    with pytest.raises(Exception, match="NOT_ACTIVE"):
        authoritative_proposal_binding_for_execution(
            store, approval["requestId"], proposal["proposedPrompt"]
        )
    store.close()


def test_execution_binding_rejects_original_prompt_digest_corruption(tmp_path):
    from capt_runtime.prompt_proposals import authoritative_proposal_binding_for_execution

    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("provider selection\n")
    store = EventStore(str(tmp_path / "ledger.db"))
    relay = RuntimeCommandService(
        store, "operator", "session", runtime_service=RuntimeService(store),
        prompt_compiler=_compiler(),
    )
    proposal = relay.execute(
        _cmd("compile_prompt_proposal", _compile_payload(str(root)), "compile-origin-corrupt")
    )["result"]
    approval = relay.execute(_cmd("request_prompt_proposal_approval", {
        "proposalId": proposal["proposalId"],
        "proposalRevision": proposal["revision"],
        "selection": "upgrade",
    }, "approve-origin-corrupt"))["result"]

    class CorruptProposalStore:
        def require_state(self, stream_id):
            state = store.require_state(stream_id)
            if stream_id.startswith("prompt_proposal-"):
                state = dict(state)
                state["originalPromptDigest"] = "sha256:" + "0" * 64
            return state

    with pytest.raises(Exception, match="ORIGINAL_DIGEST"):
        authoritative_proposal_binding_for_execution(
            CorruptProposalStore(), approval["requestId"], proposal["proposedPrompt"]
        )
    store.close()


def test_execution_binding_rejects_proposal_snapshot_corruption(tmp_path):
    from capt_runtime.prompt_proposals import authoritative_proposal_binding_for_execution

    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("provider selection\n")
    store = EventStore(str(tmp_path / "ledger.db"))
    relay = RuntimeCommandService(
        store, "operator", "session", runtime_service=RuntimeService(store),
        prompt_compiler=_compiler(),
    )
    proposal = relay.execute(
        _cmd("compile_prompt_proposal", _compile_payload(str(root)), "compile-snapshot-corrupt")
    )["result"]
    approval = relay.execute(_cmd("request_prompt_proposal_approval", {
        "proposalId": proposal["proposalId"],
        "proposalRevision": proposal["revision"],
        "selection": "upgrade",
    }, "approve-snapshot-corrupt"))["result"]

    class CorruptProposalStore:
        def require_state(self, stream_id):
            state = store.require_state(stream_id)
            if stream_id.startswith("prompt_proposal-"):
                state = dict(state)
                state["targetRoot"] = state["targetRoot"] + "/corrupt"
            return state

    with pytest.raises(Exception, match="SNAPSHOT"):
        authoritative_proposal_binding_for_execution(
            CorruptProposalStore(), approval["requestId"], proposal["proposedPrompt"]
        )
    store.close()
