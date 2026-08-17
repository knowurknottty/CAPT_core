# CAPT Capability Matrix

This matrix distinguishes **merged `main`** from **active integration** and **release proof**.

Legend:

- **MERGED** — present on `main` and reachable in its documented surface.
- **INTEGRATING** — implemented on the current open stacked PR lineage, not yet shipped on `main`.
- **HISTORICALLY PROVEN** — preserved exact evidence exists for the numbered v0.5 lineage.
- **PENDING PROOF** — implementation may exist, but the required terminal/live acceptance has not been established.

| Capability | `main` | Active stack | Proof boundary |
|---|---|---|---|
| normal `capt` lifecycle | MERGED | — | v0.5/v0.6-onramp tests + historical release evidence |
| durable memory CLI/API | MERGED | — | tested/historical evidence |
| EventStore + RuntimeService | MERGED | hardened in #46 | authoritative runtime boundary |
| checkpoint/restart/no-repeat resume | MERGED | hardened lifecycle in #46 | historical installed proof + newer focused tests |
| evidence / verification / ClaimGuard | MERGED | projection/provenance strengthened | do not equate evidence with verification/completion |
| shared operator facade | MERGED | extended | UI remains non-authoritative |
| Textual TUI | MERGED MVP | cockpit upgrade in #47 | merged interactive smoke; upgraded slice not shipped |
| TUI human approve/deny | MERGED MVP | prompt-approval binding strengthened #47 | governed command path |
| CaveCAPT presentation verbosity | MERGED | — | presentational only |
| provider registry/config | MERGED | consumed by #47 | registration ≠ execution |
| provider health/model discovery | MERGED where adapter supports it | — | adapter-specific |
| model-selection/favorites/overrides | MERGED foundation | used in cockpit | selection ≠ live governed inference |
| bounded ProviderDriver inference | NO | INTEGRATING #47 | controlled HTTP protocol tests; live exact-head acceptance pending |
| Ollama native generation transport | NO | INTEGRATING #47 | `/api/generate`; controlled server proof |
| OpenAI-compatible generation transport | NO | INTEGRATING #47 | `/chat/completions`; controlled server proof |
| prompt enhancement engines | NO | INTEGRATING #47 | deterministic presentation-side proposal |
| response-mode/context-budget cockpit | NO | INTEGRATING #47 | requested/effective provenance in active branch |
| cognitive provenance envelope | NO | INTEGRATING #47 | focused branch tests; not release proof |
| Discovery Governor / SEAL scanner | NO | INTEGRATING #44 | local integration evidence; unmerged |
| Ouroboros execution/recovery hardening | NO | INTEGRATING #46 | focused + full-suite evidence reported on branch |
| bounded Cohort coordination | NO | INTEGRATING #48 | durable persistence/reconstruction still absent |
| fail-closed SecurityGate | NO | INTEGRATING #49 | intentionally BLOCKED pending applicable-control evidence |
| Tk desktop operator | MERGED MVP | — | reference/fallback, not native product |
| SwiftUI native app | NO | client-contract library merged | no shipped `.app` |
| true Model A -> restart -> Model B continuity | NO | scaffold/target | PENDING PROOF |
| unrestricted autonomous repo mutation | NO | NO | explicitly not claimed |
| Windows support | UNVERIFIED | — | requires separate proof |

## Rule

Code presence never upgrades itself into release truth. Use the smallest claim supported by the exact source and evidence.