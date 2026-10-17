# CAPT Foundry M0 - current-main recovery evidence (2026-10-17)

This note updates the historical M0 report without retroactively claiming that old full-suite results apply to the current baseline.

## Proven
- Isolated recovery branch: recovery/foundry-m0-current-20261017.
- Sources restored from feat/capt-foundry-m0 and rebased against current Core origin/main; no changes to RuntimeService authority.
- Renamed Foundry test_corpus.py to test_foundry_corpus.py to avoid a pytest collection collision with SOMA.
- Combined Foundry/SOMA tests: 169 passed.
- Ruff check for capt_foundry and its tests: all checks passed.
- Generated contract drift: OK.
- Earlier staged gitleaks scan: no leaks; repeat on final commit.

## Not yet a release guarantee
- Full repository tests were not green. First current-worktree failure: TypeScript cross-language contract build is missing.
- The same fixture parity test failed on baseline CAPT Core.
- Earlier full-suite attempt also reported many failures and file-descriptor exhaustion.
- No production integration or deployment is claimed. Current-HEAD CI, security and contract gates required.

## Ownership
Foundry owns only research curation metadata and exports. It never creates a second CAPT evidence ledger,
governance authority, provenance authority or agent execution root.
