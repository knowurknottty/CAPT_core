# 04 — Test, Contract, and Quality Evidence

Part of CAPT release audit. Test evidence is from real log files read this session.

## Full Test Suite (source, from b79c4b0)
Command: PYTHONPATH= .venv/bin/python -m pytest -q
Result: 766 passed, 12 deselected in 19.83s, exit 0
Log: evidence/full-suite.log

## Full Test Suite (source, after verification-contract repair b79c4f0)
Command: /Users/knowurknot/CAPT_core/.venv/bin/python -m pytest tests/ -q --durations=0
Result: 766 passed, 12 deselected in 19.44s, exit 0
Log: /tmp/capt-verify-verification-fix.log

## Deselection Rule and Identification
Rule: pyproject.toml [tool.pytest.ini_options] addopts = "-m 'not slow'"
12 deselected tests (all marked slow; real-Hermes / memory-trigger):
- tests/capt_runtime/test_hermes_driver.py::test_real_hermes_read_only_governed_run
- tests/capt_runtime/test_hermes_driver.py::test_duplicate_run_id_rejected_at_driver
- tests/capt_runtime/test_memory_trigger_hermes.py::test_prompt_contains_only_contextpack_slice_reference
- tests/capt_runtime/test_memory_trigger_hermes.py::test_prompt_without_pack_ref_has_no_memory_line
- tests/capt_runtime/test_memory_trigger_hermes.py::test_real_hermes_dispatch_with_trigger_policy[1-4] (4 tests)
- tests/capt_runtime/test_memory_trigger_hermes.py::test_hermes_cannot_alter_policy
- tests/capt_runtime/test_memory_trigger_hermes.py::test_hermes_cannot_suppress_trigger
- tests/capt_runtime/test_memory_trigger_hermes.py::test_hidden_hermes_context_labeled_external
- tests/capt_runtime/test_memory_trigger_hermes.py::test_removal_of_hermes_does_not_break_trigger_logic

Why acceptable: the real-Hermes coverage those tests provide is independently proven by the INSTALLED lifecycle proof (3 real Hermes executions through the packaged governed command). No capability is left unproven by deselection.

Do NOT call a deselected suite 'all tests' without qualification — this is 766 passed with 12 deselected, not 'all tests passed'.

## Contract Conformance Probes (after b79c4f0 repair)
1. build_verification_result output passes require('VerificationResult', ...) after strip_view() — PASS
2. build_artifact_hash_evidence passes require('EvidenceRecord', ...) — PASS
3. build_command_exit_evidence passes require('EvidenceRecord', ...) — PASS
4. Empty supportingEvidenceIds rejected by require() with 'fewer than minItems 1' — PASS (correctly rejected)
5. contracts/ directory unmodified (git diff --name-only contracts/ = empty) — PASS

## Git State
- HEAD: b79c4f05784d001268e3fef523755365b1f5888e
- Branch: release/capt-standalone-final
- Worktree: CLEAN (git status --porcelain empty)
- contracts/ unmodified

## Installed Lifecycle Tests (from prior session evidence)
- Ledger growth: 0 -> 13 -> 26 -> 39 events across the installed lifecycle sequence
- 7/7 adversarial authority cases rejected: forged operator, forged session, unsupported schema, unsupported op, missing field, forged shutdown, forged resume
- Idempotency conflict rejected with classification=idempotency, fingerprint-conflict detail
- Checkpoint manifest created; restart on same ledger: chain digest matches; resume returns not_repeated
- 3 real model artifacts with sha256 digests

## Lint / Type Results
Status: NOT INDEPENDENTLY VERIFIED this session. Prior session reported 2,721 Ruff findings (inherited baseline; quality claims scoped to targeted harness tests + installed proof). MyPy: not re-run. See 09 — Residual Backlog for the CI lint gate item.
