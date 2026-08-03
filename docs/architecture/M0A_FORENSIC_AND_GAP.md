# M0-A Forensic Implementation Map & Gap Analysis

**Session:** HY3 independent review of `capt-m0a` (HEAD `6665a6a`)
**Method:** source + test inspection, not documentation. Docs cross-checked against code and treated as unreliable where they disagreed.
**Scope guard:** M0-A only. M0-B, M0-C, real ExecutionDriver, distributed infra NOT in scope (ADR-0111).

---

## Phase 1 — Repository Forensics

Legend: IM=Implemented, PA=Partial, DC=Disconnected, PL=Planned, AB=Absent, UN=Unclear.
"Source" cites the file the claim is verified against.

| # | Component (spec) | Class | Source (verified) | Notes |
|---|---|---|---|---|
| 1 | Runtime trust boundaries (gov/cog/exec/verif/claim planes) | IM | `capt_runtime/authority.py:25-40` | Deny-by-default act→actor matrix; `require_authority()` enforced in every service method. |
| 2 | Transactional event ledger | IM | `capt_runtime/store.py:33-44,83-86,396-424` | SQLite WAL; `events` table; hash-chain `chain_next()`; `verify_chain()` recomputes. |
| 3 | Checkpointing | IM | `capt_runtime/checkpoint.py:51-128,138-167` | `create_checkpoint()` derives `recoveryState` from open reservations; `verify_checkpoint()` rejects corruption/schema mismatch. |
| 4 | Lifecycle / state machines | IM | `capt_runtime/aggregates/*.py` | Mission/Task/Capability/Claim/DriverRun each with explicit `*_TRANSITIONS` + terminal sets. |
| 5 | ClaimGuard (promotion gate) | IM (gate) | `capt_runtime/aggregates/claim_driver.py:120-169` | Completion claim cannot reach `accepted` without independent `verified` status + evidence. Legacy `capt_solo/foundry/claimguard.py` is DC (not imported). |
| 6 | ContextPack | AB (M0-A) | — | Not in `capt_runtime`. Exists in `capt_solo/memory/` but out of M0-A scope. |
| 7 | Knowledge Bubbles | AB (M0-A) | ADR-0111 #8 | `capt_solo/foundry/bubble.py` explicitly untouched. |
| 8 | Memory engine | DC | `capt_runtime/contracts.py` (no import of `capt_solo`) | `capt_solo/memory/engine.py` exists; `capt_runtime` does NOT import it (grep-verified). Reuse pattern only (ADR-0104). |
| 9 | Governance kernel (decision logic) | PL | `capt_runtime/services.py:81-120` | Runtime RECORDS `PolicyDecision` authored by `governance_kernel`; it does not implement the kernel's decision logic. Boundary IM, logic PL. |
| 10 | Permissions / capabilities | IM | `capt_runtime/aggregates/capability.py` | Full lifecycle: grant/lease/reserve/finalize/revoke/expire; `scope_contains()`; `check_lease()` revalidates pre-side-effect. |
| 11 | Plugin system | AB (M0-A) | — | `capt_solo/plugin/` exists, DC from `capt_runtime`. |
| 12 | IPC / bridge | AB (M0-A) | ADR-0111 #5 | No network/socket in `capt_runtime` (grep-verified). `capt_solo/khsb/bus.py` DC. |
| 13 | Existing schemas (CAPT Core) | PA/INC | `capt_solo/memory/models.py`, `foundry/registry.py` | Hand-written `@dataclass`, `asdict()`, no schema version, no discriminated unions. Not adopted as canonical (ADR-0101). |
| 14 | Canonical contract source (M0-A) | IM | `contracts/schema/*.json` (13 files) | JSON Schema 2020-12, single `CONTRACT_SCHEMA_VERSION=1.0.0`. |
| 15 | Generated bindings (TS+Py) | IM | `contracts/generated/{typescript,python}/` | `generate.py` emits both; `check_drift.py` green (11 files match source). |
| 16 | Aggregate ownership model | IM | `capt_runtime/aggregates/*.py` `OWNED_FIELDS` | Disjoint-field assertion tested (`test_aggregates::test_ownership_disjoint`). |
| 17 | EventEnvelope | IM | `contracts/schema/event.schema.json`, `capt_runtime/commands.py:57-95` | Store assigns `streamVersion`/`globalSequence`/`payloadDigest` (caller cannot forge). |
| 18 | CheckpointManifest | IM | `contracts/schema/checkpoint.schema.json`, `capt_runtime/checkpoint.py` | |
| 19 | Replay support | IM | `capt_runtime/replay.py` | `full_replay` + `checkpoint_replay`; reducers skip `version<=current` (idempotent). |
| 20 | Conformance tests | IM | `tests/capt_runtime/` (9 files, 51 tests) | Includes two-process restart proof (`test_replay.py:67`). |

