# BASELINE EVIDENCE REPORT — CAPT_core v0.4.1 baseline

**Phase:** 0 — Baseline verification
**Branch:** `integration/full-public-architecture` (created from `main` @ `abeff5c`)
**Date:** 2026-07-26
**Operator:** autonomous implementation agent (evidence-only pass; no runtime behavior changed)
**Source-of-truth priority applied:** executable code/tests > runtime registries/config > build/release artifacts > design specs > forensic corpus

---

## 1. Commit / tag / tree

| Field | Value | Evidence |
|-------|-------|----------|
| Repository | `knowurknottty/CAPT_core` (local clone `/Users/knowurknot/capt-solo`) | `git remote -v` |
| Baseline branch | `main` | `git branch -a` |
| Baseline HEAD | `abeff5c1fcb498533bce70448c069e59f4f0c8a0` | `git rev-parse main` |
| Baseline HEAD subject | `release: complete CAPT Solo v0.4 proof-governed skill runtime` | `git log -1 main` |
| Integration branch | `integration/full-public-architecture` @ `abeff5c` (new, unpushed) | `git checkout -b ... main` |
| Tags | `v0.4.0` only (no `v0.4.1` tag despite wheel labeled 0.4.1) | `git tag` |
| Working tree | clean at branch creation | `git status --short` |

**Conflict recorded:** wheel + docs declare version `0.4.1`; git tag set is only `v0.4.0`; `pyproject.toml` declares `version = "0.1.0"`. Three divergent version signals. Not silently resolved — flagged for owner.

---

## 2. Package metadata

| Field | Value | Evidence |
|-------|-------|----------|
| Distribution name | `capt-solo` | `pyproject.toml` |
| Declared version | `0.1.0` | `pyproject.toml` `[project]` |
| Built wheel | `dist/capt_solo-0.4.1-py3-none-any.whl` | `ls dist/` |
| License | MIT (pyproject) | `pyproject.toml` |
| Python requires | `>=3.8` | `pyproject.toml` |
| Entry point | `hermes_plugins: capt-solo = capt_solo.plugin:get_plugin` | `pyproject.toml` |
| Packages declared | `capt_solo, core, memory, ctp, khsb, plugin` | `pyproject.toml` `[options]` |

