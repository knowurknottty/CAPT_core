# TREASURE_CHEST_REQUIREMENTS — actionable requirement register

Generated: 2026-07-30. Source: captstreasurechest @ `75355f84` (18 docs, 4,186
lines, read in full). Every requirement carries a stable ID, classification,
and the evidence basis for that classification. Evidence checks were run TODAY
against integration HEAD `716ecc9` unless stated.

Classification vocabulary (per mission): VERIFIED_SATISFIED,
SATISFIED_UNDER_ANOTHER_NAME, PARTIALLY_SATISFIED, BACKUP_ONLY,
NOT_IMPLEMENTED, DOCUMENTATION_ONLY, RELEASE_EVIDENCE_MISSING, POST_V0_5,
SUPERSEDED, OWNER_DECISION.

## TC-GOV — Governance & status rules (doc 00)

| ID | Requirement | Class | Evidence |
|---|---|---|---|
| TC-GOV-001 | Evidence-authority precedence (sealed artifacts > tracked contents > manifests > logs > plans) | VERIFIED_SATISFIED | Operating practice; AGENTS.md authority order encodes equivalent rule |
| TC-GOV-002 | Exact-SHA rule: any edit ⇒ new candidate; prior results historical | VERIFIED_SATISFIED (as rule), enforced by `release_validation.py` clean-tree + sha checks | validator run today |
| TC-GOV-003 | Documentation truth rule: no stale SHAs/test totals/status | PARTIALLY_SATISFIED | Violation found: CURRENT_STATE/RELEASE_STATE say `UNFROZEN` while tracked manifest says `3888f08` |
| TC-GOV-004 | Status `NOT READY — BLOCKERS REMAIN` until final gates | VERIFIED_SATISFIED | README/RELEASE_STATE carry pre-release language |
| TC-GOV-005 | Required YAML session header on agent reports | DOCUMENTATION_ONLY | process rule, adopted going forward |

## TC-ARCH — Public architecture (docs 01, 13)

| ID | Requirement | Class | Evidence |
|---|---|---|---|
| TC-ARCH-001 | Six-pillar public architecture (Identity&Scope, Evidence, Verification, Context, Transactions, Governance) | VERIFIED_SATISFIED on integration | `capt_solo/{core,evidence,verification,contextpack,ctp,foundry…}` + ADRs + 715 tests |
| TC-ARCH-002 | Local-first, no cloud, no network on import | VERIFIED_SATISFIED | socket-deny import test passed today in clean venv, no Hermes installed |
| TC-ARCH-003 | Record convergence (ReceiptEnvelope, CheckpointRecord, SubjectRef/StateRef) | POST_V0_5 | doc 13 explicitly defers; "no new record unification work should delay v0.5" |
| TC-ARCH-004 | Engines (math/physics/invention) behind experimental extras | POST_V0_5 | doc 13 candidate moves after v0.5 |
| TC-ARCH-005 | PULSE/network gateways behind explicit optional plugin boundaries | PARTIALLY_SATISFIED | pulse.py is disabled-by-default, lazy-import, opt-in — but not an extras-gated plugin |

## TC-SPACE — First-class Spaces (doc 15 Workstream D)

| ID | Requirement | Class | Evidence |
|---|---|---|---|
| TC-SPACE-001 | Durable `Space` abstraction above projects/agents/models/sessions/tools | NOT_IMPLEMENTED | no `capt_solo/spaces` on ANY branch (verified both main and integration trees) |
| TC-SPACE-002 | Space owns memory namespaces, capability policy, tool permissions, runtime bindings, CTP scope, evidence scope, governance history, recovery, audit | NOT_IMPLEMENTED (partial seams exist) | memory has per-record `namespace`; `ProjectWorkspace`/`WorkspaceScope` in evidence/workspace_isolation.py provide project-level isolation; nothing owns cross-subsystem policy |
| TC-SPACE-003 | Space ops: create/get/list/update/activate/deactivate/export/import/archive/tombstone | NOT_IMPLEMENTED | no such API |
| TC-SPACE-004 | Cross-Space isolation, auditable destructive ops, backup-gated migration, deterministic default-Space migration, no orphans | NOT_IMPLEMENTED | — |
| TC-SPACE-005 | Deliverables SPACE_ARCHITECTURE/MIGRATION/SECURITY_BOUNDARIES + space_schema.json | NOT_IMPLEMENTED | files absent |

## TC-RUNTIME — Provider-neutral runtime (doc 15 Workstream E)

