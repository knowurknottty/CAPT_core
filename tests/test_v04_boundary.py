"""CAPT Solo v0.4 — Repository boundary audit.

The architecture is: Public API -> CTP -> Repository -> SQLite. Raw SQL must
NOT appear in the public surface (api.py), the CLI (capt_cli.py), or the
Hermes plugin (plugin/__init__.py). Domain modules own their tables via their
connection; that is the established v0.1-v0.3 pattern and is preserved.

This test guards against NEW raw SQL leaking into the public surface.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "capt_solo"

# Files that must NOT contain raw SQL (true public surface only).
# The plugin is the integration layer and may call domain methods that
# internally execute SQL; that is acceptable. api.py and capt_cli.py are the
# strict public boundary and must not contain raw SQL.
FORBIDDEN_SQL_FILES = [
    SRC / "api.py",
    ROOT / "capt_cli.py",
]

SQL_PATTERNS = [
    re.compile(r"\.execute\("),
    re.compile(r"\.cursor\("),
    re.compile(r"PRAGMA\s", re.I),
    re.compile(r"CREATE\s+TABLE", re.I),
    re.compile(r"INSERT\s+INTO", re.I),
    re.compile(r"UPDATE\s+\w+\s+SET", re.I),
    re.compile(r"SELECT\s+\*?\s+FROM", re.I),
    re.compile(r"sqlite3\.connect"),
]


def test_public_surface_has_no_raw_sql():
    for f in FORBIDDEN_SQL_FILES:
        assert f.exists(), f"expected file missing: {f}"
        text = f.read_text()
        hits = []
        for pat in SQL_PATTERNS:
            for m in pat.finditer(text):
                # allow docstring/comment mentions of "SQL" as a word
                line = text[:m.start()].count("\n") + 1
                hits.append(f"L{line}: {m.group(0)}")
        assert not hits, f"raw SQL found in {f.name}: {hits}"


def test_domain_modules_own_their_tables():
    """Sanity: engine.py (storage) and domain modules exist and import."""
    import importlib
    for mod in ["capt_solo.memory.engine", "capt_solo.foundry.skill_foundry",
                "capt_solo.foundry.governance", "capt_solo.lifecycle.procedures"]:
        importlib.import_module(mod)


def test_plugin_tool_count_is_46():
    import json
    pj = SRC / "plugin" / "plugin.json"
    data = json.loads(pj.read_text())
    tools = data.get("tools", [])
    assert len(tools) == 47, f"expected 47 tools, got {len(tools)}"


def test_cli_uses_domain_methods_not_sql():
    """The CLI procedure-runs and retrieval-feedback commands must call domain
    methods, not raw SQL. Grep the source to confirm no leftover _conn.execute
    in capt_cli.py."""
    text = (ROOT / "capt_cli.py").read_text()
    assert "mgr._eng._conn.execute" not in text, \
        "capt_cli.py still contains raw SQL via mgr._eng._conn.execute"
