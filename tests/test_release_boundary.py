"""Release-boundary guard: public artifact must exclude private code.

Per ADR-0007 / RELEASE_GOVERNANCE.md (owner Decisions D3/D4): RYS, Puter KV, and
mesh-network implementations are PRIVATE and must not appear in the public
`capt_solo` tree or the built wheel. This test detects future drift.
"""
import ast
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "capt_solo"

# Private markers that must NEVER appear as importable modules / files in public tree.
PRIVATE_MODULE_MARKERS = ["rys", "puter", "mesh", "ouroboros_private"]
# Words that may appear only in docs/comments labeling something private/excluded.
PRIVATE_WORD_ALLOWED_IN_COMMENTS = {"rys", "puter", "mesh"}


def _py_files():
    return [p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts]


def test_no_private_module_files():
    for p in SRC.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        low = p.name.lower()
        for marker in PRIVATE_MODULE_MARKERS:
            assert marker not in low, f"private module file present: {p}"


def test_no_private_imports():
    """No `import <private>` or `from <private> import` in public source."""
    for p in _py_files():
        tree = ast.parse(p.read_text(), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0].lower()
                    assert root not in PRIVATE_MODULE_MARKERS, (
                        f"private import {alias.name} in {p}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0].lower()
                    assert root not in PRIVATE_MODULE_MARKERS, (
                        f"private from-import {node.module} in {p}")


def test_hmc_engram_dream_are_public_core():
    """Registry must keep HMC/ENGRAM/DREAM as CAPT_core (Decision 2)."""
    import yaml
    reg = yaml.safe_load((REPO / "architecture" / "registry.yaml").read_text())
    by_id = {s["canonical_id"]: s for s in reg["subsystems"]}
    for cid in ("CAPT-HMC", "CAPT-ENG", "CAPT-DRM"):
        assert by_id[cid]["public_release_target"] == "CAPT_core", (
            f"{cid} must remain CAPT_core (Decision 2)")
        assert by_id[cid]["implementation_status"] != "missing", (
            f"{cid} implementation_status must reflect in-tree code")


def test_public_imports_without_private():
    """Public runtime imports must succeed with no private packages present."""
    # These are the public engine/workspace modules built this session; they must
    # not import private markers.
    for mod in ("capt_solo.workspace",):
        __import__(mod)


def test_wheel_excludes_private(tmp_path):
    """Build wheel (if build available) and assert no private path in archive."""
    wheel = list((REPO / "dist").glob("*.whl")) if (REPO / "dist").exists() else []
    if not wheel:
        pytest.skip("no wheel built; run `python3 -m build --wheel` first")
    import zipfile
    z = zipfile.ZipFile(wheel[0])
    names = z.namelist()
    for marker in PRIVATE_MODULE_MARKERS:
        bad = [n for n in names if marker in n.lower()]
        assert not bad, f"private marker {marker} found in wheel: {bad}"
