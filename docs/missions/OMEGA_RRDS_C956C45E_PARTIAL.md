# OMEGA / RRDS-1 — CAPT Core current-source review (PARTIAL)

**Date:** 2026-10-18 (America/Chicago). **Target:** `knowurknottty/CAPT_core` `main`, `c956c45e33119cd31ce7e61c55334e803f20bf3f`. **Verdict:** `PARTIAL_OR_UNVERIFIED`, **not** `DEEP_COVERAGE_GATE_PASS`.

## Scope and preservation

- Exact local and remote `main` match the pinned SHA above. The reviewer and separate check worktrees were detached at that SHA; neither contained the in-progress uncommitted OMEGA Markdown.
- All existing untracked operator evidence and user files were preserved in the original checkout. Neither product code, historical release reports, root `AGENTS.md`, licenses nor provenance canary were altered in this documentation tranche.
- Historical v0.5 and September/October snapshot claims are not promoted to current-HEAD release authorization. The current package still declares `capt-solo 0.5.0`.

## Recursive census and separate-worktree re-enumeration

| Measured condition | Reviewer worktree | Second worktree |
|---|---:|---:|
| Git-tracked tree files | 1,032 | 1,032 |
| RRDS census entries | 1,033 | 1,033 |
| In-scope source files | 681 | 681 |
| Source directories | 47 | 47 |
| Risk-classified source candidates | 411 | 411 |
| Unreadable files | 0 | 0 |
| Symlinks | 0 | 0 |
| Matching Git-tracked file bytes | 1,032 / 1,032 | 1,032 / 1,032 |

The extra census entry is the untracked-by-Git **`.git` pointer file** created separately in each worktree. RRDS excludes `.git` directories but currently records a regular `.git` file; raw worktree census digest maps therefore disagree at `.git` alone. Removing only that repository-control metadata entry from the comparison yields **exact file/digest equivalence**. The two full census JSONs and inspection/verdict JSONs were generated outside the repository in the operator's temporary review directory. This is a **tooling discrepancy to fix**, not a source mismatch or justification to weaken the RRDS gate.

Test runs generated Git-ignored Python caches. RRDS currently walks those caches too, so a test run between census and verification causes `tree membership drift`. After cleaning only the dedicated temporary checkout's generated cache files, the definitive gate result below had no membership-drift problem.

## Actually inspected and journaled file/line receipts

CAPT Node operation `omega-rrds-c956-source-receipts-20261018-01` returned exit 0 and a durable stdout evidence digest. It printed the SHA-256 and selected source lines for these **15 files** at the pinned HEAD. [Machine-readable receipts](OMEGA_RRDS_C956C45E_RECEIPTS.csv) repeat the relative paths, SHA-256, actual line span and operation identity.

| Source | Examined lines | Evidence-bound observation |
|---|---|---|
| [`capt_runtime/services.py`](../../capt_runtime/services.py) | L40–L63 | RuntimeService commits events before dispatch |
| [`capt_runtime/store.py`](../../capt_runtime/store.py) | L136–L166 | EventStore transactional SQLite state and initialization |
| [`capt_runtime/governed_service.py`](../../capt_runtime/governed_service.py) | L187–L212 | Bot registration requires authority and commits identity |
| [`capt_runtime/cli_ramp.py`](../../capt_runtime/cli_ramp.py) | L52–L89 | Runtime-health probe authenticates over local IPC |
| [`capt_runtime/provider_model_preflight.py`](../../capt_runtime/provider_model_preflight.py) | L27–L76 | Official OpenRouter metadata GET and bounded failure classification |
| [`capt_runtime/drivers/provider.py`](../../capt_runtime/drivers/provider.py) | L943–L960 | Exact-origin preflight before authorized inference |
| [`capt_runtime/aggregates/human_approval.py`](../../capt_runtime/aggregates/human_approval.py) | L40–L80 | Bounded HumanApproval state/fields |
| [`capt_runtime/aggregates/bot.py`](../../capt_runtime/aggregates/bot.py) | L30–L47 | Bot identity fields and delegation prerequisites |
| [`capt_runtime/biocapt_cohort_reader.py`](../../capt_runtime/biocapt_cohort_reader.py) | L44–L90 | Lease-checked, read-only bioCAPT boundary |
| [`capt_runtime/tool_broker.py`](../../capt_runtime/tool_broker.py) | L70–L105 | ToolBroker source boundary (selected lines only) |
| [`capt_runtime/driver_host.py`](../../capt_runtime/driver_host.py) | L30–L80 | DriverHost source boundary (selected lines only) |
| [`scripts/capt_repo_audit_gate.py`](../../scripts/capt_repo_audit_gate.py) | L95–L160 | RRDS-1 inspection and deep-coverage gate logic |
| [`tests/capt_runtime/test_provider_model_preflight.py`](../../tests/capt_runtime/test_provider_model_preflight.py) | L1–L50 | Deterministic no-inference preflight checks |
| [`tests/capt_runtime/test_bot_foundation_service.py`](../../tests/capt_runtime/test_bot_foundation_service.py) | L1–L45 | Bot authority test coverage, selected lines |
| [`capt_cli.py`](../../capt_cli.py) | L115–L139 | Declared CLI and Solo-memory command surface |

