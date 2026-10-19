from __future__ import annotations
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts"/"capt_repo_audit_gate.py"
spec=importlib.util.spec_from_file_location("rrds",SOURCE)
assert spec and spec.loader
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

@pytest.fixture
def repo(tmp_path):
    p=tmp_path/"repo"
    (p/"src"/"deep").mkdir(parents=True)
    (p/"src"/"security").mkdir(parents=True)
    for path,body in [("src/main.py","entrypoint\n"),
                      ("src/deep/worker.py","deep\n"),
                      ("src/security/token.py","deny\n")]:
        (p/path).write_text(body)
    subprocess.run(["git","init","-q",str(p)],check=True)
    subprocess.run(["git","-C",str(p),"add","."],check=True)
    subprocess.run(["git","-C",str(p),"-c","user.name=Fixture","-c",
                    "user.email=fixture@example.invalid","commit","-qm","frozen"],check=True)
    return p

def receipt(c,path):
    entry=next(x for x in c["files"] if x["path"]==path)
    return dict(path=path,sha256=entry["sha256"],line_evidence="L1: examined",
                node_evidence_ref="node-evidence://test-fixture-not-real")

def inspection(c, paths):
    return dict(schema="capt.rrds.inspection.v1",
                critical_paths=["src/security/token.py"],
                inspected=[receipt(c,x) for x in paths])

def complete(c):
    return inspection(c,[x["path"] for x in c["files"] if x["source"]])

def test_complete_fixture_passes(repo):
    c=m.census(repo)
    r=m.verify(c,complete(c))
    assert r["status"]=="DEEP_COVERAGE_GATE_PASS"
    assert r["inspected_source_directories"]==3

def test_one_level_is_not_deep(repo):
    c=m.census(repo)
    r=m.verify(c,inspection(c,["src/main.py"]),minimum=0.01)
    assert r["status"]=="PARTIAL_OR_UNVERIFIED"
    assert "src/deep" in r["uninspected_directories"]
    assert "src/security" in r["uninspected_directories"]

def test_missing_node_receipt_rejected(repo):
    c=m.census(repo)
    i=complete(c)
    del i["inspected"][0]["node_evidence_ref"]
    assert m.verify(c,i)["status"]=="PARTIAL_OR_UNVERIFIED"

def test_post_inventory_source_mutation_rejected(repo):
    c=m.census(repo)
    i=complete(c)
    (repo/"src"/"main.py").write_text("tampered")
    r=m.verify(c,i)
    assert r["status"]=="PARTIAL_OR_UNVERIFIED"
    assert any("changed bytes" in s for s in r["problems"])

def test_changed_head_rejected(repo):
    c=m.census(repo)
    i=complete(c)
    (repo/"next.txt").write_text("other commit")
    subprocess.run(["git","-C",str(repo),"add","next.txt"],check=True)
    subprocess.run(["git","-C",str(repo),"-c","user.name=Fixture","-c",
                    "user.email=fixture@example.invalid","commit","-qm","next"],check=True)
    assert any("Git HEAD" in s for s in m.verify(c,i)["problems"])

def test_symlink_exclusion_refused(repo):
    (repo/"src"/"alias").symlink_to(repo.parent,target_is_directory=True)
    c=m.census(repo)
    assert m.verify(c,complete(c))["status"]=="PARTIAL_OR_UNVERIFIED"

def test_duplicate_receipt_rejected(repo):
    c=m.census(repo)
    i=complete(c)
    i["inspected"].append(i["inspected"][0].copy())
    assert any("duplicate" in s for s in m.verify(c,i)["problems"])

def test_ci_empty_index_claims_zero_covered(repo,tmp_path):
    index=ROOT/"docs"/"review-evidence"/"rrds-index.json"
    assert index.exists()
    assert json.loads(index.read_text())["reviews"]==[]


def test_each_directory_inspected_but_not_every_source_file_fails(repo):
    c = m.census(repo)
    i = complete(c)
    # Add a second source in a previously inspected directory at a new pinned HEAD.
    p = repo/"src"/"deep"/"other.py"
    p.write_text("def other(): pass\n")
    subprocess.run(["git","-C",str(repo),"add","."],check=True)
    subprocess.run(["git","-C",str(repo),"-c","user.name=Fixture","-c",
                    "user.email=fixture@example.invalid","commit","-qm","more source"],check=True)
    fresh=m.census(repo)
    existing=[x["path"] for x in fresh["files"] if x["source"] and x["path"]!="src/deep/other.py"]
    outcome=m.verify(fresh,inspection(fresh,existing),minimum=0.01)
    assert outcome["status"]=="PARTIAL_OR_UNVERIFIED"
    assert outcome["inspected_source_directories"]==3
    assert any("100%" in p for p in outcome["problems"])


def test_linked_git_worktree_metadata_is_not_source_drift(repo, tmp_path):
    """Two checkouts at one Git HEAD must not mismatch only on .git pointers."""
    second = tmp_path / "independent"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--detach", str(second), "HEAD"],
        check=True, capture_output=True, text=True,
    )
    assert (second / ".git").is_file()
    primary = m.census(repo)
    other = m.census(second)
    assert primary["head"] == other["head"]
    assert {x["path"]: x["sha256"] for x in primary["files"]} == {
        x["path"]: x["sha256"] for x in other["files"]
    }
    assert ".git" not in {x["path"] for x in other["files"]}
    assert not other["errors"] and not other["symlinks"]


def test_git_metadata_exclusion_does_not_hide_other_symlinks(repo, tmp_path):
    """Excluding the root Git pointer cannot hide other tree symlinks."""
    # A directory symlink elsewhere in the tree remains an unresolved boundary.
    alias = repo / "src" / "deep" / "linked-dir"
    alias.symlink_to(tmp_path, target_is_directory=True)
    result = m.census(repo)
    assert "src/deep/linked-dir" in result["symlinks"]
    assert m.verify(result, complete(result))["status"] == "PARTIAL_OR_UNVERIFIED"
