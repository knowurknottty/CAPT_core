"""Dead context paths are marked unshipped — and stay that way.

``context_pipeline`` implements the documented five-stage architecture
(ADR-DT-PLANE-CONV, Gate 7) and ``context_merkle`` is a component-provenance
experiment (CAPT-UPG-013). Neither has a runtime caller: the live ContextPack
producer is ``MemoryTriggerEngine._fire_retrieval`` under ``capt_runtime/memory/``,
and nothing under ``capt_runtime/`` or ``desktop/`` imports either module — only
tests and ``scripts/context_merkle_probe.py`` do.

Of the three honest options (wire it, delete it, label it) the worst is a
well-documented dead path that reads as load-bearing. These tests make the label
an assertion: if someone wires one of them, the scan fails and the marker has to
be flipped deliberately rather than drifting into a lie.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, ".")

import pytest

REPO = Path(__file__).resolve().parents[2]
DEAD_MODULES = ("context_pipeline", "context_merkle")
PRODUCTION_DIRS = ("capt_runtime", "desktop")

# Matches `from ...context_merkle import x`, `from .context_merkle import x`,
# and `import capt_runtime.context_pipeline`. The trailing \b keeps
# `context_pipeline_digest` from matching.
IMPORT_RE = re.compile(
    r"^[ \t]*(?:from\s+\S*\b(?P<from_mod>context_pipeline|context_merkle)\b"
    r"|import\s+.*\b(?P<import_mod>context_pipeline|context_merkle)\b)",
    re.MULTILINE,
)


def _production_files():
    own = {"%s.py" % m for m in DEAD_MODULES}
    for directory in PRODUCTION_DIRS:
        for path in (REPO / directory).rglob("*.py"):
            if "__pycache__" in path.parts or path.name in own:
                continue
            yield path


@pytest.mark.parametrize("module", DEAD_MODULES)
def test_module_declares_itself_unshipped(module):
    mod = __import__("capt_runtime.%s" % module, fromlist=["SHIPPED"])
    assert getattr(mod, "SHIPPED", None) is False, (
        "capt_runtime.%s claims to be shipped. If it is genuinely wired into a "
        "live path now, update this test deliberately and say which path." % module
    )


def test_no_production_module_imports_a_dead_context_path():
    offenders = []
    for path in _production_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        if IMPORT_RE.search(text):
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], (
        "production modules import a dead context path: %s — either wire it in "
        "(and flip SHIPPED) or delete it; do not leave it half-wired" % offenders
    )


def test_the_scan_would_actually_catch_a_wiring():
    """Falsifiability: prove the detector matches real imports.

    A guard that cannot fail is decoration. These positive and negative controls
    show the scan would fire on a genuine wiring and stays quiet otherwise.
    """
    assert IMPORT_RE.search("from capt_runtime.context_pipeline import run_pipeline")
    assert IMPORT_RE.search("from .context_merkle import build_context_merkle")
    assert IMPORT_RE.search("import capt_runtime.context_pipeline")
    assert IMPORT_RE.search("    from capt_runtime.context_merkle import x")
    # unrelated names must not trip it
    assert not IMPORT_RE.search("from capt_runtime.contextpack import build_pack")
    assert not IMPORT_RE.search("context_pipeline_digest = 1")
    assert not IMPORT_RE.search("context_merkle_root = None")


def test_the_live_context_pack_producer_still_exists():
    """The claim 'this is dead because something else does the job' must hold.

    If the live producer vanished, the dead paths would stop being dead — this
    module would then be the only implementation, and the marker would be wrong.
    """
    from capt_runtime.memory.engine import MemoryTriggerEngine

    assert hasattr(MemoryTriggerEngine, "_fire_retrieval")
