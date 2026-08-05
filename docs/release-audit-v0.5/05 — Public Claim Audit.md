## Status: INCOMPLETE AUDIT

No complete, standalone public-claim matrix artifact was found in the release evidence directory (/tmp/capt-release-evidence-b45c4b0*). This document is a factual summary from available evidence only.

## Claims Verified Against Evidence

| Claim | Source | Classification | Evidence |
|-------|--------|----------------|----------|
| CAPT Standalone Harness v0.5 provides a governed, authenticated, headless CAPT runtime | release-decision.md | VERIFIED | installed lifecycle proof: start/health/capabilities/command/stop through token-authenticated socket from installed wheel |
| A packaged model-capable ExecutionDriver exists and is proven through the installed wheel | evidence-manifest.md | VERIFIED | 3 real Hermes model tasks executed through run_approved_hermes_inspection; real artifacts produced |
| CAPT owns runtime/lifecycle; model backend owns inference only | execution-limitation-statement.md | VERIFIED | authority chain documented and proven through installed lifecycle |
| 7/7 adversarial authority cases rejected with zero mutation | evidence-manifest.md section 5 | VERIFIED | adversarial-battery.py run output; ledger inspection |
| Checkpoint/restart/resume/no-repeat proven through installed wheel | release-decision.md section 4 | VERIFIED | ledger growth 0->39 events; chain digest match; not_repeated |
| Verification contract conforms to frozen schema | This audit (b79c4f0) | VERIFIED | conformance probe; 766 passed; contracts/ unmodified |
| General model-driven engineering is proven | (none) | NOT SUPPORTED BY EVIDENCE | only bounded read-only repository inspection is proven, not arbitrary engineering |
| Remote push / GitHub presence | (none) | NOT VERIFIED | no push attempted; all commits are LOCAL ONLY |
| Wheel rebuilt after verification-contract repair | (none) | NOT YET DONE | wheel at sha256 348fe9da... was built from b45c4b0; repair is at b79c4f0 |

## Claims Not Assessed
Full public-claim audit requires reconciliation with external public statements (GitHub README, social media, documentation site). No comprehensive inventory of public claims was performed. This is marked INCOMPLETE AUDIT for that reason.
