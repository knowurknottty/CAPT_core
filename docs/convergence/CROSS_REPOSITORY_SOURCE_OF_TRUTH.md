# CROSS_REPOSITORY_SOURCE_OF_TRUTH — CAPT Core v0.5 Convergence

Generated: 2026-07-30 (HY3 convergence pass)
Method: live remote inspection + local execution. All results below were
reproduced TODAY unless explicitly marked historical.

## 1. Repository authority map

| Repo | Visibility | Default branch | HEAD (verified today) | Role |
|---|---|---|---|---|
| knowurknottty/CAPT_core | PUBLIC | main | `55e149bbb078b197429ee21d02e8e3265b551e6e` | Canonical public repo; implementation + release destination |
| knowurknottty/capt-core-v05-hardening-backup | private | codex/capt-v0.5-p0-release-hardening | `a04b6fc3003ed7a01ee05117d92b715c1ec272a1` | Forensic preservation; NOT canonical |
| knowurknottty/captstreasurechest | private | main | `75355f846f3ddde880670f0ba4b1488dc9b55886` | Operating manual + release specification; documentation/evidence ONLY |

Local working tree: `~/capt-solo` on `integration/capt-v05-release-corrected`
@ `716ecc933eb45b31a0ec461c72ce4ced3da3b2b7`, Python 3.12.13 venv, clean tree
(only untracked `.capt_state/`).

## 2. THE CENTRAL STRUCTURAL FACT (new since last reconciliation)

**Public `main` and the v0.5 integration branch are DISJOINT SUPERSETS that
diverged at `abeff5c1` (v0.4.0).**

Verified today:
- `origin/main` is NOT an ancestor of integration HEAD.
- 29 commits exist only on main; 66 commits exist only on integration.
- File-level: 271 files differ, +28,885 / −3,402 lines.

What each side exclusively holds:

| Only on public main (29 commits) | Only on integration (66 commits) |
|---|---|
| ATE component (`capt_solo/components/anti_token_extraction.py` + mcp.json) | Entire v0.5 architecture: `evidence/` (13 files), `verification/` (6), `knowledge/`, `contextpack/`, `continuity/`, `execution/`, `learning/`, `ontology/`, `research/`, `engines/`, `workspace.py` |
| `.gitleaks.toml` + `.github/workflows/release-security.yml` | Release identity Option A + `release_validation.py` + `capt release validate` |
| `tests/test_v04_anti_token_extraction.py` (575 lines) | 715-test suite, workspace CLI, ADRs, PUBLIC_API_MANIFEST_V0.5.json |
| `docs/WHITEPAPER.md` (561 lines) + `docs/DESIGN.md` + docs refresh + README rewrite | All archaeology/reconciliation docs (21 files in docs/release/) |

Consequence: the earlier "recover ATE from hardening/* branches" plan is
OBSOLETE. **ATE is now IN public main** (merged via PR #4 `3248444`). The
recovery direction has inverted: the question is how integration acquires
main's ATE+CI+whitepaper content, and how main acquires the v0.5 architecture.

**The v0.5 integration branch exists ONLY locally and on the private backup
remote. It is NOT on public origin.** A repo clone of public CAPT_core does not
contain v0.5.

## 3. Checkpoint reproducibility (rerun today, not inherited)

| Gate | Recorded | Reproduced today | Status |
|---|---|---|---|
| Source commit `3888f08e…` | exists | EXISTS, ancestor of HEAD | PASS |
| Metadata tip `be4b0da8…` | exists | EXISTS, ancestor of HEAD | PASS |
| Option A lineage | corrected | HEAD `716ecc9` descends 3888f08→…→be4b0da→…716ecc9 | PASS |
| 715 tests | 715 passed | **`715 passed in 27.91s`** (Python 3.12.13) | PASS |
| Artifact build | wheel+sdist | `capt_solo-0.5.0-py3-none-any.whl` sha256 `78e49f1b…3396`; sdist sha256 `4f7d5b85…80e8` | PASS |
| Clean install | passed | fresh venv: `pip install` OK, `import capt_solo` → 0.5.0, `capt --help` OK | PASS |
| Release validator | passed | `capt release validate --final` → **12/12 pass, exit 0** | PASS (see note) |

Notes and defects observed during reproduction:
1. `capt release validate` (non-final) exits 1 on `candidate.manifest_state`:
   the TRACKED manifest carries `candidate_sha=3888f08…` while the design
   (CANDIDATE_IDENTITY_DESIGN_REVIEW.md) says the tracked manifest stays
   `UNFROZEN` and only a generated final manifest carries the SHA. The tracked
   state deviates from its own design. → Package B item.
2. `capt workspace status`/agent startup regenerates `CHECKPOINT.md`
   (checkpoint_id/commit/timestamp), dirtying the tree and failing
   `candidate.clean_tree` under `--final` until reverted. Self-dirtying
   worktree is a release-mechanics defect. → Package B item.
3. Four stale worktrees under `/tmp` (capt-0.5.0-final*, capt-contextpack-rc*)
   — all ancestors of HEAD, no unique work; safe to prune. → Package A item.

## 4. Evidence-authority ruling (per Treasure Chest doc 00)

1. The corrected checkpoint (3888f08/be4b0da/715 tests) is REPRODUCIBLE and is
   the implementation baseline of record.
2. Prior green results are historical; today's rerun (this document) is the
   current evidence set for the UNCHANGED candidate. Any new commit creates a
   new candidate requiring rerun.
3. The backup repo contains ZERO unique commits (every backup branch tip is an
   ancestor of local HEAD; verified `git rev-list --count HEAD..<branch>` = 0
   for all). Its value is purely forensic.
4. The Treasure Chest is requirement authority (docs 00–17), not evidence.

## 5. Current release-status language

- Integration README: "CAPT is pre-release software… not published, tagged, or
  approved" — CORRECT.
- `RELEASE_STATE.md` / `CURRENT_STATE.md`: `candidate_sha: UNFROZEN` —
  contradicts the tracked manifest (defect #1 above).
- Public main README: "public runtime currently includes the v0.4
  proof-governed architecture plus v0.4.1 hardening work" — accurate for main.
- Required status until all gates pass: `NOT READY — BLOCKERS REMAIN` (doc 00).
  That status STANDS.
