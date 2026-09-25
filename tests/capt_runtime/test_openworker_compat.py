from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from capt_runtime.openworker_compat import (
    WorkspaceTrustStore,
    bound_tool_result,
    build_user_content,
    check_url,
    content_to_text,
    current_time,
    environment_context,
    is_readonly_command,
    read_targets,
    reviewer_text,
)
from capt_runtime.openworker_compat import basedir, session_facts, toolresult


def test_attachment_builder_preserves_multimodal_parts_and_hides_payload_from_reviewer():
    image = "data:image/png;base64," + base64.b64encode(b"fake-png").decode()
    content = build_user_content(
        "inspect these",
        [
            {"kind": "image", "data_url": image},
            {"kind": "text", "name": "notes.md", "text": "outside-authored payload"},
            {
                "kind": "pdf",
                "name": "report.pdf",
                "data_url": "data:application/pdf;base64,JVBERi0xLjQ=",
            },
        ],
    )
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "inspect these"}
    assert content[1]["image_url"]["url"] == image
    assert content[2]["type"] == "text"
    assert content[3]["type"] == "file"
    flattened = content_to_text(content)
    assert "inspect these" in flattened and "[image]" in flattened and "[pdf]" in flattened
    review = reviewer_text(content)
    assert "inspect these" in review
    assert "outside-authored payload" not in review
    assert "[user attached: notes.md]" in review


def test_attachment_builder_skips_invalid_remote_image():
    assert build_user_content(
        "hi", [{"kind": "image", "data_url": "https://example.com/image.png"}]
    ) == "hi"


def test_tool_result_bound_keeps_head_tail_and_canonical_raw_is_external_to_projection():
    raw = {"stdout": "BEGIN-" + ("x" * 30000) + "-END", "exitCode": 0}
    bounded = bound_tool_result(
        raw, max_bytes=10000, spill_dir=None, step=0, tool_name="capt_shell_exec"
    )
    assert raw["stdout"].endswith("-END")
    assert bounded is not raw
    assert bounded["stdout"].startswith("BEGIN-")
    assert bounded["stdout"].endswith("-END")
    assert "bytes omitted here" in bounded["stdout"]
    assert "CAPT ToolResult ledger" in bounded["stdout"]
    assert len(toolresult.serialize_result(bounded).encode("utf-8")) <= 10000


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "rg needle . | head -20",
        "sed -n '1,20p' README.md",
        "find . -maxdepth 2 -type f",
    ],
)
def test_readonly_classifier_accepts_conservative_local_reads(command):
    assert is_readonly_command(command)


@pytest.mark.parametrize(
    "command",
    [
        "curl https://example.com",
        "python3 -c 'print(1)'",
        "cat README.md > /tmp/x",
        "git status && rm -rf build",
        "./script.sh",
    ],
)
def test_readonly_classifier_fails_closed_for_egress_or_execution(command):
    assert not is_readonly_command(command)


def test_readonly_target_extraction_surfaces_files():
    cmd = "grep needle README.md docs/SECURITY.md | head -20"
    assert is_readonly_command(cmd)
    targets = read_targets(cmd)
    assert "README.md" in targets
    assert "docs/SECURITY.md" in targets


@pytest.mark.parametrize(
    "url, fragment",
    [
        ("http://127.0.0.1:8000", "loopback"),
        ("http://169.254.169.254/latest/meta-data", "link-local"),
        ("http://10.1.2.3", "private network"),
        ("http://100.64.0.1", "shared address space"),
    ],
)
def test_url_guard_blocks_local_network_surfaces_without_dns(url, fragment):
    reason = check_url(url)
    assert reason is not None
    assert fragment in reason


def test_url_guard_accepts_public_literal_without_dns():
    assert check_url("https://8.8.8.8/") is None


def test_workspace_trust_is_explicit_canonical_and_reversible(tmp_path):
    store = WorkspaceTrustStore(tmp_path / "trust.json")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    assert not store.is_trusted(workspace)
    canonical = store.set_trusted(workspace, True)
    assert canonical == str(workspace.resolve())
    assert store.is_trusted(workspace)
    assert store.list() == [canonical]
    store.set_trusted(workspace, False)
    assert not store.is_trusted(workspace)


def test_base_dir_rejects_escape(monkeypatch, tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    inside = base / "inside"
    inside.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setenv("CAPT_BASE_DIR", str(base))
    assert basedir.ensure_under_base(inside) == inside.resolve()
    with pytest.raises(basedir.OutsideBaseDir):
        basedir.ensure_under_base(outside)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def test_session_facts_freeze_known_world_and_redact_query(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "remote", "add", "origin", "https://github.com/org/repo.git")
    root = SimpleNamespace(path=tmp_path, writable=True)
    world = session_facts.capture(
        roots=[root], allowed_domains=["Python.org"], workspace=tmp_path
    )
    assert world.remotes == (("origin", "https://github.com/org/repo.git"),)
    assert world.hosts == ("github.com", "python.org")
    rendered = world.render()
    assert "origin -> https://github.com/org/repo.git" in rendered
    assert "python.org" not in rendered
    src = session_facts.ingestion_source(
        {"url": "https://GitHub.com/search?q=SECRET_FROM_DOTENV"}
    )
    assert src == "github.com"
    assert "SECRET" not in src


def test_session_facts_category_detection():
    assert session_facts.is_ingesting(SimpleNamespace(category="web"))
    assert session_facts.is_ingesting(SimpleNamespace(category="mcp"))
    assert not session_facts.is_ingesting(SimpleNamespace(category="filesystem"))


def test_environment_context_reports_workspace_and_git_state(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True)
    (repo / "x.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "x.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
    block = environment_context(repo)
    assert str(repo.resolve()) in block
    assert "Git branch: main" in block
    assert "Git status: clean" in block
    assert "initial" in block


def test_current_time_shape():
    now = current_time()
    assert set(now) == {"local", "timezone", "utc", "weekday"}
    assert now["utc"].endswith("Z")
