# Release Security Dependency Decision (anti-token-extraction)

Date: 2026-08-03
Context: PR #23 "Release Security" workflow jobs `python (3.10)` / `python (3.12)`
fail. The M0-A/M0-B conformance suites ("M0-A Contract & Runtime Proof") PASS.

## 1. Exact failing workflow / step / error

- Workflow: `.github/workflows/release-security.yml` (name: "Release Security").
- Failing jobs: `python (3.10)`, `python (3.12)` (matrix).
- Failing step: **"Install pinned Anti-Token-Extraction"** (lines 29–32):
  `python -m pip install git+https://github.com/knowurknottty/anti-token-extraction.git@b68adac...`
- Exact error (from job log `91585169649`):
  `ERROR: Failed to build 'git+https://github.com/knowurknottty/anti-token-extraction.git@...'`
  `when git clone ... https://github.com/knowurknottty/anti-token-extraction.git ...`
  `exit code: 128`. Then `##[error]Process completed with exit code 1.`

## 2. Is the dependency private?

Yes. `knowurknottty/anti-token-extraction` is a **private** GitHub repository.
The workflow declares `permissions: contents: read` and checkout uses
`persist-credentials: false`, so the `GITHUB_TOKEN` cannot clone a private repo.
There is **no scoped credential** (no `token:` with `contents:read` on that repo,
no `secrets` reference) capable of accessing it. Hence the clone fails.

## 3. Same failure on the M0-A base branch?

Yes. `gh run list --branch feat/capt-runtime-m0a-contract-state-proof` shows the
"Release Security" workflow in `failure` state on the base branch too. The
failure is **pre-existing and environmental**, not introduced by M0-B.

## 4. Required or optional?

**Optional at the test level.** All 44 skipped tests are in
`tests/test_v04_anti_token_extraction.py` with the skip reason
"anti-token-extraction upstream package not installed in this env." The local
and CI conformance suites (which do not require the package) PASS. The package
is a security *extension*, not a runtime prerequisite.

## 5. Do the 44 local skips correspond exactly to its absence?

Yes. 44 skipped = 44 tests in `test_v04_anti_token_extraction.py`, all gated on
the package being importable. Exact correspondence confirmed.

## 6. Does the workflow distinguish optional vs required correctly?

**No.** The workflow makes the optional package install a **hard prerequisite**
that breaks the entire `python` job before any test runs. A required release test
job should not fail solely because an *optional security extension* cannot be
installed in a given environment. This is the core design flaw.

## 7. Classification

**Mixed cause:**
- CI configuration defect — the workflow does not tolerate the optional
  dependency being unavailable (no `continue-on-error`, no conditional install,
  no separate optional job).
- Credential/access defect — no token is provisioned to clone the private repo.
- The dependency itself is **intentional optional-dependency behavior** at the
  test level (graceful skip when absent).

It is **NOT** a product defect in M0-B (M0-B does not depend on the package).

## 8. Decision memo — options compared

| # | Option | Security | Supply-chain | Reproducibility | Secret exposure | Maint. | Public-release | Local-first | Release-claim effect |
|---|--------|----------|--------------|----------------|----------------|--------|---------------|-------------|----------------------|
| 1 | Scoped credential to clone private repo in CI | + | = | + | **RISK** (token in CI) | low | OK | n/a | green |
| 2 | Publish/mirror package to accessible registry (PyPI/internal) | + | + | + | low | med | OK | OK | green |
| 3 | Vendor pinned, audited copy in-repo | + | + (no external) | + | none | med | OK | OK | green |
| 4 | **Split required vs optional security jobs** | + | = | + | none | low | OK | OK | optional job non-green, required green |
| 5 | Allow optional suite to skip with explicit non-green | + | = | + | none | low | acceptable | OK | honest status |
| 6 | Remove dependency if obsolete | + | + | + | none | low | OK | OK | green (if truly obsolete) |
| 7 | Retain failure as deliberate blocker | + | = | - | none | none | BLOCKS release | BLOCKS local | red |

### Recommendation: **Option 4 (split required vs optional) + Option 5 (explicit
optional status)**, with **Option 3 (vendor)** or **Option 2 (mirror)** as the
follow-up if the anti-token-extraction controls must run in CI.

Rationale:
- Option 4 separates the *required* release gate (conformance + audit of what is
  present) from the *optional* security-extension suite. The required job stays
  green when the extension is absent; the optional job is allowed to be
  non-green or skipped-with-note. This preserves release-claim honesty without
  blocking on an inaccessible private repo.
- Option 5 makes the optional status explicit rather than a misleading red X.
- Options 1 (token) and 7 (deliberate blocker) are rejected: token exposure is a
  secret-risk; a deliberate blocker prevents truthful local-first / public
  acceptance.
- Options 2/3 are the durable fix if the extension's checks are load-bearing:
  mirror to an accessible registry or vendor a pinned copy so CI can actually
  install it without a private-token secret.

## 9. Authorization

This memo is **analysis only**. No CI change is made here. The recommended fix
(Option 4+5) is narrow and aligns with existing repository policy (optional
security extensions must not block required gates), but implementing it requires
editing `.github/workflows/release-security.yml` — a change outside M0-B scope.
Per mission discipline, a precise follow-up issue / workflow document is the
correct vehicle; the actual edit should be authorized separately (e.g. its own
PR against `main` or the integration branch). Not executed in this pass.
