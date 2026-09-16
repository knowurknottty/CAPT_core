# CAPT Capability Matrix

Source snapshot: `1e85bac5d17cde342a1ae55e6ee3da5fa681ff61`. Package remains `capt-solo 0.5.0`.

This matrix describes **merged `main` as of 2026-09-15** and keeps implementation, engineering proof, and release proof separate.

Legend:

- **MERGED** — present on Core `main` and reachable through the documented source surface.
- **SEPARATE** — exists only in another branch/edition/repository or an open benchmark lane.
- **PENDING PROOF** — code may be merged, but the cited terminal/live/release evidence does not automatically apply to the current literal head.

| Capability | Core `main` | Proof boundary |
|---|---|---|
| normal `capt` lifecycle | MERGED | package version remains `capt-solo 0.5.0`; newer integration proof is SHA-bound |
| EventStore + authenticated RuntimeService | MERGED | authoritative runtime boundary |
| checkpoint/restart/governed resume | MERGED | exact-prefix replay + governed replay fork integrated; unknown external effects require reconciliation, not an exactly-once guarantee |
| durable memory / ContextPack | MERGED | runtime MemoryStore/ContextPack are separate from the standalone Solo MemoryEngine and model session state |
| evidence / verification / ClaimGuard separation | MERGED | evidence is not auto-verification or task completion |
| shared operator facade | MERGED | UI remains non-authoritative |
| Textual TUI | MERGED | thin client over RuntimeService |
| Tk desktop operator | MERGED MVP | reference/fallback surface |
| native `CAPTNativeMac` application target | MERGED | historical build/test receipts are SHA-bound; no current-HEAD build or signed/notarized distribution established here |
| governed human approve/deny | MERGED | one-use exact model-visible approval binding |
| provider registry / health / model discovery | MERGED | discovery/health != execution proof |
| governed Ollama generation | MERGED | model output is an untrusted observation/artifact candidate; evidence admission and verification are separate |
| local/authenticated OpenAI-compatible execution | MERGED | endpoint/resource/provenance bounds apply |
| bounded local model prewarm | MERGED | readiness != model-quality proof |
| coherent provider/model persistence | MERGED | global vs session selection remains explicit |
| generic direct native MLX placeholder | NOT CLAIMED | use materially configured OpenAI-compatible MLX/MTPLX path instead |
| cross-model continuation context | MERGED | exact context/approval identity is bound; release proof remains separate |
| durable Cohorts + Chamber | MERGED | quorum/consensus cannot manufacture verification |
| governed artifact promotion | MERGED | promotion is a separate authority transaction |
| capability lease inspect/revoke | MERGED | bounded authority path |
| `.capt-flight` forensic bundle | MERGED | projection/evidence only |
| provenance / epistemic / security projections | MERGED | projections do not create correctness |
| 47-control Security Closure Cockpit | MERGED | exact-source receipt required for release authorization |
| macOS ↔ RuntimeService ↔ MCP shared authority | MERGED + recorded acceptance | test-provider acceptance != model-quality proof |
| pinned external authored skills | MERGED | immutable pack bytes/provenance bound before dispatch |
| managed-local Agent Skills import/verify | MERGED | PR #129; pack snapshot/digests are state-local and governed |
| contextual authored-skill auto-selection | MERGED | explicit pinned selection outranks managed-local selection |
| authored-skill execution anti-drift | MERGED | changed approved bytes fail closed |
| governed ToolBroker | MERGED | PR #126; RuntimeService/EventStore retain authority |
| durable ToolExecution lifecycle/reconciliation | MERGED | indeterminate effects are reconciled, not blindly replayed |
| local terminal backend | MERGED | consequential execution remains capability governed |
| SSH terminal backend | MERGED | configured profile/readiness required |
| Docker terminal backend | MERGED | real-daemon acceptance is environment dependent |
| governed file/code adapters | MERGED | bounded tool authority; not unrestricted repo mutation |
| CAPT-UPG-020→024 probes/benchmarks + debt projection | MERGED | PR #146 (`cefc885`); empirical effectiveness, real-grammar performance, and provider-cache proof remain separate |
| Inversion Labs specialist edition | SEPARATE | separate branch/runtime lineage, not Core-main authority |
| native control center / Prompt Intelligence | MERGED (#148) | proposals and approval binding; source presence does not prove installed/live behavior |
| semantic operator-control API | MERGED (`42a6cd2`) | revision/digest-bound configuration and selection; non-authoritative coordination over RuntimeService |
| hardening tiers 1–5 | MERGED (#155) | read projections, authority gates, identity-refusal audit, honest provenance; `context_pipeline` / `context_merkle` explicitly unshipped |
| SOMA M0 | MERGED (#156) | trajectory/reducer/receipt and local benchmark contracts; live runtime integration and competition readiness not established |
| native model answer / execution receipt separation | MERGED (`d33a5e4`) | answer text and retained execution details are separate; output does not become verification |
| actionable research prompt routing | MERGED (`1e85bac`) | AUTO recognizes additional action signals subject to the four-word minimum and operator engine/mode policy; does not establish Search/Deep Research product completion |
| Secure Intake / Quarantine | DESIGN ON MAIN | approved design/plans merged via #128; implementation not claimed |
| Projects / composer capability palette | DESIGN ON MAIN | implementation not claimed |
| Search / Deep Research governance | DESIGN ON MAIN | implementation not claimed |
| Model Council alpha core | MERGED ALPHA (#153) | tiers/logical blast, launch interlocks, epistemic analysis, durable replay/checkpoint state, and Council Chamber projection; live provider/native GUI/release proof not claimed |
| unrestricted autonomous repo mutation | NO | explicitly not claimed |
| Windows support | UNVERIFIED | separate platform proof required |

## Release evidence rule

The exact release-security closure baseline `2199c036aa22af33fb3eb0700f63f820a35aa55a` has a hosted PASS receipt. The ToolBroker PR #126 exact head `b21ed6e7ff3996d48c756e342b278b69af0d666f` also had hosted M0-A and Release Security PASS before squash merge.

Those receipts are not transferable labels for an arbitrary descendant SHA. Current `main` must be evaluated at its own exact source identity for release authorization.

## Rule

Code presence never upgrades itself into release truth. Use the smallest claim supported by the exact source, target branch, and evidence identity.
