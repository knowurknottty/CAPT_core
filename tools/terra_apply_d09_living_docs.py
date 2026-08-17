from __future__ import annotations

import subprocess
from pathlib import Path

PR47_HEAD = "4334657a919f74803e65d9b01aa5054d6d7b9a61"
TERRA_EVIDENCE = "90e459917e238669caed2b0895f48b48e9ac2ad0"
HERMES_BRANCH = "evidence/hermes-local-002-r6"
HERMES_HEAD = "5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04"
HERMES_REPORT = "reports/local-evidence/HERMES_AGENT_TUI_WORKSPACE_TESTS_AND_STATE_MAP_8F97AE9_2026-08-17.md"

EXPECTED_FILES = {
    "README.md",
    "capt_ui/ACCEPTANCE_STATUS.md",
    "capt_ui/README.md",
    "docs/ARCHITECTURE.md",
    "docs/CHANGELOG.md",
    "docs/CURRENT_STATE.md",
    "docs/DEMOS.md",
    "docs/MODEL_PROVIDERS.md",
    "docs/PLUGIN_GUIDE.md",
    "docs/PROVIDERS.md",
    "docs/RELEASE_EVIDENCE.md",
    "docs/ROADMAP.md",
    "docs/SECURITY.md",
    "docs/TROUBLESHOOTING.md",
    "docs/TUI.md",
    "docs/V0_6_UI_UX_PRODUCTIZATION.md",
    "docs/WHITEPAPER.md",
}


def read(path: str) -> str:
    return Path(path).read_text()


def write(path: str, text: str) -> None:
    Path(path).write_text(text)


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}: {old[:180]!r}")
    write(path, text.replace(old, new, 1))


def replace_section(path: str, start: str, end: str, replacement: str) -> None:
    text = read(path)
    if text.count(start) != 1:
        raise SystemExit(f"{path}: section start not unique: {start!r}")
    start_idx = text.index(start)
    try:
        end_idx = text.index(end, start_idx + len(start))
    except ValueError as exc:
        raise SystemExit(f"{path}: section end missing: {end!r}") from exc
    write(path, text[:start_idx] + replacement.rstrip() + "\n\n" + text[end_idx:])


# ============================================================================
# PASS 1 — Exact factual correction and primary PR #47 proof refresh.
# ============================================================================

replace_once(
    "README.md",
    "| #47 | prompt assembly, cognitive provenance, TUI cockpit, ProviderDriver | **near-complete integration slice; not yet merged** |",
    "| #47 | prompt assembly, cognitive provenance, TUI cockpit, ProviderDriver | **exact-head source/editable full-suite verified; not yet merged; installed/live-provider proof remains separate** |",
)
replace_once(
    "README.md",
    "- explicit **ENHANCE -> REVIEW -> APPROVE -> RUN** when human verification is required;",
    "- explicit **ENHANCE -> REVIEW -> APPROVE -> RUN** for transformed prompts, with durable RuntimeService approval required for RUN even when enhancement is `OFF`;",
)
replace_section(
    "README.md",
    "### Latest Hermes local integration evidence",
    "See [`docs/CURRENT_STATE.md`]",
    f'''### Hermes LOCAL-002 metadata status

On 2026-08-17, Terra independently attempted to resolve the operator-supplied LOCAL-002 identifiers. The expected branch `{HERMES_BRANCH}`, supplied HEAD `{HERMES_HEAD}`, and named report `{HERMES_REPORT}` are absent from the current GitHub remote/API.

The previously stated `HERMES_LOCAL_002_COMPLETE`, 98/0/0 focused result, 174/0/2 broader result, npm-version notes, and no-blocker statement are therefore **operator-supplied, currently unverified metadata**, not independently usable evidence.

This does **not** invalidate preserved historical v0.5 Hermes evidence. If LOCAL-002 is later restored and independently verified, it would still be adjacent Hermes workspace evidence only; it would not by itself prove PR #47 exact-head correctness, installed-wheel behavior, live-provider execution, destructive rollback, restart continuity, or release readiness.

PR #47 itself now has separate clean source/editable proof at `{PR47_HEAD}`: 8 approval-security tests, 31 focused prompt/provider/TUI/operator tests, 18 Ouroboros lifecycle tests, 387 `capt_runtime` passes, and 861 full-repository passes. Installed-artifact/live-provider/restart/destructive proof remains separate.''',
)

