#!/usr/bin/env python3
"""Validate docs/API.md against the live source so it cannot silently go stale.

The committed docs/API.md must equal the output of the generator run against
the current source. A drift between documentation and code fails this test.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_api_reference_is_current():
    generated = REPO / "docs" / "API.md"
    # Run the generator in --check mode; it returns 0 when the committed doc
    # equals the freshly generated output.
    env = dict(os.environ)
    # If capt_solo is not pip-installed into the test interpreter, import it
    # from the repository source tree (matching how the rest of the suite runs).
    repo_py = [str(REPO), str(REPO / "contracts" / "generated" / "python")]
    existing = env.get("PYTHONPATH", "").split(os.pathsep)
    env["PYTHONPATH"] = os.pathsep.join(repo_py + [p for p in existing if p])

    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "generate_api_reference.py"),
         "--check", str(generated)],
        capture_output=True, text=True, cwd=str(REPO), env=env,
    )
    assert r.returncode == 0, (
        "docs/API.md is stale. Run `python3 scripts/generate_api_reference.py` "
        "and commit the result.\nSTDOUT:\n%s\nSTDERR:\n%s" % (r.stdout, r.stderr)
    )
