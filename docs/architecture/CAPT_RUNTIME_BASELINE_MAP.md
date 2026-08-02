# CAPT Runtime — Repository Forensic Baseline Map (Gate 0)

**Status:** Accepted (Gate 0 artifact)
**Branch:** `feat/capt-runtime-m0a-contract-state-proof`
**Base commit:** `022f970cc05a59876394db9e46d1206c3a84e776` (`origin/docs/capt-runtime-architecture-spec`)
**Base of architecture branch:** `e215a9e` on `origin/main` (spec branch = main + 3 docs commits, no code delta)
**Method:** source and test inspection, not documentation reading. Documentation was cross-checked against code and treated as unreliable where it disagreed.

## 1. Measured baseline

| Measure | Value | How measured |
|---|---|---|
| Tracked files | 123 | `git ls-files \| wc -l` |
| Python files | 77 | `git ls-files \| grep '\.py$'` |
| Python LOC | 16,498 | line count over tracked `.py` |
| TypeScript files | 0 | `find . -name '*.ts' -o -name 'package.json' -o -name 'tsconfig.json'` → empty |
| Test files | 31 under `tests/` | `git ls-tree` |
| Baseline test result | `361 passed, 44 skipped`, exit 0, 4.55s | `python3 -m pytest -q` (Python 3.9.6, pytest 8.4.2) |
| Skip cause (all 44) | `anti-token-extraction upstream package not installed in this env` | `pytest -q -rs` |
| Pre-existing failures | none observed | same run |

The 44 skips are a single environmental cause (an unpinned optional upstream package). They are **not** masked and **not** attributable to product code. No pre-existing failure is being hidden by this work.

## 2. Current runtime and package layout

Single Python package `capt_solo` (distribution name `capt-solo`, version 0.4.1, `requires-python >=3.8`, setuptools backend, zero runtime third-party dependencies).

```
capt_solo/
├── api.py              public facade (health(), re-exports)
├── core/               config (paths, CAPT_SOLO_HOME), errors (exception hierarchy)
├── ctp/journal.py      Cognitive Transaction Protocol: append-only JSONL journal
├── khsb/bus.py         in-process signal bus (publish/subscribe/request/reply/ack)
├── memory/             SQLite memory engine (1364 LOC), CSG, context builder, trust,
│                       antitoken, dedupe, normalize, pipeline, search, secrets, models
├── lifecycle/          memory lifecycle engine, sessions+checkpoints, procedures,
│                       prospective, semantic, feedback, manager
├── foundry/            skill_foundry, registry (CapabilityRegistry), proof (ProofEngine),
│                       claimguard, governance, bubble, harness, workflow_proof,
│                       columns, composition, curator
├── components/         anti_token_extraction adapter (pinned external component)
├── plugin/             Hermes plugin surface (818 LOC, ~40 capt_* tools)
└── skills/             8 SKILL.md documents
capt_cli.py             CLI entry (397 LOC)
verify_runtime.py       610-LOC runtime self-verification harness
tests/                  31 pytest modules
```

## 3. Component classification against the CAPT Runtime Architecture Spec

Legend: **IR** implemented and reusable · **PI** partially implemented · **DC** disconnected · **INC** incompatible · **PO** planned only · **ABS** absent · **UNC** unclear.

