# CAPT Core v0.5 Public API Stability

- **Status:** Current v0.5 compatibility declaration
- **Version:** `0.5.0`
- **Architecture:** ADR-0008 through ADR-0012
- **Artifact gate:** `tests/test_distribution_contract.py`

This document declares what an external user may depend upon in v0.5. It does
not promise that every shipped module is stable.

## Stability Tiers

| Tier | Promise |
|---|---|
| Stable | Maintained within the current major version; incompatible change requires deprecation or migration |
| Provisional | Public and tested; may evolve through a documented compatibility path |
| Experimental | Research or demonstration surface; no general compatibility promise |
| Internal | Implementation detail; no compatibility promise |

`capt_solo.api` is a stable convenience facade. It is not the only valid public
import path.

## Adoption Profiles

| Profile | Required imports | Dependencies | Persistence | Network | Tier | Installed smoke |
|---|---|---|---|---|---|---|
| Evidence | `capt_solo.evidence` | standard library | none unless caller chooses a store | none | Provisional | Evidence serialization round trip |
| Verification | `capt_solo.verification` | standard library, local Git for VSI capture | local JSONL only when `VerificationStore` is used | none | Provisional | equivalent and changed VSI comparison |
| Context | `capt_solo.contextpack` | standard library | none | none | Stable schema v1 | canonical round trip, validation, handoff |
| Transaction | `capt_solo.ctp` | standard library | explicit local append-only JSONL | none | Stable | commit receipt and chain integrity |
| Workspace | `capt_solo.workspace`, installed `capt` command | PyYAML, local Git for repository operations | explicit workspace files only | none | Provisional | import and CLI startup |
| Full runtime | `capt_solo.api` | PyYAML plus standard library | local SQLite and JSONL under `CAPT_SOLO_HOME` | none by default | Stable facade | isolated health check |

Profile smoke behavior is implemented by `tools/profile_smoke.py` and exercised
from both wheel and sdist environments.

## Package and Module Inventory

| Surface | Tier | Owner | Version | Compatibility and persistence | Artifact | Proof |
|---|---|---|---|---|---|---|
| `capt_solo` | Stable | Runtime SDK | 0.5 | `__version__` remains compatible | wheel + sdist | distribution contract |
| `capt_solo.api` | Stable | Runtime SDK | 0.5 | facade symbols preserved within v0 | wheel + sdist | `test_api.py`, installed runtime smoke |
| `capt_solo.core` | Stable | Core | 0.5 | config and error hierarchy preserved | wheel + sdist | API/runtime tests |
| `capt_solo.memory` | Stable | Memory | schema v5 | migrations are forward-only and backup-gated | wheel + sdist | memory and migration suites |
| `capt_solo.ctp` | Stable | Transactions | journal v0 | append-only event compatibility; no silent rewrite | wheel + sdist | CTP tests and installed smoke |
| `capt_solo.khsb` | Stable | Knowledge/coordination service | 0.5 | in-process API; no network behavior | wheel + sdist | KHSB/runtime tests |
| `capt_solo.lifecycle` | Stable | Lifecycle service | 0.5 | existing session/procedure APIs preserved | wheel + sdist | v0.3 lifecycle suites |
| `capt_solo.contextpack` | Stable | Context | schema v1 | canonical fixture and digest are permanent v1 sentinels | wheel + sdist | ContextPack fixture and installed smoke |
| `capt_solo.plugin` | Stable | Plugin SDK | manifest 0.5 | tool names retained or deprecated explicitly | wheel + sdist | plugin suites and artifact-data gate |
| `capt_solo.evidence` | Provisional | Evidence | 0.5 | canonical new evidence record; stored records require adapters before incompatible change | wheel + sdist | evidence core/workspace/CLI/adversarial suites |
| `capt_solo.verification` | Provisional | Verification | VSI 0.5 | VSI and JSONL records evolve compatibly | wheel + sdist | VSI suite and installed smoke |
| `capt_solo.ontology` | Provisional | Identity/Ontology | ontology 0.5 | shared vocabulary; no claim of universal ontology completeness | wheel + sdist | knowledge/learning imports and distribution gate |
| `capt_solo.knowledge` | Provisional | Knowledge | 0.5 | specialized evidence type retained for compatibility | wheel + sdist | knowledge/evidence suite |
| `capt_solo.foundry` | Provisional | Foundry service | bubble v2 | persisted Foundry schemas remain migration-governed | wheel + sdist | v0.4 Foundry suites |
| `capt_solo.workspace` | Provisional | Workspace service | workspace v0.5 | writes only through explicit commands | wheel + sdist | workspace and security suites |
| `capt_solo.continuity` | Provisional | Continuity service | CVE 0.2 | policy and receipts remain versioned v0.2 | wheel + sdist | continuity suites |
| `capt_solo.execution` | Provisional | Execution service | 0.5 | capability boundary types may evolve compatibly | wheel + sdist | execution-boundary suite |
| `capt_solo.engines` | Experimental | Domain engines | 0.5 | no foundational API guarantee | wheel + sdist | math/physics/invention suites |
| `capt_solo.learning` | Experimental | Learning service | 0.5 | research maturity; persisted changes remain governed | wheel + sdist | continuous/DREAM suites |
| `capt_solo.research` | Experimental | Research adapters | 0.5 | health/adapters only; missing external modules stay absent | wheel + sdist | research adapter suite |
| `capt_solo.pulse` | Experimental | Optional model gateway | 0.5 | disabled by default; explicit configuration required | wheel + sdist | release-boundary suite |
| other unlisted submodules | Internal | owning package | n/a | no compatibility promise | may ship | package tests only |

