# CAPT Functionality Matrix

This matrix describes **merged `main`** after PR #117. Implementation presence and release authorization remain different states.

| Capability | Merged `main` | Release/evidence boundary |
|---|---|---|
| runtime lifecycle / EventStore authority | yes | authoritative runtime foundation |
| checkpoint / exact historical replay | exact-prefix replay + governed replay fork | historical proof remains SHA-bound |
| durable memory / ContextPack | yes | approval/context binding integrated |
| authored-skill verification | yes | exact selected bytes bound into model-visible approval |
| evidence / verification / ClaimGuard separation | yes | no auto-verification |
| bounded IPC framing + rejection audit | integrated | release-control evidence still exact-head gated |
| capability lease inspect/revoke | integrated | governed authority path |
| governed artifact promotion | integrated | promotion != verification |
| provider registry/health/model list | integrated | health != governed execution proof |
| governed Ollama generation | integrated | provider result remains evidence |
| local OpenAI-compatible generation/prewarm | integrated | loopback/local boundary enforced |
| provider/model session isolation | integrated native behavior | distribution proof separate |
| generic native MLX adapter | **unregistered unless materially configured** | MTPLX/OpenAI-compatible path is separate |
| Textual/Tk operator surfaces | merged | thin clients over RuntimeService |
| native `CAPTNativeMac` executable target | merged / builds and tests | signing/notarization/distribution remain separate |
| human approve/deny | integrated | exact model-visible approval binding |
| cross-model continuation context | integrated | source/evidence identity remains bound |
| durable Cohorts + Chamber | integrated | quorum/consensus != verification |
| `.capt-flight` forensic bundle | integrated | projection/evidence only |
| Provenance Lens / DAG | integrated | provenance != correctness |
| Security Closure Cockpit | integrated, fail-closed | **release authorization blocked** |
| macOS ↔ RuntimeService ↔ MCP shared authority | acceptance proven on recorded snapshot | not model-quality proof |
| public release authorization | **NO** | exact merged-head Release Security failed |

## Verification boundary

The frozen 2026-08-19 convergence snapshots remain valid for the SHAs that produced them: Core Python **1,055 passed / 57 skipped / 12 deselected**, Swift **64 / 7 skipped / 0 failures**, strict concurrency PASS, ThreadSanitizer PASS, contract drift PASS, MCP PR #2 PASS, and cross-surface acceptance PASS.

The exact merged PR #117 head `570babeef113943860c1268722200a48639e406d` has M0-A PASS, Native macOS Swift PASS, and Release Security **FAIL**. Do not relabel older artifact hashes or gate counts as merge-head evidence.

## Deliberate separate lines

CAPT-UPG-020→024 remain benchmark/probe/pending-verification work. Inversion Labs/Forge remains a separate governed edition line. Public-release design/planning remains on #111/#116. None is silently counted as merged Core release functionality.

## Authority boundary

Every UI and compatibility surface is a projection/control client. RuntimeService/EventStore remain authoritative.
