import hashlib
import os
from pathlib import Path

import pytest

from capt_runtime.prompt_compiler.repository_intelligence import (
    ForgeLimits,
    analyze_repository,
    gap_analysis,
    sigma_brief,
)


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda p: str(p.relative_to(root))):
        rel = str(path.relative_to(root))
        h.update(rel.encode())
        if path.is_symlink():
            h.update(b"SYMLINK")
            h.update(os.readlink(path).encode())
        elif path.is_file():
            h.update(path.read_bytes())
    return h.hexdigest()


def fixture_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# Demo\n- preserve durable audit trail\n", encoding="utf-8")
    (root / "app.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    (root / "test_app.py").write_text("def test_run():\n    assert True\n", encoding="utf-8")
    (root / ".env").write_text("OPENROUTER_API_KEY=super-secret-value\n", encoding="utf-8")
    (root / "blob.bin").write_bytes(b"\x00\x01SECRET-BINARY")
    ignored = root / "node_modules"
    ignored.mkdir()
    (ignored / "dep.js").write_text("const token='secret-secret-secret';", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("OUTSIDE-SYMLINK-SECRET", encoding="utf-8")
    (root / "escape.txt").symlink_to(outside)
    return root


def test_repository_archaeology_is_read_only_bounded_and_secret_safe(tmp_path):
    root = fixture_repo(tmp_path)
    before = tree_digest(root)
    result = analyze_repository(root, ForgeLimits(max_files=16, max_total_bytes=65536, max_depth=4, max_file_bytes=8192))
    assert tree_digest(root) == before
    assert set(result["files"]) == {"README.md", "app.py", "test_app.py"}
    joined = repr(result)
    assert "super-secret-value" not in joined
    assert "OUTSIDE-SYMLINK-SECRET" not in joined
    assert "SECRET-BINARY" not in joined
    assert {".env", "blob.bin", "node_modules", "escape.txt"}.issubset(set(result["excluded"]))


def test_repository_archaeology_rejects_noncanonical_and_symlink_root(tmp_path):
    root = fixture_repo(tmp_path)
    with pytest.raises(ValueError, match="canonical"):
        analyze_repository(Path(str(root / ".." / "repo")))
    link = tmp_path / "repo-link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        analyze_repository(link)


def test_gap_analysis_preserves_conservative_lexical_states(tmp_path):
    root = fixture_repo(tmp_path)
    gaps = {g["expectation"]: g for g in gap_analysis(root, [
        "preserves durable audits trail",
        "quantum banana reactor",
    ])["gaps"]}
    assert gaps["preserves durable audits trail"]["status"] == "related_text_found"
    assert gaps["preserves durable audits trail"]["tokenCoverage"] == 1.0
    assert gaps["quantum banana reactor"]["status"] == "not_observed"


def test_gap_analysis_uses_whole_tokens_not_substrings(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("durable auditing trailer notes\n", encoding="utf-8")
    gap = gap_analysis(root, ["durable audit trail"])["gaps"][0]
    assert gap["status"] == "partial_text_evidence"
    assert gap["tokenCoverage"] == pytest.approx(1 / 3)
    assert gap["observedPaths"] == []


def test_sigma_brief_is_advisory_non_mutating_and_non_overclaiming(tmp_path):
    root = fixture_repo(tmp_path)
    before = tree_digest(root)
    result = sigma_brief(root, "Strengthen audit trail and tests", ["preserve audit trail", "add recovery test"])
    assert tree_digest(root) == before
    brief = result["brief"]
    assert "SIGMA IMPLEMENTATION BRIEF" in brief
    assert "Strengthen audit trail and tests" in brief
    assert result["epistemicClass"] == "advisory"
    assert not any(term in brief.lower() for term in ["patentable", "prior art search complete", "novelty percentage", "reviewer consensus"])
