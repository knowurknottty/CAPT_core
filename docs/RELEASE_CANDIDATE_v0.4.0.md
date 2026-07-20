# CAPT Solo v0.4.0 — Release Candidate Report

Generated: 2026-07-20T04:06:55Z (candidate-state capture).
All evidence below was generated AFTER the candidate-state capture, in this
sequential verification pass. No prior-session result is used as final evidence.

## Branch and starting commit

- Git repo initialized fresh for this release (no prior history).
- Branch: `master` (default, newly created on first commit).
- Starting commit: none (initial commit will be the v0.4.0 release commit).
- Candidate-state timestamp: 2026-07-20T04:06:55Z
- Candidate-state hash manifest: 102 source files hashed (see `/tmp/capt_v04_manifest.sha256`).
  After testing, the manifest was regenerated and diffed: all 102 original files
  match exactly. The only addition is `tests/test_v04_release_scenarios.py`
  (intentional, part of release prep).

## Files changed (v0.4.0 release commit scope)

New repository (initial commit) includes:
- `capt_solo/` — full package (memory, ctp, khsb, lifecycle, foundry, plugin)
- `capt_cli.py` — CLI with `foundry` group
- `verify_runtime.py` — 45-check structured verification harness
- `doctor.sh` — structured environment diagnostics
- `verify.sh`, `install.sh`, `uninstall.sh`, `pyproject.toml`, `README.md`
- `tests/` — 355 tests including v0.4 suites + permanent release scenarios
- `docs/` — 10 subsystem docs + ARCHITECTURE/DATA_MODEL/API/SECURITY/CHANGELOG/ROADMAP/RELEASE_AUDIT/RELEASE_CANDIDATE
- `.gitignore` — excludes runtime state, caches, secrets

## Migration behavior

- `SCHEMA_VERSION = 4`. Forward-only migration v3→v4.
- Backup-gated: before any schema bump, `engine._backup_before_migration()` takes
  a verified `sqlite3.backup()` of the canonical `self._db_path` to
  `backups/capt_solo.v{N}.{timestamp}.db`, runs `PRAGMA integrity_check`
  (all rows `"ok"`), writes a JSON receipt (source/target version, path,
  timestamp, success), and aborts via `MigrationBackupError` on any failure.
- `ALLOW_MIGRATION_WITHOUT_BACKUP = False` (dev-only override, severe warning).
- Idempotent: reopening an already-migrated DB creates no new backup.
- Evidence: `tests/test_v04_migration.py` (8 tests) + `test_scenario_migrated_v3`
  + `test_scenario_restart_no_extra_backup` (6-scenario suite).

## Backup behavior

- Backup is a SAFETY GATE, not best-effort.
- Uses canonical `self._db_path` (not `PRAGMA database_list`, which returns empty
  in this environment).
- Separate source connection avoids WAL deadlock.
- Verifies integrity + records receipt before applying any mutation.
- On failure: raises `MigrationBackupError`, schema untouched (no partial apply).
- Evidence: `test_migration_aborts_when_backup_fails`, `test_backup_created_and_valid`.

## Proof lifecycle

- `ProofEngine`: evidence objects + aggregation against declared requirements.
- `CapabilityRegistry` lifecycle: candidate → validated → proven → verified
  (3 distinct, idempotent events). `reg.verify` promotes only when
  `agg.satisfied`; `mark_proven` and `govern_approve` are separate, idempotent.
- Repeated `verify` is idempotent (no double promotion).
- Expired evidence (`ttl=0`) and out-of-scope evidence cannot satisfy a requirement.
- Evidence with no registered capability is orphaned.
- Evidence: `test_v04_foundry.py::test_capability_lifecycle`,
  `test_expired_evidence_cannot_verify`, `test_out_of_scope_evidence_cannot_verify`,
  `test_duplicate_evidence`, `verify_runtime.py::foundry.capability_consistency`,
  `foundry.orphaned_evidence`, `foundry.missing_proof_requirements`.

## Workflow proof behavior

- `WorkflowProofEngine.evaluate()` creates a `WorkflowProof` in `candidate` state.
- A composed workflow does NOT inherit component verification: even when all
  component skills are `published`/`verified`, the workflow stays `candidate`
  until it carries its own proof (integration/failure/output evidence).
