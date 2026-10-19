# OMEGA v3 — CAPT Core documentation mission 001

**Mission:** evidence-first documentation improvement on CAPT Core. **State:** PARTIAL — reader-documentation work performed; not a complete independent RRDS-1 deep audit, full regression pass, or release. **Date:** 2026-10-18.

## Pinned inputs and preservation

- Canonical remote: `https://github.com/knowurknottty/CAPT_core`.
- Working checkout: local `main` worktree; absolute user-specific filesystem path intentionally omitted.
- Pinned local and remote main: `0d8e46d095243e80febd4e30f5ae52c9202316d9`.
- Package metadata and installed CLI identify `capt-solo 0.5.0` (source and installed metadata, not release certificate).
- Initial tracked-file diff: empty.
- Pre-existing untracked files and local evidence directories preserved untouched; their user-specific names are intentionally omitted from this public report.
- No repo root agent/provenance/license/security policies edited, no product code edited, no commit/push/merge/release performed.

## Census receipt

- **1,028 Git-tracked files** were enumerated and hashed with SHA-256 from on-disk bytes while tracked files matched the pinned source; **0 unreadable tracked files** and **0 tracked symlinks** were reported.
- Manifest: [pinned tracked-file census](OMEGA_20261018_PINNED_CENSUS.sha256). It deliberately excludes untracked evidence, runtime data, caches, and other worktrees.
- Initial docs inventory: **214 physically present `.md` files** under `docs/`: **213 Git-tracked** plus **one pre-existing, untracked local mission note**. Of the physical files, **53** were in the `docs/` root and **8** in `docs/CHEATSHEETS/`. The 213 pinned tracked documents, their H1 titles, last-touch commit and *preliminary*, explicitly unreviewed classification are in [the machine-readable documentation inventory](OMEGA_20261018_DOC_INVENTORY.csv).
- **Important:** hashing is not deep review. The manifest has not been independently re-enumerated in a second verifier worktree, source-line inspection receipts are incomplete, and `DEEP_COVERAGE_GATE_PASS` has not been obtained.
- In-scope continuation: `capt_runtime/`, `capt_solo/`, `capt_ui/`, `desktop/`, `contracts/`, `integrations/`, `scripts/`, `tests/`, and relevant docs/release gates.

## Finding register

| ID | Observation and evidence | Severity for documentation | Disposition |
|---|---|---|---|
| DOC-001 | Root README begins with multiple October 8 media milestones before the install and reader navigation; checked `README.md` headings | Medium | Add front-door reader routing while preserving milestone histories |
| DOC-002 | `docs/README.md` and `START_HERE.md` retain September 15 source snapshot wording | Medium | Clarify historical snapshots and link current pinned observation |
| DOC-003 | `docs/CURRENT_STATE.md` describes an October 8 source head `80d3b82`; `git rev-list --count 80d3b82..HEAD` returned **128**, and `git diff --stat` found **156 changed files** | High | Explicit dated-state notice; **do not** claim a new capability matrix is verified |
| DOC-004 | First-class public ELI5, glossary, persona onboarding and technical-manual paths were missing as standalone canonical pages in observed `docs/` filenames | Medium | Add navigation-focused guides linked to source/canonical references |
| DOC-005 | Original doc suite already has a generated API and extensive cheatsheet collection | Medium risk of duplication | Preserve and link rather than regenerate |
| DOC-006 | Root `AGENTS.md` requires RRDS-1, including independent verifier and 100% in-scope source coverage | Critical to review verdict | Maintain `PARTIAL`; no unsupported deep-review claim |

## Verified local commands and receipts

