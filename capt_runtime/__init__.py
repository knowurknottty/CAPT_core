"""CAPT M0-A runtime: contract and state-transition proof.

Scope is deliberately narrow (ADR-0111). This package proves transactional
state transitions, capability lifecycle, checkpointing, and replay. It does
NOT integrate an execution driver, perform external side effects, or
implement the full CAPT harness.

Relationship to `capt_solo`: this is an additive, parallel package. No
existing capt_solo module is modified by M0-A. See
docs/architecture/CAPT_RUNTIME_BASELINE_MAP.md for the term mapping.
"""

RUNTIME_VERSION = "0.1.0"

__all__ = ["RUNTIME_VERSION"]