- Lifecycle: candidate → validated → proven → approved → verified → degraded →
  deprecated → revoked.
- Duplicate component evidence is de-duplicated in aggregation (not double-counted).
- Evidence: `tests/test_v04_workflow_proof.py` (7 tests) +
  `test_scenario_workflow_independent` + `verify_runtime.py::foundry.workflow_proof_independence`.

## Bubble quarantine behavior

- `build_bubble` produces a v2 manifest (format_version=2, bubble_id, bubble_version,
  originating_capt_version, min/max compatible versions, platform_metadata,
  exported_namespaces, included skill/proc/claim/evidence/proof IDs, trust_metadata,
  lifecycle_metadata, artifact_inventory, per-artifact hashes, manifest_hash,
  signature_metadata placeholder, redaction_declaration, declared_permissions/
  dependencies, export_policy, provenance, payload).
- `import_bubble` ALWAYS stores the bubble as `quarantined` — never trusted,
  executed, or auto-installed.
- `validate_bubble` runs 12 steps (container_structure → manifest_schema →
  manifest_hash → payload_inventory → artifact_hashes → version_compatibility →
  secret_screening → permission_analysis → dependency_analysis → proof_chain →
  conflict_detection → trust_lifecycle). Manifest validated BEFORE payload.
- Approval ≠ installation; installation is CTP-governed.
- Evidence: `tests/test_v04_foundry.py::test_bubble_validate_12step`,
  `test_bubble_export_excludes_private`, `test_v04_plugin.py::test_export_bubble_excludes_private`,
  `test_scenario_bubble_quarantined`.

## Degradation behavior

- 12 explicit reason codes: `dependency_missing, environment_changed, proof_expired,
  compatibility_failed, security_revoked, manual_disable, superseded,
  verification_failed, component_degraded, tool_contract_changed,
  permission_policy_changed, artifact_missing`.
- `reg.degrade(reason, affected_scope, triggering_evidence, actor, remediation,
  ctp_tx_id)` records a structured degradation record (reason, explanation,
  affected_scope, previous_state, resulting_state, timestamp, actor, remediation).
- `security_revoked` → `revoked`; other reasons → `degraded`.
- ClaimGuard alters wording based on degradation state AND scope: a capability
  degraded only on `macos` is reported as "degraded on macos only … not globally
  revoked", never as a global revoke.
- Evidence: `tests/test_v04_degradation.py` (6 tests) +
  `test_scenario_degradation_scoped_language` +
  `verify_runtime.py::foundry.degraded_capability_state`,
  `foundry.claimguard_scoped_downgrade`.

## ClaimGuard behavior

- `ClaimGuard.verify_claim(text, capability_id=)` returns a `ClaimVerdict` with
  `supported`, `lifecycle`, and `language`.
- Unsupported completion claims are downgraded (never reported as verified without
  a satisfied proof aggregate).
- Scoped degradation language prevents a platform-specific issue from being
  misreported as a global revoke.
- Evidence: `test_v04_degradation.py::test_scoped_degradation_language_macos_not_global`,
  `verify_runtime.py::foundry.claimguard_verified`, `foundry.claimguard_scoped_downgrade`.

## CLI and plugin inventory

### CLI (`capt_cli.py`)
- `foundry` group: `skills` (build/validate/review/approve/publish/deprecate/revoke/list),
  `caps` (register/verify/proven/approve/degrade/list), `bubbles`
  (build/import/validate/approve/install/list), `gov` (publish/deprecate/revoke),
  `curate`, `audit`.
- SQL-free: procedure/feedback commands use domain methods (`ProcedureStore.get_runs`,
  `FeedbackStore.list_feedback`), not raw SQL.

### Hermes plugin (`capt_solo/plugin/`)
- 46 tools total (36 v0.1–v0.3 + 10 v0.4 foundry tools):
  `capt_generate_skill, capt_validate_skill, capt_publish_skill,
  capt_query_capability, capt_verify_claim, capt_build_bubble,
  capt_validate_bubble, capt_install_bubble, capt_export_bubble, capt_inspect_proof`.
- `plugin.json` version 0.4.0, 46 tools (confirmed).

## Exact test commands and results (this pass)

