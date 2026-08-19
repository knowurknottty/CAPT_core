# Inversion Labs CAPT R1 — Functionality & Final Reconciliation

**Final classification:** `INVERSION_LABS_R1_DOGFOOD_READY_WITH_BOUNDED_LIMITS`

**Frozen CAPT-core base:** `5f2917772e675523176a3112c49e28ffba20b8f1`

**Executed runtime source head:** `819b94f30b97d18c64a61dea5e2db905a7df2d74`

**Retained wheel SHA-256:** `7f065a6977b99bb42e98f389057da47a5193851b9060524b20c0c28cd3eadf9b`

**Retained sdist SHA-256:** `a06f191357498302637b8560c91366b63db5e06335264a721a4e8cf2d5b7756f`

**Evidence:** `reports/lab/INVERSION_LABS_R1_DOGFOOD.md` and `.json`

## Meaning of the classification

R1 is ready for internal Inversion Labs work. The restored specialist engines run inside CAPT's existing authority model, produce durable provenance/evidence, survive installed-artifact and native-app dogfood, and do not promote their own conclusions.

`WITH_BOUNDED_LIMITS` is intentional, not a euphemism for a failed gate. R1 deliberately exposes only donor operations that survived code review and executable tests. Placeholder or scientifically unvalidated donor routines remain unavailable; analogy and consensus remain advisory; Forge is bounded read-only; remote/network Lab engines and direct authoritative writes are excluded.

This classification does **not** imply public-release readiness or scientific validation of every inherited algorithm.

## What powers are restored

| Capability | R1 status | Epistemic class | Authority behavior |
|---|---|---|---|
| Cyclotomic field summary | READY | calculation | Proposed observation + evidence; never auto-verified |
| McMillan transition-temperature equation | READY | calculation / physics | Formula evaluation only; no material-validity claim |
| Structural analogy / role mapping | READY | heuristic | Deterministic SHA-256-seeded VSA/SME advisory |
| Schema abstraction | READY | advisory | Structural recurrence only; no truth/generalization claim |
| QIPC-inspired belief aggregation | READY | advisory | Probability/entropy/confidence diagnostics only |
| Repository archaeology | READY | advisory | Read-only, root-bounded, secret/binary/symlink exclusions |
| Gap analysis | READY | advisory | Distinguishes exact `text_match_found`, co-located `related_text_found`, distributed `partial_text_evidence`, and zero-signal-token `not_observed`; lexical coverage excludes a bounded set of common function words, uses whole tokens with camel/Pascal/snake identifier boundaries plus conservative symmetric `s`/`es` inflections, and suppresses short-lexeme collisions such as `new`/`news`; all states are lexical evidence only, never “implemented” |
| SIGMA implementation brief | READY | advisory | Bounded implementation input; not approval or verification |
| ForgeProof rubric scoring | READY | advisory | Operator-supplied scores; no fabricated reviewer |
| Native Labs workstation | READY | renderer/controller | Uses only `lab_engines` + `run_lab_engine_advisory` IPC |
| Separate Lab runtime/app state | READY | operational | `~/.capt-inversion-labs`; core `~/.capt` left unchanged |

## What is intentionally *not* restored

- legacy bioCAPT kernel authority, memory authority, claim authority, ActionPacket authority, or trust-state authority;
- placeholder class-group/discrete-log, protein-gradient, Eliashberg, or simplistic superconducting predictor routines;
- simulated prior-art search, patentability claims, novelty percentages, or fabricated reviewer consensus;
- direct Lab writes to authoritative project files;
- network/remote Lab execution in R1;
- automatic verification, ClaimGuard acceptance, task success, mission completion, or claim promotion from specialist output.

## Governed execution path

Every accepted Lab run follows this path:

`authenticated command -> pre-admission contract/lineage validation -> durable command claim -> DriverRun -> local bounded adapter -> canonical JSON artifact -> exact SHA-256 re-read -> completed DriverRun -> proposed observation Claim -> artifact_hash EvidenceRecord`

The task and mission are not promoted by the Lab command. Verification remains an independent later authority.

## Final acceptance gates

