# CAPT Functionality Matrix

This matrix describes **merged Core `main` as of 2026-08-27**. Implementation presence, exact-head engineering verification, installed-runtime proof, and public-release authorization are distinct states.

| Capability | Merged `main` | Release/evidence boundary |
|---|---|---|
| runtime lifecycle / EventStore authority | yes | authoritative runtime foundation |
| checkpoint / exact historical replay | exact-prefix replay + governed replay fork | historical proof remains SHA-bound |
| durable memory / ContextPack | yes | approval/context binding integrated |
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
| governed Ollama generation | integrated | provider result remains evidence |
| local/authenticated OpenAI-compatible generation/prewarm | integrated | endpoint/resource/provenance bounds apply |
| provider/model session isolation | integrated native behavior | distribution proof separate |
| generic direct native MLX adapter | **not claimed** | materially configured OpenAI-compatible MLX/MTPLX path is separate |
| Textual/Tk operator surfaces | merged | thin clients over RuntimeService |
| native `CAPTNativeMac` executable target | merged / builds and tests | signing/notarization/distribution remain separate |
| human approve/deny | integrated | exact model-visible approval binding |
| selected authored-skill visibility in native approvals | integrated | display is projection, not authority |
| cross-model continuation context | integrated | source/evidence identity remains bound |
| durable Cohorts + Chamber | integrated | quorum/consensus != verification |
| `.capt-flight` forensic bundle | integrated | projection/evidence only |
| provenance / epistemic projections | integrated | provenance != correctness |
| Security Closure Cockpit | integrated, fail-closed | authorization is exact-SHA evidence |
| macOS ↔ RuntimeService ↔ MCP shared authority | acceptance recorded on bound snapshots | not model-quality proof |
| Secure Intake / Quarantine | design/plans on main | implementation not claimed |
| Projects / public composer palette | design/plans on main | implementation not claimed |
| Search / Deep Research governance | design/plans on main | implementation not claimed |
| Cohort Council product layer | design/plans on main | low-level Cohorts do not imply Council |
| public release authorization for arbitrary current head | **NO INHERITANCE** | evaluate exact release source; old receipts do not transfer |

## Verification boundary

Important SHA-bound evidence includes:

- PR #117 exact head `570babeef113943860c1268722200a48639e406d`: M0-A PASS, Native macOS Swift PASS, Release Security FAIL.
- release-security closure baseline `2199c036aa22af33fb3eb0700f63f820a35aa55a`: Release Security PASS with **21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE** and M0-A PASS.
- ToolBroker PR #126 exact head `b21ed6e7ff3996d48c756e342b278b69af0d666f`: full engineering gates plus hosted M0-A and Release Security PASS. Its squash merge is content/tree-identical but has a different SHA.
- managed-skills PR #129 head `e55037d92e89c5a960ecad908a1714c06c0aad0b`: focused managed/authored/runtime tests, full Python suite, Swift suite, installed-wheel and live skill-selection/anti-drift evidence recorded in the PR.

At audit start, current `main` `3aee737…` had a mixed M0-A push result caused by a Python 3.10 Docker availability-probe timeout while the Python 3.12, contract, and TypeScript jobs passed. The failed job was retried; treat the hosted retry as the authoritative current-run fact when complete.

## Deliberately separate lines

CAPT-UPG-020→024 (#89/#91/#93/#95/#97) remain the open benchmark/probe lane. Inversion Labs/Forge remains a separate edition/history lineage. The approved public-release design and plans are now preserved on Core `main` via PR #128, but their product features are not silently counted as implemented.

## Authority boundary

Every UI, compatibility surface, skill pack, provider adapter, and tool adapter is subordinate to RuntimeService/EventStore/governance. None becomes an alternate authority plane.