replace_once(
    "capt_ui/ACCEPTANCE_STATUS.md",
    '''Still outside the focused PR proof:

- exact terminal stacked-head acceptance;
- installed-wheel/live-provider acceptance;
- full restart/process-boundary cross-model continuity.
''',
    f'''Current PR #47 source/editable proof at `{PR47_HEAD}`:

- 8 approval-security regressions passed;
- 31 focused prompt/provider/TUI/operator tests passed;
- 18 Ouroboros lifecycle tests passed;
- `tests/capt_runtime`: 387 passed / 10 skipped / 12 deselected;
- full repository: 861 passed / 67 skipped / 12 deselected.

Still outside that proof class:

- installed non-editable wheel/live-provider acceptance;
- terminal cumulative-stack acceptance beyond this PR head;
- full restart/process-boundary cross-model continuity;
- destructive external-provider/tool-kill rollback E2E.
''',
)
replace_section(
    "capt_ui/ACCEPTANCE_STATUS.md",
    "## Hermes Agent workspace/TUI evidence",
    "## Cross-model continuity",
    f'''## Hermes Agent workspace/TUI metadata — currently unverified

The operator supplied LOCAL-002 metadata for `{HERMES_BRANCH}` / `{HERMES_HEAD}` / `{HERMES_REPORT}`, including `HERMES_LOCAL_002_COMPLETE`, Node/npm details, 98/0/0 focused, 174/0/2 broader, and a no-product/state-map-blocker statement.

Terra could not retrieve the branch, commit, or report from the current GitHub remote/API. Those LOCAL-002 values are therefore **not accepted evidence at this checkpoint**. Historical v0.5 Hermes evidence remains separate and intact. If LOCAL-002 is restored, its claims must be re-read from the repository record before they are promoted back into acceptance status.''',
)

replace_once(
    "capt_ui/README.md",
    "These features remain active integration until the stack merges and terminal acceptance is recorded.",
    f"These features remain active integration until the stack merges. PR #47 head `{PR47_HEAD}` has clean source/editable full-suite verification, but installed-artifact, live-provider, terminal cumulative-stack, and cross-model restart acceptance remain separate gates.",
)
replace_section(
    "capt_ui/README.md",
    "## Hermes TUI workspace evidence",
    "## Authority invariant",
    f'''## Hermes TUI workspace metadata

The previously documented `HERMES_LOCAL_002_COMPLETE` workspace/state-map result is currently **unverified operator-supplied metadata**. Terra could not retrieve `{HERMES_BRANCH}`, `{HERMES_HEAD}`, or `{HERMES_REPORT}` from the current GitHub remote/API. The supplied 98/0/0 and 174/0/2 counts and no-blocker statement must not be used as evidence unless the record is restored and independently verified.''',
)

replace_once(
    "docs/ARCHITECTURE.md",
    "PR #47 adds a bounded ProviderDriver for Ollama native generation and OpenAI-compatible chat-completions transport. Controlled HTTP tests establish protocol/lifecycle behavior; intended live-provider installed-runtime acceptance remains a separate proof class.",
    f"PR #47 adds a bounded ProviderDriver for Ollama native generation and OpenAI-compatible chat-completions transport. Exact head `{PR47_HEAD}` has clean source/editable full-suite verification, including the governed approval/dispatch path; intended live-provider and installed-runtime acceptance remain separate proof classes.",
)
replace_once(
    "docs/ARCHITECTURE.md",
    "Hermes is a compatibility/execution client, not CAPT authority. Historical v0.5 evidence established bounded installed-wheel behavior. The `HERMES_LOCAL_002_COMPLETE` evidence branch adds a current local Hermes Agent TUI workspace/state-map result with no product/state-map blocker, while preserving bounded residual gaps.",
    f"Hermes is a compatibility/execution client, not CAPT authority. Historical v0.5 evidence established bounded installed-wheel behavior. Separately, operator-supplied LOCAL-002 metadata referenced `{HERMES_BRANCH}` / `{HERMES_HEAD}`, but Terra could not retrieve that branch, commit, or report from the current GitHub remote/API. `HERMES_LOCAL_002_COMPLETE` and its supplied workspace counts/no-blocker statement are therefore currently unverified and are not architectural evidence.",
)

