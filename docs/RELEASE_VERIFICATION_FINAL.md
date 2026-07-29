# Release Verification Final

## Candidate

`6075d55e52d93c22bfdde6f85c06405384e4a01c` (`0.5.0`, untagged).

## Completed clean-worktree checks

- `python3 -m pytest -q -rs`: 669 passed, 1 skipped.
- `python3 verify_runtime.py`: 46 pass, 0 warn, 0 fail, 0 skip.
- `python3 capt_cli.py architecture validate`: 15 checks, 0 fail.
- `python3 -m compileall -q capt_solo`: passed.
- `python3 -m build`: passed; metadata-license deprecation warnings removed.

Artifacts produced from the frozen worktree:

- wheel SHA-256: `d5b19487d1906018de3755c764d5e3301808d544f0e7dd7103636ebac15748c6`
- sdist SHA-256: `143fa5d6908feb472cf2fd7f590bf48ca38adef1fdc385588ec42fbc08171d06`

## Not ready declaration

This document is intentionally not a release approval. The in-progress
repository-wide security scan has not been sealed and fresh wheel/sdist install
smoke checks remain to be rerun against this final SHA. No tag or publication
was created.
