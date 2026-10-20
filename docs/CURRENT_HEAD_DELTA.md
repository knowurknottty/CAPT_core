# CAPT Core current-HEAD delta — selected evidence, not full rebaseline

**Checked:** October 18, 2026 (US Central). **Reviewed Core snapshot:** `c956c45e33119cd31ce7e61c55334e803f20bf3f` (then-current `main`, not a continually refreshed revision). The preceding OMEGA model-review pass used `0d8e46d095243e80febd4e30f5ae52c9202316d9`. **Audit status: PARTIAL, not release-certified.**

The [capability matrix](CAPABILITY_MATRIX.md) is a September 15 snapshot; [functionality](FUNCTIONALITY_MATRIX.md) and [current-state](CURRENT_STATE.md) documents preserve October 8 evidence. There are **134 intervening commits** (`80d3b82..c956c45e`); the prior 128-commit/156-path baseline described the earlier `0d8e46d` head. Commit subjects are discovery leads, not proof of full feature or release maturity.

## Source and targeted-test reconciliation

| Subsystem | Tracked source at pinned HEAD | Evidence boundary |
|---|---|---|
| CAPT Bot identity | [`aggregates/bot.py`](../capt_runtime/aggregates/bot.py), [`governed_service.py`](../capt_runtime/governed_service.py) `register_bot`, [Bot schema](../contracts/schema/bot.schema.json), [native BotBrowser](../capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/BotBrowserView.swift) | Source present; selected Bot tests pass. Not a complete autonomous CAPT-Bot R5 release |
| Optional bioCAPT QIPC | [Runtime opt-in startup gates](../desktop/capt_runtime_service.py) and [read-only cohort reader](../capt_runtime/biocapt_cohort_reader.py) | Source present; selected host and reader fixtures pass. Not proof of a live integrated bioCAPT service |
| Claim-once handoff | Commit `3239a017`; [dedicated test module](../tests/capt_runtime/test_claim_once_handoff.py) | Selected tests pass. No general external exactly-once guarantee established |
| Broader 128-commit delta | Includes approval/reconciliation, provider/credential controls, packaging, calibration and loop detection | Not exhaustively reviewed; needs independent RRDS-1 source receipts |

### Actual executed test batch

From the pinned checkout, using its existing Python 3.12 environment:

```zsh
.venv/bin/python -m pytest -q \
  tests/capt_runtime/test_bot_foundation_aggregates.py \
  tests/capt_runtime/test_bot_foundation_contracts.py \
  tests/capt_runtime/test_bot_foundation_service.py \
  tests/capt_runtime/test_biocapt_cohort_reader.py \
  tests/test_biocapt_qipc_runtime_host_optin.py \
  tests/capt_runtime/test_claim_once_handoff.py
```

**Observed:** `54 passed, 1 skipped in 0.41s`, exit 0, using a renewed governed CAPT Node capability. The six modules cover several separate behaviors; **do not** count all 54 as Bot tests. This is not a clean-install run, a complete suite, a Swift verification, or live model/provider acceptance.

## Latest source changes, PR #221 and PR #222