replace_once(
    "docs/CHANGELOG.md",
    "- PR #47: prompt assembly/cognitive provenance, TUI cockpit, bounded ProviderDriver;",
    f"- PR #47: prompt assembly/cognitive provenance, TUI cockpit, bounded ProviderDriver; exact source/editable head `{PR47_HEAD}` passed clean security, focused, lifecycle, runtime, and full-repository verification;",
)
replace_section(
    "docs/CHANGELOG.md",
    "### Evidence",
    "## v0.5.0",
    f'''### Evidence

- Terra audit evidence is persisted at `evidence/terra-pr47-prompt-approval-verification-r1` / `{TERRA_EVIDENCE}`;
- PR #47 clean head `{PR47_HEAD}` passed 8 approval-security, 31 focused, 18 Ouroboros lifecycle, 387 `capt_runtime`, and 861 full-repository tests in the source/editable proof class;
- earlier documentation recorded operator-supplied `HERMES_LOCAL_002_COMPLETE` metadata for `{HERMES_BRANCH}` / `{HERMES_HEAD}` with reported 98/0/0 and 174/0/2 counts;
- Terra later confirmed the LOCAL-002 branch, commit, and named report are absent from the current GitHub remote/API, so those Hermes values are currently **unverified metadata, not evidence**;
- installed-artifact/live-provider, true cross-model restart continuity, and destructive external-provider/tool-kill rollback remain separate proof classes.''',
)

replace_once(
    "docs/CURRENT_STATE.md",
    "| #47 | prompt/cognitive provenance + TUI cockpit + ProviderDriver | near-complete integration slice; unmerged |",
    "| #47 | prompt/cognitive provenance + TUI cockpit + ProviderDriver | exact-head source/editable full-suite verified; unmerged; installed/live-provider proof still open |",
)
replace_once(
    "docs/CURRENT_STATE.md",
    "The active ProviderDriver has real Ollama and OpenAI-compatible HTTP transport code and controlled HTTP protocol tests. That is **not yet equivalent to exact-head live-provider installed-runtime acceptance**.",
    f"The active ProviderDriver has real Ollama and OpenAI-compatible HTTP transport code and controlled HTTP protocol tests. At PR #47 head `{PR47_HEAD}`, clean verification passed 8 approval-security tests, 31 focused prompt/provider/TUI/operator tests, 18 Ouroboros lifecycle tests, 387 `capt_runtime` tests, and 861 full-repository tests. That is **exact-head source/editable proof**, not live-provider or installed-runtime acceptance.",
)
replace_section(
    "docs/CURRENT_STATE.md",
    "## Hermes local workspace evidence — `HERMES_LOCAL_002_COMPLETE`",
    "## Current highest-value unresolved gates",
    f'''## Hermes LOCAL-002 metadata — currently unverifiable

The operator previously supplied:

- branch `{HERMES_BRANCH}`;
- HEAD `{HERMES_HEAD}`;
- report `{HERMES_REPORT}`;
- classification `HERMES_LOCAL_002_COMPLETE`;
- Node `v22.22.2`, system npm `11.14.1` engine-incompatible, workspace npm `11.17.0` via `npx`;
- focused 98 passed / 0 failed / 0 skipped;
- broader 174 passed / 0 failed / 2 skipped;
- no product/state-map blocker.

Terra independently checked the current remote/API and found the supplied branch, commit, and named report absent. The metadata above is therefore **operator-supplied and currently unverified**. The earlier connector-lag explanation is withdrawn; current repository state does not support treating LOCAL-002 as published evidence.

This quarantine does not alter preserved historical v0.5 Hermes proof. If LOCAL-002 is restored, the report must be independently retrieved and reconciled before its claims are promoted. Even then it would remain adjacent workspace evidence, not proof of PR #47 exact-head correctness, an installed wheel, a live provider, destructive rollback, process-boundary restart continuity, or release readiness.''',
)

