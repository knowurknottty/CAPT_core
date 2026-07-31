# MICRO_AUDIT_EVIDENCE_INDEX — Phase B

Candidate SHA: `be2863508e47c3cb9ea4b4320ebab29bdcf64d94`
All evidence attributable to candidate SHA + artifact hash.

| Check | Command | WDIR | Exit | Raw evidence location | SHA |
|---|---|---|---|---|---|
| B1 | `.venv/bin/python -m capt_cli release validate` | ~/capt-solo | 0 | MICRO_AUDIT_REPORT.md (10 pass/0 fail) | be28635 |
| B2 | `git ls-tree` + `unzip -l` + manifest parse | ~/capt-solo | 0 | MICRO_AUDIT_REPORT.md (4 inventories agree) | be28635 |
| B3 | `[ -f docs/security/... ]` + `[ -f docs/release/... ]` | ~/capt-solo | 0 | both exist | be28635 |
| B4 | `ls` of advertised paths | ~/capt-solo | 0 | both present | be28635 |
| B5 | content review of 2 reports | ~/capt-solo | 0 | reports cite regenerated evidence | be28635 |
| B6 | content review | ~/capt-solo | 0 | "no new public claim" stated | be28635 |
| B7 | grep CORRECTION NOTICE | ~/capt-solo | 0 | EXACT_SHA doc corrected | be28635 |
| B8 | `git show --stat be28635` | ~/capt-solo | 0 | 5 files only | be28635 |
| B9 | grep SHA in 4 docs | ~/capt-solo | 0 | all 4 contain SHA | be28635 |
| B10 | `git status` | ~/capt-solo | 0 | CLEAN | be28635 |

## Artifact hashes
- wheel: e9e316464916a5ae97a4306ba15ad87dc1b191ee49d4cb047e9a9950248a3ba9
- sdist: 92962c3b26687a61391593caba5ae0ea58a96c44374761616ba421d95189c480

## Raw logs retained
- /tmp/micro_validate.txt (full `capt release validate` output)
- release_evidence/micro_audit_findings.json
