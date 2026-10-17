# CAPT worktree recovery register — 2026-10-17

This file records source identities and a test-gated reconciliation plan. It is not evidence that candidate code was merged or released.

## Verified baseline

- Registry entries inspected: **152**
- Ancestor-of-main worktrees: **47**
- Candidate worktrees (including patch-equivalent/non-ancestral histories): **105**
- Distinct candidate HEADs: **94**
- Candidates with tracked modifications: **27**
- Detached candidate worktrees: **10**
- Main HEAD matches published origin/main at audit time: **e9c7b80d455cfc9415813bdfe4296eb6933fed6f**
- Audit time UTC: 2026-10-17T10:01:44.465178+00:00

## Reconciliation classes

1. Ancestral: commit already reachable from main. Dirty content is independently preserved.
2. Non-ancestral but patch-equivalent: requires per-file and test evidence; do not re-apply.
3. Clean candidate: inspect current target code and commit ancestry; cherry-pick only missing, small, independently testable changes.
4. Dirty candidate: preserve original state; review its diff, snapshot SHA and owner; isolate specific changes before attempting application.
5. Shared HEAD: multiple checkouts at the same commit represent one source lineage; do not count each as a separate innovation.
6. Large/divergent integration: use a dependency DAG and component-level salvage, never a wholesale merge of historical stacks.

## Gates required for every non-trivial merge

- Identity: repository/worktree, SHA, branch, remote, clean/dirty inventory.
- Scope: diff review and duplicate/overlap analysis against latest main.
- Quality: focused tests, relevant end-to-end tests, security and authorization checks.
- Governed execution: CAPT Node capability must authorize the exact worktree.
- Remote delivery: protected PR, head SHA binding, CI, review, merge readback.
- Preservation: no reset, clean, force-push, automated stash, branch/worktree removal.

## Small clean candidates requiring exact patch review

- docs/current-state-pr-reconciliation-r1 — 9f440d9372cc; historical unique commits 1; dirty inventory 0.
- feat/capt-skills-external-pack-r1 — f0651b8ca131; historical unique commits 1; dirty inventory 0.
- fix/standard-native-sigpipe-20260924 — c59270840bc7; historical unique commits 1; dirty inventory 0.
- feat/capt-runtime-m0b-readonly-driver-proof — c518acf4a91c; historical unique commits 1; dirty inventory 0.
- docs/hermes-moa-capt-case-study-20260921 — 80b4628f37f6; historical unique commits 1; dirty inventory 0.
- feature/council-demo-wiring — 6d5e8b67e749; historical unique commits 1; dirty inventory 0.
- (detached) — b21ed6e7ff39; historical unique commits 2; dirty inventory 0.
- design/native-prompt-intelligence-software-dev-r1 — cafa1815c5ce; historical unique commits 2; dirty inventory 0.
- feat/capt-foundry-m0 — 8edb3ff3ef37; historical unique commits 2; dirty inventory 0.
- feat/capt-refresh-v1-20261012 — eff6164356b5; historical unique commits 2; dirty inventory 0.
- feat/tia-core-authority-r1 — 4e5694326391; historical unique commits 2; dirty inventory 0.
- work/capt-core-terminal-release-closure-r2 — b21ed6e7ff39; historical unique commits 2; dirty inventory 1.
- audit/tia-core-muse — 4e5694326391; historical unique commits 2; dirty inventory 2.
- integration/capt-core-upgrades-20260924 — cc70501f2e00; historical unique commits 3; dirty inventory 0.
- feat/rrds1-review-depth-20261012 — ef189732a6de; historical unique commits 3; dirty inventory 0.
- fix/runtime-r5-socketfix-20260924 — c7af9be0574c; historical unique commits 4; dirty inventory 0.
- integration/capt-core-63-r1 — a1c0d6d49b8d; historical unique commits 4; dirty inventory 0.
- feature/capt-moa-planning-r1 — e26a07c23aca; historical unique commits 4; dirty inventory 0.
- (detached) — ad9521b0fec4; historical unique commits 4; dirty inventory 0.
- feat/native-authored-skills-r1 — e55037d92e89; historical unique commits 5; dirty inventory 0.

## Scope and safety

CAPT-macOS is an independent Git repository with uncommitted Council, Kanban and bridge edits; its local path is not currently in the active CAPT Node capability roots. Do not silently move or publish those edits through another authority plane.

Worktree paths, unrelated personal files, credentials and local auth material are excluded from this published register.

## Exit conditions

Every candidate is annotated as integrated, proven equivalent, superseded, merged, or specifically blocked, with an evidence pointer. The register is not complete until every candidate has such a terminal disposition. The current values are audit-only.