---

## Phase 2 — Gap Analysis (repo vs approved spec)

**Missing contracts (M0-A):** none. All 15 required M0-A contract types present in `contracts/schema/`.

**Deferred (correctly out of M0-A, ADR-0111):** real ExecutionDriver; M0-B read-only driver proof; M0-C governed write; Kafka/Redis; multi-agent; Knowledge Bubble execution; scheduler policy.

**Duplicate concepts:**
- `capt_solo/memory/engine.py` (SQLite+WAL memory store) vs `capt_runtime/store.py` — different lifecycle/authority owner. Resolution: reuse PATTERN, separate file (ADR-0104). Do NOT merge.
- `capt_solo/foundry/claimguard.py` vs `ClaimAggregate.decide()` — M0-A re-implements the promotion GATE as contract; legacy engine disconnected.

**Conflicting abstractions:**
- `capt_solo` uses `Dict[str,Any]` + dataclass `asdict()`; M0-A uses generated contracts + `canonical_json` (deterministic digest). Resolution: M0-A canonical (ADR-0101); `capt_solo` not adopted as source.

**Migration candidates (future phases, do not touch now):**
- `capt_solo/foundry/registry.py:Capability` → wrap via `CapabilityAggregate` in M0-B.
- `capt_solo/memory/engine.py` → wrap SQLite+WAL+versioned-migration pattern for M0-B runtime store if needed.

**Modules to leave untouched:** `capt_solo/foundry/bubble.py`, `capt_solo/memory/engine.py` (pattern only), `capt_solo/plugin/`, `capt_solo/khsb/bus.py`, `capt_solo/foundry/claimguard.py`.

**Modules to wrap (not rewrite):** memory engine (SQLite+WAL), capability registry.

**Technical debt / architectural risk:**
1. `capt_runtime/contracts.py:15-17` injects generated Python bindings via `sys.path.insert`. Intentional (keeps generated code out of package), but fragile to layout changes.
2. Single SQLite file = no horizontal scale. By design (ADR-0104); M0-B may revisit.
3. 44 skipped tests = optional `anti-token-extraction` upstream package absent in this env. Environmental, not product. Not masking any failure.
4. Cross-language parity test requires `node` on PATH (see Environment Limitations).

---

## Phase 3 — ADR Freeze

All 10 required decision topics are covered by Accepted ADRs (dated 2026-08-02). No new ADR required; freeze confirmed.

| Required topic | ADR | Status |
|---|---|---|
| Canonical schema language | 0101 | Accepted |
| Aggregate ownership | 0103 | Accepted |
| Event ledger semantics | 0104 | Accepted |
| Replay semantics | 0108 | Accepted |
| Checkpoint manifests | 0109 | Accepted |
| Capability lifecycle | 0107 | Accepted |
| Driver trust boundary | 0110 | Accepted |
| Generated bindings | 0102 | Accepted |
| Outbox pattern | 0105 | Accepted |
| Optimistic concurrency | 0106 | Accepted |

(Also present: 0111 M0-A exclusions.) No implementation proceeds beyond these; M0-B/C deferred.

