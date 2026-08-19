import hashlib
import os
from pathlib import Path

import pytest

from capt_lab.contracts import LabEngineRequest, LabInputError
from capt_lab.engines.forge import ForgeLimits, analyze_repository, execute_forge
from capt_lab.registry import build_default_registry


def req(operation, value):
    return LabEngineRequest.from_mapping({
        "engineId": "lab.forge", "operation": operation, "input": value,
        "missionId": "m-f", "taskId": "m-f-task-1",
    })


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*"), key=lambda x: str(x.relative_to(root))):
        rel = str(p.relative_to(root))
        h.update(rel.encode())
        if p.is_symlink():
            h.update(b"SYMLINK")
            h.update(os.readlink(p).encode())
        elif p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


def fixture_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# Demo\nRequirements:\n- preserve audit trail\n", encoding="utf-8")
    (root / "app.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    (root / "test_app.py").write_text("def test_run():\n    assert True\n", encoding="utf-8")
    (root / ".env").write_text("OPENROUTER_API_KEY=super-secret-value\n", encoding="utf-8")
    (root / "id_rsa").write_text("-----BEGIN PRIVATE KEY-----\nSECRET\n", encoding="utf-8")
    (root / "blob.bin").write_bytes(b"\x00\x01\x02SECRET-BINARY")
    ignored = root / "node_modules"
    ignored.mkdir()
    (ignored / "dep.js").write_text("const password='nope';", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("OUTSIDE-SYMLINK-SECRET", encoding="utf-8")
    (root / "escape.txt").symlink_to(outside)
    return root, outside


def test_repository_archaeology_is_read_only_bounded_and_secret_safe(tmp_path):
    root, outside = fixture_repo(tmp_path)
    before = tree_digest(root)
    result = analyze_repository(root, ForgeLimits(max_files=16, max_total_bytes=65536, max_depth=4, max_file_bytes=8192))
    after = tree_digest(root)
    assert before == after
    assert result["fileCount"] == 3
    assert set(result["files"]) == {"README.md", "app.py", "test_app.py"}
    joined = repr(result)
    assert "super-secret-value" not in joined
    assert "PRIVATE KEY" not in joined
    assert "OUTSIDE-SYMLINK-SECRET" not in joined
    assert "SECRET-BINARY" not in joined
    assert ".env" in result["excluded"]
    assert "id_rsa" in result["excluded"]
    assert "blob.bin" in result["excluded"]
    assert "node_modules" in result["excluded"]
    assert "escape.txt" in result["excluded"]


def test_repository_archaeology_rejects_noncanonical_or_symlink_root(tmp_path):
    root, _ = fixture_repo(tmp_path)
    with pytest.raises(LabInputError, match="canonical"):
        analyze_repository(Path(str(root / ".." / "repo")), ForgeLimits())
    link = tmp_path / "repo-link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(LabInputError, match="symlink"):
        analyze_repository(link, ForgeLimits())


def test_repository_archaeology_enforces_file_and_byte_limits(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for i in range(5):
        (root / f"f{i}.txt").write_text("x" * 100, encoding="utf-8")
    result = analyze_repository(root, ForgeLimits(max_files=2, max_total_bytes=150, max_depth=2, max_file_bytes=100))
    assert result["fileCount"] <= 2
    assert result["bytesRead"] <= 150
    assert result["truncated"] is True


def test_gap_analysis_reports_documented_expectation_without_inventing_completion(tmp_path):
    root, _ = fixture_repo(tmp_path)
    out = execute_forge(req("gap_analysis", {
        "root": str(root),
        "expectations": ["preserve audit trail", "implement quantum banana reactor"],
    }), {})
    assert out.epistemic_class == "advisory"
    gaps = out.observation["gaps"]
    assert [g["expectation"] for g in gaps] == ["implement quantum banana reactor", "preserve audit trail"]
    assert all(g["status"] in {"text_match_found", "not_observed"} for g in gaps)
    assert "implemented" not in {g["status"] for g in gaps}


def test_gap_analysis_distinguishes_related_text_from_zero_evidence(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text(
        "CAPT preserves a durable audit trail for every governed driver run.\n",
        encoding="utf-8",
    )
    out = execute_forge(req("gap_analysis", {
        "root": str(root),
        "expectations": ["preserve durable audit trail", "quantum banana reactor"],
    }), {})
    gaps = {item["expectation"]: item for item in out.observation["gaps"]}
    related = gaps["preserve durable audit trail"]
    absent = gaps["quantum banana reactor"]
    assert related["status"] == "related_text_found"
    assert related["tokenCoverage"] == 1.0
    assert related["observedPaths"] == ["README.md"]
    assert absent["status"] == "not_observed"
    assert absent["tokenCoverage"] == 0.0
    assert absent["observedPaths"] == []
    assert out.observation["notObservedCount"] == 1


def test_gap_analysis_uses_whole_tokens_not_substring_matches(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text(
        "durable auditing trailer notes\n",
        encoding="utf-8",
    )
    out = execute_forge(req("gap_analysis", {
        "root": str(root),
        "expectations": ["durable audit trail"],
    }), {})
    gap = out.observation["gaps"][0]
    assert gap["status"] == "partial_text_evidence"
    assert gap["tokenCoverage"] == pytest.approx(1 / 3)
    assert gap["observedPaths"] == []


def test_gap_analysis_ignores_nonsemantic_stopword_only_overlap(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("the unrelated notes exist\n", encoding="utf-8")
    out = execute_forge(req("gap_analysis", {
        "root": str(root),
        "expectations": ["the quantum banana reactor"],
    }), {})
    gap = out.observation["gaps"][0]
    assert gap["status"] == "not_observed"
    assert gap["tokenCoverage"] == 0.0
    assert gap["observedPaths"] == []


def test_gap_analysis_matches_simple_inflections_symmetrically(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("preserve durable audit trail\n", encoding="utf-8")
    out = execute_forge(req("gap_analysis", {
        "root": str(root),
        "expectations": ["preserves durable audits trail"],
    }), {})
    gap = out.observation["gaps"][0]
    assert gap["status"] == "related_text_found"
    assert gap["tokenCoverage"] == 1.0
    assert gap["observedPaths"] == ["README.md"]


def test_gap_analysis_does_not_treat_short_lexemes_as_inflections(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("news audit\n", encoding="utf-8")
    out = execute_forge(req("gap_analysis", {
        "root": str(root),
        "expectations": ["new audit"],
    }), {})
    gap = out.observation["gaps"][0]
    assert gap["status"] == "partial_text_evidence"
    assert gap["tokenCoverage"] == 0.5
    assert gap["observedPaths"] == []


def test_gap_analysis_reports_partial_cross_repository_text_evidence(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.md").write_text("durable audit records\n", encoding="utf-8")
    (root / "b.md").write_text("trail recovery notes\n", encoding="utf-8")
    out = execute_forge(req("gap_analysis", {
        "root": str(root),
        "expectations": ["preserve durable audit trail"],
    }), {})
    gap = out.observation["gaps"][0]
    assert gap["status"] == "partial_text_evidence"
    assert 0.0 < gap["tokenCoverage"] < 1.0
    assert gap["observedPaths"] == []
    assert out.observation["notObservedCount"] == 0


def test_sigma_brief_is_non_mutating_and_contains_no_fake_patent_claims(tmp_path):
    root, _ = fixture_repo(tmp_path)
    before = tree_digest(root)
    out = execute_forge(req("sigma_brief", {
        "root": str(root),
        "objective": "Strengthen audit trail and tests",
        "expectations": ["preserve audit trail", "add recovery test"],
    }), {})
    assert tree_digest(root) == before
    brief = out.observation["brief"]
    assert "SIGMA IMPLEMENTATION BRIEF" in brief
    assert "Strengthen audit trail and tests" in brief
    forbidden = ["patentable", "prior art search complete", "novelty percentage", "reviewer consensus"]
    assert not any(term in brief.lower() for term in forbidden)
    assert out.epistemic_class == "advisory"


def test_forgeproof_score_applies_supplied_rubric_scores_without_fabricating_review():
    out = execute_forge(req("forgeproof_score", {
        "scores": {
            "Precision": 5, "Reusability": 4, "Safety": 5,
            "Auditability": 5, "Effectiveness": 4,
        },
        "notes": {
            "Assumptions": "bounded internal use",
            "Known limits": "not externally benchmarked",
            "Experimental elements": "none",
            "Confidence tag": "high",
        },
    }), {})
    assert out.observation["averageScore"] == pytest.approx(4.6)
    assert out.observation["meetsThreshold"] is True
    assert out.observation["weakDimensions"] == []
    assert out.observation["scoreSource"] == "operator_supplied"


def test_forgeproof_score_rejects_missing_dimension_or_out_of_range():
    with pytest.raises(LabInputError):
        execute_forge(req("forgeproof_score", {"scores": {"Precision": 5}, "notes": {}}), {})


def test_registry_marks_forge_available_and_network_off():
    item = next(x for x in build_default_registry().describe() if x["engineId"] == "lab.forge")
    assert item["available"] is True
    assert item["requiresFilesystem"] is True
    assert item["requiresNetwork"] is False
