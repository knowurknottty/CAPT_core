# Donor Integration Report — R1 (Cohort 3/3 Final Convergence)

- Council `council-capt-donor-convergence-r1-20260924` · Mission `m-capt-donor-convergence-r1-20260924`
- Cohort: glm53-flash (z-ai/glm-5.3-flash via openrouter), configuration `donor-convergence-r1`
- Head at execution: `ba0f315` + uncommitted integration edits (see §2); branch `feat/openworker-convergence-r1`
- Continuation evidence consumed: `~/.capt/staging/dr-capt-donor-mimo26-r3/provider-analysis-dr-capt-donor-mimo26-r3.md` (cohort 2/3 donor matrix, 33-candidate charter, 11 vessels) and `~/.capt/staging/dr-capt-donor-qwen38-r5/provider-analysis-dr-capt-donor-qwen38-r5.md` (cohort 1/3: ls-remote feasibility observation).

## 1. Starting state (observed, not remembered)

- Cohort 1/3 left no ledger/report/commits (confirmed by r3; unchanged this round). Only donor-code baseline: `e8ee447` openworker compat.
- Cohort 2/3 froze all donor HEADs + licenses (40 rows; prose said 41 — discrepancy recorded) and designed but did not implement the gitleaks-derived redaction (tool budget exhausted). Its §5 BLOCKED items were this round's work queue.
- Working tree at start of this pass already contained the redaction integration as uncommitted edits with CAPT execution receipts/rollbacks attached (file-mutation receipts in-tree), plus the registry test file. Verification status was UNPROVEN. This pass verified, completed, and documented that work rather than rescanning donors.

## 2. Integrated mechanism: gitleaks-derived provider-token redaction (CHERRY_PICKED → INTEGRATED)

**Gap (evidence from r3, verified by inspection this round):** CAPT's three redaction layers had no provider-specific token patterns. A bare OpenRouter/AWS/GitHub/HF/JWT token under a benign key name could traverse flight-bundle export, discovery evidence, or memory screening in clear text. `security_gate.py` lists "secret scan" only as an unimplemented checklist hint.

**Donor provenance:** gitleaks/gitleaks @ `b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b`, MIT © 2019 Zachary Rice; frozen SHA live-re-queried this round — NO DRIFT. Form: hand-adapted 14-regex registry (upstream rule ids recorded per pattern), not a config transplant; CAPT-native additions labeled as such; MIT notice + frozen SHA retained in the module; stdlib-only (no dependency-surface widening).

**Wiring (4 surfaces):**
| Surface | Change | Semantics |
|---|---|---|
| `capt_runtime/secret_patterns.py` (new) | `CREDENTIAL_PATTERNS` registry, `find_credential_shapes`, `redact_credential_shapes` | detection + family-labeled redaction; private_key/AWS(AKIA,ASIA,ABIA,ACCA,A3T)/GitHub PAT + fine-grained/GitLab/HF/npm/Linear/Google/Stripe/Slack(+webhook)/OpenRouter/generic `sk-`/JWT |
| `capt_runtime/discovery/redaction.py` | registry runs **first**, then legacy heuristics | family markers survive before generic long-token clobbering |
| `capt_runtime/flight_recorder.py` | registry applied to **every string value** in forensic bundles | tokens under benign keys cannot leave the bundle; digest strings deliberately preserved so manifests stay verifiable |
| `capt_solo/memory/secrets.py` | 5 provider families added to durable-memory screening | closes the bare-token-persists-in-memory hole; local copy preserves module decoupling (verified: no `capt_solo→capt_runtime` import exists anywhere) |

**Deliberate non-wiring (with rationale, not omission):**
- `governed_composition.py`: digest-input surface; secrets omitted by key and references hashed — hashing is not disclosure; registry substitution would churn composition digests. REJECT.
- `security_gate.py`: catalog describes required *evidence*, does not execute scans; conflating them would weaken fail-closed release semantics. The registry now supplies the local scan primitive for that evidence. REJECT for this round.

