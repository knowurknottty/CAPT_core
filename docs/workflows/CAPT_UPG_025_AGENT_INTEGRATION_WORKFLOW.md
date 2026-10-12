# CAPT-UPG-025 Agent Integration Workflow

**Status:** proposed operating procedure
**Applies to:** every automated agent working on items in `docs/upgrade-campaign/capt_upg_025_backlog.json`
**Program rationale:** `docs/upgrade-campaign/CAPT-UPG-025-068_SAME_UID_HARDENING_AND_EVOLUTION.md`
**Precedence:** `AGENTS.md` > this workflow > item text. If they conflict, stop and escalate to the operator.

---

## 1. Roles

Each item passes through four separate roles. **One agent may hold at most one role per item.** The queue tool enforces the most important split: a claimant can never mark its own item `merged`.

| Role | Responsibility | Suggested binding (map to your current roster) |
|---|---|---|
| **Implementer** | Claim, reproduce red, implement, produce green evidence, open the PR | VESPER (Claude Code) |
| **Adversary** | Try to break the change: bypasses, regressions, weakened tests, overclaims. Never edits the PR branch; findings go back as review comments | AXIOM (anti-confabulation lane), or a different model family from the implementer |
| **Verifier** | Fresh session with no implementation context: re-run every `verification` command from a clean clone at the PR head SHA, check each acceptance criterion literally, record receipts | A new session of any agent that did not touch the item |
| **Operator** | Owns ADRs, key custody, migrations and merges; resolves escalations | Kirk (human). Not delegable for items flagged `needs_adr` or `risk: high` |

Items with `owner_role: verifier` (052, 053) or `adversary` (060) put that role in the implementer seat. The other three roles still apply.

## 2. Workspace safety (non-negotiable)

This campaign exists because model processes running as the operator can reach CAPT authority. Agents doing the work must not repeat that.

1. Work in a **disposable clone or git worktree**, never in a checkout attached to the live runtime.
2. Export a throwaway state directory before running anything:
   ```sh
   export HOME="$(mktemp -d)"   # isolates ~/.capt, ~/.capt-solo, ~/.hermes
   export CAPT_STATE_KEY_B64="$(python3 -c 'import os,base64;print(base64.b64encode(os.urandom(32)).decode())')"
   ```
   On macOS this keeps the code path on the env key and away from the operator's keychain item.
3. Never read, copy, or connect with `~/.capt/runtime.token`, `runtime.sock`, `runtime.db`, `keys/`, or the `capt-runtime-state` keychain item of the operator account.
4. No credentials in prompts, logs, PR bodies, or evidence files (AGENTS.md). Use fixtures.
5. Network: package registries and GitHub only. Provider calls go to local fixtures.

If a task appears to require the live runtime, it is an operator task. Set the item to `blocked` with reason `ENV_REQUIRES_OPERATOR`.

## 3. Coordination: the queue

The backlog JSON is the shared work ledger. Mutate it **only** through the tool:

```sh
python3 scripts/upg_queue.py validate                        # schema, deps, cycles, paths
python3 scripts/upg_queue.py ready [--role implementer]      # frontier, conflict-aware, P0 first
python3 scripts/upg_queue.py show CAPT-UPG-028
python3 scripts/upg_queue.py claim CAPT-UPG-028 --agent vesper
python3 scripts/upg_queue.py set CAPT-UPG-028 red --agent vesper --note "repro test committed"
python3 scripts/upg_queue.py set CAPT-UPG-028 green --agent vesper --evidence "<log digest or CI URL>"
python3 scripts/upg_queue.py set CAPT-UPG-028 in_review --agent vesper --evidence "PR #<n>"
python3 scripts/upg_queue.py set CAPT-UPG-028 merged --agent kirk --evidence "merge <sha>"
python3 scripts/upg_queue.py status | graph
```

**Where the ledger lives.** Keep the authoritative copy on a long-lived branch, `campaign/upg-025`. Each status change is one commit there, with the message `upg-queue: <ID> <from>-><to> (<agent>)`.

**Races between agents on different machines:**
1. `git fetch && git rebase origin/campaign/upg-025`
2. Run `claim`
3. `git push` without force
4. If the push is rejected, another agent won. Fetch, re-run `ready`, pick again.

Pass `--expect-status` whenever you act on a status you observed earlier. A stale view then fails instead of overwriting.

