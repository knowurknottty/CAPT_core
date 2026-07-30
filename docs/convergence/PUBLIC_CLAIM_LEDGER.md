# PUBLIC_CLAIM_LEDGER — every material public claim and its evidence

Generated: 2026-07-30. Covers public-facing statements in CAPT_core (both
public main and integration README, package metadata, docs). Per doc 15 G:
exact wording, source, implementation/test/runtime/packaging evidence, security
implication, limitation, disposition.

Legend: ✅ evidenced · ⚠️ partial · ❌ unsupported (must fix) · 🔄 deferred

## A. Integration README (v0.5.0, the candidate)

| # | Claim (verbatim) | Source | Evidence | Disposition |
|---|---|---|---|---|
| A1 | "Secure, auditable, model-agnostic cognitive infrastructure." | integration README L1 | model-agnostic: zero hermes imports proven; auditable: CTP+evidence+release validator proven; secure: local-first + command-injection tests, but no full scan at SHA yet | ⚠️ secure needs scan (Package C) |
| A2 | "CAPT is a local-first verification substrate" | README L5 | local-first: state dir, no network on import proven | ✅ |
| A3 | "runs underneath models and protocols rather than requiring one provider" | README | pulse.py disabled-by-default, lazy import; no provider import in core | ✅ |
| A4 | "CAPT is pre-release software. It has not been published… approved for public release." | README L11 | accurate; no tag/publish done | ✅ |
| A5 | Six-pillar capability list (memory, evidence, verification, context, transactions, governance) | README | all implemented + 715 tests | ✅ |
| A6 | "model-agnostic" (repeated) | README | architecture-level true; no operational adapter proof yet | ⚠️ keep as architecture claim, not feature claim |

## B. Public main README (v0.4.1 — what the world currently sees)

| # | Claim | Source | Evidence | Disposition |
|---|---|---|---|---|
| B1 | "integrates with Hermes while keeping the runtime self-hostable and inspectable" | main README L9 | true: plugin inbound-only, core hermes-free | ✅ |
| B2 | "public runtime currently includes the v0.4 proof-governed architecture plus v0.4.1 hardening work" | main README | accurate for main | ✅ (but stale vs v0.5 candidate) |
| B3 | "Open source. See [LICENSE](LICENSE) for the exact terms." | main README L175 | ❌ LICENSE FILE ABSENT on main (and on integration) while pyproject says MIT | ❌ FIX (Package F — add LICENSE) |
| B4 | "Memory Engine — local SQLite storage with namespaces…" | main README | true; engine tested | ✅ |
| B5 | ATE component described implicitly via "tool governance" | main README | ATE present on main only | ✅ on main |

## C. Package metadata

| # | Claim | Source | Evidence | Disposition |
|---|---|---|---|---|
| C1 | name = capt-solo, version 0.5.0 | integration pyproject | ✅ matches `__version__="0.5.0"` | ✅ |
| C2 | version 0.1.0 | main `__init__.py` | ❌ mismatch: pyproject says 0.4.1, __init__ says 0.1.0 | ❌ FIX (Package F — reconcile main OR replace main with integration) |
| C3 | license MIT | integration pyproject | ❌ no LICENSE file shipped (wheel built today has no LICENSE) | ❌ FIX (Package F) |
| C4 | dependencies = pyyaml only | both pyproject | ✅ verified; no hidden deps | ✅ |

## D. Whitepaper (main, v0.4-era)

| # | Claim | Source | Evidence | Disposition |
|---|---|---|---|---|
| D1 | "Hermes is the current integration target… not a permanent architectural dependency of CAPT Core." | WHITEPAPER L419 | ✅ matches code (inbound plugin only) | ✅ |
| D2 | "Hermes or local caller" (architecture diagram) | WHITEPAPER L89 | ✅ acceptable; revisit with adapter work | ✅ |
| D3 | v0.5 content (Spaces, adapter contract) | — | whitepaper is v0.4-era; does NOT yet describe v0.5 | 🔄 deferred to Package F whitepaper refresh (post-scope) |

## E. Cross-cutting terminology discipline (doc 15 G)

- Core vs Solo vs Space vs adapter vs Hermes: Core/Solo/Hermes consistent.
  Space/adapter cannot be referenced as present (not implemented) — ledger
  ensures no public doc asserts them. ✅

## F. Disposition summary

- ❌ Unsupported claims to FIX before any release: B3 (missing LICENSE file),
  C2 (main __version__ mismatch), C3 (MIT declared, no LICENSE shipped).
- ⚠️ Claims needing evidence completion: A1 (security scan at SHA), A6
  (model-agnostic as architecture, not feature).
- 🔄 Deferred: D3 whitepaper v0.5 refresh (post-scope decision).
- All fixes are Package F (Documentation Truth) + Package C (security scan).
  No claim currently asserts Spaces or runtime adapters as shipped — the
  ledger keeps the public surface honest under the v0.5.0 split.
