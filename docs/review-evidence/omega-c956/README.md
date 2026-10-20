# OMEGA RRDS evidence — c956c45e frozen source

**Source commit:** c956c45e33119cd31ce7e61c55334e803f20bf3f (not later current main). **This directory provides mechanically complete file/line accounting, NOT a certified semantic deep review.**

- **tracked-content-sha256.txt:** SHA-256 of all **1,032 Git-tracked paths** at this exact commit, excluding the Git worktree's private .git pointer.
- **automated-structural-source-index.json:** source-file structural records produced by a journaled CAPT Node read of **681 source files**, totaling **6,224,814 bytes**. Includes declaration/line mappings, import and security marker summaries, and syntax diagnostics. Original artifact SHA-256: 197b3c248ae2864839fc22a030f491fb6fe3a06bb42c530b594b03513f8920d6. Node operation: omega-rrds-c956-full-scan-20261018-02.
- **mechanical-inspection-receipts.json:** per-file SHA-256 plus exact source-line/symbol evidence, marked **AUTOMATED STRUCTURAL INSPECTION ONLY**; all 411 risk candidates declared.
- **mechanical-coverage-verdict.json:** actual RRDS verify output after clearing test-generated caches in the dedicated temporary checkout. Status **DEEP_COVERAGE_GATE_PASS** for structural receipt breadth, 681/681 and 47/47 directories.

**Limitations:** This verifier checks digest accounting and line evidence format, but **does not prove semantic understanding**. Node evidence references are opaque to the tool, rather than checked against a cryptographically authenticated remote journal. Complete hashes and line references are not themselves evidence of comprehensive architectural source review. Separate model/human verification should re-enumerate, falsify fixtures and examine critical entry/authority/effect/witness paths.

**Independent verifier report:** [Codex adversarial verification](independent-codex-verification.md) is preserved substantively, with only Markdown trailing whitespace normalized for Git hygiene. It independently re-hashed all 681 source files and verified 5,617 declaration locators, but inspected only 26 critical implementation boundaries semantically. Its verdict was mechanical coverage **PASS**, semantic completeness **PARTIAL**, independent certification **FAIL / withheld**. The report refers to the original validator and original L1 empty-file locator; subsequently hardened receipts in this folder use an explicit L0 empty-file marker and a source-line byte-span SHA-256. Never overwrite or retroactively revise the verifier's historical findings.

**Hardened gate recheck:** With follow-up RRDS hardening revision 1267262aaec27dd29f9a60838cafd0e09172f5c5 (not included in the earlier merged PR #225; not yet on main), all 681 receipts rechecked successfully, and four deliberately corrupted fixtures (forged source/risk classification, bogus line hash, duplicate census path, and invented line of an empty file) were rejected. This newer structural gate still cannot verify semantic comprehension or remote Node journal authenticity, so the independent sign-off remains withheld.

**Not release-certified:** This dossier is **NOT in the certified docs/review-evidence/rrds-index.json index**. Do not label RRDS-1 deep review PASS or add it to that index until the complete separate semantic verifier review is accepted. A new main commit requires new evidence, not an inherited receipt.

**Data:** Only public Git-tracked source paths and symbol summaries, no operator EventStore tokens, private paths, or provider secrets.
