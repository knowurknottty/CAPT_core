# CAPT Foundry M0 — Verification Report

**Repository:** `knowurknottty/CAPT_core`
**Branch:** `feat/capt-foundry-m0`
**Base SHA:** `5fb323d6edd8511b687eaec9f6656fc4b4d0b320` (origin/main, unchanged)
**Commit:** `620094c`
**Worktree:** `/Users/knowurknot/capt-foundry-m0` (clean)
**Date:** 2026-08-03

---

## 1. Deliverables

| # | Capability | Module | Status |
|---|---|---|---|
| 1 | Research Entity Registry | `capt_foundry/entities.py` | Implemented |
| 2 | Research Alias Registry | `capt_foundry/entities.py` | Implemented |
| 3 | Corpus / Document Manifest | `capt_foundry/corpus.py` | Implemented |
| 4 | Curated Artifact Publisher | `capt_foundry/publisher.py` | Implemented |
| 5 | Obsidian Projection | `capt_foundry/projection.py` | Implemented |
| 6 | SEAL Research Asset Export | `capt_foundry/seal_export.py` | Implemented |

Supporting: `canonical.py` (deterministic digests), `storage.py` (separate
versioned SQLite store), `errors.py`.

**Deliberately NOT implemented** (verified already satisfied at base; building
them would be a defect): persisted evidence graph, proof ledger, temporal
ordering. Asserted by `test_foundry_declares_no_runtime_ownership_concepts`.

Governance: **ADR-0130** (Accepted) covers all seven mandated points.
**ADR-0131** (Proposed, recommendation only) records the lineage divergence.
Both registered in the existing `ADR-01xx` series. No second governance
structure created.

---

## 2. Test results — real execution

| Gate | Command | Result |
|---|---|---|
| Targeted | `pytest tests/capt_foundry/ -q` | **153 passed** |
| Full suite | `pytest tests/ -q` | **622 passed, 44 skipped** |
| Base comparison | same at `5fb323d` | 469 passed, 44 skipped |
| Delta | | **+153 new, 0 regressions, skips unchanged** |
| Lint | `ruff check capt_foundry tests/capt_foundry` | **All checks passed** |
| Syntax | `python3 -m compileall` | exit 0 |
| Contract drift | `contracts/tools/check_drift.py` | **OK (11 files match)** |
| Runtime verifier | `verify_runtime.py` | 52 pass / 1 warn / 0 fail |
| Secret scan | `gitleaks protect --staged` | **no leaks found** |

The single `verify_runtime` warning (`component.ate_pinned_commit`) is
**pre-existing**: an isolated detached worktree at `5fb323d` with no Foundry code
produces the identical `52 pass / 1 warn / 0 fail`.

Test distribution (each verified by a per-file run): canonical 10, entities 24,
corpus 25, publisher 18, projection 27, seal_export 18, lifecycle 4,
adversarial 27 = 153.

---

## 3. Lifecycle proof

`tests/capt_foundry/test_lifecycle.py::test_full_lifecycle` executes the complete
M0 chain as one continuous evidence chain:

approved source → entity registration → alias registration → document metadata
ingestion → corpus manifest → curated asset → provenance receipt → deterministic
persistence → query/retrieval → SEAL export → Obsidian projection → **replay in a
fresh OS process** → integrity verification.

Replay uses `_replay_probe.py` in a **separate interpreter** against the same
database file, asserting `manifest_hash`, `corpus_digest`, `export_digest`,
`payload_digest_matches`, and alias resolution all survive a process boundary.
The Markdown rendered from the replayed manifest is byte-identical to the
original note.

---

## 4. Triple-recursion pass

**Pass 1 — targeted.** Two genuine defects found and fixed:

1. **YAML front-matter injection** in `projection._fm_escape`. Quotes were
   escaped, newlines were not, so a hostile `published_by` could inject an
   arbitrary front-matter key. Fixed to escape the full C0 range plus DEL.
   Confirmed by an actual `yaml.safe_load`: the hostile document now parses to
   exactly one key.
2. **Incorrect test expectation** (`c.notes.d0` vs the real `c.notes.d0000`).
   The code was right, my assertion was wrong; the assertion was corrected —
   the implementation was not weakened to fit it.

**Pass 2 — adversarial.** 27 attacks, all repelled: SQL injection via
identifiers and via free-text names; forging a verification verdict; silent
false joins; direct DB tampering; schema-version confusion; orphan alias via raw
SQL (blocked by `PRAGMA foreign_keys=ON`); four vault path-escape variants;
symlink overwrite; SEAL concepts smuggled through free text; import-time side
effects; `PYTHONHASHSEED` non-determinism; partial state after a failed publish.

**Pass 3 — guard validity (do the guards have teeth?).** A test that cannot fail
proves nothing, so each guard family was mutation-tested:

