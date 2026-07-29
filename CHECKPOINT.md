# CHECKPOINT.md — Immediate Resume Contract

- **checkpoint_id**: `CKPT-2026-07-29-v0.5-p0-hardening`
- **branch**: `codex/capt-v0.5-p0-release-hardening`
- **commit**: `1b74e3a` (latest verified checkpoint; work after it is not frozen)
- **candidate_sha**: `UNFROZEN`
- **release_status**: `HARDENING — NOT RELEASE READY`
- **publication_status**: `NOT PUBLISHED`
- **completed**:
  - captured the packaging baseline at the mission start;
  - repaired package discovery and console-script installation;
  - added wheel/sdist content and isolated installed-profile tests;
  - drafted six-pillar architecture and public API authority contracts.
- **in_progress**: semantic release validation and authority freshness.
- **next_action**: finish negative semantic tests, then run the installed
  verification-first tutorial.
- **remaining_sequence**: tutorial → canonical security closure → frozen
  candidate verification → owner handoff.
- **owner_gate**: no tag, publish, merge, or push.
- **protected_path**: `.capt_state/` must remain untouched.
- **generated_at**: `2026-07-29`
