# RRDS-1: CAPT reviewer and verifier contracts

## Reviewer must produce
1. **Pinned inputs:** repository canonical URL/name, checked-out HEAD, worktree, status, precise task, limitations.
2. **Complete recursive census:** all source-bearing directories, files, and their SHA-256; report excluded/vendor/generated trees and any symlinks and unreadable paths. One-level enumeration is SAMPLE only.
3. **Cross-boundary architecture analysis:** entrypoint -> capability/authorization -> effect -> witness for every proposed change; alternate call sites and tests.
4. **Receipts:** file path and digest plus exact line/symbol evidence; mark observed, code-read, inferred, or proposed. Failed/omitted probes remain visible.
5. **Coverage:** execute scripts/capt_repo_audit_gate.py verify against the frozen census and inspection records. If the verdict isn't DEEP_COVERAGE_GATE_PASS, publish PARTIAL with a continuation frontier.
6. **Risk decisions:** no cherry-pick based solely on a sampled review; license and provenance check required.
Reviewer never self-declares independent verification or merges work.

## Independent verifier must produce
- Re-enumerate the same checked-out HEAD from a separate session/worktree; compare every path, digest, declared exclusion, and receipt to reviewer evidence.
- Run the RRDS CLI, falsify one shallow-scan fixture and one altered-source fixture, inspect any critical paths the heuristics missed.
- Confirm integration tests or state NOT_RUN with environment blockers.
- Submit verdict PASS, PARTIAL, or FAIL with exact input/head/digest and omissions.
- Never count a model consensus as evidence or silently upgrade PARTIAL to PASS.

## CI contract
CI must run scripts/capt_repo_audit_gate.py through tests/test_capt_repo_audit_gate.py. If a repository-review evidence index is proposed for release, CI must verify every declared dossier against its accessible pinned source tree. An external checkout not available in CI is UNVERIFIED, not pass. A PR describing itself as a completed deep review must carry review receipts and a separate verifier approval. Branch protection must require the RRDS job before it becomes a merge blocker; a YAML workflow by itself does not enforce branch policy.

## Stages
discovered -> triaged -> sampled -> inventoried -> deep-reviewed -> validated. Do not skip or collapse stages. The 70% diagnostic floor is not sufficient for deep-review status: the deep gate requires 100% of declared in-scope source-file receipts: every source-bearing directory and every risk-critical path must have examined-file receipts. Missing source trees, symlinks, dependency boundaries, drift, unreadable paths, or incomplete receipts force PARTIAL.
