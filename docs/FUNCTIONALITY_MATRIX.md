# CAPT Functionality Matrix

This matrix distinguishes protected `main` from the terminal PR #117 convergence candidate. “Candidate” means implemented and integrated on the convergence line; it does not mean release-authorized.

| Capability | Protected `main` | Terminal convergence candidate |
|---|---|---|
| runtime lifecycle / EventStore authority | yes | yes, reconciled |
| checkpoint / exact historical replay | foundation | exact prefix replay + governed replay fork |
| durable memory / ContextPack | yes | yes, approval/context reconciliation included |
| authored-skill verification | yes | exact selected bytes bound into model-visible approval |
| evidence / verification / ClaimGuard separation | yes | yes |
| bounded IPC framing | partial historical baseline | integrated |
| security rejection audit | partial historical baseline | integrated |
| capability lease inspect/revoke | foundation | integrated |
| governed artifact promotion | no | integrated |
| provider registry/health/model list | yes | yes + legacy backfill/coherence repair |
| governed Ollama generation | historical/stacked | integrated |
| local OpenAI-compatible generation | historical/stacked | integrated + prewarm |
| provider/model session isolation | no | native origin-session bound |
| generic native MLX adapter | no | **unregistered unless materially configured** |
| Textual/Tk operator surfaces | yes | yes + UPG projections |
| native macOS executable target | no/contract-era baseline | `CAPTNativeMac` builds and tests |
| human approve/deny | yes | exact model-visible approval binding |
| cross-model continuation context | partial/stacked | integrated |
| durable Cohorts | no/coordination-era baseline | EventStore persistence + evidence admission + steering |
| Cohort Chamber | no | integrated |
| `.capt-flight` forensic bundle | no | integrated |
| Provenance Lens / DAG | no | integrated |
| Security Closure Cockpit | no | integrated, fail-closed |
| macOS ↔ RuntimeService ↔ MCP shared authority | no | acceptance proven |
| public release authorization | no claim | **BLOCKED pending security evidence** |

## Fresh terminal-candidate verification

- Core Python: **1,055 passed / 57 skipped / 12 deselected / 0 failures**.
- Swift normal: **64 / 7 skipped / 0 failures**.
- Swift strict concurrency/warnings-as-errors: **PASS**.
- ThreadSanitizer: **64 / 7 skipped / 0 failures**.
- Contract generation/drift: **PASS**.
- MCP PR #2 suite against the same Core candidate: **PASS**; MCP Ruff **PASS**.
- Cross-surface disposable-runtime acceptance: **PASS**.
- Broad repository Ruff F/E9: **known legacy cleanup debt; not globally clean**.

## Deliberate non-convergence lines

CAPT-UPG-020→024 remain benchmark/probe/pending-verification work. Inversion Labs/Forge remains a separate governed edition line. Neither is silently counted as Core release functionality.

## Authority boundary

Every UI and compatibility surface is a projection/control client. RuntimeService/EventStore remain authoritative.