**Discriminating tests** (`tests/capt_runtime/test_secret_pattern_registry.py`, 12):
registry/fixture bijectivity (adding a pattern without a fixture fails; fixture rot fails); per-family detect+redact in every wired layer; benign false-positive negatives (SHA-256 digests, UUIDs, prose like "sk-2 is a keyboard key", `AKIAXYZ` short strings) must survive all layers; end-to-end flight-bundle export with a fine-grained GitHub PAT under a benign key must not appear in the archive in clear text; memory-screen bare-provider-key regression; provenance-retention assertion (frozen SHA + MIT notice must remain in the module). Fixtures are assembled at runtime so no source line contains a contiguous credential literal.

**Mutation discriminability (r3 vessel v0007's bar, executed):** disabling the `github_pat` pattern → 3 tests fail; restored → 12/12. Not vacuous.

## 3. Verification gates (executed this round)

| Gate | Command/interpreter | Result |
|---|---|---|
| Targeted registry tests | `~/CAPT_core/.venv/bin/python -m pytest tests/capt_runtime/test_secret_pattern_registry.py` | 12 passed |
| Full CAPT suite | same venv, `python -m pytest -q` | **1573 passed, 18 skipped, 13 deselected, 0 failed** |
| Contract drift | `python3 contracts/tools/check_drift.py` | OK — 11 generated files match schema source |
| Diff hygiene | `git diff --check` | clean (exit 0) |
| Mutation check | pattern disabled → targeted suite | 3 failed → restored → green |
| SHA drift (gitleaks) | `git ls-remote` | NO DRIFT |
| Push/merge/publish | — | NOT performed (mission invariant) |

Environment honesty: system `/usr/bin/python3` (3.9) cannot collect the suite (`datetime.UTC` absent; 27 collection errors) — environmental, not code. Under `/opt/homebrew/bin/python3.12` without project deps, 25 failures were all `ModuleNotFoundError: textual` — also environmental. Green run used the project venv (`~/CAPT_core/.venv`, Python 3.12.13) where all deps resolve.

## 4. Donor dispositions

Full 40-donor matrix with frozen SHAs, licenses, and finalized dispositions: **`docs/convergence/DONOR_LEDGER_OPENWORKER_OPENJIUWEN_R1.md`** (§3). Summary deltas vs the r3 provisional labels:

- gitleaks: CHERRY_PICK_CANDIDATE → **INTEGRATED** (this round; the only disposition upgraded to code).
- All other rows: r3 dispositions upheld; the "(provisional)" ALREADY_PRESENT labels remain provisional — semantics equivalence UNPROVEN (no mechanism inspection this round).
- openworker: INTEGRATED baseline unchanged (`e8ee447`); no further cherry-picks justified this round (remaining mechanisms are runtime/plugin/GUI domains that would rival CAPT control planes or need governed-network gating that does not exist yet).

## 5. Known corruption event (honesty record)

During this round's first ledger write, a degenerative loop produced a corrupted artifact; it was detected by post-write verification, overwritten with the clean ledger, and verified byte-level (no loop artifacts; 57 table rows; all 40 donors present). The corrupted draft was never committed. Recorded here because completion claims must include tool-failure history, not hide it.

## 6. Weak spots / weak evidence (explicit)

1. **39-donor SHA drift re-query: UNPROVEN** (only gitleaks re-queried). Open mechanizable follow-up.
2. **≈38 donors lack mechanism inspection**; dispositions rest on license, domain fit, and CAPT-inventory reasoning. The r3 caveat stands.
3. snyk/agent-scan identity at frozen SHA; semgrep LGPL version: UNVERIFIED.
4. The redaction integration's provenance header states it is "not a wholesale copy" — true for the code shape (hand-adapted regex subset + notice), but upstream's full rule catalog is far larger; CAPT's registry is a high-precision subset, and a clean scan never proves absence of secrets (stated in the module docstring).
5. Full-suite green is evidence at this HEAD with this interpreter; it does not constitute release evidence (release gate is `security_gate.py` with operator-supplied evidence at an exact SHA — not run, not claimable here).

## 7. Completion statement (bounded)

Mission-required artifacts now exist: donor ledger (§4 above), integration report (this file), discriminating tests for the one enabled consequential mechanism, and the source changes it requires. Contract drift, targeted tests, full suite, and diff checks executed clean; no push/merge performed. What remains open is enumerated in §6 and the ledger §7 — none of it silently dropped. Any claim beyond this (e.g. "all donors mechanically inspected", "release-ready") is **UNPROVEN** and asserted by no one in this council chain.