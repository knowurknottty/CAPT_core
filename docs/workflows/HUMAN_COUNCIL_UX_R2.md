# Human Council UX R2

This refines the normal `capt council` experience without changing RuntimeService authority, approval rules, or cohort provider-call semantics.

## Human-facing capabilities

- Each cohort appears in an individual visual card showing provider, model, logical vessel count, configuration and objective excerpt; Edit loads that cohort into the editor.
- Providers and cached model IDs come from the existing ProviderManager registry without contacting the network. `Refresh models` is an explicit user action. An unlisted model ID can be typed manually.
- Presets include Donor convergence (three named Flash providers with 11 vessels each), Blank Council and Latest autosave.
- The draft autosave is atomic, 0600 and stored at `~/.capt/ui/council-autosave.json`. It preserves unsaved editor text and intermediate form fields without storing approvals, receipts or credentials.
- On startup, the human is asked whether to recover an existing draft. Recovery never restores authority or authorizes provider execution.
- Approval labels distinguish requested, approved, denied and expired states; colors supplement, not replace, textual labels.
- Execution status lanes read DriverRun and reconciliation state from RuntimeService. Missing state remains unknown; generated model text never becomes a verified outcome by display alone.
- Request, decision, refresh and receipt queries are backgrounded rather than blocking the Tk event loop.
- After a workflow change, the approval digest and unapplied cohort edits are checked again before authorizing Launch.

## Boundaries

This is a presentation-only improvement. Live model availability, budget, charter generation and actual source integrations are separately verified runtime concerns. No model call or approval is triggered by loading a preset, autosaving or recovery.

## Verification

Run `tests/capt_ui/test_council_ux.py`, the existing Council workflow tests, a Tk startup smoke test, `contracts/tools/check_drift.py`, and the full CAPT pytest suite.


## Verification receipts — 2026-10-12

- Targeted Council/UI regression tests: 16 passed.
- Native Tk creation and first update: passed (window geometry 1480×900).
- Contract drift: OK, 11 generated files.
- Full suite on feature worktree: 1621 passed, 24 failed, 18 skipped, 13 deselected before the final two added tests.
- The pristine parent 2b0e09e baseline reproduced the exact same 24 test failures: 1618 passed, 24 failed, 18 skipped, 13 deselected. These are pre-existing runtime integration failures, not a green suite; no code in this change attempts to conceal or fix them.
- No live provider call, approval, or mission launch was performed by this UX work.