**Avoiding file conflicts.** `ready` sorts items whose footprint overlaps in-flight work to the bottom, and `claim` refuses them. This prevents two agents editing `store.py` or `services.py` at once. Do not work around it by trimming an item's `files` list. If an item's real footprint differs from the backlog, fix the backlog in its own commit, reviewed by the operator.

### Legal transitions

```
open ──claim──▶ claimed ──▶ red ──▶ green ──▶ in_review ──▶ merged
  │                │          │       ▲           │
  ├▶ deferred      ├▶ open    ├▶ blocked  └── changes_requested ◀┘
  └▶ rejected      └▶ blocked     (red/green/blocked)
green ▶ red (regression found before review)
blocked ▶ open | claimed      deferred ▶ open      merged / rejected: terminal
```

- `green`, `in_review` and `merged` require `--evidence`.
- Only the claimant may move an item to `in_review`.
- The claimant may never move its own item to `merged`.

## 4. Per-item gates

Each gate produces an artifact. If an artifact is missing, the gate is not passed.

### G0 — Pre-flight (Implementer)

- Run `validate`, then `ready`, then `claim`.
- Read the item in full, including `summary`, `evidence`, `acceptance` and `verification`.
- Check for **baseline drift**: `git log 80d3b82..origin/main -- <item files>`. If the code changed since the review, re-confirm the defect before anything else. If it is gone, set `blocked` with reason `BASELINE_DRIFT` and escalate. Do not "fix" code that is already fixed.
- If `needs_adr: true`, stop here. Draft the ADR under `docs/architecture/decisions/` (options, decision, consequences, rollback), open it as its own PR, and leave the item `claimed` until the operator merges the ADR.

**Artifact:** the claim commit; an ADR PR if one is needed.

### G1 — Red (Implementer)

- For `V`, `V-code` and `R` items, write the failing test first, encoding the defect exactly as the `evidence` field describes. Commit it alone, with the message `test(upg-NNN): reproduce <defect>`.
- Record the failing output.
- For `P` items, write the acceptance tests first. They must fail because the feature is absent.
- An `R` item whose defect cannot be reproduced is set to `blocked` with reason `NOT_REPRODUCED`. Attach what was tried and escalate; it may become `rejected`.

**Artifact:** a red test commit, then `set ... red --note "<test id>, <failure line>"`.

### G2 — Implement (Implementer)

- Make the smallest change that satisfies the acceptance criteria. No drive-by refactors: they inflate the footprint and the review.
- Must hold:
  - No test is deleted, skipped or loosened to get green (AGENTS.md).
  - Schema changes go through `contracts/` plus the generators, and the drift checks pass.
  - Ledger and storage changes come with a migration, a MIGRATIONS.md entry, and a test that upgrades a ledger created at the baseline SHA.
  - Historical evidence files are not edited.
  - Typed code with explicit error paths. Every new failure mode has a stable error code.

### G3 — Green (Implementer)

Run all of these from a clean worktree:

```sh
python -m pytest -q                                   # full suite, not just the item
ruff check capt_runtime capt_solo capt_ui desktop capt_cli.py scripts
python3 scripts/upg_queue.py validate
# plus every command in the item's "verification" list
# Swift items additionally:
swift test --package-path capt_ui/surfaces/desktop_swift
```

- Compare the result against the baseline: 2039 passed / 1 known host-dependent failure, which UPG-038 removes.
- Any new failure blocks green, even one that looks unrelated. Diagnose it, or set `blocked` with reason `TEST_REGRESSION`.

**Artifact:** test log, with its sha256 digest, attached via `set ... green --evidence`.

### G4 — Pull request (Implementer)

- Branch: `upg/NNN-<slug>`. Base: `main`.
- **One item per PR.**
- Every commit message ends with the trailer `CAPT-UPG: NNN`.
- PR body template:

```markdown
## CAPT-UPG-NNN — <title>
Provenance: V | V-code | R | P     Tier: P0..P3     Risk: low|medium|high

### Defect / intent
<one paragraph, from the item summary, updated if drift was found>

### Red evidence
<test id + failing assertion, commit sha>

### Green evidence
<full-suite summary line, verification command outputs, log digest>

### Acceptance checklist
- [ ] <each acceptance line, verbatim, with a pointer to the test or file proving it>

### Proof ladder reached
source present → tested → (integrated?) → (installed?)   ← state exactly how far, nothing more

### Residual risk / follow-ups
<what this does NOT close; new backlog items proposed, not silently added>
```