**Defect (baseline integrity):** `capt_solo/ctp` is listed in `[options].packages` and imported by `api.py` / `verify_runtime.py` / `foundry/governance.py`, but `capt_solo/ctp/` is **gitignored** (`ctp/` in `.gitignore`) and **absent from the committed tree** (`git ls-files capt_solo/ctp/` returns nothing). A fresh clone therefore cannot import the package. The built wheel *does* contain `capt_solo/ctp/__init__.py` and `capt_solo/ctp/journal.py`, proving the source existed locally at build time but was never committed (it lives only in the builder's untracked working copy). This is a release-gate gap, not a code defect in the modules themselves.

---

## 3. Tree / module inventory (committed)

```
capt_solo/
  __init__.py, api.py
  core/        config.py, errors.py
  memory/      engine.py(1364), models.py(230), csg.py(375), pipeline.py(195),
               context.py(164), search.py(102), deduplicate.py(100), normalize.py(81),
               trust.py(136), secrets.py(84), antitoken.py(273)
  ctp/         *** MISSING FROM TREE (gitignored; present only in wheel) ***
  khsb/        __init__.py, bus.py(173)
  lifecycle/   lifecycle.py(452), sessions.py(572), procedures.py(391), manager.py(334),
               prospective.py(265), feedback.py(198), semantic.py(153), __init__.py
  foundry/     skill_foundry.py(478), bubble.py(412), registry.py(352), harness.py(312),
               proof.py(303), workflow_proof.py(273), claimguard.py(208), composition.py(156),
               governance.py(137), curator.py(115), columns.py(94), __init__.py
  plugin/      __init__.py(808), plugin.json
  skills/      8 skills (capt-arch-decision, capt-bootstrap, capt-debug,
               capt-knowledge-capture, capt-memory-review, capt-recovery,
               capt-session-recap, capt-transaction)
tests/         30 test modules (361 test functions)
docs/          20 markdown docs
verify_runtime.py, verify.sh, doctor.sh, install.sh, uninstall.sh, capt_cli.py
```

---

## 4. Release gates

| Gate | Command | Result | Evidence |
|------|---------|--------|----------|
| Import / verify harness | `PYTHONPATH=. python3 verify_runtime.py` | **FAIL (rc=1)** | `ModuleNotFoundError: No module named 'capt_solo.ctp.journal'` — caused by the missing `ctp/` tree (see §2). |
| Test suite | `PYTHONPATH=. python3 -m pytest -q` | **ERROR (rc=2)** | 16 collection errors, same root cause (`capt_solo.ctp.journal` import). |
| Test function count | `grep -c def test_` | 361 functions across 30 modules | static count |
| verify_runtime checks defined | `grep -c CheckResult` | 2 helper sites; ~52 distinct check_ids emitted | see §5 |
| doctor.sh | not executed (requires install prefix) | not run | deferred; no behavior change requested |

**Note:** gates fail *only* because of the uncommitted `ctp/` package. The modules that exist are importable in isolation (the wheel build succeeded). The gate failure is a packaging/repo-hygiene defect, recorded here as evidence; it is NOT fixed in this inventory pass per the issue's "evidence inventory only" directive.

---

## 5. verify_runtime.py check catalog (52 check_ids)

mem: db, store, get, update, delete, search, export_json, json, integrity_check, backup
ctp: begin, commit, abort, idempotency_guard, double_finalize_guard, integrity_check, recover_no_pending, audit_trail
khsb: publish_subscribe, request_reply, request_timeout, ack
foundry: schema_version, migration_backup_dir, proof_integrity, orphaned_evidence, missing_proof_requirements, capability_consistency, degraded_capability_state, degradation_reason_codes, workflow_proof_independence, workflow_stale_component_proof, bubble_quarantined_isolation, governance_receipt, ctp_receipt_linkage, cli_registration, plugin_registration, public_api_smoke, sql_boundary_audit, secret_screening, skill_validate, skill_published, claimguard_verified, claimguard_scoped_downgrade
verify: nobody, req, topic, ack
capt: health
plugin: plugin.json
verify.sh / capt_cli.py (script presence checks)

---

## 6. Public APIs (committed surface)

- `capt_solo.api`: `health()`, `CTPRuntime`, `KHSB`, `MemoryEngine` (re-exported)
- `capt_solo.foundry`: `ProofEngine`, `CapabilityRegistry`, `SkillFoundry`, `ClaimGuard`, `ValidationHarness`, `KnowledgeBubbleRuntime`, `Governance`, `ProofRequirement`, `WorkflowProofEngine`, `DEGRADATION_REASONS`
- `capt_solo.memory`: `MemoryEngine`, `CSG`, `AntiToken` (extract/validate/render), `trust`, `secrets.screen`, `search`, `deduplicate`, `normalize`
- `capt_solo.khsb`: `bus` (publish/subscribe, request/reply)
- `capt_solo.lifecycle`: `Lifecycle`, `SessionStore`, `ProcedureStore`, `ProspectiveMemory`, `FeedbackStore`, `SemanticIndex`
- `capt_solo.ctp`: **MISSING** — `CTPRuntime`, `Receipt` (only in wheel)
- CLI: `capt_cli.py`

---

## 7. Persisted schema (SQLite, `SCHEMA_VERSION = 4`)

32 tables (evidence: `CREATE TABLE` in `memory/engine.py`):

schema_version, memories, tags, memory_nodes, memory_edges, memory_aliases, memory_conflicts, context_builds, context_build_items, memory_lifecycle_transitions, memory_retention_policies, sessions, session_checkpoints, session_events, session_consolidations, procedures, procedure_versions, procedure_runs, prospective_memories, retrieval_feedback, retrieval_adaptation, semantic_index_metadata, proof_evidence, proof_requirements, capabilities, skills, skill_candidates, composite_workflows, workflow_proofs, knowledge_bubbles, governance_audit, capability_degradations

Schema migration path: `engine.py` migrates `current < SCHEMA_VERSION` forward; `test_migration.py` / `test_v03_migration.py` / `test_v04_migration.py` cover migration.

---

## 8. Tests / coverage

- 30 test modules, 361 test functions (static count).
- Coverage artifact `.coverage` present (not measured this pass).
- No coverage gate threshold configured in `pyproject.toml` or `verify_runtime.py` (evidence: none found).

---

## 9. Docs

20 docs present: API, ARCHITECTURE, CAPABILITY_REGISTRY, CHANGELOG, CLAIMGUARD, CLI, DATA_MODEL, EXTENDING, GOVERNANCE, KNOWLEDGE_BUBBLES, MIGRATIONS, PLUGIN_GUIDE, PROOF_ENGINE, RELEASE_AUDIT_v0.4, RELEASE_CANDIDATE_v0.4.0, ROADMAP, SECURITY, SKILL_FOUNDRY, SKILL_GUIDE, VALIDATION.

---

## 10. Baseline conflicts / open findings (owner decisions required)

| # | Finding | Severity | Owner decision needed |
|---|---------|----------|----------------------|
| B1 | `capt_solo/ctp/` missing from committed tree (gitignored) → fresh clone cannot import; verify_runtime + pytest fail. | HIGH (release blocker) | Commit `ctp/` (restore from wheel source) OR change `.gitignore` + import strategy. Must not be silently deferred. |
| B2 | Version divergence: `pyproject 0.1.0` vs wheel/docs `0.4.1` vs tag `v0.4.0`. | MED | Pick canonical version + tag `v0.4.1`. |
| B3 | Memory/knowledge stack in capt-solo is a *subset* of the forensic corpus. HMC, ECHO, ENGRAM, DREAM, Holographic Memory, autobiographical memory, consent, synchronization, Proof Ledger, Skill Radar are **absent** from capt-solo and exist only in external repos (`biocapt-ecosystem/primary/biocapt-desktop/modules/*_mobile.py`). | HIGH (scope) | Owner must decide which external components belong in the public CAPT release and whether to port them into capt-solo or keep them external. |
| B4 | Forensic corpus recommends deletions/simplifications that are explicitly NOT approved. | INFO | No action; corpus is evidence only. |

---

## 11. Reproduce commands

```bash
cd /Users/knowurknot/capt-solo
git checkout integration/full-public-architecture
git rev-parse HEAD                      # abeff5c...
git ls-files capt_solo/ctp/             # (empty -> confirms B1)
PYTHONPATH=. python3 verify_runtime.py  # rc=1, ModuleNotFoundError capt_solo.ctp.journal
PYTHONPATH=. python3 -m pytest -q       # 16 collection errors
grep -c "def test_" tests/*.py           # 361
```
