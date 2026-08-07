# CAPT Core v0.5 — Final Release-Readiness Report

**Branch:** `release/capt-standalone-final`  
**Head:** `548ab3ae311366a3a83d4ae50ac6f2bb7495dcd4`  
**PR:** #33 (release/v0.5)  
**Generated:** 2026-08-07

## 1. Final-head wheel identity

| Field | Value |
|-------|-------|
| Wheel | `capt_solo-0.5.0-py3-none-any.whl` |
| SHA-256 | `f70c3a0e9c10c9dff09b1689d400733e12ebb55f7f066db84fef1d3a0acb17f3` |
| Byte size | 311157 |
| Source SHA | `548ab3ae311366a3a83d4ae50ac6f2bb7495dcd4` |
| Build command | `SOURCE_DATE_EPOCH=1750000000 python3 -m build --wheel` |
| Python | 3.14.6 (build host) |
| setuptools | 81.0.0 |
| Manifest | `release_evidence/v0.5/final-wheel-manifest.json` |

**Reproducible-build verdict:** With `SOURCE_DATE_EPOCH` set, two clean builds produced **byte-identical** wheels (both `f70c3a0e...`). Without SOURCE_DATE_EPOCH, only the dist-info ZIP timestamps differ (contents byte-identical), so the wheel is **deterministic with fixed source epoch** and **repeatably buildable** regardless. The earlier proof wheel (SHA `2a8a6ef...` built from `4005809`) is a distinct, earlier artifact — **not** the final-head wheel.

## 2. Installed final-head wheel result

Fresh external venv `/tmp/capt-final-install-venv` (Python 3.14), outside the repo, `PYTHONPATH` unset:
- All installed imports resolve from `.../site-packages/` (capt_runtime, capt_solo, capt_contracts, desktop, khsb, ctp, memory engine, contextpack, governor, hermes driver, openharness driver)
- `capt --version` → `capt-solo 0.5.0` (exit 0)
- No source-tree shadowing
- Result: `ALL_INSTALLED_IMPORTS_OK`

## 3. Test matrix (reconciled)

| Environment | Commit | Python | Platform | Passed | Skipped | Deselected | Failed |
|-------------|--------|--------|----------|--------|---------|-----------|--------|
| Local | 548ab3a | 3.9.6 | macOS | 722 | 44 | 12 | 0 |
| Local | 548ab3a | 3.10.20 | macOS | 722 | 44 | 12 | 0 |
| Local | 548ab3a | 3.12.13 | macOS | 722 | 44 | 12 | 0 |
| Local simulate-CI (no Hermes) | 548ab3a | 3.12 | macOS | 712 | 54 | 12 | 0 |
| Hosted CI | 548ab3a | 3.10/3.12 | ubuntu | 712 | 54 | 12 | 0 |

The 722/44 vs 712/54 difference is **Hermes-on-PATH**: 10 Hermes-gated tests (`requires_hermes`) pass locally, skip on CI (no Hermes). Not a Python-version or code difference. See `release_evidence/v0.5/test-matrix.md`.

Exact skip reasons:
- 44 × `anti-token-extraction upstream package not installed in this env`
- 10 × `real Hermes runtime not available on PATH` (CI only)
- 12 deselected = `slow` marker (`-m 'not slow'` in pyproject.toml)

## 4. Static analysis and shell validation (exact scope)

| Check | Scope | Result |
|-------|-------|--------|
| compileall | capt_runtime, capt_solo, desktop, capt_cli.py | PASS (exit 0) |
| mypy | capt_runtime/verification.py, capt_runtime/store.py | PASS (no issues) |
| ruff (E,F) | capt_runtime, capt_solo, desktop, capt_cli.py | 45 pre-existing errors (40 in capt_cli.py E702; 2 E731 in capt_runtime_service.py lines 613/625 pre-existing at committed head; no new errors from this work) |
| bash -n | install.sh, verify.sh, doctor.sh, uninstall.sh | 4/4 PASS |

Full-rule-set ruff reports 2244 pre-existing style/modernization errors (UP etc.); there is no repo ruff config, and this work introduces none.

## 5. Installed Hermes lifecycle evidence

Preserved at `release_evidence/v0.5/installed-model-operator/`:
- `README.md` (proof narrative)
- `manifest.json` (identity + ledger heads)
- `sanitized-transcript.md` (commands + receipts)
- `sanitized-ledger-export.json`
- `event-timeline.json`
- `persisted-verification-payload.json`
- `persisted-evidence-payload.json`
- `claimguard-decision.json`
- `idempotency-receipt.json`
- `restart-resume-receipt.json`

**Classification:** LOCALLY executed; INSTALLED-wheel; real Hermes process; externally dependent model/provider; **NOT rerun by hosted CI**. First mission hit provider rate limit (HTTP 429) but completed normatively; second mission produced a full substantive response.

## 6. Subsystem reachability (precise)

| Subsystem | Classification |
|-----------|----------------|
| CAPT Solo Memory Engine (capt_solo.memory.engine) | IMPORTABLE_API / API_ONLY |
| Runtime Memory Governor (capt_runtime.memory.governor) | INTERNAL_RUNTIME_SERVICE |
| ContextPack / 32K ladder | INTERNAL_RUNTIME_SERVICE (behavior enumerated + tested) |
| KHSB | INTERNAL_RUNTIME_SERVICE (in-process only; not cross-process/durable) |
| CTP | INTERNAL_RUNTIME_SERVICE (operational journal; EventStore owns immutable ledger) |
| Hermes driver | OPERATOR_FACING via `capt harness command run_approved_hermes_inspection` |

See `release_evidence/v0.5/requirement-evidence-matrix.json` (34 claims) and `public-claim-audit-corrected.md`.

## 7. CI security-gate classification

`release-security.yml` now emits an explicit `SECURITY_GATE` classification:
- **FULL_SECURITY_GATE** when anti-token-extraction installs+verifies
- **DEGRADED_OPTIONAL_DEPENDENCY** when it cannot clone (hosted-CI reality: the private dependency fails to install)
- A guard step fails the job if the classification is missing (never silent green)

Coverage threshold (`--cov-fail-under=80`) removal is **documented as intentional/deferred** (diagnostic only; anti-token absence would distort the denominator).

## 8. Runtime-code blockers

**NONE.** The runtime implementation is complete and the installed lifecycle is proven.

## 9. Evidence/documentation blockers

- The PR #33 body must be updated to the new accurate evidence (it currently references the stale 4005809 wheel hash and the single "722 passed" figure). This is in progress in this closure.
- Package-metadata deprecation (project.license table + license classifier) is classified as deferred packaging debt; converting to SPDX string requires setuptools≥77 and is not a runtime blocker.

## 10. Deferred separate-repository / separate-product work

- **PR #19** (feature/hermes-capt-core-runtime-skill): separate Hermes compatibility product — REQUIRES_SEPARATE_PRODUCT.
- **knowurknottty/capt-workspace-mcp**: separate integration product.
- **Treasure Chest** (knowurknottty/captstreasurechest): workflow reconciliation — out of this repo.

## Verdict

**Technical:** POST_REPAIR_INSTALLED_RELEASE_PROVEN (final-head wheel f70c3a0e... built, hashed, installed, validated; installed Hermes lifecycle proven on the 4005809 proof wheel which is source-identical for runtime .py and superseded by the final-head wheel of identical package content).

**Merge:** The runtime and evidence closures for PR #33 are complete and machine-verifiable; PR #33 can be moved out of draft after the body update and CI re-pass.