| Command / check | Actual outcome | Scope |
|---|---|---|
| `git rev-parse HEAD` | `0d8e46d095243e80febd4e30f5ae52c9202316d9` | Local pinned identity |
| `git ls-remote origin refs/heads/main` | Same SHA | Remote observed, not ongoing watch |
| `.venv/bin/capt --version` | `capt-solo 0.5.0` | Installed CLI version string |
| `.venv/bin/capt --help` | CLI parser help displayed | Read-only command discovery |
| `.venv/bin/capt status --help` | `--state-dir` exposed | Read-only subcommand help |
| `.venv/bin/python --version` | Python 3.12.13 | Check environment |
| `.venv/bin/python -m pytest -q tests/test_api_reference.py tests/test_capt_repo_audit_gate.py` | **10 passed in 0.75s**, exit 0 | Two test modules, not the entire suite |
| `.venv/bin/python -m pytest -q tests/test_v04_cli.py tests/test_capt_cli_src_path.py tests/test_memory.py` | **31 passed in 3.63s**, exit 0 | Three CLI/memory test modules, not full suite |
| Disposable `START_HERE.md` shell example extracted and run using `zsh` with the checkout venv on `PATH` | Store and search each exited 0; same memory ID/text returned; temporary state cleaned by the example's trap | Actual exact documented example, isolated Solo memory only |
| Markdown link/anchor check: 10 principal pages | **246** local links, **0** invalid paths/anchors | Scope is selected primary docs; not external URLs |
| Markdown relative-file scan: all `docs/**/*.md` plus root guides | **222** Markdown files, **324** relative-file link targets, **0** missing paths | File existence only; does not validate all anchors in historical docs |
| `git diff --check` | Exit 0 | Tracked modifications only; other new Markdown reviewed separately |
| Census traversal and SHA-256 hashing | 1,028 tracked files; no read/hash errors | Inventory only, not receipt coverage |
| Separate `git archive HEAD` byte/digest comparison against the pinned SHA-256 manifest | **1,028/1,028 matched; 0 missing, 0 extra, 0 digest mismatches; exit 0** | Independent data path within the **same agent session**, not an independent RRDS-1 verifier |

**NOT RUN:** full Python test suite, native Swift builds/tests, fresh clean-room package install, billed/live providers, externally consequential tool actions, security release gate, independent RRDS verifier, actual release/signing/notarization. No completion claim for these.

## Coverage architecture

| Reader outcome | Canonical path/action | Initial result |
|---|---|---|
| Purpose and maturity | Root `README.md`; `CURRENT_STATE.md` | UPDATED with prominent distinctions |
| Safe first visit | `START_HERE.md`, `INSTALLATION.md` | UPDATED entry point; retained install guidance |
| Normal operations | `USER_GUIDE.md`, `CLI.md`, `TUI.md` | LINK / RETAIN |
| Beginner explanation | `EXPLAINED_SIMPLY.md` | CREATED |
| Technical authority overview | `TECHNICAL_MANUAL.md`, `ARCHITECTURE.md` | CREATED overview; LINK source |
| Onboarding by audience | `ONBOARDING.md` | CREATED |
| Glossary | `GLOSSARY.md` | CREATED |
| Quick reference | `CHEATSHEETS/` | RETAIN / LINK |
| Maintainer drift prevention | `DOCS_MAINTENANCE.md` | CREATED guidance; CI changes not authorized |
| Public API | `API.md`, generator and test | RETAIN; generated reference not edited |
| Historical release/security evidence | `RELEASE_EVIDENCE.md`, release reports | RETAIN HISTORICAL |

## Triple-pass review ledger

This is a **single-agent editorial review**, not the independent reviewer/verifier pair required by RRDS-1. Work proceeded from D0 drafts through distinct structural, adversarial and reader/execution passes. The observed checks apply only to the named scopes. `PASS (docs)` means the page passed the scoped editorial and link checks; it does **not** imply a comprehensive code/release review.

