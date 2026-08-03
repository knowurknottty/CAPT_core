"""Pytest configuration for the CAPT runtime M0-A conformance suite.

Ensures the generated Python bindings are importable regardless of how pytest
is invoked, and that the repo root is on sys.path so `contracts.tools.*` and
`capt_runtime.*` resolve.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GEN_PY = REPO / "contracts" / "generated" / "python"

for p in (str(REPO), str(GEN_PY)):
    if p not in sys.path:
        sys.path.insert(0, p)


