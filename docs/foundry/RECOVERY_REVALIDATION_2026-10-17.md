# CAPT Foundry M0 - current-main recovery evidence (2026-10-17)

This note updates the historical M0 report without retroactively claiming that old full-suite results apply to the current baseline.

## Proven
- Isolated recovery branch: recovery/foundry-m0-current-20261017.
- Sources restored from feat/capt-foundry-m0 and rebased against current Core origin/main; no changes to RuntimeService authority.
- Renamed Foundry test_corpus.py to test_foundry_corpus.py to avoid a pytest collection collision with SOMA.
- Combined Foundry/SOMA tests: 171 passed.
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


## Post-construction vault redirect regression (2026-10-17)

Synthetic temp-folder test demonstrated that replacing the initialized Obsidian
projection subdirectory with an outside-pointing symlink redirected subsequent
writes beyond the declared vault. The root could also be substituted by a
symlink after initialization. The old code did not provide a safe write-time
directory identity check.

The exporter now uses no-follow directory handles anchored to the original
vault/subdirectory device and inode, performs file access relative to those
handles, and atomically replaces exported notes without following a final
symlink. Two regression tests first failed on the vulnerable code and now pass.
All 29 projection tests and the combined 171 Foundry/SOMA tests pass.
No runtime ledger, approval authority, or private user data was involved.

This protects the supported local-platform symlink-swap threat model, not
against a privileged actor who can mount or rename directories out from under
open directory descriptors; deployments still require filesystem permissions
and vault ownership appropriate to their threat model.