replace_section(
    "docs/RELEASE_EVIDENCE.md",
    "## Active PR evidence",
    "## Hermes local evidence — LOCAL-002",
    f'''## Active PR evidence

Each active stacked PR has its own evidence boundary. PR #47 now has clean exact-head **source/editable-runtime** verification at `{PR47_HEAD}`:

- approval-security regressions: 8 passed;
- focused prompt/provider/TUI/operator suite: 31 passed;
- Ouroboros lifecycle: 18 passed;
- `tests/capt_runtime`: 387 passed / 10 skipped / 12 deselected;
- full repository: 861 passed / 67 skipped / 12 deselected;
- contract drift and `git diff --check`: passed.

That proof does not convert the source tree into an installed-wheel, live-provider, process-boundary cross-model, destructive rollback, or release artifact proof.''',
)
replace_section(
    "docs/RELEASE_EVIDENCE.md",
    "## Hermes local evidence — LOCAL-002",
    "## What still requires separate proof",
    f'''## Hermes LOCAL-002 metadata — quarantined pending retrieval

The operator supplied branch `{HERMES_BRANCH}`, HEAD `{HERMES_HEAD}`, report `{HERMES_REPORT}`, classification `HERMES_LOCAL_002_COMPLETE`, and reported 98/0/0 focused plus 174/0/2 broader results with Node/npm environment notes and a no-product/state-map-blocker statement.

Terra later verified that the branch, commit, and named report are absent from the current GitHub remote/API. These values are therefore **not independently usable evidence**. The prior explanation that GitHub retrieval was merely lagging is superseded by the later remote/API audit.

Historical v0.5 Hermes evidence remains authoritative for its own bounded release lineage. If LOCAL-002 is restored, its report must be retrieved and reviewed before any of its claims re-enter the release ledger. Even a restored LOCAL-002 record would remain adjacent Hermes workspace evidence rather than proof of PR #47 exact head, installed-wheel behavior, live-provider execution, destructive rollback, restart continuity, or release readiness.''',
)

replace_section(
    "docs/DEMOS.md",
    "## Hermes local TUI/workspace evidence",
    "## Acceptance target — real provider execution",
    f'''## Hermes local TUI/workspace metadata

LOCAL-002 was previously described as a focused Hermes workspace/state-map evidence record. Terra could not retrieve `{HERMES_BRANCH}`, `{HERMES_HEAD}`, or `{HERMES_REPORT}` from the current remote/API, so `HERMES_LOCAL_002_COMPLETE` and the supplied 98/0/0 and 174/0/2 counts are currently **unverified metadata**, not a demo or acceptance artifact. See [`CURRENT_STATE.md`](CURRENT_STATE.md).''',
)

replace_once(
    "docs/MODEL_PROVIDERS.md",
    "Hermes remains a compatibility/execution client path, not CAPT runtime authority. Historical v0.5 evidence proves bounded installed-wheel interaction; newer lifecycle hardening lives in PR #46. The dedicated `HERMES_LOCAL_002_COMPLETE` evidence branch additionally records the local Hermes Agent TUI workspace/state-map test result described in `CURRENT_STATE.md`.",
    f"Hermes remains a compatibility/execution client path, not CAPT runtime authority. Historical v0.5 evidence proves bounded installed-wheel interaction; newer lifecycle hardening lives in PR #46. The separately supplied LOCAL-002 identifiers (`{HERMES_BRANCH}` / `{HERMES_HEAD}`) are currently absent from the GitHub remote/API, so `HERMES_LOCAL_002_COMPLETE` and its supplied workspace results are **unverified metadata**, not provider evidence. See `CURRENT_STATE.md`.",
)

