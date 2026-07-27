# ADR-0005 — Local-first; optional network transports

- **Title:** Local-first; optional network transports
- **Status:** Accepted
- **Date:** 2026-07-26
- **Context:** CAPT must run fully offline. Some capabilities (PULSE LLM gateway, RYS bridge, synchronization transports) require network. Treating them as mandatory would violate local-first.
- **Decision:** Local-first is the default (I-01). Network capabilities are optional transports/plugins, disabled by default, independently degradable (I-09). Synchronization *abstraction* is a canonical Layer 3 capability (un-gated); only its network transports (LAN/P2P/cloud) require security review. Filesystem and removable-media transports are un-gated.
- **Evidence:** CANONICAL_ARCHITECTURE L3.22 (Synchronization refinement); CAPT_CANON §8; I-01, I-05, I-09.
- **Consequences:** Baseline startup has no mandatory network init. PULSE/RYS/cloud-sync are not in baseline packaging by default.
- **Alternatives considered:** Mandatory network for sync (rejected: violates I-01); gate the sync abstraction (rejected: abstraction is required).
- **Related invariants:** I-01, I-05, I-09.
- **Supersedes:** none.
- **Superseded by:** none.