| Public file | Pass 1 — coverage/structure, corrective action | Pass 2 — adversarial source/safety, corrective action | Pass 3 — reader/execution, evidence | Scoped status |
|---|---|---|---|---|
| `README.md` | Moved audience navigation into first fold; retained historical milestone material | Added actual pinned HEAD and explicit maturity separation | In 10-page anchor/path check: no invalid links | PASS (docs) |
| `START_HERE.md` | Replaced older snapshot framing and added onboarding pathway | Explicitly bounded Solo vs RuntimeService memory; preserved release caveat | Added disposable example and executed **the exact fenced shell example**, both actions exit 0 | PASS (docs) |
| `docs/README.md` | Preserved current canonical guides and existing cheatsheets; exposed missing audiences | Flagged 128-commit status drift without alleging new feature certification | Primary index links checked; no broken target | PASS (docs) |
| `docs/CURRENT_STATE.md` | Preserved the substantive dated source/evidence record, no contradictory rewrite | Added clearly visible October 8 freeze and current remote SHA | Status-to-mission and onboarding links resolved | PASS (snapshot labeling) |
| `docs/EXPLAINED_SIMPLY.md` | Gave beginners a distinct, short conceptual entrance | Differentiated returned tool output from admission/verification/completion | All checked links/anchors resolved; safe read-only commands previously verified | PASS (docs) |
| `docs/GLOSSARY.md` | One navigable term table, no duplicate technical API | Solo memory/runtime separation; idempotency caveat; no live proof by consensus | Checked all referenced source/canonical files | PASS (docs) |
| `docs/ONBOARDING.md` | Organized evaluator, operator, integrator, contributor, maintainer and security paths | Distinguished free local checks from provider credential/cost gates | Checked persona route links/anchors, including root Start Here section | PASS (docs) |
| `docs/TECHNICAL_MANUAL.md` | Created source-linked architecture route rather than rewriting `ARCHITECTURE.md` | Clearly labeled conceptual diagram, exact-tested vs installed/live/release states | Source file paths exist; command-help and 10 relevant tests confirmed | PASS (scoped reference) |
| `docs/DOCS_MAINTENANCE.md` | Added canonical-ownership/contract-impact checklist | Explicit owner approval and independent-verifier limitations | 222-file tree path scan found no missing targets | PASS (guidance) |

**Residual limitation across all pages:** only selected source contracts and test modules were reviewed. Source semantics beyond the cited entry points, full-platform reproducibility, provider/media acceptance and 128-commit capability reconciliation remain **PARTIAL**, not falsely certified. This ledger is not an RRDS-1 independent-verifier receipt.

## October 8 → October 18 change frontier (triage, not certification)

The `80d3b82..0d8e46d` Git range contains 128 commits touching 156 paths: 34 under `capt_runtime/`, 15 under `capt_ui/`, 11 under `contracts/`, 53 under `tests/`, 25 under `docs/`, plus other trees. These are **Git change counts**, not a count of finished features or passing integration flows.

Follow-up source review should prioritize the following **commit-identified topics**. Commit subjects identify where to investigate; they are *not* proof of release readiness.

| Area to inspect | Illustrative commits | Exact boundary to establish |
|---|---|---|
| Governed bioCAPT / QIPC opt-in observer | `1a85e859`, `375ac011`, `071a5092` | Disabled-by-default behavior, safe read-only authority, grant/no-grant, actual host registration |
| RRDS-1 audit gate | `c0196a16`, `9d5d7f4a` | Full census, examined-file receipts, falsification fixtures and independent verification |
| Mission approval and recovery | `6f708869`, `c1a05bb6`, `585c6106` | Transactional authority, revocation, durable replay and unknown external effects |
| Provider, tool and credential boundaries | `247acdac`, `14bb4b1b`, `38499f6c` | No credential forwarding, bounded process cleanup and remote provider policy |
| Native app packaging and rollback | `b6a9a8c2`, `727729d043`, `934c51ed` | Source presence vs reproducible build, signed install and actual release artifact |
| Media/provider extensions | `01178518` | Configured routes vs approved/live model calls, artifacts and billable semantics |
| Optional durable claim-once handoff | `3239a017` | Owner identity, replay, resource scoping, exact code/test contract |
| Runtime improvement primitives | `047a1601`, `0d822fd3`, `60562d4a`, `9a7c6e6b`, `af22e343`, `186cd316` | GateResult, CBIT, gate metrics, information flow, calibration and loop-detection tests and integration |

**Publication rule:** No table entry upgrades the October 8 capability matrix to current-HEAD release proof. Deep audit and feature-specific verification remain queued.

## OMEGA 13-enhancement gate scorecard

States follow the mission kit: `IMPLEMENTED` means a real local artifact and relevant check; `IN PLACE` means verified existing mechanism; `PARTIAL` has real work plus unresolved scope; `PROPOSED` is not installed.