| # | Gate | Disposition | Evidence |
|---|---|---|---|
| 1 | Frozen core regression remains green | **PASS** | Final source regression 938/57/12; retained-wheel regression 938/57/12; Lab is stacked from frozen core `5f291777…` |
| 2 | Registry deterministic with exact donor provenance | **PASS** | Registry/contract tests; packaged donor manifest digest `sha256:dc86c8b8769f4cfba27e03e5d1c7edb460ee84b95a02f2b75673da39235a9d74` |
| 3 | Unknown engine/op and malformed inputs fail before DriverRun | **PASS** | Contract/registry + governed-runtime negative tests |
| 4 | Mission/task mismatch fails before execution | **PASS** | Runtime advisory spoof test; no DriverRun created |
| 5 | Same-key/same-payload replay does not rerun | **PASS** | Unit tests and all four retained-wheel dogfood runs returned `idempotent/duplicate` with one DriverRun |
| 6 | Same-key/different-payload collision fails closed | **PASS** | Runtime advisory collision test |
| 7 | Engine failure yields failed DriverRun and no fabricated evidence | **PASS** | Runtime advisory failure test |
| 8 | Success yields completed DriverRun + proposed observation Claim + evidence | **PASS** | Four retained-wheel dogfood receipts + authoritative readback |
| 9 | No auto verification/promotion/task success/mission completion | **PASS** | Task `pending -> pending`, mission `draft -> draft`, no forbidden promotion events in retained-wheel dogfood |
| 10 | Artifact tamper/digest mismatch blocks evidence admission | **PASS** | Runtime advisory tamper test |
| 11 | Structural analogy is deterministic across fresh processes | **PASS** | Cross-process SHA-256-seeded VSA test |
| 12 | Math donor and Lab adapter tests pass | **PASS** | Donor Rust 17/17 + `cargo check`; Lab Math 15/15 |
| 13 | Forge traversal/symlink/secret/size protections fail closed | **PASS** | Forge 8/8; live fixture excluded `.env` and escaping symlink |
| 14 | Native UI never labels proposed advisory verified | **PASS** | Swift projection tests + signed-app Labs UI visibly rendered `CALCULATION` + `UNVERIFIED` |
| 15 | Clean installed artifact + signed native dogfood | **PASS** | Retained wheel 938/57/12; signed bundle verified; four IPC engine runs; real native chat + native Math Lab run; final Lab runtime live Swift 4/4 |

**Acceptance total: 15 PASS / 0 FAIL / 0 BLOCKED.**

## Exact validation counts

- Final source-tree Python: **938 passed / 57 skipped / 12 deselected / 0 failed**.
- Retained-wheel Python from site-packages: **938 passed / 57 skipped / 12 deselected / 0 failed**.
- Final Swift normal: **35 passed / 4 live skipped / 0 failed**.
- Final Swift live against `~/.capt-inversion-labs`: **4 passed / 0 failed** in 60.894 seconds.
- Focused Math: 15; Analogy+Consensus: 15; Forge: 8; governed Lab runtime: 9; targeted authority/security/model/replay regression: 55.
- Original CAPTLang Math donor: **17 Rust tests passed**, `cargo check --all-features` passed.

The retained-wheel CLI regression used a temporary `capt_cli.py` symlink that pointed to the installed site-packages copy because eleven existing tests intentionally invoke `python capt_cli.py` relative to CWD. That accommodation did not import the worktree package.

## Native application / coexistence

- Bundle: `Inversion Labs CAPT.app`
- Bundle identifier: `com.inversionlabs.capt.lab`
- Development Team: `49FBXNL38U`
- Lab state root: `~/.capt-inversion-labs`
- Core state root remains: `~/.capt`
- External Lab override: `CAPT_LAB_STATE_DIR`
- Child CAPT processes receive the Lab root through CAPT's canonical `CAPT_STATE_DIR` contract.
- Lab encrypted session cache: `~/.capt-inversion-labs/ui/native_sessions.enc`, mode `0600`, Keychain-backed AES-GCM key.
- Plaintext searches for the native dogfood prompt and response token returned zero matches.

During Lab installation the golden installed core source marker, core wheel hash, and core ledger file hash were unchanged.

## Native dogfood nuance

The signed app completed one full native chain on source `819b94f…`: real local chat -> bound approval -> human approval -> Ollama DriverRun -> `awaiting_verification` task -> Labs -> Math advisory -> DriverRun/Claim/Evidence -> visible `UNVERIFIED`.

That UI run used the first exact-source installation wheel. Its `lab.math` implementation digest is byte-identical to the retained final wheel's `lab.math` implementation digest. The runtime was then repinned to the retained wheel; all four engines and all four live Swift runtime tests were rerun against that retained wheel.

A later macOS Accessibility attempt to repeat the already-proven Labs button after the repin reported the button enabled but did not deliver the Swift action; no DriverRun was created and the attempt is not counted. `CAPTRuntimeClient.connect()` explicitly drops and reopens the socket, and the final live shutdown/rebootstrap/reconnect test passed. This is retained as an automation limitation, not execution evidence.

## Operational use

R1 is suitable now for internal:

- mathematical and selected physics calculations where the exposed operation is explicitly implemented;
- structural analogy and cross-domain mapping;
- multi-perspective belief/uncertainty aggregation;
- read-only repository archaeology and gap finding;
- generating bounded SIGMA implementation briefs;
- ForgeProof-style self-review inputs;
- CAPT-on-CAPT analysis before governed software mutation/promotion.

For any output that matters consequentially, continue to use CAPT's independent verification / ClaimGuard / human approval path rather than treating the Lab engine result as truth.

## Next development boundary

R1 should dogfood real Inversion Labs work before adding more donor engines. New engines must earn admission operation-by-operation with provenance, deterministic or bounded behavior, focused tests, honest epistemic classification, and the same non-promotion rule. Do not re-import the old bioCAPT authority model to gain convenience.