No importable `capt_solo.*` package is intentionally excluded from v0.5
artifacts. `capt_solo.skills` is a data directory, not a Python package.

## Canonical and Specialized Record Ownership

| Record | Tier | Ownership and compatibility |
|---|---|---|
| `capt_solo.evidence.EvidenceRecord` | Provisional canonical | default for new public evidence workflows |
| `capt_solo.verification.VerifiedStateIdentity` | Provisional | state identity for current VSI verification |
| `capt_solo.verification.VerificationRecord` | Provisional | current verification attestation-like record |
| `capt_solo.verification.VerificationEvidence` | Stable specialized | verifier execution evidence payload |
| `capt_solo.contextpack.ContextPack` | Stable schema v1 | deterministic context exchange record |
| `capt_solo.contextpack.ContextPackValidation` | Stable schema v1 | ContextPack gate result |
| `capt_solo.ctp.Receipt` | Stable specialized | transaction finalization receipt |
| `capt_solo.foundry.proof.Evidence` | Stable specialized | Foundry proof-store compatibility record |
| `capt_solo.knowledge.evidence.EvidenceRecord` | Provisional compatibility | Knowledge view; not the new general evidence default |
| `capt_solo.lifecycle.sessions.Checkpoint` | Stable specialized | session checkpoint format |
| `capt_solo.evidence.MissionCheckpoint` | Provisional specialized | mission recovery checkpoint |
| `capt_solo.foundry.governance.GovernanceReceipt` | Provisional specialized | governed Foundry operation receipt |
| continuity evidence and receipts | Provisional specialized | CVE v0.2 policy records |
| `capt_solo.memory.interfaces.MemoryRecord` | Provisional protocol | adapter-facing record |
| `capt_solo.memory.types.MemoryRecord` | Provisional taxonomy | converged-memory taxonomy record |

ADR-0009 and ADR-0012 prohibit silent record replacement. Future
`CheckpointRecord`, `ReceiptEnvelope`, and Subject/Actor/State/Scope references
are post-v0.5 design targets.

## CLI Contract

The installed command is `capt`. Command groups are classified as follows:

| Command group | Tier | Side effects |
|---|---|---|
| `capt doctor` | Stable | read-only; no persistence or network |
| `capt release validate` | Stable | read-only source/artifact semantic gate |
| `capt memory` | Stable | explicit local SQLite operations |
| `capt session` | Stable | explicit local session operations |
| `capt procedure` | Stable | explicit local procedure operations |
| `capt prospective` | Stable | explicit local prospective-memory operations |
| `capt retrieval` | Stable | explicit local feedback operations |
| `capt foundry` | Provisional | explicit local Foundry/governance operations |
| `capt canon` | Provisional | local facade operations |
| `capt verify` | Provisional | local verification command and JSONL record |
| `capt evidence` | Provisional | explicit local evidence operations |
| `capt continuity` | Provisional | local policy evaluation and explicit output |
| `capt mission` | Provisional | explicit checkpoint writes |
| `capt selfmod` | Provisional | explicit governed proposal/checkpoint writes |
| `capt workspace` | Provisional | source-workspace operations; writes only on explicit checkpoint/archive commands |
| `capt architecture` | Provisional | source-workspace registry inspection |

Subcommand arguments and exit codes documented in `docs/CLI.md` are part of the
same tier as their command group.

## Plugin Tool Contract

The Hermes plugin manifest is stable for v0.5. All 46 declared tools are shipped
in `capt_solo/plugin/plugin.json` and created by `capt_solo.plugin:get_plugin`:

```text
capt_store_memory
capt_search_memory
capt_get_memory
capt_begin_transaction
capt_commit_transaction
capt_abort_transaction
capt_send_message
capt_health
capt_export_project
capt_import_project
capt_build_context
capt_explain_context
capt_add_memory_relation
capt_detect_memory_conflicts
capt_review_memory_conflicts
capt_compress_memory
capt_memory_pipeline_status
capt_session_begin
capt_session_checkpoint
capt_session_resume
capt_session_status
capt_session_consolidate
capt_session_close
capt_promote_memory
capt_archive_memory
capt_pin_memory
capt_explain_memory_lifecycle
capt_create_procedure
capt_get_procedure
capt_record_procedure_run
capt_find_procedures
capt_add_prospective_memory
capt_list_pending_intents
capt_resolve_intent
capt_record_retrieval_feedback
capt_get_restart_context
capt_generate_skill
capt_validate_skill
capt_publish_skill
capt_query_capability
capt_verify_claim
capt_build_bubble
capt_validate_bubble
capt_install_bubble
capt_export_bubble
capt_inspect_proof
```

Compatibility applies to tool names and documented inputs/outputs. A
security-motivated removal may fail closed immediately and will be documented.

## Schemas and File Formats

| Format | Tier/version | Compatibility promise | Proof |
|---|---|---|---|
| ContextPack canonical JSON | Stable v1 | exact canonical fixture and digest | `test_contextpack_v1.py` |
| Memory SQLite | Stable schema v5 | forward migration with backup gate | migration suites |
| CTP JSONL journal | Stable v0 | append-only; unknown/corrupt records fail integrity | CTP suites |
| Knowledge Bubble manifest | Stable v2 | validation before install; prior versions handled explicitly | bubble suites |
| Plugin manifest JSON | Stable 0.5 | packaged and tool inventory tested | plugin/distribution suites |
| Verification JSONL | Provisional 0.5 | records remain readable through compatible parser changes | VSI suite |
| Evidence JSONL | Provisional 0.5 | `EvidenceRecord.to_dict/from_dict` compatibility | evidence/distribution suites |
| Mission checkpoint JSON | Provisional 0.5 | bounded path and explicit divergence | evidence workspace suites |
| Session checkpoint storage | Stable subsystem format | migration-governed with Memory schema | session/migration suites |
| CVE policy/pack/receipt | Provisional v0.2 | versioned policy and digest validation | continuity suites |
| `architecture/*.schema.json` | Provisional workspace schemas | source-workspace compatibility; additive changes preferred | workspace suites |
| `architecture/registry.yaml` | Internal governance format | schema/fitness validated; not runtime SDK | architecture fitness suite |

## Deprecation and Replacement

Stable surfaces receive a documented deprecation period within major version
zero where practical. Persisted-state changes require migration and backup.
Provisional surfaces may change sooner but still require release notes,
compatibility handling where state exists, and installed-artifact tests.
Experimental surfaces may be removed from a later artifact when their absence is
documented and no stable package depends upon them.