replace_once(
    "docs/PLUGIN_GUIDE.md",
    f'''- historical v0.5 installed-wheel bounded Hermes proof;
- active #46 lifecycle hardening;
- `HERMES_LOCAL_002_COMPLETE` local Hermes Agent TUI workspace/state-map evidence on `{HERMES_BRANCH}` at `{HERMES_HEAD}`.

LOCAL-002 reports 98/0/0 focused and 174/0/2 broader tests with no product/state-map blocker. It explicitly does not close the destructive external-provider/tool-kill rollback E2E gap.''',
    f'''- historical v0.5 installed-wheel bounded Hermes proof;
- active #46 lifecycle hardening;
- operator-supplied LOCAL-002 metadata for `{HERMES_BRANCH}` at `{HERMES_HEAD}`.

Terra could not retrieve the LOCAL-002 branch, commit, or named report from the current GitHub remote/API. Its `HERMES_LOCAL_002_COMPLETE`, 98/0/0, 174/0/2, and no-blocker statements are therefore **currently unverified** and must not be used to certify a compatibility client. Destructive external-provider/tool-kill rollback remains separately unproven.''',
)

replace_section(
    "docs/PROVIDERS.md",
    "## Hermes local workspace evidence",
    "## TUI integration",
    f'''## Hermes LOCAL-002 workspace metadata

The operator supplied `HERMES_LOCAL_002_COMPLETE` metadata for `{HERMES_BRANCH}` / `{HERMES_HEAD}` with reported 98/0/0 focused and 174/0/2 broader tests and npm environment details. Terra could not retrieve that branch, commit, or `{HERMES_REPORT}` from the current GitHub remote/API.

Accordingly, LOCAL-002 is **currently unverified metadata, not provider evidence**. Historical v0.5 Hermes proof remains separate. The missing LOCAL-002 record cannot close destructive rollback, general live-provider acceptance, installed-runtime acceptance, or any PR #47 proof boundary. See [`CURRENT_STATE.md`](CURRENT_STATE.md) and [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md).''',
)

replace_once(
    "docs/ROADMAP.md",
    "- [ ] **#47 TUI cognition + ProviderDriver** — merge prompt assembly/provenance, cockpit controls, and bounded Ollama/OpenAI-compatible generation.",
    f"- [ ] **#47 TUI cognition + ProviderDriver** — merge prompt assembly/provenance, cockpit controls, and bounded Ollama/OpenAI-compatible generation; exact source/editable head `{PR47_HEAD}` is full-suite verified, while installed/live-provider proof remains separate.",
)
replace_section(
    "docs/ROADMAP.md",
    "## Hermes local evidence checkpoint",
    "## Release-critical acceptance still open",
    f'''## Hermes LOCAL-002 evidence checkpoint

- [ ] restore/publish an independently retrievable LOCAL-002 branch/commit/report if this evidence record is intended to remain part of the public ledger;
- [ ] independently verify the operator-supplied `{HERMES_BRANCH}` / `{HERMES_HEAD}` metadata and the reported 98/0/0, 174/0/2, skip, npm, and no-blocker claims before promoting them back to evidence;
- [ ] destructive external-provider/tool-kill rollback E2E remains separately unproven regardless of LOCAL-002 restoration.''',
)

replace_section(
    "docs/SECURITY.md",
    "## Hermes workspace evidence",
    "## Data at rest",
    f'''## Hermes workspace metadata boundary

Operator-supplied LOCAL-002 metadata described `HERMES_LOCAL_002_COMPLETE`, successful non-destructive workspace suites, and no product/state-map blocker while leaving destructive external-provider/tool-kill rollback unproven. Terra could not retrieve `{HERMES_BRANCH}`, `{HERMES_HEAD}`, or the named report from the current GitHub remote/API, so those LOCAL-002 security/recovery statements are **currently unverified and must not close any control**.

The destructive rollback/reconciliation gate remains open independently of whether LOCAL-002 is later restored.''',
)