| Gate | State | Evidence and unresolved boundary |
|---|---|---|
| 1. Drift detection | PARTIAL | `DOCS_MAINTENANCE.md` maps code surfaces to docs; no automated change-impact detector |
| 2. Docs-as-code CI | PROPOSED | No new CI workflow installed; existing workflow/doc gates still require targeted review |
| 3. Two-layer information architecture | IMPLEMENTED | README/index lead to beginner, onboarding and technical references; link checks pass |
| 4. Claim/source traceability | PARTIAL | Pinned SHA/census/source links and selected exact tests; not full RRDS file/line receipts |
| 5. Public feature coverage | PARTIAL | Front-door, CLI/API, user/technical, cheatsheets and status mapped; 128-commit delta open |
| 6. Role-based reader journeys | PARTIAL | Paths for novice, operator, expert and security reader; only isolated Solo memory executed |
| 7. Version-aware documentation | PARTIAL | Dated snapshots explicitly marked; current exact-HEAD matrix/migrations still require verification |
| 8. Three-pass improvement cycle | PARTIAL | Corrective editorial passes recorded below; no autonomous long-running drift monitor |
| 9. Executable examples | IMPLEMENTED | Exact isolated `START_HERE.md` shell block executed and returned a stored/searchable record |
| 10. Architecture decision intelligence | PARTIAL | Architecture references linked; ADR corpus not separately audited and no new ADR accepted |
| 11. Publication safety | PARTIAL | Provenance/security policy preserved, no secrets published, no provider charges; exhaustive safety scan not run |
| 12. Discovery and accessibility | IMPLEMENTED | Persona-first navigation; 10-page link+anchor check and 222-file path scan pass |
| 13. Clean-room reproducibility | PARTIAL | Isolated memory exercise passes using pre-existing venv; *fresh clone/install* not run |

The `IN PLACE` state is intentionally not used as a broad endorsement of existing CI or product functionality without an exact-head check.

## Governed MiMo / CAPT Node continuation (2026-10-18, US Central)

A fresh signed CAPT Node capability was observed after the expired-capability refusal; a governed `git rev-parse HEAD` probe returned the pinned `0d8e46d` checkout, exit 0. A scoped OpenRouter MiMo 2.6 Flash review was requested and approved by RuntimeService, then the connector timed out. **No blind redispatch occurred.** Canonical RuntimeService subsequently showed its one-use approval consumed, the DriverRun `completed` at `result_persisted`, and the task **awaiting_verification**. The stored Markdown artifact SHA-256 `339f8bc80a7595dc8eee661e5854c6a0629414648971e15a5c0cd8bf38f5feb1` matched the evidence receipt. Its findings were treated as untrusted and adversarially checked: see [review correction ledger](OMEGA_MIMO26_PEER_REVIEW_20261018.md). This was a CAPT-governed model review **from a Bot integration perspective**, not an autonomous CAPT-Bot worker run.

Targeted Bot, bioCAPT/QIPC, and claim-once tests at the pinned checkout: **54 passed, 1 skipped in 0.41s**, exit 0, across six test modules (see [current-HEAD delta notes](../CURRENT_HEAD_DELTA.md)). This is additional selected unit/fixture evidence, not a full RRDS source review, Swift acceptance, installed-runtime release certification, or proof of live CAPT-Bot R5 integration. A remote provider was invoked for the review; whether it incurred a charge was **not checked**. The initial-phase no-provider-dispatch statement above therefore applies only to that initial phase.

## Blocked or outstanding gates

1. Independent, fresh-worktree RRDS-1 re-enumeration and in-scope examined-file/line receipts.
2. Exact-HEAD validation of the 128-commit delta and capability matrix; no blanket promotion from historical statuses.
3. Broader test matrix, Swift build, provider/runtime live acceptance, reproducible install, and release-security checks.
4. Owner approval before any commit, PR, CI workflow addition, merge or release.

## Three-pass OMEGA continuation ledger (2026-10-18, US Central)