| Injected violation | Guard | Result |
|---|---|---|
| `def submit(...)` in `canonical.py` | no-submission | **FAILED as designed** |
| `import socket` in `errors.py` | no-network | **FAILED as designed** |
| `"case_id"` in the export envelope | SEAL boundary | **FAILED as designed** |
| real file write under the import guard | no-import-writes | **detected** |
| real `sqlite3.connect` under the guard | no-import-construction | **detected** |

Every file was restored; `git status` confirmed byte-identical restoration, and
the full suite was re-run green afterwards.

---

## 5. Boundary compliance (ADR-0130), mechanically asserted

| Rule | Enforcing test |
|---|---|
| No second composition root | `test_no_runtime_construction_during_publish` — monkeypatches `KnowledgeBubbleRuntime.__init__` to raise; publish still succeeds via the `@staticmethod` |
| No import-time construction / global singleton | `test_foundry_has_no_import_time_side_effects` |
| No import-time writes | `test_foundry_writes_no_files_at_import` |
| Does not own evidence/ledger/authority | `test_foundry_declares_no_runtime_ownership_concepts` |
| Foundry never imports SEAL | `test_foundry_does_not_import_seal` |
| No network | `test_foundry_makes_no_network_imports` |
| No submission, no prompt generation | `test_no_submission_or_prompt_generation_capability` |
| No SEAL-owned concepts exported | `test_export_emits_no_seal_owned_concepts` + runtime `ValidationError` |
| Asserts no verification status | `test_foundry_cannot_mint_a_verification_verdict` |
| Digests agree with runtime | `test_matches_capt_runtime_contracts_byte_for_byte` |

Frozen M0-A/M0-B code was not modified. Only additive files plus one line in the
ADR index. All 469 base tests still pass.

---

## 6. Constraint compliance

| Captain constraint | Evidence |
|---|---|
| No repository-history repair | Base `5fb323d` unchanged; no merge, rebase, or cherry-pick |
| No branch reconciliation | Only `feat/capt-foundry-m0` created |
| No importing from unmerged branches | Nothing copied from `~/capt-solo`; zero files read from it this pass |
| No recreating missing subsystems | No `evidence/`, no ProofGraph, no ledger |
| No broad scans | `index_directory` requires explicit paths; `test_index_never_recurses_implicitly` |
| No uncontrolled ingestion | Metadata only; document bodies never stored |
| No automatic prompt generation | Guard test |
| No automatic submission | Guard test |
| No network | Guard test |
| `~/capt-solo` untouched | Still 33 dirty (pre-existing, unchanged) |

---

## 7. Residual risks (disclosed)

1. **Foundry state is not in the runtime ledger.** By design (ADR-0130): the
   Foundry writes no events. Governed Foundry actions must be issued as
   `RuntimeService` commands by the caller. No such caller exists yet — that is
   an M1 integration concern, not a silent gap.
2. **`StreamId` cannot express Foundry aggregates.** The contract pattern admits
   only `mission|task|capability|driverrun|claim`. Recorded in ADR-0130; changing
   it needs a contract ADR.
3. **Bubble-format fallback path.** If `capt_solo.foundry.bubble` were
   unimportable the publisher emits a self-describing envelope that declares
   `bubble_format_used = "capt_foundry.fallback_envelope"`. It cannot silently
   masquerade as the canonical format. Unreached in this environment.
4. **No cross-process write concurrency test.** Single-writer assumed, matching
   local-first usage. Multi-writer contention is untested.
5. **Alias normalization is deliberately conservative.** NFKC + casefold +
   whitespace only. `Müller` ≠ `Muller` by design — recall is traded for
   precision, and ambiguity surfaces as `AmbiguousAlias` rather than a guess.
6. **Projection is one-directional.** Vault edits are never read back and will be
   overwritten; the note says so in its own body.

---

## 8. Unrelated observation (not mine)

`~/seal-pdfs` shows one untracked file, `docs/HANDOFF.md` (mtime 02:01,
"FROZEN AT HEAD 457d4d4"). It was created by a different workflow: my commit
touches zero files in that repository, and I only read from it. Flagged, not
touched.

---

## 9. Status

**STATUS: FOUNDRY_M0_IMPLEMENTED_AND_VERIFIED**

- Files changed: 23 added, 1 modified (ADR index), 0 deleted
- Commit `620094c` on `feat/capt-foundry-m0`; **not pushed** (no push authorized)
- Worktree clean; full suite green after commit
- Mode: BOOTSTRAP_DEGRADED — no CAPT runtime governed this session. All
  discipline above is prompt-enforced and evidenced by real tool output; none of
  it is runtime-enforced. MemoryUseGate and ClaimGuard did not execute.
