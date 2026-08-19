# CAPT Core Main Convergence + macOS/MCP Integration Workflow R1

## Purpose
Converge the verified CAPT Core stacked lines into one exact-head integration candidate before merging to `main`, while preserving RuntimeService/EventStore authority and proving the native macOS and companion MCP surfaces against the same runtime contract.

## Current authority baseline
- Repository: `knowurknottty/CAPT_core`
- Candidate spine head: `fix/local-openai-compatible-provider-r1` @ `5ec276e891cf9fbfff2ce619a742f4b0f210c1ee`
- Main: resolve fresh at execution time; do not rely on this document for a mutable SHA.
- Companion MCP repository: `knowurknottty/capt-workspace-mcp`; local commits must be pushed to an explicit branch/PR before release claims.

## Non-negotiable invariants
1. RuntimeService/EventStore remain authoritative; native UI and MCP are projections/controllers only.
2. No provider output auto-verifies, auto-ClaimGuard-accepts, or completes a task/mission.
3. Human approval binding remains exact, single-use, expiry-aware, idempotent, and fail-closed.
4. New Chat never inherits another session's pending approval and uses the current global provider/model preference.
5. Local OpenAI-compatible credentialless dispatch is admitted only for explicit LOCAL providers on loopback endpoints.
6. MCP may expose governed commands but may not mint CAPT authority, cache authoritative state as truth, or bypass RuntimeService admission.
7. Merge order follows semantic dependency, not PR number or age.

## Phase A — Freeze and classify branch topology
- Fetch/prune all remotes and record `main`, candidate spine, UPG terminal head, native hardening heads, and MCP head SHAs.
- Build an ancestry matrix for every open PR/branch against the candidate spine.
- Classify each as one of:
  - `ANCESTOR_ALREADY_INCLUDED`
  - `STACKED_SUCCESSOR`
  - `DIVERGENT_RECONCILE`
  - `SUPERSEDED_CLOSE`
  - `DESIGN_REVIEW_ONLY`
  - `EMPIRICAL_PROBE_NOT_RELEASE_BLOCKING`
- Never merge a PR whose change is already present in a newer descendant; close/supersede it with lineage noted instead.

## Phase B — Reconcile native macOS hardening
Known divergent native lines must be explicitly reviewed against the provider spine, especially:
- `fix/macos-native-session-navigation-dogfood-r1`
- `integration/native-openrouter-hardening-dogfood`

For each divergent commit:
1. inspect diff against merge-base;
2. map behavior to current native tests and RuntimeService contracts;
3. cherry-pick/reimplement only changes not already subsumed by newer code;
4. add/retain a discriminating regression test before implementation when behavior changes;
5. reject stale state-machine or approval semantics even if the code applies cleanly.

Required native gate on the resulting integration head:
```bash
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```
Then run the opt-in live RuntimeService tests against a disposable CAPT state dir and one local provider. Record exact source SHA, runtime ledger before/after, approval/task/DriverRun states, and verificationId.

## Phase C — Reconcile the UPG line semantically
Do not merge UPG PRs one-by-one into `main` from stale bases. Treat the verified UPG terminal line as a feature inventory and transplant missing semantics onto the current candidate spine.

Minimum inventory to reconcile:
- bounded production IPC framing;
- strict state permissions / at-rest boundary behavior actually implemented;
- durable security rejection audit trail;
- token/request/output/cost ceilings;
- injection assurance gates;
- destructive/ambiguous effect recovery;
- isolated workspace mutation + governed promotion;
- durable Cohort persistence and steering;
- `.capt-flight` forensic bundle;
- ContextPack component provenance probe where useful;
- epistemic ladder;
- lease inspector/revoke;
- point-in-time replay + governed replay fork;
- provenance DAG/Lens;
- Cohort Chamber;
- Security Closure Cockpit.

For every item, prove either `ALREADY_PRESENT_EQUIVALENT_OR_STRONGER` or land a minimal current-stack change with tests. Do not copy old aggregate/state code merely to preserve branch history.

