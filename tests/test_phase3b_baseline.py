"""Phase 3B — baseline/packaging repair verification.

Locks the version-identity resolution (DEBT-002) and CTP source presence
(DEBT-001) so the clean-clone baseline cannot silently regress.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CANONICAL_VERSION = "0.4.1"


def test_b_version_identity_consistent():
    """All package-level version identifiers must agree on the canonical version."""
    pyproject = (REPO / "pyproject.toml").read_text()
    assert f'version = "{CANONICAL_VERSION}"' in pyproject, \
        f"pyproject.toml must declare {CANONICAL_VERSION}"

    init = (REPO / "capt_solo" / "__init__.py").read_text()
    assert f'__version__ = "{CANONICAL_VERSION}"' in init, \
        f"capt_solo/__init__.py must declare {CANONICAL_VERSION}"

    bubble = (REPO / "capt_solo" / "foundry" / "bubble.py").read_text()
    assert f'CAPT_SOLO_VERSION = "{CANONICAL_VERSION}"' in bubble, \
        f"bubble CAPT_SOLO_VERSION must be {CANONICAL_VERSION}"

    plugin = (REPO / "capt_solo" / "plugin" / "plugin.json").read_text()
    assert f'"version": "{CANONICAL_VERSION}"' in plugin, \
        f"plugin.json must declare {CANONICAL_VERSION}"


def test_b_ctp_source_present_and_importable():
    """CTP source must be committed in the tree (not only in a local wheel)."""
    ctp_journal = REPO / "capt_solo" / "ctp" / "journal.py"
    assert ctp_journal.exists(), "capt_solo/ctp/journal.py must be in the tree"
    # It must actually import (proves it is real source, not a stub).
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("ctp_journal_check", ctp_journal)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    assert hasattr(mod, "CTPRuntime"), "ctp journal must define CTPRuntime"
    assert hasattr(mod, "Receipt"), "ctp journal must define Receipt"


def test_b_ctp_not_gitignored():
    """The ctp/ directory must not be excluded from version control."""
    gitignore = (REPO / ".gitignore").read_text()
    assert "ctp/" not in gitignore.splitlines(), ".gitignore must not exclude ctp/"