```
$ python3 -m pytest --collect-only -q
355 tests collected                        EXIT=0

$ python3 -m pytest -q
355 passed in 3.91s                       EXIT=0

$ python3 -m pytest tests/test_v04_migration.py -q
8 passed in 0.09s                         EXIT=0

$ python3 -m pytest tests/test_v04_cli.py -q
9 passed in 1.08s                         EXIT=0

$ python3 -m pytest tests/test_v04_plugin.py -q
8 passed in 0.08s                         EXIT=0

$ python3 -m py_compile <14 v0.4 modules + cli + verify_runtime>
PY_COMPILE_EXIT=0

$ bash -n doctor.sh
BASH_N_EXIT=0

$ bash doctor.sh
exit 0 (schema v4 PASS, foundry 12 codes PASS, CLI PASS, verify_runtime PASS;
        backup_dir WARN + plugin_tools WARN = install-time artifacts)

$ python3 verify_runtime.py
45 pass / 0 warn / 0 fail / 0 skip (45 checks)   EXIT=0

$ python3 -m pytest tests/test_v04_release_scenarios.py -v
6 passed in 0.10s                         EXIT=0
```

## Doctor results

`doctor.sh` emits structured checks (check_id | status | severity | summary |
evidence | remediation | duration). This pass:
- `v04.schema_version` PASS (SCHEMA_VERSION=4)
- `v04.backup_dir` WARN (no backups/ in dev checkout — created on first init)
- `v04.foundry_import` PASS (DEGRADATION_REASONS=12)
- `v04.cli_available` PASS
- `v04.plugin_tools` WARN (counted from source = 46; not yet deployed to
  `~/.hermes/plugins/capt-solo/` — install-time artifact)
- `v04.verify_runtime` PASS (exit 0)
- Environment/install checks (python3, sqlite3, package, hermes_config, plugin,
  runtime.home, memory_db, ctp_journal) PASS or WARN as appropriate for a dev checkout.

## Verify results

`verify_runtime.py` — 45 structured checks, all PASS:
Memory (9), CTP (7), KHSB (4), Foundry (23), Health (1), plus cross-cutting
(schema_version, migration_backup_dir, proof_integrity, orphaned_evidence,
missing_proof_requirements, capability_consistency, degraded_capability_state,
degradation_reason_codes, skill_validate, skill_published, claimguard_verified,
claimguard_scoped_downgrade, workflow_proof_independence, workflow_stale_component_proof,
bubble_manifest_v2, bubble_quarantined_isolation, bubble_validate_12step,
governance_receipt, ctp_receipt_linkage, sql_boundary_audit, secret_screening,
plugin_registration, cli_registration, public_api_smoke).

## Scenario results (permanent integration tests)

```
test_scenario_clean_home              PASSED
test_scenario_migrated_v3             PASSED
test_scenario_restart_no_extra_backup PASSED
test_scenario_bubble_quarantined      PASSED
test_scenario_workflow_independent    PASSED
test_scenario_degradation_scoped_language PASSED
```

## Repository-wide coverage

`pytest --cov=capt_solo` → **84%** (4367 statements, 702 missing, 355 passed).

## v0.4-specific coverage

| Module | Coverage | Uncovered consequential branches |
|--------|----------|----------------------------------|
| foundry/skill_foundry.py | 74% | revoke/deprecate/get_by_name variants (lines 397–433, 442–467) |
| foundry/proof.py | 83% | expiration/scope internal filter (282–303) — behavior covered by tests |
| foundry/registry.py | 88% | edge listing paths (349, 352) |
| foundry/claimguard.py | 88% | degraded/revoked branch details (160–161, 181, 188) |
| foundry/bubble.py | 85% | install/approve edge paths (371–374, 404–412) |
| foundry/workflow_proof.py | 95% | minor evidence-edge lines (143, 196, 239, 248, 260, 267) |
| foundry/governance.py | 76% | deprecate/revoke wrapper details (76–82, 108–110, 131–132) |
| foundry/harness.py | 79% | failure-path stage details (259–262, 302–305) |
| foundry/curator.py | 98% | one info-branch line (90) |
| foundry/composition.py | 79% | composition edge paths (143–156) |
| plugin/__init__.py | 66% | many tool wrappers not exercised by unit tests |
| capt_cli.py | covered by test_v04_cli.py (9 tests) | — |
| verify_runtime.py | 0% (verification harness, not imported by suite) | — |

