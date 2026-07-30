# TREASURE_CHEST_REQUIREMENT_MATRIX — CAPT Core v0.5

Generated: 2026-07-30
Source: knowurknottty/captstreasurechest (cloned read-only to /tmp/tc_clone)
Rule preserved: no intended capability promoted to implementation claim without evidence.
Status vocabulary per review spec.

## Requirement inventory (by Treasure Chest doc)

### doc 00 — Scope/Status Rules
| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 00.1 | Status language "NOT READY — BLOCKERS REMAIN" until gates pass | SATISFIED_IN_PUBLIC_REPO (as policy) | doc 00 rule; public repo not yet at READY |
| 00.2 | Exact-SHA rule: post-edit = new candidate | SATISFIED_IN_PUBLIC_REPO | release_validation.py enforces |
| 00.3 | Documentation truth rule (no stale SHA/test totals) | PARTIALLY_SATISFIED | archaeology docs had stale claims (corrected in ARCHAEOLOGY_REVIEW); public docs need audit |

### doc 01 — Public Release Vision (six pillars)
| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 01.1 | Six-pillar public architecture | SATISFIED_IN_PUBLIC_REPO | PUBLIC_ARCHITECTURE.md, ADR-0008 |
| 01.2 | Local-first, model-agnostic, no cloud required | SATISFIED_IN_PUBLIC_REPO | memory/antitoken, pulse optional, no network on import (verified) |
| 01.3 | State-bound verification, invalidation, receipts, recovery | SATISFIED_IN_PUBLIC_REPO | VSI, CTP, evidence engine |

### doc 02 — Confirmed Progress
| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 02.1 | 18 source packages ship in wheel | SATISFIED_IN_PUBLIC_REPO | wheel built 258KB, 18 pkgs |
| 02.2 | `capt` console command | SATISFIED_IN_PUBLIC_REPO | entry point present |
| 02.3 | Six-pillar ADRs + manifests | SATISFIED_IN_PUBLIC_REPO | adr/, PUBLIC_API_MANIFEST_V0.5.json |
| 02.4 | Verification-first onboarding tutorial | SATISFIED_IN_PUBLIC_REPO | examples/verification_first/run.py |
| 02.5 | Semantic release validation | SATISFIED_IN_PUBLIC_REPO | release_validation.py, `capt release validate` |
| 02.6 | Repository-wide security closure | MISSING_RELEASE_REQUIRED | Codex scan failed; no final scan (doc 02 "Not confirmed") |
| 02.7 | Exact-SHA final wheel/sdist build + clean install | PARTIALLY_SATISFIED | built + installed once; not re-run at final SHA per doc 07 |

### doc 03 — Pending Master Plan
| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 03.1 | Phase 2 manual security campaign (Bandit/Semgrep/gitleaks/adversarial) | MISSING_RELEASE_REQUIRED | not executed; Batch 1 proposes gitleaks+CI but not full campaign |
| 03.2 | Phase 3 finding validation + regression tests | PARTIALLY_SATISFIED | 6 Codex candidates closed with tests in 3888f08; full campaign pending |
| 03.3 | Phase 4 trust/privacy docs (privacy arch, data-flow, threat model) | MISSING_RELEASE_REQUIRED | no Trust Center/Threat Model in public repo |
| 03.4 | Phase 5 exact-SHA closure (wheel/sdist/6 profiles/tutorial) | PARTIALLY_SATISFIED | built; full 6-profile clean-env re-run not done at final SHA |
| 03.5 | Phase 6 Codex corroboration | POST_V0_5 | owner decision on re-run |

### doc 04 — Manual Security Campaign
| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 04.1 | Sensitive-asset + entry-point inventory | DOCUMENTATION_ONLY | not present as artifact |
| 04.2 | 14 manual scopes (path traversal, cmd injection, deserialization, etc.) | MISSING_RELEASE_REQUIRED | only 6 Codex candidates adjudicated |