**Coverage limit:** selected line ranges are not exhaustive inspection of even these 15 files. The receipt count is an accounting measure, **not** proof that all code paths or contracts in each file were understood.

## Formal RRDS gate

The repository's own `scripts/capt_repo_audit_gate.py verify` was executed on the frozen reviewer census and 15 journaled file receipts. It returned **exit 1** and `PARTIAL_OR_UNVERIFIED`: **15/681 source files (2.2%)** with receipts across **6/47 source directories**; **398 risk-classified paths** remained uninspected. It correctly reported the missing breadth and 100% deep-review requirement. **Do not merge or market this as full audit completion.**

Falsification checks in the second worktree executed three existing RRDS tests: shallow one-level review, altered source after inventory, and one-inspection-per-directory without full-file coverage. **3 passed, 6 deselected**. This is a separate-worktree technical check by the **same assistant**, **not** a separate human or independent model verifier. An independent verifier's final sign-off is still outstanding.

## Why RRDS CI can be green while this review is still PARTIAL

The PR's **RRDS-1 Reviewer Evidence Gate** completed successfully, but the checked-in [`docs/review-evidence/rrds-index.json`](../review-evidence/rrds-index.json) contains `"reviews": []`. The `ci` mode of [`scripts/capt_repo_audit_gate.py`](../../scripts/capt_repo_audit_gate.py) validates the available indexed reviews; when there are **zero** and the PR body does not claim `RRDS-1: PASS`, it can return success. This is the gate's intentional **zero-certified-reviews** case, **not** acceptance of the off-repo partial census as a passing full-depth review.

Thus: **CI green = no indexed invalid deep review; local `verify` = explicit `PARTIAL_OR_UNVERIFIED`.** Full independent deep verification still requires in-scope line/source receipts and a separate verifier before anyone uses the wording `RRDS-1: PASS`. Do not silently add this partial dossier to the release-certified index.

## Current-HEAD execution evidence

On the clean reviewer worktree, 11 selected Python test modules covering provider model preflight, driver, recovery, CLI/runtime, RRDS, Bot, bioCAPT/QIPC and claim-once returned **112 passed, 1 skipped in 12.57s, exit 0**. The existing Python virtual environment was reused; **fresh dependency installation, all other Python test trees, Swift native build/tests, live provider/billing reconciliation and security/release pipeline were NOT RUN**.

Current-HEAD source adds pre-inference OpenRouter model metadata GET (official origin only, no model prompt in catalog request) and authenticates runtime health probes instead of generating spurious denials. See [provider documentation](../PROVIDERS.md), [troubleshooting](../TROUBLESHOOTING.md) and [source delta](../CURRENT_HEAD_DELTA.md). Network metadata lookup is distinct from inference and does not guarantee model quality, capacity or cost.

## Full runtime-suite follow-up (isolated macOS path experiment)

The first `tests/capt_runtime` run in a long macOS temporary workspace returned **1,656 passed, 14 failed, 13 skipped, 12 deselected**. Most failure traces explicitly reported `AF_UNIX path too long`; the failing group included socket-based Bot, local provider, media, recovery and Docker-context tests. **That first run remains a historical FAIL and has not been erased.**

The **same 14 failed cases** were rerun with a short `--basetemp=/tmp/oc.XXXXXX` path and all **14 passed in 10.09s**. Finally, a **complete repeat of `tests/capt_runtime` at the same pinned HEAD** with short `--basetemp` plus isolated `CAPT_STATE_DIR` and `CAPT_SOLO_HOME` returned **1,670 passed, 13 skipped, 12 deselected, 0 failed, in 85.64s; exit 0**. The exact checkout and Python 3.12 environment were unchanged.

**Interpretation:** a long pytest base path caused environment-dependent socket test failures on macOS; correcting the path removed every observed failure and the complete rerun passed. This is **runtime-test evidence**, not full repository Python/Swift/release certification or a 100%-reviewed source tree. Future documentation of macOS test execution should use a short dedicated temporary directory for socket fixtures.