| ID | Requirement | Class | Evidence |
|---|---|---|---|
| TC-RUNTIME-001 | Runtime adapter contract normalizing identity/provenance/generation/streaming/tools/limits/cancellation/usage/refusals/retry/network/secrets/local-vs-remote | NOT_IMPLEMENTED | no `capt_solo/adapters`; `research/adapter.py` is a narrower seam (research-task adapter with registry+fallback), not a model-runtime contract |
| TC-RUNTIME-002 | AdapterRegistry: register/unregister/list/get/health/select | SATISFIED_UNDER_ANOTHER_NAME (partial precedent) | `ResearchAdapterRegistry` implements register/get/fallback for research tasks only — a design precedent, not the required contract |
| TC-RUNTIME-003 | Core imports and operates without Hermes | VERIFIED_SATISFIED | proven today: clean venv (no hermes), socket-denied, all core packages import; only `plugin/__init__.py` mentions Hermes (inbound wrapper, not import); zero `import hermes` anywhere |
| TC-RUNTIME-004 | Two proven paths (direct/local non-Hermes + Hermes behind same contract) | NOT_IMPLEMENTED | no adapter contract exists to put either behind |
| TC-RUNTIME-005 | Selection respects Space policy (local-only, allowlists, fallback order) | NOT_IMPLEMENTED | depends on TC-SPACE + TC-RUNTIME-001 |
| TC-RUNTIME-006 | Hermes presented as one adapter, not architectural dependency | PARTIALLY_SATISFIED | whitepaper (main) already states harness-independence; plugin is inbound-only; but no outbound adapter layer exists to demonstrate it |

## TC-SECURITY — Security campaign (docs 03, 04, 05, 06, 11)

