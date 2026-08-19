"""CLI coverage for pinned external authored skills."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import capt_cli


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _fixture_pack(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "CAPT_Skills"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "CAPT Tests")
    _git(root, "remote", "add", "origin",
         "https://github.com/knowurknottty/CAPT_Skills.git")
    name = "inversion-motion-craft"
    path = root / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    content = f"---\nname: {name}\nversion: 0.1.0\n---\n\n# Motion\n"
    path.write_text(content)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    lock = {
        "schemaVersion": "1.0.0",
        "packName": "CAPT_Skills",
        "packVersion": "0.1.0",
        "repository": "https://github.com/knowurknottty/CAPT_Skills.git",
        "ref": "v0.1.0",
        "commit": _git(root, "rev-parse", "HEAD"),
        "tree": _git(root, "rev-parse", "HEAD^{tree}"),
        "skills": [{
            "name": name, "version": "0.1.0",
            "path": f"skills/{name}/SKILL.md",
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
        }],
    }
    return root, lock


def test_skills_status_and_list_are_read_only_verified_views(tmp_path, monkeypatch, capsys):
    root, lock = _fixture_pack(tmp_path)
    monkeypatch.setattr(capt_cli, "load_capt_skills_lock", lambda: lock, raising=False)
    rc = capt_cli.main(["--json", "skills", "status", "--root", str(root)])
    assert rc == 0
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "VERIFIED"
    assert status["trust"] == "pinned_external"
    assert status["commit"] == lock["commit"]

    rc = capt_cli.main(["--json", "skills", "list", "--root", str(root)])
    assert rc == 0
    listing = json.loads(capsys.readouterr().out)
    assert listing == [{
        "name": "inversion-motion-craft",
        "version": "0.1.0",
        "contentDigest": "sha256:" + lock["skills"][0]["sha256"],
    }]


def test_skills_status_fails_closed_when_checkout_is_dirty(tmp_path, monkeypatch, capsys):
    root, lock = _fixture_pack(tmp_path)
    monkeypatch.setattr(capt_cli, "load_capt_skills_lock", lambda: lock, raising=False)
    path = root / lock["skills"][0]["path"]
    path.write_text(path.read_text() + "\nDIRTY\n")
    rc = capt_cli.main(["skills", "status", "--root", str(root)])
    assert rc == 1
    assert "dirty skill pack checkout rejected" in capsys.readouterr().err


def test_skills_show_returns_verified_content(tmp_path, monkeypatch, capsys):
    root, lock = _fixture_pack(tmp_path)
    monkeypatch.setattr(capt_cli, "load_capt_skills_lock", lambda: lock, raising=False)
    rc = capt_cli.main([
        "--json", "skills", "show", "inversion-motion-craft", "--root", str(root)
    ])
    assert rc == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["name"] == "inversion-motion-craft"
    assert shown["contentDigest"] == "sha256:" + lock["skills"][0]["sha256"]
    assert shown["content"].startswith("---\nname: inversion-motion-craft")
