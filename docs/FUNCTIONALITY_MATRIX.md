# CAPT Functionality Matrix

Source snapshot: `1e85bac5d17cde342a1ae55e6ee3da5fa681ff61`. Package remains `capt-solo 0.5.0`.

This matrix describes **merged Core `main` as of 2026-09-15**. Implementation presence, exact-head engineering verification, installed-runtime proof, and public-release authorization are distinct states.

| Capability | Merged `main` | Release/evidence boundary |
|---|---|---|
| runtime lifecycle / EventStore authority | yes | authoritative runtime foundation |
| checkpoint / exact historical replay | exact-prefix replay + governed replay fork | historical proof remains SHA-bound |
| durable memory / ContextPack | yes | runtime MemoryStore/ContextPack binding integrated; standalone Solo memory does not imply runtime admission |
| pinned external authored skills | yes | immutable selected bytes bound into model-visible approval |
| managed-local authored skills | yes | import/verify + deterministic contextual selection + anti-drift |
| evidence / verification / ClaimGuard separation | yes | no auto-verification |
| bounded IPC framing + rejection audit | integrated | release-control evidence is exact-source gated |
| capability lease inspect/revoke | integrated | governed authority path |
| governed artifact promotion | integrated | promotion != verification |
| ToolBroker / ToolExecution | integrated | durable execution/effect/reconciliation state |
| local terminal tool | integrated | capability governed |
| SSH terminal tool | integrated | profile/readiness required |
| Docker terminal tool | integrated | real-daemon acceptance environment dependent |
| governed file/code tools | integrated | bounded adapters, not unrestricted authority |
| provider registry/health/model list | integrated | health != governed execution proof |
| governed Ollama generation | integrated | provider result is an untrusted observation/artifact candidate; evidence admission and verification remain separate |
| local/authenticated OpenAI-compatible generation/prewarm | integrated | endpoint/resource/provenance bounds apply |
| provider/model session isolation | integrated native behavior | distribution proof separate |
| generic direct native MLX adapter | **not claimed** | materially configured OpenAI-compatible MLX/MTPLX path is separate |
| Textual/Tk operator surfaces | merged | thin clients over RuntimeService |
| native `CAPTNativeMac` executable target | merged application/test source | historical build/test receipts are SHA-bound; current-HEAD build and signing/notarization/distribution not established here |
| human approve/deny | integrated | exact model-visible approval binding |
| selected authored-skill visibility in native approvals | integrated | display is projection, not authority |
| cross-model continuation context | integrated | source/evidence identity remains bound |
| durable Cohorts + Chamber | integrated | quorum/consensus != verification |
| `.capt-flight` forensic bundle | integrated | projection/evidence only |
| provenance / epistemic projections | integrated | provenance != correctness |
| Security Closure Cockpit | integrated, fail-closed | authorization is exact-SHA evidence |
| macOS ↔ RuntimeService ↔ MCP shared authority | acceptance recorded on bound snapshots | not model-quality proof |
| native control center / Prompt Intelligence | MERGED (#148) | proposals and approval binding; source presence does not prove installed/live behavior |
| semantic operator-control API | MERGED (`42a6cd2`) | revision/digest-bound configuration and selection; non-authoritative coordination over RuntimeService |
| hardening tiers 1–5 | MERGED (#155) | read projections, authority gates, identity-refusal audit, honest provenance; `context_pipeline` / `context_merkle` explicitly unshipped |
| SOMA M0 | MERGED (#156) | trajectory/reducer/receipt and local benchmark contracts; live runtime integration and competition readiness not established |
| native model answer / execution receipt separation | MERGED (`d33a5e4`) | answer text and retained execution details are separate; output does not become verification |
| actionable research prompt routing | MERGED (`1e85bac`) | AUTO recognizes additional action signals subject to the four-word minimum and operator engine/mode policy; does not establish Search/Deep Research product completion |
| CAPT-UPG-020→024 | merged (#146) | scorer/probes, admitted-candidate symbol index, cognitive-debt surface; effectiveness and provider-cache proof separate |
| Secure Intake / Quarantine | design/plans on main | implementation not claimed |
| Projects / public composer palette | design/plans on main | implementation not claimed |
| Search / Deep Research governance | design/plans on main | implementation not claimed |
| Model Council alpha core | merged (#153) | logical tiers/interlocks, dissent analysis, durable replay/checkpoints, read-only Chamber; live provider/native Council GUI/release proof separate |
| public release authorization for arbitrary current head | **NO INHERITANCE** | evaluate exact release source; old receipts do not transfer |

## Verification boundary

Important SHA-bound evidence includes:

- PR #117 exact head `570babeef113943860c1268722200a48639e406d`: M0-A PASS, Native macOS Swift PASS, Release Security FAIL.
- release-security closure baseline `2199c036aa22af33fb3eb0700f63f820a35aa55a`: Release Security PASS with **21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE** and M0-A PASS.
- ToolBroker PR #126 exact head `b21ed6e7ff3996d48c756e342b278b69af0d666f`: full engineering gates plus hosted M0-A and Release Security PASS. Its squash merge is content/tree-identical but has a different SHA.
- managed-skills PR #129 head `e55037d92e89c5a960ecad908a1714c06c0aad0b`: focused managed/authored/runtime tests, full Python suite, Swift suite, installed-wheel and live skill-selection/anti-drift evidence recorded in the PR.

Historical August 27 audit: `3aee737…` had a mixed M0-A push run (`32958741310`): Python 3.12, contract drift, and TypeScript parity passed; Python 3.10 failed during the Docker availability probe. A retry was recorded by that audit; no retry outcome or current-HEAD CI result is established here. This is historical evidence, not status for `1e85bac…`.

## Deliberately separate lines

CAPT-UPG-020→024 merged through PR #146; #89/#91/#93/#95/#97 remain historical lineage, with empirical benchmark claims separately gated. Inversion Labs/Forge remains a separate edition/history lineage. The approved public-release design and plans are now preserved on Core `main` via PR #128, but their product features are not silently counted as implemented.

## Authority boundary

Every UI, compatibility surface, skill pack, provider adapter, and tool adapter is subordinate to RuntimeService/EventStore/governance. None becomes an alternate authority plane.
