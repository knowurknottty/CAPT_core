"""External execution receipt helpers (re-exported for package clarity)."""

from __future__ import annotations

from typing import Any, Dict

from .translation import build_receipt, external_run_id_for


def make_receipt(run_id: str, summary: str, observed_at: str) -> Dict[str, Any]:
    """Convenience wrapper around translation.build_receipt."""
    return build_receipt(run_id, external_run_id_for(run_id), summary, observed_at)
