from pathlib import Path

import pytest

from capt_runtime.managed_skills import import_managed_skill_pack
from capt_runtime.store import EventStore
from desktop.capt_runtime_service import RuntimeQueryService


def test_managed_skills_query_is_metadata_only_and_advertised(tmp_path: Path):
    source = tmp_path / "source" / "skills" / "reviewer"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: reviewer\ndescription: Review code carefully\nversion: 1.2.3\n---\n# Reviewer\n\nInspect evidence.\n"
    )
    state = tmp_path / "state"
    state.mkdir()
    import_managed_skill_pack(tmp_path / "source", state / "skills" / "ultimate")
    store = EventStore(str(state / "runtime.db"))
    try:
        query = RuntimeQueryService(store)
        caps = query.handle({"op": "capabilities"})["result"]
        assert "managed_skills" in caps["queryOperations"]
        result = query.handle({"op": "managed_skills"})["result"]
        assert result["installed"] is True
        assert result["packName"] == "ultimate"
        assert result["skills"][0]["name"] == "reviewer"
        assert result["skills"][0]["version"] == "1.2.3"
        assert "content" not in result["skills"][0]
    finally:
        store.close()


def test_managed_skills_query_reports_absent_pack_without_fabricating(tmp_path: Path):
    store = EventStore(str(tmp_path / "runtime.db"))
    try:
        result = RuntimeQueryService(store).handle({"op": "managed_skills"})["result"]
        assert result["installed"] is False
        assert result["skills"] == []
        assert result["packRoot"].endswith("skills/ultimate")
    finally:
        store.close()


def test_runtime_skill_context_accepts_explicit_managed_skill_names(tmp_path: Path):
    from capt_runtime.authored_skills import prepare_runtime_skill_context

    source = tmp_path / "source" / "skills" / "reviewer"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: reviewer\ndescription: Review code carefully\nversion: 1.2.3\n---\n# Reviewer\n\nInspect evidence.\n"
    )
    state = tmp_path / "state"
    state.mkdir()
    import_managed_skill_pack(tmp_path / "source", state / "skills" / "ultimate")

    context, names = prepare_runtime_skill_context(
        {"objective": "review code", "managedSkillNames": ["reviewer"]},
        state_root=state,
    )

    assert names == ["reviewer"]
    assert context is not None
    assert context["trust"] == "managed_local"
    assert context["skills"][0]["name"] == "reviewer"


def test_runtime_skill_context_rejects_managed_and_authored_selection_together(tmp_path: Path):
    from capt_runtime.authored_skills import prepare_runtime_skill_context
    from capt_runtime.errors import CaptRuntimeError

    with pytest.raises(CaptRuntimeError, match="SKILL_SELECTION_CONFLICT"):
        prepare_runtime_skill_context(
            {
                "objective": "review",
                "managedSkillNames": ["reviewer"],
                "skillPackRoot": "/tmp/authored",
                "skillNames": ["reviewer"],
            },
            state_root=tmp_path,
        )


def _command(op: str, payload: dict, key: str) -> dict:
    return {
        "commandId": "cmd-" + key,
        "operatorId": "operator-test",
        "sessionId": "session-test",
        "schemaVersion": "1.0.0",
        "correlationId": "corr-" + key,
        "idempotencyKey": key,
        "timestamp": "2026-09-07T08:00:00Z",
        "op": op,
        "payload": payload,
    }


def test_managed_skill_mutation_commands_are_advertised(tmp_path: Path):
    store = EventStore(str(tmp_path / "runtime.db"))
    try:
        caps = RuntimeQueryService(store).handle({"op": "capabilities"})["result"]
        assert "install_managed_skill" in caps["commandOperations"]
        assert "create_managed_skill" in caps["commandOperations"]
    finally:
        store.close()


def test_operator_install_managed_skill_command_merges_and_is_idempotent(tmp_path: Path):
    from capt_runtime.composition import create_runtime
    from desktop.m1_command_service import RuntimeCommandService

    source = tmp_path / "incoming" / "reviewer"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: reviewer\ndescription: Review code carefully\nversion: 1.2.3\n---\n\n# Reviewer\n\nInspect evidence.\n"
    )
    runtime = create_runtime(str(tmp_path / "state" / "runtime.db"))
    try:
        svc = RuntimeCommandService(
            runtime.store, "operator-test", "session-test", runtime_service=runtime.service
        )
        command = _command(
            "install_managed_skill",
            {"sourcePath": str(tmp_path / "incoming"), "packName": "ultimate"},
            "install-reviewer",
        )
        first = svc.execute(command)
        assert first["status"] == "accepted", first
        assert first["result"]["installed"] is True
        assert first["result"]["skillNames"] == ["reviewer"]
        retry = svc.execute(command)
        assert retry["status"] == "idempotent", retry
        assert retry["result"]["manifestDigest"] == first["result"]["manifestDigest"]
        queried = RuntimeQueryService(runtime.store).handle({"op": "managed_skills"})["result"]
        assert [item["name"] for item in queried["skills"]] == ["reviewer"]
    finally:
        runtime.close()


def test_operator_create_managed_skill_command_builds_verified_skill(tmp_path: Path):
    from capt_runtime.composition import create_runtime
    from desktop.m1_command_service import RuntimeCommandService

    runtime = create_runtime(str(tmp_path / "state" / "runtime.db"))
    try:
        svc = RuntimeCommandService(
            runtime.store, "operator-test", "session-test", runtime_service=runtime.service
        )
        result = svc.execute(_command(
            "create_managed_skill",
            {
                "name": "capt-ui-review",
                "description": "Use when reviewing CAPT macOS interface changes.",
                "version": "1.0.0",
                "body": "## When to Use\n\nReview the native interface with evidence.\n",
                "packName": "ultimate",
            },
            "create-capt-ui-review",
        ))
        assert result["status"] == "accepted", result
        assert result["result"]["skillNames"] == ["capt-ui-review"]
        root = Path(result["result"]["packRoot"])
        assert (root / "skills" / "capt-ui-review" / "SKILL.md").is_file()
        queried = RuntimeQueryService(runtime.store).handle({"op": "managed_skills"})["result"]
        assert queried["skills"][0]["name"] == "capt-ui-review"
    finally:
        runtime.close()