---

## Phase 4 — M0-A Implementation Status

All 13 required artifacts present and verified:
- language-neutral schema source ✓ · TS bindings ✓ · Py bindings ✓
- aggregate ownership model ✓ · Mission/Task/Capability/Claim aggregates ✓
- EventEnvelope ✓ · CheckpointManifest ✓ · transactional ledger ✓ · replay ✓ · conformance tests ✓

No M0-A source was modified this session: the implementation pre-existed at HEAD `6665a6a` and is faithful to spec. Re-implementation would risk regressing a green suite.

---

## Triple Recursion (Construct / Adversarial / Reconcile)

**EventEnvelope (construct):** store assigns version/sequence/digest. *Adversarial:* can a caller forge ordering? `envelope()` leaves placeholders; `commit_command` overwrites them inside the txn and calls `require("EventEnvelope", envelope)` before durable (store.py:278-305). *Reconcile:* safe — caller cannot set `streamVersion`/`globalSequence`/`payloadDigest`.

**Capability check_lease (construct):** revalidates pre-side-effect. *Adversarial:* lease widening? `activate_lease` enforces `scope_contains(grant, lease)` + op subset + window subset (capability.py:122-140). *Reconcile:* escalation structurally impossible.

**Replay (construct):** reducers skip `version<=current`. *Adversarial:* duplicate delivery double-counts? `full_replay` twice → identical digest (test_replay.py:86). *Reconcile:* idempotent at (stream,version).

**Checkpoint (construct):** `recoveryState` derived from open reservations. *Adversarial:* can a caller declare `clean` while consequential work open? `create_checkpoint` computes it, never accepts (checkpoint.py:83-89). *Reconcile:* cannot mask unresolved work.

**Outbox/dispatch (construct):** dispatch strictly post-commit. *Adversarial:* inline dispatch before commit? `_commit` calls `dispatch()` only after `commit_command` returns (services.py:43-52). *Reconcile:* at-least-once by construction; subscribers must be idempotent (tested).

---

## Verification

- **Repository map:** above (Phase 1 table).
- **Gap analysis:** above (Phase 2).
- **ADR list:** 0101–0111, all Accepted; freeze confirmed.
- **Files created this session:** `docs/architecture/M0A_FORENSIC_AND_GAP.md` (this file). No M0-A runtime source created/modified.
- **Files modified this session:** none.
- **Tests executed:** `pytest tests/capt_runtime` → 51 passed; full `pytest` → 412 passed, 44 skipped; `check_drift.py` → OK.
- **Commands executed (exit codes):** `pytest tests/capt_runtime -q` → 0; `pytest -q` (node on PATH) → 0; `contracts/tools/generate.py` → 0; `contracts/tools/check_drift.py` → 0; `node contracts/tools/ts_parity.mjs` → 0; grep forbidden-imports → 1 (clean); grep capt_solo-import → 1 (clean).
- **Environment limitations:** `node` present at `/Users/knowurknot/.local/bin/node` but NOT on default `subprocess` PATH, so `test_cross_language_fixture_parity` fails under bare `pytest` (passes when `PATH` includes that dir). Runtime itself has zero JS dependency. 44 skips = absent optional `anti-token-extraction` package.
- **Remaining blockers:** none for M0-A proof. Recommended (not applied): make the parity test locate `node` robustly so bare `pytest` is green; deferred to Captain authorization.

---

## Part 1 Additions — Evidence Confidence, Ownership, Trust, Threats, Maturity

### Evidence-confidence legend
- **High** — directly demonstrated by source and tests.
- **Medium** — strongly supported but not exhaustively exercised.
- **Low** — inferred from incomplete evidence.

### Aggregate ownership matrix (M0-A)