Then: `set ... in_review --evidence "PR #<n>"`.

### G5 — Adversarial review (Adversary)

The adversary checks out the PR head in its own disposable workspace and tries to break the change:

1. **Bypass:** can the original defect still be reached by another path? For example, a second `urlopen`, a second `self._conn` access, a different plugin tool or CLI flag.
2. **Regression:** run the Hostile Vessel suite once it exists (060). Before then, re-run the item's original reproduction script, then one variant you design yourself.
3. **Test integrity:** diff every test file. Flag removed assertions, widened tolerances, new `skip` or `xfail`, and mocked-away boundaries.
4. **Overclaim:** compare the PR body and any doc changes against the proof ladder. Flag any "verified", "secure" or "complete" wording not backed by a receipt.
5. **Failure modes:** for every new error path, ask what the operator sees, what is logged (secret-free?), and whether the system fails closed.

The outcome is either `approve` or `changes_requested`, posted as a review with findings that each carry a concrete reproduction. To request changes: `set ... changes_requested --agent axiom --note "<summary>"`.

A finding without a reproduction is labelled `concern`, not `blocking`.

### G6 — Independent verification (Verifier)

- Start a fresh session with no access to the implementer's or adversary's conversation history.
- Clone at the PR head SHA, apply the workspace-safety exports, and run every `verification` command plus the full suite.
- Tick each acceptance criterion only when it is evidenced. "Looks right" does not count.
- Post a verification receipt comment:

```text
VERIFIER RECEIPT  CAPT-UPG-NNN  head=<sha>
suite: <passed/failed/skipped>   log sha256: <digest>
acceptance: <n>/<n> evidenced   unevidenced: <list or none>
verdict: PASS | FAIL
```

### G7 — Merge (Operator)

- Merge only with: adversary `approve`, verifier `PASS`, CI green on the exact head SHA, and an operator-approved ADR when `needs_adr`.
- Squash-merge so that `CAPT-UPG: NNN` stays in the final message.
- Then run `set ... merged --agent kirk --evidence "merge <sha>"` on the campaign branch.

### G8 — Post-merge propagation (Implementer, next session)

- Update `docs/CAPT_HARDENING_BACKLOG.md` or `FUNCTIONALITY_MATRIX.md` **only** with present-tense claims about the merged SHA. Never rewrite earlier entries.
- If the item closes a Hostile Vessel class, remove its `xfail` in the same PR or the next one. Strict xfail will force this anyway.
- Run `ready` again. New items may now be unblocked.

## 5. Failure propagation (AFP classes)

When an agent cannot continue, it sets `blocked` with exactly one reason code, a note, and the evidence it has. **It never improvises around the obstacle.**

| Code | Meaning | Required action |
|---|---|---|
| `BLOCKED_DEP` | A dependency's real state contradicts the backlog | Escalate. Do not claim the dependency yourself without releasing this item |
| `BASELINE_DRIFT` | Code changed since review; the defect may be gone or moved | Re-confirm. Propose an edit to the backlog item |
| `NOT_REPRODUCED` | An `R` or `V-code` item does not reproduce | Attach attempts. Operator decides on `rejected` |
| `ACCEPTANCE_UNSATISFIABLE` | Criteria conflict, or need a product decision | Escalate with options. Do not reinterpret the criteria |
| `SCOPE_DRIFT` | The fix needs files outside the declared footprint | Stop. Propose a footprint change or a new item |
| `TEST_REGRESSION` | An unrelated test fails after the change | Diagnose. Never skip it |
| `ENV_UNAVAILABLE` | Toolchain missing (Swift, macOS-only API, Docker) | Hand off to an agent with the right environment |
| `ENV_REQUIRES_OPERATOR` | Needs the live runtime, keychain, or real credentials | Operator task |
| `ADR_PENDING` | Waiting on operator ADR approval | Wait. Do not start G1 |

**Escalation channel:** a note on the item, plus a comment on the PR or ADR. If the operator surface supports it (Kanban R2 once it lands), mirror the blocked card there.

## 6. Hard stop conditions (operator must decide)

Any agent stops and escalates before:

- Changing key custody, at-rest encryption, or anything in `state_security.py` (029, 046).
- Any ledger or schema migration (033, 045, 046, 050, 061).
- Changing what counts as human authority (026, 041, 043).
- Moving or editing anything under `release_evidence/` or the dated root-level evidence files (055 requires `git mv` only, with history preserved).
- Adding a new runtime dependency to `pyproject.toml` (test extras are allowed).
- Any change that would make a currently passing security or release gate optional.

## 7. Kickoff prompts

Paste into the agent's session, with the placeholders filled in.

### Implementer

```text
You are the IMPLEMENTER for CAPT-UPG-<NNN> in knowurknottty/CAPT_core.
Follow docs/workflows/CAPT_UPG_025_AGENT_INTEGRATION_WORKFLOW.md exactly, and AGENTS.md above it.
1. Apply the workspace-safety exports (§2). Never touch the operator's live ~/.capt.
2. G0: validate, confirm the item is in `ready`, claim it as --agent <name>, check baseline drift since 80d3b82.
   If needs_adr is true, draft the ADR PR and stop.
3. G1: commit a failing test that reproduces the item's evidence. Record red.
4. G2/G3: smallest change meeting every acceptance line. Full suite + ruff + the item's verification commands. Record green with a log digest.
5. G4: open one PR using the template. State the proof-ladder level exactly; claim nothing beyond it.
If anything in §5 or §6 applies, set blocked with the code and stop. Do not improvise.
Report: PR URL, red/green evidence, residual risk.
```

### Adversary

```text
You are the ADVERSARY reviewing PR #<n> (CAPT-UPG-<NNN>) in knowurknottty/CAPT_core.
You did not write this change. Your job is to break it, not to improve its style.
Work in a disposable clone at the PR head with the workspace-safety exports.
Check, with a reproduction for each finding: (1) bypass paths for the original defect,
(2) the original repro plus one new variant of your design, (3) test-integrity diff
(removed assertions, new skips/xfails, mocked boundaries), (4) overclaims against the proof ladder,
(5) failure-mode behaviour (fail closed? secret-free logs? operator-visible?).
Post a review: approve, or changes_requested with blocking findings (reproduced) and concerns (unreproduced).
Never push to the PR branch.
```

### Verifier

```text
You are the VERIFIER for PR #<n> (CAPT-UPG-<NNN>). Ignore all prior discussion; use only the repository at head <sha>
and the backlog item text. Fresh clone, workspace-safety exports, then run every command in the item's
"verification" list and the full test suite. For each acceptance line, cite the file/test that evidences it;
anything without evidence is unevidenced. Post the VERIFIER RECEIPT block (§4 G6). Verdict PASS only if every
acceptance line is evidenced and the suite matches baseline (no new failures).
```

### Operator checklist (human)

```text
[ ] ADR merged (if needs_adr)      [ ] adversary approve
[ ] verifier PASS on exact head    [ ] CI green on exact head
[ ] proof-ladder claim in PR is honest   [ ] no historical evidence edited
→ squash-merge, then: upg_queue.py set <ID> merged --agent kirk --evidence "merge <sha>"
```

## 8. Throughput and health signals

Track these from the backlog `history` arrays, which the queue writes automatically:

| Signal | Healthy | Investigate when |
|---|---|---|
| claim → green (P0) | ≤ 1 working day | > 3 days: the item is mis-scoped; split it |
| changes_requested rate | 20–50% | ~0%: the adversary is rubber-stamping. > 70%: implementer prompts need work |
| `NOT_REPRODUCED` on V-code | rare | frequent: baseline drift or review error; re-baseline the backlog |
| Hostile Vessel strict-xfail count | monotonically ↓ | ↑: a new escape class was found. Good news; add an item |
| Items blocked > 48h | 0 | operator queue is the bottleneck |

## 9. Suggested first session

Wave 0 has five independent items with disjoint footprints, which is safe to run in parallel:

```text
VESPER-a : CAPT-UPG-028  (store.py lock discipline)
VESPER-b : CAPT-UPG-027  (HTTP opener + CI gate)
VESPER-c : CAPT-UPG-030  (process-group reaping)
VESPER-d : CAPT-UPG-025 then 026 (foundry + plugin; 026 shares plugin files with 037)
Operator : CAPT-UPG-040  (threat-model ADR, which unblocks 10 items)
AXIOM    : adversary on each PR as it reaches in_review
```

Hold 029 (key custody) until its ADR is approved. It is the one Wave-0 item where a wrong fix can make existing ledgers permanently unreadable.