| # | Concept in spec | Existing artifact | Class | Evidence | M0-A disposition |
|---|---|---|---|---|---|
| 1 | Language-neutral contract source | none | **ABS** | no `contracts/`, no `.json` schema, no IDL anywhere in tree | Create `contracts/schema/` |
| 2 | Generated TS bindings | none | **ABS** | 0 `.ts` files, no `package.json` | Create `contracts/generated/typescript/` |
| 3 | Generated Python bindings | none | **ABS** | all Python types are hand-written dataclasses | Create `contracts/generated/python/` |
| 4 | Data models / schemas | `capt_solo/memory/models.py`, `foundry/registry.py:Capability`, `foundry/proof.py:Evidence` | **PI / INC as contract source** | hand-written `@dataclass`, `asdict()` serialization, no schema version on the object, no discriminated unions, `Dict[str, Any]` used in `creation_metadata`, `compatibility_matrix`, `meta` | Do not touch. Not adopted as canonical contract source (would make Python authoritative — violates spec §18) |
| 5 | Transactional state store | `capt_solo/memory/engine.py` (SQLite, WAL, `schema_version` table, versioned migrations 1→4, verified pre-migration backup) | **IR (as memory store), PI (as runtime state store)** | `engine.py:86-90` sqlite3 + WAL + FK on; `_init_schema`; `_backup_before_migration` | Reuse the **pattern** (SQLite + WAL + versioned schema + backup gate). Do **not** extend `memory.db` with runtime aggregates: different lifecycle, different authority owner. New store file, same conventions |
| 6 | Append-only event ledger | `capt_solo/ctp/journal.py` (append-only JSONL, fsync per record, integrity re-parse) | **PI** | `journal.py:116-129` fsync append; `_apply` reducer; `Receipt` | Adapt concepts, do not reuse implementation: journal has **no** stream version, no aggregate binding, no schema version, no payload digest, no global sequence, no optimistic concurrency, and is not in the same transaction as any state mutation |
| 7 | Outbox / post-commit dispatch | none | **ABS** | `grep -rni outbox` → 0 hits outside the new spec docs | Implement |
| 8 | Optimistic concurrency / aggregate versions | none | **ABS** | no `expected_version` anywhere; `Capability.updated_at` is a timestamp, not a version | Implement |
| 9 | Aggregate ownership | none formalized | **ABS** | `Governance._act` (`foundry/governance.py:64`) wraps arbitrary callables in a CTP tx; any subsystem can mutate any table via the shared `conn` | Implement and enforce structurally |
| 10 | Policy engine / PolicyDecision | none | **ABS** | `grep -rni policy` → only `export_policy`, `retention_policy`, `permission_policy_changed` string constant | Implement `PolicyDecision` contract + kernel |
| 11 | Governance kernel | `capt_solo/foundry/governance.py` (137 LOC) | **PI / different concept** | it is a *CTP-wrapping audit facade* over foundry mutations (`publish_skill`, `approve_capability`, `install_bubble`), not an authorization kernel. No deny path, no scope, no lease | Do not touch. Mapping recorded in §5 |
| 12 | Capability / permission concept | `capt_solo/foundry/registry.py:CapabilityRegistry` | **PI / semantically different** | a *capability catalogue* with lifecycle `candidate/validated/verified/deprecated/revoked/degraded/experimental` answering "can CAPT do X?". It has **no** subject, resource, scope, operations, grant, lease, reservation, use limit, validity window, or issuing authority | Do not touch. New `CapabilityAggregate` covers authorization; naming collision resolved in §5 |
| 13 | ClaimGuard | `capt_solo/foundry/claimguard.py:ClaimGuard` | **PI / different layer** | operates on **natural-language text** (`verify_claim(text)`), downgrades wording via `CLAIM_TRIGGERS`. Returns `ClaimVerdict{supported, language, missing}`. No `ClaimRecord`, no `EvidenceRecord` link, no accept/qualify/reject/**escalate** decision enum, no promotion state | Do not touch. New `ClaimGuardDecision` contract is structural, not lexical. Mapping in §5 |
| 14 | Verification pipeline | `capt_solo/foundry/proof.py:ProofEngine` + `foundry/harness.py:ValidationHarness` (12 stages) | **PI, reusable later** | `ProofEngine.aggregate()` returns satisfied/unsatisfied requirements; evidence has sha256, TTL, expiry | Not wired in M0-A. Candidate adapter for M0-B/M0-C verification strategies |
| 15 | Evidence record | `capt_solo/foundry/proof.py:Evidence` | **PI** | has `sha256_of`, `type`, `scope`, TTL, `is_valid()`; lacks schema version, correlation/causation, mission binding | New `EvidenceRecord` contract; adapter deferred |
| 16 | Checkpoint | `capt_solo/lifecycle/sessions.py:checkpoint()` + `session_checkpoints` table (`engine.py:341`) | **PI / different scope** | session-scoped restart packet (objective, progress, CSG + antitoken render). Not a runtime manifest: no aggregate versions, no lease state, no ledger position, no outbox state, no policy digest, no integrity digest | Do not touch. New `CheckpointManifest` |
| 17 | Replay | `CTPRuntime._load()` replays the JSONL journal into memory | **PI** | `journal.py:66-82` — a real replay reducer, but per-transaction only; no aggregate state, no duplicate-tolerance test, no checkpoint+tail equivalence | Adapt concept; new implementation |
| 18 | Memory / ContextPack contract | `capt_solo/memory/context.py:build_context()` → `ContextBuildResult` | **IR (for memory), ABS (as disclosure-controlled ContextPack)** | returns `ContextItem`s with trust; **no** sensitivity classification, consent scope, redaction state, or downstream-use restriction fields required by spec §16 | Out of M0-A scope (spec §16 is a driver-boundary concern → M0-B) |
| 19 | Lifecycle models | `capt_solo/lifecycle/lifecycle.py:LifecycleState`, `MemoryTier`, `RetentionClass`, `_valid_transitions_from` | **IR for memory, INC for missions/tasks** | it is a *memory* lifecycle (`candidate/active/archived/...`), not a mission or task lifecycle | Reuse the transition-table pattern only |
| 20 | Mission / Task / TaskGraph | none | **ABS** | no mission, task, objective, or dependency concept in the tree | Implement |
| 21 | Driver / execution boundary | none | **ABS** | closest is `foundry/harness.py` (in-process skill validation), not an external driver host | M0-A: contract + state model only, integration explicitly disabled |
| 22 | Test framework | pytest 8.4.2, `tests/conftest.py` with autouse `isolated_home` via `reset_paths_for_test` | **IR** | `conftest.py:15-18` | Reuse. New tests follow the same isolation contract |
| 23 | Build tooling | setuptools via `pyproject.toml`; no `[tool.pytest]`, no ruff/mypy/black config; `ruff`, `mypy`, `black`, `flake8` **not installed** on host | **PI** | `which ruff mypy black flake8` → empty | Add byte-stability + drift checks that need no new dependency |
| 24 | CI | `.github/workflows/release-security.yml` — pytest+coverage≥80, `verify_runtime.py`, `doctor.sh`, build, wheel smoke, pip-audit, `compileall`, grep-based security invariants, gitleaks | **IR** | file read in full | Extend with a contracts drift + parity job |
| 25 | ADR / architecture convention | **none** as files; `capt_solo/skills/capt-arch-decision/SKILL.md` describes the practice; spec doc embeds "ADR-001…006" as sections | **PO** | `find -iname '*adr*'` → only the skill dir | Create `docs/architecture/decisions/` and number from ADR-0101 to avoid collision with spec-embedded ADR-001…006 |
| 26 | Signal bus | `capt_solo/khsb/bus.py:KHSB` | **IR / DC for this purpose** | in-process, synchronous dispatch inside `publish()`, no durability, no ordering guarantee, no ack persistence | Matches spec's *EphemeralSignalBus*, **not** the outbox. Do not use for authoritative events |

## 4. Overlap and contradiction with the new spec

### Genuine overlap (reuse pattern, not code)
- SQLite + WAL + `schema_version` + migration-with-verified-backup (`memory/engine.py`) → adopted as the persistence convention for the new runtime store.
- Append-only + fsync + reducer-on-load (`ctp/journal.py`) → adopted as the ledger convention.
- pytest isolated-home fixture convention (`tests/conftest.py`) → adopted for runtime tests.
- Lifecycle transition-table validation (`lifecycle/lifecycle.py`) → adopted as the state-machine convention.

### Contradictions that forbid direct reuse

| Contradiction | Spec requirement | Current code | Resolution |
|---|---|---|---|
| C1 | "Capability" = scoped authorization to act (grant/lease/reservation) — spec §9 | `Capability` = a catalogued skill CAPT may possess | Namespace separation: new types live in `capt_runtime`/`contracts`; `capt_solo.foundry.registry.Capability` untouched and renamed **only in documentation** as *CapabilityCatalogEntry* |
| C2 | ClaimGuard decides `accept/qualify/reject/escalate` on a structured `ClaimRecord` — spec §12.2 | ClaimGuard rewrites English sentences | New structural ClaimGuard. Existing lexical guard remains a downstream presentation control |
| C3 | Events must carry stream id, stream version, schema version, correlation, causation, digest — spec §13 | CTP events carry `{type, tx_id, timestamp, …}` only | New `EventEnvelope`; CTP journal untouched |
| C4 | Aggregate has exactly one authoritative mutator — spec §6 | `Governance._act(fn)` executes any callable against a shared connection | New store refuses cross-aggregate event append (enforced, tested) |
| C5 | Authoritative events dispatch **only** after commit — spec §5 | `KHSB.publish()` dispatches synchronously in-process with no commit relationship | Outbox with post-commit dispatch; KHSB explicitly classified as ephemeral-only |
| C6 | Contracts language-neutral at source — spec §18 / invariant 14 | all types are Python `@dataclass` | JSON Schema 2020-12 canonical source; Python and TypeScript both generated |
| C7 | No unbounded dictionaries in security-critical contracts | `Dict[str, Any]` in `meta`, `creation_metadata`, `compatibility_matrix`, `export_policy` | New contracts use discriminated unions; a single explicit, validated extension boundary |

### No duplicate canonical contract
Gate 0 exit criterion: *no proposed contract duplicates an existing canonical CAPT contract without an explicit migration decision.* Verified — the only name collisions are `Capability`, `ClaimGuard`, `Evidence`, and `checkpoint`, all of which are **semantically different concepts** at a different layer, documented in §5 and ADR-0103. No existing contract is migrated, deprecated, or modified by M0-A.

## 5. Term mapping (existing → new)

| Existing CAPT Solo term | Location | New runtime term | Relationship |
|---|---|---|---|
| `Capability` (registry) | `foundry/registry.py:57` | *CapabilityCatalogEntry* (conceptual) | Disjoint. New `Capability`/`CapabilityGrant` describes authorization, not possession |
| `CapabilityRegistry.verify()` | `foundry/registry.py:194` | `VerificationResult` | Analogous intent, incompatible shape |
| `ClaimVerdict` | `foundry/claimguard.py:43` | `ClaimGuardDecision` | New type is structural (`accept/qualify/reject/escalate`) and claim-record bound |
| `Evidence` | `foundry/proof.py:59` | `EvidenceRecord` | Adapter candidate for M0-B, not adapted in M0-A |
| `CTPRuntime` / `Receipt` | `ctp/journal.py` | `EventLedger` + `Outbox` + `CommandLog` | Concept ancestor; not reused |
| `session_checkpoints` row | `memory/engine.py:341` | `CheckpointManifest` | Disjoint scope (memory session vs runtime state) |
| `KHSB` | `khsb/bus.py` | `EphemeralSignalBus` | Direct match to spec §4.4 ephemeral role |
| `Governance` | `foundry/governance.py:50` | `AuditStream` (partial) | Audit facade, not `GovernanceKernel` |
| `ProofEngine` | `foundry/proof.py:125` | `VerificationPipeline` (future strategy) | Deferred to M0-B |

## 6. Do-not-touch list for M0-A

Frozen for this gate. Any diff to these files invalidates the M0-A evidence chain:

```
capt_solo/**            (entire package)
capt_cli.py
verify_runtime.py
verify.sh doctor.sh install.sh uninstall.sh
tests/**                (all 31 pre-existing modules)
docs/*.md               (all pre-existing docs)
```

M0-A adds only:
```
contracts/**
capt_runtime/**
tests/runtime/**
docs/architecture/**    (new files only)
.github/workflows/capt-runtime-contracts.yml
pyproject.toml          (packaging entries for the two new packages only)
```

## 7. Environment facts relevant to verification

| Fact | Value |
|---|---|
| Host | macOS 26.4.1, arm64 |
| Default `python3` | 3.9.6 (`/usr/bin/python3`), pytest 8.4.2, jsonschema 4.25.1 present |
| Second interpreter | `/opt/homebrew/bin/python3.12`, pytest 9.0.3 |
| Node | v22.22.2; `tsc` 6.0.3 on PATH (global) |
| TS compile+execute proven | `tsc --strict` + `node` round trip, exit 0 |
| Not installed | ruff, mypy, black, flake8 |
| CI Python matrix | 3.10, 3.12 |

**Consequence for M0-A:** generated Python bindings must be import-clean on **3.9** (host) through **3.12** (CI). This forbids `X | Y` type syntax at runtime and `match` statements in generated Python. Lint/format/type-check commands cannot be run as "repository-appropriate equivalents" because no such tool is configured or installed; the substitute gates are `compileall`, deterministic-regeneration byte-equality, and `tsc --strict --noEmit`. This is recorded as an environment limitation, not a product failure.