replace_once(
    "docs/TROUBLESHOOTING.md",
    "| Hermes workspace uses wrong npm | system npm may violate Hermes workspace engine requirement | use the faithful workspace npm path recorded by the Hermes evidence report |",
    "| Hermes workspace uses wrong npm | system npm may violate the workspace's declared engine requirement | follow the checked-out Hermes workspace's own engine/package-manager declaration; do not rely on the currently unavailable LOCAL-002 report |",
)
replace_section(
    "docs/TROUBLESHOOTING.md",
    "## Hermes workspace note",
    "## Security-related failures",
    f'''## Hermes workspace note

The operator-supplied LOCAL-002 metadata stated Node `v22.22.2`, system npm `11.14.1` engine-incompatible, and npm `11.17.0` via `npx` for the faithful workspace run. Terra could not retrieve `{HERMES_BRANCH}`, `{HERMES_HEAD}`, or the report from the current GitHub remote/API. Treat those version details as **unverified historical metadata**, not as current troubleshooting authority; inspect the actual checked-out Hermes workspace requirements instead.''',
)

replace_once(
    "docs/TUI.md",
    "When enhancement is enabled and human verification is required, RUN is locally blocked until the proposal is approved.",
    "When enhancement is enabled, the transformed proposal must be produced before APPROVE. RUN always requires a durable RuntimeService-backed prompt approval, including when enhancement is `OFF`; the separate human-result-verification preference does not grant execution authority.",
)
replace_section(
    "docs/TUI.md",
    "## Hermes Agent TUI workspace evidence",
    "## What these controls do not do",
    f'''## Hermes Agent TUI workspace metadata

The operator supplied LOCAL-002 identifiers `{HERMES_BRANCH}` / `{HERMES_HEAD}` / `{HERMES_REPORT}` plus `HERMES_LOCAL_002_COMPLETE`, Node/npm details, 98/0/0 focused, 174/0/2 broader, and no-product/state-map-blocker claims.

Terra could not retrieve the branch, commit, or report from the current GitHub remote/API. Those LOCAL-002 TUI/workspace statements are therefore **currently unverified metadata** and are not part of the accepted TUI evidence ledger. Historical v0.5 Hermes evidence remains separate.''',
)
replace_once(
    "docs/TUI.md",
    "PR #47 contains the bounded ProviderDriver used by the upgraded run path. Its controlled HTTP tests are meaningful protocol/lifecycle evidence, but the final exact-head live-provider installed-runtime acceptance remains open.",
    f"PR #47 contains the bounded ProviderDriver used by the upgraded run path. Exact head `{PR47_HEAD}` has clean source/editable security, focused, Ouroboros lifecycle, runtime, and full-repository verification. Live-provider and installed-runtime acceptance remain open as separate proof classes.",
)
replace_once(
    "docs/TUI.md",
    "- Hermes local TUI/workspace state map: **`HERMES_LOCAL_002_COMPLETE` on dedicated evidence branch**;\n- PR #47 cockpit/provider execution: **IMPLEMENTED IN ACTIVE INTEGRATION, NOT SHIPPED**;",
    f"- Hermes LOCAL-002 TUI/workspace state map: **OPERATOR-SUPPLIED / CURRENTLY UNVERIFIED**;\n- PR #47 cockpit/provider execution at `{PR47_HEAD}`: **EXACT-HEAD SOURCE/EDITABLE VERIFIED, NOT SHIPPED**;",
)

replace_once(
    "docs/V0_6_UI_UX_PRODUCTIZATION.md",
    "The dedicated `HERMES_LOCAL_002_COMPLETE` evidence branch further maps/tests the Hermes Agent TUI workspace integration state with no product/state-map blocker, while leaving a destructive rollback E2E gap.",
    f"Later documentation recorded operator-supplied LOCAL-002 metadata for `{HERMES_BRANCH}` / `{HERMES_HEAD}` and described `HERMES_LOCAL_002_COMPLETE`; Terra subsequently found the branch, commit, and named report absent from the current GitHub remote/API. That later metadata is **not part of this historical planning baseline's verified evidence** and remains quarantined unless restored and independently checked.",
)