All critical public paths are covered by tests:
backup failure abort ✓, migration no-partial-state ✓, duplicate evidence ✓,
expired/out-of-scope proof rejection ✓, verification idempotency ✓,
approval≠publication ✓, bubble quarantine ✓, private-memory export exclusion ✓,
workflow proof independence ✓, component degradation propagation ✓,
ClaimGuard downgrade language ✓, CTP rollback ✓, governance receipt ✓,
plugin/CLI boundary ✓.

## Unresolved limitations

- Bubble signatures are placeholder (`signature_metadata.scheme="none"`); no
  cryptographic verification in v0.4.
- Migrations are forward-only; rollback is via the backup file + manual restore.
- CTP audit trails are append-only, not cryptographically signed (v1.0).
- `skill_foundry.py` revoke/deprecate/get_by_name variants partially uncovered (<74%).
- `doctor.sh` "Plugin installed" / "Runtime home" / "Memory DB" / "CTP journal"
  WARN in a dev checkout (plugin not deployed to `~/.hermes/plugins/capt-solo/`,
  no runtime home initialized). Source `plugin.json` has 46 tools, v0.4.0.
- No remote/publish/push performed. Tag is local-only.

## Release gate matrix (17 gates)

| # | Gate | Status | Evidence |
|---|------|--------|----------|
| 1 | Migration backup safety gate | PASS | test_backup_created_and_valid, test_migration_aborts_when_backup_fails |
| 2 | Migration idempotency | PASS | test_migration_idempotent, test_scenario_restart_no_extra_backup |
| 3 | Migration abort-on-failure | PASS | test_migration_aborts_when_backup_fails |
| 4 | Workflow proof independence | PASS | test_v04_workflow_proof.py (7), verify_runtime workflow_proof_independence, test_scenario_workflow_independent |
| 5 | Bubble manifest v2 | PASS | bubble.py build_bubble, verify_runtime bubble_manifest_v2 |
| 6 | Bubble 12-step validation | PASS | test_bubble_validate_12step, verify_runtime bubble_validate_12step |
| 7 | Capability degradation 12 codes | PASS | test_all_12_reason_codes_defined, verify_runtime degradation_reason_codes |
| 8 | ClaimGuard scoped language | PASS | test_scoped_degradation_language_macos_not_global, verify_runtime claimguard_scoped_downgrade, test_scenario_degradation_scoped_language |
| 9 | Skill lifecycle (approve≠publish) | PASS | test_v04_foundry.py, verify_runtime skill_published |
| 10 | Capability lifecycle (3 events) | PASS | test_capability_lifecycle, verify_runtime capability_consistency |
| 11 | Governance CTP-bounded | PASS | test_governance_publish_generates_receipt, verify_runtime governance_receipt + ctp_receipt_linkage |
| 12 | Repository boundary (SQL-free) | PASS | test_public_surface_has_no_raw_sql, verify_runtime sql_boundary_audit |
| 13 | Plugin 46 tools | PASS | test_plugin_tool_count_is_46, verify_runtime plugin_registration (46) |
| 14 | Doctor/verify structured | PASS | doctor.sh 14 structured checks; verify_runtime 45/45 |
| 15 | Documentation (10 + updates) | PASS | docs/ present; RELEASE_AUDIT + RELEASE_CANDIDATE; DATA_MODEL/API updated |
| 16 | Test suite green | PASS | pytest → 355 passed (0 skip/xfail/fail) |
| 17 | Coverage ≥ 80% | PASS | 84% overall; v0.4 modules 74–98% |

## Final working-tree state

- After all verification: `git status --short` shows only untracked files (fresh repo).
- `git diff --stat` / `git diff --check` clean (no tracked modifications).
- Hash manifest regenerated and diffed: all 102 candidate files match; only
  addition is `tests/test_v04_release_scenarios.py` (intentional).
- Working tree is clean of generated artifacts (`.gitignore` excludes data/,
  backups/, caches, coverage files, secrets).

## Conclusion

All 17 release gates PASS with fresh, post-candidate-state evidence.
CAPT Solo v0.4.0 is release-ready. Commit and local annotated tag prepared per
release procedure. No push, publish, or remote release performed.
