# Hermes Integration — Forensic Correction

Branch: `feat/capt-runtime-hermes-execution-driver`
Base: `5fb323d6edd8511b687eaec9f6656fc4b4d0b320` (integrated main, freeze tag `capt-runtime-m0`)

## 1. Scope

Audit of the prior agent's ("Ling") Hermes-integration changes, recovery of
repository discipline, and replacement with a defensible integration bound to the
frozen ExecutionDriver architecture.

## 2. Repository verification

| Check | Value |
|---|---|
| Path | `/Users/knowurknot/CAPT_core` |
| Remote | `https://github.com/knowurknottty/CAPT_core.git` |
| Freeze tag | `capt-runtime-m0` present |
| Base commit | `5fb323d6edd8511b687eaec9f6656fc4b4d0b320` |
| Worktrees | single |

Homebrew bioCAPT, `Biocapt-ecosystem-fullcaptlang`, `captrys`, legacy prototypes,
and site-packages installs were **not** used. `capt_runtime` resolves from the
repository working tree only — no installed `capt_runtime` distribution exists on
this machine.

## 3. What Ling actually changed

Preserved before any modification:

* `/tmp/ling-hermes-integration-current.patch` (2,811 bytes)
* `/tmp/ling-evidence-<TS>/` with SHA-256 sums of every changed and untracked file

| File | Pre-existing or new | Change made | Actual runtime effect | Architectural fit | Disposition |
|---|---|---|---|---|---|
| `capt_solo/hermes/adapter.py` | pre-existing (in `origin/main`) | none by Ling | CAPT-local Python class; constructs and returns dicts | not an external Hermes integration | unchanged, left as-is |
| `capt_solo/plugin/__init__.py` | pre-existing | local uncommitted edits adding Hermes-facing plugin surface | registers plugin tools in the generic Hermes plugin registry | wrong registry — bypasses `DriverRegistry` | **reverted** (not carried onto this branch) |
| `tests/test_plugin.py` | pre-existing | exact tool count `47 → 50` | asserts a number, not behaviour | brittle; proves nothing semantically | **reverted** |
| `~/.hermes/plugins/capt-solo/` | pre-existing user-scope plugin | resolves `CAPT_SOLO_REPO`; loads `capt_solo` | plugin **fails to load** against `/Users/knowurknot/CAPT_core`; loads only against `/Users/knowurknot/capt-solo` | out-of-repo, unverified | out of scope of this branch; documented, not modified |

### Classification of Ling's implementation

Category **6 — incomplete/misleading implementation**, with elements of
category **4 (thin plugin façade)**.

Evidence:

* No Hermes process was ever spawned by the code. No `subprocess`, no socket, no
  IPC, no model call crossed a process boundary.
* The "integration" consisted of a CAPT-local class plus plugin-registry entries.
  A registry entry is not a model-turn bridge.
* The only test change was an integer count. No semantic coverage was added.
* The `capt-solo` Hermes plugin does not load against the authoritative
  repository at all, so the claimed integration could not have run.

No part of Ling's change was retained.

## 4. Bridge duplication analysis

`origin/feature/capt-bootstrap-bridge` contains a bootstrap-bridge design
(`protocol.py`, `ownership_guard.py`, `hermes_middleware.py`, `runner_process.py`).
It is **not merged into `main`** and is not part of the frozen M0 baseline.

The bridge presumes a Hermes-side middleware hook that suppresses direct model
execution and forwards turns to a CAPT Agent Runner. On the installed runtime
(Hermes Agent v0.19.1, upstream `dae5df22`) that middleware path exists in Hermes'
own source but is not wired to CAPT, and enabling it would place Hermes *inside*
the CAPT trust boundary — the opposite of the frozen ADR-0120 posture where the
driver is untrusted and external.

Conclusion: **no second bridge was created.** Mode A (external ExecutionDriver)
was selected instead, reusing the frozen boundary with zero new wire contracts.
See `HERMES_INTEGRATION_MODE_ADR.md`.

## 5. Branch discipline

Ling's edits were uncommitted working-tree changes on `main`. They were:

1. captured to a patch and a hashed evidence directory,
2. confirmed absent from `origin/main` (`git diff --exit-code` between
   `55e149b` and `5fb323d` for the affected files returned 0),
3. reverted from the working tree,
4. `main` fast-forwarded to `origin/main` (`5fb323d`),
5. new branch `feat/capt-runtime-hermes-execution-driver` cut from that commit.

No force-push. No rewrite of frozen M0 history. The `capt-runtime-m0` tag is
untouched.

## 6. Disposition

**Option A — Revert**, applied to all of Ling's changes, plus a fresh Mode A
implementation built against the frozen driver boundary.

Rationale: the code duplicated no useful logic, exposed unsupported plugin tools,
changed a test count without semantic coverage, and provided no component that
could be refactored into an ExecutionDriver.

## 7. Residual uncertainty

* The `~/.hermes/plugins/capt-solo/` user-scope plugin remains broken against the
  authoritative repository. It is outside this repository and outside this
  mission's scope; it is documented, not fixed.
* The unmerged bootstrap-bridge branch is neither adopted nor deleted. Adopting it
  would be a Mode B decision requiring its own ADR and its own conformance proof.
