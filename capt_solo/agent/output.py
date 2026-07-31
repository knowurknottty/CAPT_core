"""CAPT Agent Runner — runtime-owned output rendering (CaveCAPT).

Output verbosity is decided by the RUNTIME, not the provider. CaveCAPT (the
default) suppresses narration, plan restatement, tool narration, and social
filler, and bounds the visible output. Blockers, gate failures, and safety
warnings are ALWAYS preserved and bypass the length cap — a cap must never
truncate a blocker (ADR-0001 / BOOT_CONTRACT).

The raw normalized provider response is preserved as an artifact by the runner
BEFORE this renderer runs; this module only decides what the human sees.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from capt_solo.agent.contracts import (
    OUTPUT_MODE_AUDIT,
    OUTPUT_MODE_CAVE,
    OUTPUT_MODE_NORMAL,
    OUTPUT_MODE_SILENT,
    OUTPUT_MODE_VERBOSE,
    OutputPolicy,
)

_SAFETY_PREFIX = "SAFETY:"
_BLOCKER_PREFIX = "BLOCKER:"


def render(
    policy: OutputPolicy,
    *,
    summary: str = "",
    blockers: Optional[Sequence[str]] = None,
    safety: Optional[Sequence[str]] = None,
    gate_result: str = "",
    phase_completions: Optional[Sequence[str]] = None,
    narration: Optional[Sequence[str]] = None,
    evidence_ids: Optional[Sequence[str]] = None,
    provider_response: str = "",
) -> str:
    """Render bounded, mode-appropriate visible output.

    Safety and blocker lines are emitted in full regardless of mode (including
    silent) and are never truncated by ``max_visible_chars``.
    """
    blockers = list(blockers or [])
    safety = list(safety or [])
    phase_completions = list(phase_completions or [])
    narration = list(narration or [])
    evidence_ids = list(evidence_ids or [])

    # Priority (never suppressed / never truncated) lines.
    priority: List[str] = []
    for s in safety:
        priority.append(f"{_SAFETY_PREFIX} {s}")
    for b in blockers:
        priority.append(f"{_BLOCKER_PREFIX} {b}")
    if gate_result and gate_result not in ("PASS",):
        priority.append(f"{_BLOCKER_PREFIX} gate={gate_result}")

    # Silent: emit ONLY priority lines (blockers/safety); nothing on success.
    if policy.mode == OUTPUT_MODE_SILENT:
        return "\n".join(priority)

    body: List[str] = []
    if policy.show_phase_completion:
        body.extend(phase_completions)
    if policy.mode in (OUTPUT_MODE_VERBOSE, OUTPUT_MODE_AUDIT) and policy.show_narration:
        body.extend(narration)
    if policy.show_final_summary and summary:
        body.append(summary)
    if policy.mode in (OUTPUT_MODE_NORMAL, OUTPUT_MODE_VERBOSE, OUTPUT_MODE_AUDIT):
        # In non-cave visible modes the provider response is shown; cave shows
        # only the runtime summary (bounded).
        if provider_response and policy.mode != OUTPUT_MODE_NORMAL:
            body.append(provider_response)
        elif provider_response and policy.mode == OUTPUT_MODE_NORMAL and not summary:
            body.append(provider_response)
    if policy.mode == OUTPUT_MODE_AUDIT and evidence_ids:
        body.append("evidence: " + ", ".join(evidence_ids))
    elif evidence_ids and policy.mode != OUTPUT_MODE_CAVE:
        body.append("evidence: " + ", ".join(evidence_ids))

    body_text = "\n".join(x for x in body if x)
    # Bound the NON-priority body only.
    cap = policy.max_visible_chars
    if cap and cap > 0 and len(body_text) > cap:
        body_text = body_text[: cap - 1].rstrip() + "\u2026"

    parts = [p for p in (body_text, "\n".join(priority)) if p]
    return "\n".join(parts).strip()
