# Public Claim Audit — CAPT Core v0.5 (Corrected)

**Status:** COMPLETE for release-relevant claims  
**Base:** release/capt-standalone-final @ `548ab3ae311366a3a83d4ae50ac6f2bb7495dcd4`  
**Audit scope:** README, CLI help, package metadata, release docs, PR body, subsystem reports.

## Corrections applied to prior claims

The earlier public-claim audit (docs/release-audit-v0.5/05) was INCOMPLETE and reflected
the pre-repair/pre-final state. This document is the corrected, evidence-tied version.

## Classified claims

| Claim | Source | Classification | Evidence basis |
|-------|--------|----------------|----------------|
| CAPT v0.5 provides a governed, authenticated, headless CAPT runtime service | release docs | RETAIN | installed lifecycle proof (start/health/capabilities/command/stop) |
| A packaged model-capable ExecutionDriver is proven through the installed wheel | PR #33 | QUALIFY | proven as **bounded read-only inspection**, not general model engineering |
| CAPT owns runtime/lifecycle; Hermes is an external ExecutionDriver (inference-only) | architecture docs | RETAIN | authority chain + installed lifecycle |
| CAPT Solo Memory Engine is present | README | QUALIFY | present and **IMPORTABLE_API**; not a harness operator command |
| CAPT Solo Memory Engine and Runtime Memory Governor are the same subsystem | (implied earlier) | REMOVE | they are **distinct subsystems**: capt_solo memory engine vs capt_runtime memory governor/trigger engine |
| KHSB is durable or cross-process | (implied) | NARROW | KHSB is **in-process only**, not durable/cross-process (bus.py docstring) |
| CTP owns immutable ledger authority | (implied) | REMOVE | CTP is an operational journal; **EventStore owns immutable ledger authority** |
| "32K ladder complete" as an aggregate claim | release docs | NARROW | tied to enumerated behaviors + tests (ContextPack rotation, trigger accounting) |
| Pre-repair wheel proves post-repair release | (suppressed) | REMOVE/NARROW | final-head wheel is f70c3a0e... (fresh build from 548ab3a); proof wheel was 4005809/2a8a6ef |
| Package inclusion equals operator reachability | (implied) | REMOVE | packaged ≠ operator-facing; separate reachability classification used (internal-runtime/API-only/operator-facing) |
| Local proof equals hosted-CI proof | (implied) | REMOVE | local installed Hermes proof is NOT rerun by hosted CI (no Hermes on CI workers) |
| General model-driven engineering is proven | (none found) | RETAIN as NOT-SUPPORTED | only bounded read-only model inspection is proven |

## No unclassified claim remains in the release evidence set

Every release-facing claim in scope received one of: RETAIN, QUALIFY, NARROW,
IMPLEMENT_AND_PROVE, REMOVE, DEFER. No claim is left unclassified.
