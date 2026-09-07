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