### doc 07 — Exact-SHA Release Closure
| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 07.1 | Required final files: RELEASE_VERIFICATION_V0.5.md | MISSING_RELEASE_REQUIRED | ABSENT |
| 07.2 | ARTIFACT_MANIFEST_V0.5.json | MISSING_RELEASE_REQUIRED | ABSENT |
| 07.3 | PACKAGE_CONTENTS_V0.5.json | MISSING_RELEASE_REQUIRED | ABSENT |
| 07.4 | CONFORMANCE_RESULTS_V0.5.json | MISSING_RELEASE_REQUIRED | ABSENT |
| 07.5 | RELEASE_SECURITY_REPORT_V0.5.md + findings/coverage/manifest JSON | MISSING_RELEASE_REQUIRED | ABSENT (security closure never completed) |
| 07.6 | Clean wheel + sdist install in isolated envs | PARTIALLY_SATISFIED | done once; not at final frozen SHA |

### doc 08 — Trust/Privacy/Compliance
| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 08.1 | Phase 1 design transparency (local-first arch, data-flow, threat model) | PARTIALLY_SATISFIED | architecture docs exist; threat model ABSENT |
| 08.2 | Phase 2 release evidence (SHA, hashes, findings) | MISSING_RELEASE_REQUIRED | depends on 07 closure |
| 08.3 | Trust Center (10 sections) | MISSING_RELEASE_REQUIRED | ABSENT |
| 08.4 | Compliance mappings (NIST/ISO/SOC2/OWASP) | MISSING_RELEASE_REQUIRED | ABSENT |
| 08.5 | No certification claims without audit | SATISFIED_IN_PUBLIC_REPO (as rule) | doc 08 language enforced |

### doc 10 — KHSB/CTP/CRP Roadmap
| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 10.1 | Ship CTP correctly + receipt-chain tests | SATISFIED_IN_PUBLIC_REPO | ctp/journal.py, test_ctp.py |
| 10.2 | KHSB secure cross-model exchange tests | PARTIALLY_SATISFIED | khsb/bus.py present; encryption-profile tests ABSENT |
| 10.3 | CRP runtime implementation | POST_V0_5 (explicitly deferred) | doc 10/03 deferred |

### doc 15 — Finish-Line Playbook
| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 15.A | Re-establish baseline + rerun full suite at final SHA | PARTIALLY_SATISFIED | ran earlier; must rerun at frozen SHA |
| 15.B | Branch census + selective integration | SATISFIED_IN_PUBLIC_REPO | BRANCH_CENSUS.md done |
| 15.C | Resolve open release/security issues | PARTIALLY_SATISFIED | 6 candidates closed; full campaign pending |
| 15.D | **First-class Space architecture** | MISSING_RELEASE_REQUIRED | no Space class in repo (only workspace_isolation.py) |
| 15.E | **Provider-neutral runtime adapter contract** (non-Hermes tested) | MISSING_RELEASE_REQUIRED | no AdapterRegistry; research/adapter.py exists but not contract-complete |
| 15.F | **Trust Center, Threat Model, NIST/ISO/SOC2, SBOM** | MISSING_RELEASE_REQUIRED | ABSENT |
| 15.G | Documentation truth audit + claim ledger | MISSING_RELEASE_REQUIRED | not done (this review is a partial step) |
| 15.H | Whitepaper finalization | POST_V0_5 | separate artifact |
| 15.I | Repository completeness audit + FINAL_RELEASE_BLOCKERS.md | MISSING_RELEASE_REQUIRED | ABSENT |

### doc 17 — GitHub Surface Triage
| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 17.1 | CAPT_core public; others private by default | OWNER_DECISION | visibility changes need GitHub settings (connector limitation noted) |
| 17.2 | Public repos pass 2-minute clarity test | DOCUMENTATION_REQUIRED | public README/claims need audit |

## Summary counts
- SATISFIED_IN_PUBLIC_REPO: ~18
- PARTIALLY_SATISFIED: ~10
- MISSING_RELEASE_REQUIRED: ~16 (security closure, Spaces, runtime adapters, Trust Center, exact-SHA evidence files, FINAL_RELEASE_BLOCKERS)
- DOCUMENTATION_ONLY / DOCUMENTATION_REQUIRED: ~4
- POST_V0_5: ~4
- OWNER_DECISION: ~2

## Critical conclusion
The Treasure Chest's v0.5 contract is NOT met by the current public repo. The
six-pillar public architecture IS met. The gap is the Treasure Chest's broader
contract (Spaces, runtime adapters, Trust Center, exact-SHA evidence). This is the
central reconciliation finding and the subject of OWNER_DECISION #1.