| Change at reviewed `c956c45e` | Verified exact source boundary | Consequence / remaining proof |
|---|---|---|
| OpenRouter catalog preflight (PR #222, `a30a3808`) | [`provider_model_preflight.py`](../capt_runtime/provider_model_preflight.py) L27–L76; [`drivers/provider.py`](../capt_runtime/drivers/provider.py) L943–L960 | Bounded authenticated official-origin **GET** before authorized inference; text/image modality classification and failure codes. **No live provider smoke or billable inference run** in this documentation pass |
| Authenticated local runtime-health probe (PR #221) | [`cli_ramp.py`](../capt_runtime/cli_ramp.py) L52–L89 | Validates local token-file permissions and IPC authentication instead of generating unauthenticated connect/close noise; actual installed-runtime effect not release-certified |
| Provider answer normalization (PR #221) | [`drivers/provider.py`](../capt_runtime/drivers/provider.py) response handling and tool-message boundary | Avoids outbound tool reply `name` and handles final-facing structured text; selected fixtures pass, but a historical failed cloud run is **not** retroactively diagnosed |
| Review source breadth and independent replication | [RRDS-1 partial review](missions/OMEGA_RRDS_C956C45E_PARTIAL.md) with [15 journaled line receipts](missions/OMEGA_RRDS_C956C45E_RECEIPTS.csv) | Two clean worktrees agree on all 1,032 tracked bytes; formal gate **PARTIAL_OR_UNVERIFIED**, **15/681 source files**; an independent reviewer approval is still missing |

### Current-HEAD test evidence (distinct from older tests)

A clean detached worktree at `c956c45e` was checked using the pre-existing Python 3.12 virtual environment. **Eleven selected test modules returned 112 passed, 1 skipped in 12.57 s, exit 0**, covering provider preflight, driver, recovery, CLI, RRDS, Bot foundation, bioCAPT/QIPC, and claim-once. In a second detached worktree, three RRDS falsification tests passed (shallow scan, post-census source mutation, incomplete per-directory inspection).

These are **selected test receipts**, not a full current-HEAD Python or Swift suite. Source/model availability, a non-inference catalog GET and a paid model completion are three separate proof obligations.

### Broader runtime-test verification

A long temporary-directory test run initially produced **1,656 pass / 14 fail / 13 skip / 12 deselected** with `AF_UNIX path too long` failures. Retesting precisely those 14 with a short macOS `--basetemp` yielded **14 pass**. A **full `tests/capt_runtime` rerun at `c956c45e`**, using a short `--basetemp` and isolated runtime/Solo state roots, then yielded **1,670 passed, 13 skipped, 12 deselected, 0 failed (85.64s; exit 0)**.

The negative initial run remains recorded; the corrected run is the applicable scoped result. See the [RRDS/verification ledger](missions/OMEGA_RRDS_C956C45E_PARTIAL.md). Other Python test trees, Swift, fresh packaging, live dependency acceptance and release authorization are **not covered** by this receipt.

## Separate CAPT-Bot repository boundary

The local [CAPT-Bot repository](https://github.com/knowurknottty/CAPT-Bot), observed at `a2ecdb752eeeb88a834839fb0591e375e104fbf8`, identifies **R5 convergence** as an unfinished workstream. Older isolated patches and compatibility tests do not certify integration into current CAPT Core. Core-owned Bot registration must not be confused with Bot-owned cognition, delegation and end-to-end autonomous work.

A governed **MiMo 2.6 Flash** source-review run was completed with a result artifact pending human verification. It did not execute as a CAPT-Bot worker. [Peer-review correction ledger](missions/OMEGA_MIMO26_PEER_REVIEW_20261018.md).

**RRDS CI distinction:** A green PR `verify-coverage` workflow does **not** certify this deep review. The checked-in review index contains zero entries, while the explicit 15/681-source-file `verify` command returned `PARTIAL_OR_UNVERIFIED`. See [the formal reconciliation](missions/OMEGA_RRDS_C956C45E_PARTIAL.md).

**Verification continuation:** [681-file structural evidence and independent Codex verifier verdict](review-evidence/omega-c956/README.md) are now available. The mechanical audit breadth gate passed, but a separate semantic verifier withheld independent sign-off. This evidence is pinned to c956c45e; after unrelated PR #223, main first moved to 40e9a964 and subsequently advanced further through other merges. Source claims at c956 are not automatically a 40e9 rebaseline. See the [full partial-review ledger](missions/OMEGA_RRDS_C956C45E_PARTIAL.md).

**Outstanding:** full source-cited 134-commit delta, independently certified RRDS-1 deep review, complete Python/Swift suite, clean install, live integration, release-security and distribution proof. [OMEGA mission status](missions/OMEGA_20261018_STATUS.md).