| Aggregate | Owns | May read | May mutate | May observe | May emit authoritative events |
|---|---|---|---|---|---|
| MissionAggregate | mission lifecycle/objectives/criteria/terminal | task graph, policy decisions (ref) | only itself | ledger, checkpoint | MissionCreated, PolicyEvaluated, MissionStateChanged |
| TaskAggregate | task lifecycle/attempts/assignment/recovery/deps | mission (ref) | only itself | ledger, checkpoint | TaskCreated, TaskTransitioned |
| CapabilityAggregate | grant/lease/reservations/consumptions/revocation | policy decision (ref) | only itself | ledger, checkpoint | CapabilityGranted/LeaseActivated/UseReserved/UseFinalized/*Revoked |
| DriverRunAggregate | driver-run lifecycle/reconciliation/workOrderVersion | mission/task (ref) | only itself | ledger, checkpoint | DriverRunCreated, DriverRunStateChanged (state-model only in M0-A) |
| ClaimAggregate | claim statement/evidence/verification/promotion/guard | mission/task (ref) | only itself | ledger, checkpoint | ClaimCreated, EvidenceRecorded, ClaimVerified, ClaimGuardDecided |

No aggregate may mutate another's OWNED_FIELDS; disjointness is asserted by `test_aggregates::test_ownership_disjoint` (High).

### Trust-boundary diagram

```
Trusted CAPT domains
────────────────────────────────
Governance
Cognition
Capability authorization
Task state
Verification
ClaimGuard
Event ledger
Checkpointing
────────────────────────────────
Untrusted execution boundary
ExecutionDriver
External harness
External model/tool observations
```

All data crossing from the untrusted boundary inward is `trust: untrusted` until CAPT validates and promotes it (High — `driver-observation-is-untrusted` fixture; `claim_driver.py:120-169`).

### Threat-to-control mapping

| Control | Protects against |
|---|---|
| CapabilityLease | privilege escalation, scope widening, use-after-revoke, expired-lease reuse |
| EventLedger | event reordering/insertion/truncation (hash-chain), partial commits |
| CheckpointManifest | corrupted recovery state, unverified resume, masked open reservations |
| ClaimGuard | self-asserted success, unverified completion promotion, evidence-less claims |
| VerificationPipeline | driver-fabricated verification results, unsupported completion |
| aggregate versioning | lost-update races, concurrent mutation (optimistic concurrency) |
| idempotency keys | duplicate command effects across restart |
| authority matrix | plane-blur (e.g. cognition granting capabilities, driver mutating state) |

### Maturity snapshot (implemented vs aspiration)

| Area | Maturity | Basis |
|---|---|---|
| contracts | Implemented (M0-A) | 121 types generated, drift-checked (High) |
| event ledger | Implemented | transactional + hash-chain (High) |
| replay | Implemented | full + checkpoint replay, idempotent (High) |
| checkpointing | Implemented | manifest + integrity digest + recoveryState (High) |
| capabilities | Implemented | grant/lease/reserve/finalize/revoke/expire (High) |
| governance decision logic | Aspiration (M0-A) | runtime records PolicyDecision; kernel logic deferred (Medium) |
| execution drivers | Absent (M0-A) → M0-B | DriverRun state-model only; real driver in M0-B (Low→High after M0-B) |
| planning | Partial | TaskAggregate transitions only; no scheduler (Medium) |
| memory integration | Disconnected | capt_runtime does not import capt_solo memory (High) |
| ContextPack integration | Absent (M0-A) | out of M0-A scope (High) |
| Knowledge Bubbles | Absent (M0-A) | bubble.py untouched (High) |
| external bridges | Absent (M0-A) | no network in capt_runtime (High) |

### Triple Recursion (forensic document)

- **Construct:** mapped 20 components to IM/PA/DC/PL/AB/UN with source citations.
- **Adversarial:** re-checked each IM claim against code; e.g. challenged "no capt_solo import" via grep (clean), challenged "hash-chain detects reordering" via store.verify_chain (High).
- **Reconcile:** no misclassifications found; ContextPack/KB/Plugin/IPC confirmed AB for M0-A (not defects). No corrections to classifications required.

---

**STATUS: M0_A_PROVEN**