| ID | Requirement | Class | Evidence |
|---|---|---|---|
| TC-SECURITY-001 | Manual security campaign: 14 review scopes, deterministic pass (bandit/semgrep/gitleaks/pip-audit) | NOT_IMPLEMENTED (campaign not run against current candidate) | no scan artifacts tied to 716ecc9 or 3888f08 in repo |
| TC-SECURITY-002 | 6 Codex candidate findings adjudicated with regression tests | VERIFIED_SATISFIED (historical, at 3888f08) | commit history + focused security tests in suite (test_doctor_sh_command_injection etc., in today's 715) |
| TC-SECURITY-003 | Secret scanning (gitleaks config + release-security CI) | SATISFIED_UNDER_ANOTHER_NAME on MAIN ONLY | `.gitleaks.toml` + release-security.yml exist on public main; ABSENT from integration branch |
| TC-SECURITY-004 | Codex deep scan | SUPERSEDED / POST_V0_5 | doc 11 postmortem: use only as corroboration, run late, budget explicitly |
| TC-SECURITY-005 | Finding lifecycle + severity rubric + evidence format | DOCUMENTATION_ONLY | process rules; adopt during campaign |
| TC-SECURITY-006 | Repository SECURITY.md | NOT_IMPLEMENTED on integration | absent at HEAD (main also lacks it; only SECURITY_BOUNDARIES.md exists on integration) |

## TC-TRUST — Trust/privacy/compliance (doc 08, 15 Workstream F)

| ID | Requirement | Class | Evidence |
|---|---|---|---|
| TC-TRUST-001 | Threat model | NOT_IMPLEMENTED | docs/THREAT_MODEL.md absent |
| TC-TRUST-002 | Trust Center (10 sections) | NOT_IMPLEMENTED | absent |
| TC-TRUST-003 | Responsible disclosure policy | NOT_IMPLEMENTED | no SECURITY.md |
| TC-TRUST-004 | SBOM + dependency/supply-chain evidence | NOT_IMPLEMENTED | trivially achievable: runtime deps = pyyaml only |
| TC-TRUST-005 | Privacy & data-handling proof | PARTIALLY_SATISFIED | local-first behavior implemented+tested; dedicated doc absent |
| TC-TRUST-006 | NIST SSDF / AI RMF / OWASP / ISO 27001 / SOC 2 mappings | NOT_IMPLEMENTED | absent; doc 08 forbids claiming certification — mappings are "support" docs |
| TC-TRUST-007 | No unsupported compliance claims | VERIFIED_SATISFIED | no such claims exist in any public doc (checked main + integration) |

## TC-RELEASE — Exact-SHA closure (doc 07)

| ID | Requirement | Class | Evidence |
|---|---|---|---|
| TC-RELEASE-001 | Full command matrix at frozen SHA (pytest, verify_runtime, architecture/workspace/release validate, doctor, compileall, build) | PARTIALLY_SATISFIED | pytest+build+release-validate rerun today; full matrix not run as one sealed session |
| TC-RELEASE-002 | Artifact inspection (contents, entry points, no secrets/state, SHA-256) | PARTIALLY_SATISFIED | hashes computed today; systematic content inspection not sealed |
| TC-RELEASE-003 | Clean install wheel AND sdist in separate envs + 6 capability profiles + tutorial + no-network | PARTIALLY_SATISFIED | wheel path done today; sdist env, 6 profiles, tutorial not rerun |
| TC-RELEASE-004 | Required final evidence files (9 absent: RELEASE_VERIFICATION, ARTIFACT_MANIFEST, PACKAGE_CONTENTS, CONFORMANCE_RESULTS, security report + 3 JSONs) | RELEASE_EVIDENCE_MISSING | verified absent today (only PUBLIC_API_MANIFEST_V0.5.json present) |
| TC-RELEASE-005 | Machine-enforced failure conditions | VERIFIED_SATISFIED (partially mechanized) | release_validation.py implements version/SHA/state checks; remainder procedural |
| TC-RELEASE-006 | One decision: READY FOR OWNER AUTHORIZATION / NOT READY | VERIFIED_SATISFIED (process) | current: NOT READY |

## TC-DOCS — Documentation truth (docs 12, 15 Workstream G/H, 16)

| ID | Requirement | Class | Evidence |
|---|---|---|---|
| TC-DOCS-001 | Public claim ledger with per-claim evidence | RELEASE_EVIDENCE_MISSING | produced in this pass: PUBLIC_CLAIM_LEDGER.md |
| TC-DOCS-002 | Correct stale v0.1/v0.4/v0.4.1 language; target v0.5.0 | PARTIALLY_SATISFIED | integration is v0.5.0-consistent (validator-enforced); PUBLIC MAIN is v0.4.1 with `__version__="0.1.0"` mismatch |
| TC-DOCS-003 | Terminology discipline (Core/Solo/Space/adapter/Hermes) | PARTIALLY_SATISFIED | Core/Solo/Hermes consistent; Space/adapter can't be documented (not implemented) |
| TC-DOCS-004 | Diagrams start with neutral caller/adapter layer | PARTIALLY_SATISFIED | whitepaper line 89 "Hermes or local caller" — acceptable; revisit with adapter work |
| TC-DOCS-005 | Whitepaper finalization (v0.5, Spaces, adapter contract, portability scenario) | POST-INTEGRATION | whitepaper exists on main only (561 lines, v0.4-era); update after scope decision |
| TC-DOCS-006 | Harsh-reviewer 5-gate review before release | NOT_IMPLEMENTED (gate not yet run) | required before freeze |
| TC-DOCS-007 | Website/launch copy structure | POST_V0_5 / OWNER_DECISION | website exists (Cloudflare, auto-deploy disabled); launch copy deferred |
| TC-DOCS-008 | 15-minute onboarding + verification-first tutorial | VERIFIED_SATISFIED on integration | docs/tutorials/VERIFY_AI_WORK_IN_FIVE_MINUTES.md + examples/verification_first/run.py in tree, tutorial tested via suite |

## TC-ECON — Token/context economics (doc 09)

| ID | Requirement | Class | Evidence |
|---|---|---|---|
| TC-ECON-001 | Structured memory, deterministic context projection, reuse-with-invalidation, digest refs | VERIFIED_SATISFIED | ContextPack v1 + memory engine + invalidation, tested in 715 |
| TC-ECON-002 | Tiered model routing | NOT_IMPLEMENTED | depends on runtime adapters (TC-RUNTIME) |
| TC-ECON-003 | Cost accounting | NOT_IMPLEMENTED | usage metadata is part of adapter contract |

## TC-PROTO — KHSB/CTP/CRP (doc 10)

| ID | Requirement | Class | Evidence |
|---|---|---|---|
| TC-PROTO-001 | CTP ships correctly with receipts/idempotency/recovery tests | VERIFIED_SATISFIED | ctp/journal.py + tests in 715 |
| TC-PROTO-002 | KHSB with encryption-profile claims tested | PARTIALLY_SATISFIED | khsb/bus.py in-process messaging tested; no encryption claims made (rule: claim nothing untested — currently honored by silence) |
| TC-PROTO-003 | CRP runtime | POST_V0_5 | explicitly deferred in docs 03/10 |

## TC-GH — GitHub surface (doc 17)

| ID | Requirement | Class | Evidence |
|---|---|---|---|
| TC-GH-001 | Lockdown: public = exception | VERIFIED_SATISFIED (exceeded) | executed 2026-07-30: 1 public repo (CAPT_core); NOTE: doc 17's keep-public list (inversion-labs, articles, capt-charles) was superseded by owner's later "CAPT_core only" order — Treasure Chest doc 17 is now STALE vs owner decision |
| TC-GH-002 | Arena: private until after CAPT Core v0.5 | VERIFIED_SATISFIED | private since 2026-07-30 |
| TC-GH-003 | 2-minute clarity test on public repos | PARTIALLY_SATISFIED | main README strong; but main lacks LICENSE file while README says "See LICENSE" — broken promise, and pyproject says MIT |

## Classification totals

VERIFIED_SATISFIED: 14 · SATISFIED_UNDER_ANOTHER_NAME: 2 ·
PARTIALLY_SATISFIED: 12 · NOT_IMPLEMENTED: 15 · RELEASE_EVIDENCE_MISSING: 2 ·
DOCUMENTATION_ONLY: 2 · POST_V0_5: 6 · SUPERSEDED: 1 · OWNER_DECISION: 1 ·
BACKUP_ONLY: 0 (backup verified to contain zero unique work)