## Follow-up independent-review attempt — not accepted

After draft PR #224 opened, a separate read-only **MiMo 2.6 Flash** source/documentation review was authorized once through CAPT RuntimeService. The transport timed out. Its immutable runtime projection subsequently showed **DriverRun `lost`**, dispatch boundary **`request_started`**, **`reconciliationStatus=required`**, and **four recorded provider HTTP request attempts**. The associated task was **`suspended`** with no result references. No verified reviewer artifact or independent RRDS-1 sign-off was produced; **no replay was authorized**. Provider-side completion and possible charges remain **unknown pending reconciliation**. A separate model attempt and the existing same-agent cross-worktree check must **not** be presented as an independent verifier PASS.

## High-value findings / next actions

| Priority | Finding / scope | Proposed action |
|---|---|---|
| HIGH (audit quality) | Worktree `.git` control file is counted as reviewed tree material despite being revision-irrelevant; Git-ignored cache files produce census drift | Separate tracked/source accounting from worktree metadata; add regression tests before any product-code change |
| MEDIUM (preflight, now resolved on later main) | At audited `c956c45e`, the text metadata preflight accepted a string `id` without requiring equality to the approved model (L73–L76). | **Resolved in merged [PR #223](https://github.com/knowurknottty/CAPT_core/pull/223)** after the audited SHA, using `PROVIDER_MODEL_PREFLIGHT_INVALID` and a negative fixture; a follow-up end-to-end no-inference regression is tracked in [PR #226](https://github.com/knowurknottty/CAPT_core/pull/226). Historical findings remain bound to their pinned source. |
| HIGH (documentation freshness) | October 8 state report and September/October matrices lag 134 commits | Preserve snapshots; maintain current-HEAD delta with source/test provenance and release gates |
| HIGH (coverage) | 666/681 source files and 398 risk-classified source paths lack deep-review receipts | Batch governed source reads, run the gate again and secure a genuinely independent verifier |

## Full structural coverage and independent challenge — continuation

**Frozen source:** c956c45e33119cd31ce7e61c55334e803f20bf3f (current main later advanced to 40e9a964 through unrelated PR #223). Journaled CAPT Node operation omega-rrds-c956-full-scan-20261018-02 read every source blob from the frozen Git tree, producing a **681-file / 47-directory / 6,224,814-byte** deterministic AST and source-line index. An independent local-byte comparison rehashed all 681 paths; 647 files have verified named-declaration locators and 34 structural or empty-file locators (one empty file originally used invalid L1, now corrected in the hardened derived receipts to L0). The raw scan's SHA-256 remains 197b3c248ae2864839fc22a030f491fb6fe3a06bb42c530b594b03513f8920d6.

Under the **original, unmerged baseline validator**, the 681 receipts returned DEEP_COVERAGE_GATE_PASS with no coverage errors; a falsification replacing all line claims and journal refs with fake text ALSO returned PASS, proving that this status did not establish trustworthy semantic or journal evidence.

Under a **separate, not-yet-merged RRDS hardening revision 1267262a** (the previously merged PR #225 contains only the original .git-pointer fix), now including independently derived source/risk classification, duplicate-census rejection, checked source-line byte spans and L0 empty-file representation, the corrected 681 receipts returned DEEP_COVERAGE_GATE_PASS (mechanical accounting only). Four independent negative input fixtures were rejected. PR #225's local RRDS regression suite returned **17 passed**. This is an improved formal gate, **not a completed deep review certification**, nor evidence that the revised gate had merged into baseline main.

A **separate Codex verifier** read the frozen source independently and rehashed all 681 source files and 5,617 declaration references. It inspected 26 critical boundaries semantically, rejected false audit-gate classifications, and documented substantive implementation concerns, including ineffective memory project/trust filters, mutable prepared mappings, and bounded authorization-helper assumptions. Its exact, unedited [verifier report](../review-evidence/omega-c956/independent-codex-verification.md) concludes: **mechanical PASS; semantic review PARTIAL; independent sign-off FAIL/WITHHELD**. A fully independent semantic source sign-off, source-level remedies, live external integrations, current-main rebaseline and release authorization are still outstanding. **No PR merged and no external bills claimed.**

## Publication boundary

Use this report only as **explicitly partial evidence** for documentation review. Its public receipt CSV contains source relative paths and digests, not credentials or private CAPT state. The report does not claim a current-head security authorization, installed app, autonomous CAPT-Bot R5 operation or complete RRDS deep review. See [OMEGA mission status](OMEGA_20261018_STATUS.md).