replace_once(
    "docs/WHITEPAPER.md",
    "In addition to historical v0.5 Hermes evidence and active lifecycle hardening, the dedicated `HERMES_LOCAL_002_COMPLETE` evidence branch records a faithful local Hermes Agent TUI workspace/state-map run with 98/0/0 focused and 174/0/2 broader test results and no product/state-map blocker. A destructive external-provider/tool-kill rollback E2E case remains outside that proof.",
    f"Historical v0.5 Hermes evidence and active lifecycle hardening remain distinct evidence classes. A later operator-supplied LOCAL-002 record referenced `{HERMES_BRANCH}` / `{HERMES_HEAD}` and claimed `HERMES_LOCAL_002_COMPLETE` with 98/0/0 focused and 174/0/2 broader results, but Terra could not retrieve the branch, commit, or named report from the current GitHub remote/API. Those LOCAL-002 statements are therefore **currently unverified metadata**. Destructive external-provider/tool-kill rollback remains independently unproven.",
)

# ============================================================================
# PASS 2 — Evidence-class audit: every touched file must explicitly quarantine
# LOCAL-002 rather than merely deleting the inconvenient identifier.
# ============================================================================

QUALIFIERS = (
    "unverified",
    "unverifiable",
    "not independently usable",
    "not accepted evidence",
    "not part of this historical planning baseline's verified evidence",
)
for path in sorted(EXPECTED_FILES):
    lowered = read(path).lower()
    if not any(q.lower() in lowered for q in QUALIFIERS):
        raise SystemExit(f"{path}: LOCAL-002 correction lacks an explicit evidence qualifier")

# ============================================================================
# PASS 3 — Public-claim audit: remove the false pushed/published/propagation
# explanation everywhere in the living/public scope while permitting literal
# identifiers only inside explicit quarantine text.
# ============================================================================

PUBLIC_PATHS = [Path("README.md"), Path("START_HERE.md")]
PUBLIC_PATHS += list(Path("docs").rglob("*.md"))
PUBLIC_PATHS += list(Path("capt_ui").rglob("*.md"))
FORBIDDEN = (
    "dedicated pushed branch",
    "operator has published",
    "Pushed HEAD:",
    "connector lagged",
    "GitHub connector had not yet propagated",
    "just-pushed remote ref",
    "evidence branch pushed",
)
for path in PUBLIC_PATHS:
    text = path.read_text()
    for phrase in FORBIDDEN:
        if phrase in text:
            raise SystemExit(f"{path}: stale evidence claim remains: {phrase!r}")

# ============================================================================
# PASS 4 — Cross-document proof-boundary reconciliation for PR #47.
# ============================================================================

for path in ("README.md", "docs/CURRENT_STATE.md", "docs/RELEASE_EVIDENCE.md"):
    text = read(path)
    for required in (PR47_HEAD, "861", "installed"):
        if required not in text:
            raise SystemExit(f"{path}: missing refreshed PR47 proof boundary token {required!r}")
    if "live-provider" not in text and "live provider" not in text:
        raise SystemExit(f"{path}: missing explicit live-provider nonclaim")

# ============================================================================
# PASS 5 — Scope/idempotence audit: exactly the 17 public files identified by
# the independent grep may change. No historical evidence artifact is rewritten.
# ============================================================================

changed = {
    line.strip()
    for line in subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines()
    if line.strip()
}
if changed != EXPECTED_FILES:
    missing = sorted(EXPECTED_FILES - changed)
    extra = sorted(changed - EXPECTED_FILES)
    raise SystemExit(f"unexpected documentation scope; missing={missing}, extra={extra}")

print("D09_LIVING_DOCS_RECONCILED_5X")
print(f"PR47_HEAD={PR47_HEAD}")
print(f"FILES={len(changed)}")