## Phase D — Push and PR the MCP companion
In `capt-workspace-mcp`:
1. branch from the local 13-commit-ahead state rather than force-updating remote `main`;
2. push the branch and open a PR;
3. include exact CAPT Core candidate SHA in the PR body;
4. run the full MCP suite with `CAPT_CORE_PATH` pointing at the exact integration candidate;
5. require the real RuntimeService fixture tests to pass, not only mocked protocol tests.

Required MCP invariants:
- authenticated bounded framed IPC;
- runtime snapshot reads authoritative RuntimeService state;
- approval request/deny/approve paths use RuntimeService commands;
- task state before materialization correctly projects pending approval without inventing task authority;
- GPT Actions gateway delegates to runtime IPC rather than duplicating state;
- ChatGPT profile exposes only intended governed tools and rejects hidden legacy tools;
- failures are fail-closed when runtime/token/socket are unavailable.

## Phase E — Cross-surface contract test: macOS ↔ Runtime ↔ MCP
Use one disposable runtime state and one candidate source SHA.

Run this sequence:
1. launch RuntimeService;
2. connect native macOS app and MCP client to the same runtime;
3. create a harmless model approval from MCP;
4. observe the same pending approval in native state projection;
5. deny it from native and prove MCP subsequently sees authoritative denial;
6. create a fresh approval from native;
7. approve/execute through MCP using the exact approval binding;
8. prove native renders the resulting DriverRun/task state as `awaiting_verification` and does not display verified/completed state unless a real verification exists;
9. retry the exact execution and prove no second provider dispatch;
10. attempt a mismatched second use and prove fail-closed rejection;
11. restart RuntimeService and prove both clients reconstruct the same ledger-backed state.

Capture: source SHA, wheel/app hashes if built, MCP commit SHA, runtime ledger head/digest before and after each consequential step, approval IDs/digests, DriverRun IDs, provider/model provenance, task states, verification IDs.

## Phase F — Browser/custom-GPT CAPT assist path
This is optional assistance, never release authority.

If Chrome DevTools or another authorized browser-control surface is available, keep the CAPT custom GPT tab open and use it only through the governed GPT Actions/MCP path. Require a read-only `captRuntimeStatus`-style probe first. If the browser/custom GPT cannot prove it is connected to the same RuntimeService/source lineage, do not use its conclusions as integration evidence.

The browser model may review diffs, challenge the merge plan, and generate adversarial test ideas. It may not approve its own consequential CAPT action, mark evidence verified, or substitute conversation text for repository/runtime authority.

## Phase G — Exact-head release candidate verification
On one clean integration branch/worktree:
```bash
python -m pytest -q
python contracts/tools/check_drift.py
cd capt_ui/surfaces/desktop_swift && swift test && swift build --product CAPTNativeMac
```
Run security/release-specific gates and `git diff --check`.
Build the wheel/sdist and native app from the exact same commit. Install into fresh environments and repeat the critical RuntimeService/native/MCP acceptance against installed artifacts.

No release-ready claim if:
- any required test is skipped without an explicit scope reason;
- source and installed-artifact SHAs differ from the recorded candidate lineage;
- security gate is BLOCKED for an applicable release control;
- MCP integration is only tested against mocks;
- native and MCP disagree about approval/task/verification state;
- any provider request occurs without a valid consumed approval when approval is required;
- replay/restart causes blind redispatch.

## Phase H — PR cleanup and merge
Only after the exact integration head passes:
1. open one terminal integration PR to `main`;
2. list every subsumed PR and the commit/behavior that supersedes it;
3. close superseded stacked PRs without separately merging them;
4. merge design-only/probe PRs only if they are intentionally part of repository history and do not misrepresent implementation state;
5. merge the terminal integration PR using one chosen strategy; record final main SHA;
6. rerun a post-merge smoke from `main` and verify installed artifacts are still derived from that exact lineage.

## Terminal classification
Exactly one:
- `READY_TO_MERGE_MAIN`
- `READY_WITH_DOCUMENTED_NONBLOCKING_DEBT`
- `NOT_READY_RECONCILIATION_REQUIRED`
- `BLOCKED`

The report must separate verified facts, inferred equivalence, unverified claims, and intentionally deferred probes.
