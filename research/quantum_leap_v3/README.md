# Quantum Leap v3: isolated prototype

This research branch is pinned to e28b665; it is not installed or integrated into RuntimeService, EventStore, approvals, ClaimGuard, or the learning plane.

The predicates are manually encoded. WITHIN means only that the specified finite predicate held at the pinned Git commit. It does not establish natural-language entailment. Every result has semantic_entailment NOT_ASSESSED and promotion_eligible false. Source scopes remain bounded, and malformed queries return INCONCLUSIVE or UNSUPPORTED.

Run: python3 -I research/quantum_leap_v3/test_beliefprobe.py ; python3 -I research/quantum_leap_v3/beliefprobe.py . research/quantum_leap_v3/spotcheck_claims.json e28b665

Caveat: regex is bounded by POSIX signal time in the main thread, and object size is limited; execution in non-main threads is unsupported. Simple AST presence and regex checks cannot prove arbitrary execution semantics. The included spotchecks are authored probes, not an independent semantic adjudication corpus.
