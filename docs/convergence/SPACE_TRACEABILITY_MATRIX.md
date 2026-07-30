# SPACE_TRACEABILITY_MATRIX — responsibility-by-responsibility

Generated: 2026-07-30. Method: behavioral comparison of Treasure Chest Space
responsibilities (doc 15 Workstream D) against actual code at integration HEAD
`716ecc9` and public main. We compare BEHAVIOR, not names. Evidence commands
run today; locations cited are real files/classes.

Legend: ✅ implemented · 🟡 partial · 🔁 other-abstraction · ❌ absent

## Responsibility map

| # | Space responsibility | Status | Implementation location | Runtime owner | Tests | Public API | Gaps | Migration implication |
|---|---|---|---|---|---|---|---|---|
| 1 | **Identity** (stable Space id + metadata) | ❌ | none | — | — | — | no Space identity record | new table |
| 2 | **Lifecycle** (active/inactive/archived) | 🟡 | `Capability.lifecycle` (candidate/validated/…) exists for capabilities; `sessions.status` (active/closed) for sessions | foundry.registry / memory.engine | registry tests | `capt foundry capability *` | lifecycle exists for OTHER objects, not a Space | reuse pattern |
| 3 | **Ownership** (who owns a Space) | ❌ | none | — | — | — | no owner field anywhere cross-subsystem | new |
| 4 | **Governance boundary** | 🟡 | `foundry/governance.py` (Governance, GovernanceReceipt); `claimguard.py` (proven/verified) | foundry | governance tests | `capt foundry governance` | governs capabilities/skills, not a Space scope | extend scope |
| 5 | **Capability policy** | 🔁 | `CapabilityRegistry` (register/revoke, lifecycle, trust, degradation) — global, single-tenant | foundry.registry | registry tests | `capt foundry capability *` | policy exists but NOT partitioned by Space | partition by Space id |
| 6 | **Project boundary** | 🔁 | `evidence/workspace_isolation.py` `ProjectWorkspace`/`WorkspaceScope` + `WorkspaceIsolationError` (path-traversal rejection) | evidence | isolation tests | internal | evidence-subsystem only; not cross-subsystem | evolve into Space-owned scope |
| 7 | **Memory namespace** | 🔁 | `memory/engine.py` `namespace` column on memories/sessions/procedures; `csg.py` namespace scoring; per-record label | memory | memory tests | `capt memory * --namespace` | flat label, no Space ownership/enforcement | map namespace set → Space |
| 8 | **Evidence namespace** | 🔁 | `evidence/workspace_isolation.py` project scope; `EvidenceRecord.scope` (doc 13) | evidence | evidence tests | internal | evidence scoped to project, not Space | Space owns evidence scope |
| 9 | **Proof scope** | 🔁 | `foundry/proof.py` `ProofEngine` with `scope` param on add_evidence/requirements | foundry | proof tests | `capt foundry proof` | scope is a string, not a Space ref | Space id becomes scope value |
| 10 | **CTP transaction scope** | ❌ | `ctp/journal.py` `Receipt` has tx_id/correlation/idempotency but NO scope field | ctp | ctp tests | `capt ctp *` | receipts not partitioned by Space | ADDITIVE: nullable `space_id` |
| 11 | **Audit history** | 🔁 | `ctp/journal.py` append-only JSONL (validate/commit/note events) — per runtime instance, not per Space | ctp | ctp tests | `capt ctp audit` | audit exists globally, not Space-scoped | Space filter view |
| 12 | **Recovery** | 🔁 | `memory/engine.py` `backup()`/`restore()`; `ctp` journal file; `foundry/bubble` export | memory/ctp/foundry | backup/restore tests | `capt memory backup` | per-subsystem recovery, no Space bundle | Space = bundle of subsystem backups |
| 13 | **Import/export** | 🔁 | `foundry/bubble.py` `export_selected`/`import_bubble` with `exported_namespaces`; `memory.export_json/import_json` | foundry/memory | bubble/memory tests | `capt foundry bubble export` | export exists for bubbles/memory, not Space | Space export = aggregate |
| 14 | **Isolation** | 🟡 | `WorkspaceIsolationError` path-traversal guard (evidence); memory namespace separation (soft) | evidence/memory | isolation tests | internal | hard isolation only at evidence path level; memory namespace is advisory | Space enforces hard cross-subsystem |
| 15 | **Policy inheritance** | ❌ | none | — | — | — | no inheritance mechanism | new |
| 16 | **Metadata** | 🔁 | `MemoryRecord.metadata`, `Capability.metadata`, `Bubble.metadata` — per-object metadata, no Space metadata | various | various | various | no Space-level metadata container | new |
| 17 | **Persistence** | 🔁 | SQLite tables per subsystem (memories, sessions, procedures, ctp journal, capabilities) under one state dir | memory/ctp/foundry | persistence tests | — | single state dir = implicit one Space; no multi-Space persistence | ADDITIVE Space tables |
| 18 | **Activation/deactivation** | 🟡 | `sessions.status` active/closed; `Capability.lifecycle` | memory/foundry | tests | CLI | activation exists for sessions/capabilities, not Spaces | reuse |

## Summary counts
- ✅ implemented as Space: **0**
- 🟡 partial (lifecycle/isolation/activation exist for other objects): **4** (2,6,14,18)
- 🔁 implemented under another abstraction (reusable as Space building blocks): **9** (4,5,7,8,9,11,12,13,16,17 → 10)
- ❌ genuinely absent: **4** (1 identity, 3 ownership, 10 CTP scope, 15 policy inheritance)

## Conclusion for Q1
No Space responsibility is fully implemented AS A SPACE. 13 of 18 responsibilities
have reusable building blocks in other abstractions (capability lifecycle, memory
namespace, evidence project scope, proof scope, CTP audit, bubble export,
isolation guard). 4 are genuinely absent (Space identity, ownership, CTP
transaction scope, policy inheritance). This confirms: Spaces are NOT satisfied
today, but the gap is consolidation + 4 new primitives, not a from-scratch build.
This is the empirical basis for classifying Spaces as consolidation (Q2), not a
missing feature that breaks current promises.