This continuation applies **three real and separate editorial checks** to the selected current-HEAD documents; it does **not** manufacture the independent RRDS-1 source verifier.

| Pass | Failure tested and concrete correction | Actual check and result | Remaining qualification |
|---|---|---|---|
| **1. Architecture/coverage** | MiMo found Bot onboarding and dated-matrix discovery weak; added current-HEAD delta, corrected historical matrix banners, linked tracked Bot and bioCAPT paths and current navigation | Whole docs tree + root guides: **224 Markdown files, 352 relative-file links, zero missing targets** | Other 128-commit areas still not catalogued with full line receipts |
| **2. Adversarial source/truth** | Rejected false “zero Bot README references” and unproven Git chronology contradiction; corrected native BotBrowser file path; kept separate CAPT-Bot R5 autonomy **unproven** | Source presence verified at `0d8e46d`; focused six-test batch **54 pass, 1 skip**; artifact digest matches original CAPT evidence | A model review is not independent verification; no full runtime/Swift suite or billable accounting |
| **3. Reader/execution** | Corrected an overly simplistic Markdown H1 check that counted shell `#` comments inside fenced README examples; did **not** change correct Markdown to accommodate a faulty checker | All eight revised/key new docs have one true H1 outside fences, all fences balanced; executed the **exact current-HEAD delta fenced zsh command**: **54 pass, 1 skip**; exit 0; `git diff --check` exit 0 | Fresh clone and public distribution not tested |

**Failure preserved:** The first atomic guarded documentation patch failed on an unmatched expected string, made **no writes**, and was replaced by a validated anchored edit. This is a successful fail-closed edit, not a passing review claim. An earlier naive H1 checker reported three root README H1s by misreading fenced shell comments; the corrected fence-aware checker found exactly one actual H1.

**Publication:** this continuation created only Markdown and local evidence; **no commit, push, PR, merge, release, or independent audit certification**.

## Decision record

Conservative choices: preserve existing canonical docs and their history; add discoverability only where missing; label the outdated snapshot as dated; no product code mutation, no external provider expense, no automated git publication, no modification to the existing provenance canary.

[Back to documentation index](../README.md) · [Maintainer instructions](../DOCS_MAINTENANCE.md)

## Current HEAD continuation — 2026-10-18 (pinned `c956c45e`)

The canonical Core checkout advanced six commits after the earlier pinned `0d8e46d` documentation pass, to `c956c45e33119cd31ce7e61c55334e803f20bf3f` (same local and remote `main`). Provider preflight, authenticated runtime health and provider response normalization were incorporated into the docs without relabeling the older evidence.

Two clean detached worktrees re-enumerated **1,032 matching Git-tracked files**. RRDS counted 681 in-scope source files, 47 source directories and 411 risk candidates. A CAPT Node operation printed SHA-256 and lines for 15 selected source files. RRDS verify returned **PARTIAL_OR_UNVERIFIED** with 15/681 file receipts, 41 uninspected directories and 398 uninspected risk candidates. The separate-worktree source match was checked by the same agent, **not** by an independent verifier.

At the new HEAD, **112 tests passed, 1 skipped** in selected Python modules; three additional RRDS falsification tests passed in the other worktree. No full Swift or Python release suite, fresh installation or live provider execution was performed during this continuation. Detailed [RRDS report](OMEGA_RRDS_C956C45E_PARTIAL.md) and [source/test delta](../CURRENT_HEAD_DELTA.md) contain scoped receipts and remaining work. Public claims stay **PARTIAL**.

### Runtime suite after environment diagnosis

The initial broad `tests/capt_runtime` run failed 14 cases with long macOS Unix-socket paths (1,656 passed; 13 skipped; 12 deselected). Retesting all 14 failed cases using short `--basetemp` succeeded (14/14). A full second run at `c956c45e` with short base and isolated CAPT runtime/Solo directories returned **1,670 passed, 13 skipped, 12 deselected, 0 failed (85.64 s)**. RRDS still **PARTIAL_OR_UNVERIFIED**, because tests and deep-source review are distinct. Full details: [current pinned RRDS report](OMEGA_RRDS_C956C45E_PARTIAL.md).
