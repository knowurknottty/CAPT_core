"""Epistemic-aware CAPT Textual surface (CAPT-UPG-014).

This is an additive presentation subclass over the canonical CaptTUI. It uses
only the shared Operator Dashboard projection and does not derive or mutate
runtime authority.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .app import CaptTUI, EvidencePanel


class EpistemicCaptTUI(CaptTUI):
    @staticmethod
    def _ladder_lines(ladder: List[Dict[str, Any]]) -> List[str]:
        if not ladder:
            return ["Epistemic state: <no claim projection>"]
        lines = ["Epistemic state (claim-scoped; not universal truth)"]
        for item in ladder[:5]:
            claim_id = item.get("claimId") or "unknown-claim"
            stages = " -> ".join(item.get("stages") or ["UNKNOWN"])
            provenance = item.get("verificationProvenance", "VERIFICATION_PROVENANCE_UNKNOWN")
            lines.append("  %s: %s [%s]" % (claim_id, stages, provenance))
        if len(ladder) > 5:
            lines.append("  ... %d more claim(s)" % (len(ladder) - 5))
        return lines

    def _render_evidence(self, verification: Dict[str, Any]) -> None:
        current = self._current_run
        if current:
            summary = "Run %s\nProvider/model: %s/%s\nState: %s" % (
                current.get("driverRunId", "unknown"),
                current.get("provider", "?"),
                current.get("model", "?"),
                current.get("status", "unknown"),
            )
        else:
            summary = "No current run receipt"

        ladder: List[Dict[str, Any]] = []
        if self._op is not None:
            try:
                ladder = self._op.dashboard().epistemic_ladder
            except Exception:  # noqa: BLE001
                ladder = []
        summary += "\n\n" + "\n".join(self._ladder_lines(ladder))

        self.query_one("#evidence", EvidencePanel).result = {
            "verification": verification,
            "current": summary,
            "note": (
                "Verification and ClaimGuard/claim acceptance are distinct. "
                "VERIFIED:<domain> is domain-scoped and does not mean universal truth."
            ),
        }


def main() -> int:
    EpistemicCaptTUI().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
