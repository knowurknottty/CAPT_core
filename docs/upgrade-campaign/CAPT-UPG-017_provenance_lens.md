# CAPT-UPG-017 — Deterministic Provenance DAG / Provenance Lens

- **Campaign ID:** `CAPT-UPG-017`
- **Issue:** #84
- **PR:** #85
- **Base:** verified CAPT-UPG-016 @ `f7a6c6d22feb08a914e931611976ab0b766f1557`
- **Parallel precursor preserved:** `archive/upg017-pre-repair-parallel` @ `6826d145f44df1cb1402a9c9f34b345d007198c5`
- **Disposition before exact-commit gate:** `IMPLEMENTED_PENDING_EXACT_COMMIT_VERIFICATION`

## Authority boundary

The Provenance DAG and every Lens surface are **read-only projection data**. They do not mutate RuntimeService/EventStore, verify claims, accept claims, grant/revoke capability authority, replay history, or infer missing relationships.

Graph rules:

- only explicit identifiers/relationships from authoritative aggregates, runtime read models, or recorded event payloads become edges;
- missing relationships remain absent/unknown;
- verification and ClaimGuard/claim decisions remain distinct nodes;
- node identity is deterministic (`kind:identity`);
- placeholder nodes may be enriched by later explicit authoritative detail;
- contradictory non-empty data for the same node identity fails visibly with `PROVENANCE_NODE_CONFLICT` rather than last-write-wins;
- cycles fail as provenance-integrity errors;
- graph digest and topological order are deterministic.

## Current governed graph coverage

### Mission / task / approval

- mission -> task: `contains_task`;
- task -> approval request: `requires_approval`;
- explicit prompt-assembly digest -> approval: `approval_binds_prompt`;
- recorded approval request -> recorded operator decision: `resolved_by`.

The approval request and the operator decision are separate nodes.

### Capability authority

- policy-decision reference -> grant: `authorizes_grant`;
- capability grant -> embedded lease: `activates_lease`;
- mission/task -> lease: explicit scope relations when mission/task IDs exist.

Lease/grant nodes are projection-only; the graph cannot issue or revoke them.

### Execution / claims / evidence / verification

- task -> DriverRun;
- task/mission -> claim;
- evidence -> claim;
- evidence -> verification;
- verification -> claim;
- claim -> recorded ClaimGuard/claim-decision projection.

The builder accepts the real current VerificationResult shape where `supportingEvidenceIds` live inside `status`, while retaining compatibility with older explicit top-level read shapes.

### Artifact promotion

The graph keeps verification/claim support separate from filesystem adoption authority:

- claim -> artifact promotion: `governs_promotion`;
- evidence -> artifact promotion: `binds_promotion_evidence`;
- verification -> artifact promotion: `binds_promotion_verification`.

### Cohort

UPG-017 intentionally shows a bounded Cohort summary only; UPG-018 owns the Deliberation Chamber.

- mission/task -> Cohort;
- recorded Cohort evidence -> Cohort;
- explicit latest human steer actor -> Cohort.

No model identity, confidence, or hidden deliberation relation is invented.

### Historical replay fork

UPG-016 integration is explicit:

- `replay_source:<globalSequence>:<sourceChainDigest>` records the historical source identity;
- replay source -> ReplayFork: `forked_from`;
- ReplayFork -> new Mission: `creates_mission`.

The node also exposes source event/state/chain identity from the authoritative ReplayFork record. This is provenance only and never reactivates historical authority.

## Authoritative read-model expansion

`project_authoritative_state()` now exposes current aggregate families needed by operator provenance surfaces:

- capabilities;
- artifact promotions;
- Cohorts;
- replay forks;

in addition to missions, tasks, approvals, DriverRuns, claims, events, and claim-scoped verification results.

## Desktop Lens

`desktop.provenance_lens` provides both automation and a real desktop view:

- `--headless`: deterministic JSON graph for testing/support/automation;
- deterministic layered left-to-right DAG layout;
- scrollable Tk/Aqua canvas with node boxes, directed edges, and relation labels;
- exact node table + selected-node incoming/outgoing detail inspector;
- graph authority/digest visible in details;
- header explicitly states projection-only / explicit-links-only semantics.

`pyproject.toml` exposes:

```text
capt-provenance = desktop.provenance_lens:main
```

and preserves the current lease-aware `capt-tui` entrypoint from UPG-015.

## TDD / source acceptance observed before commit

Focused graph/read-model/layout tests:

```text
9 passed
```

Authenticated source runtime -> headless Lens:

```text
live_headless=PASS
nodes=9
edges=9
```

Authenticated governed ReplayFork -> headless Lens:

```text
live_replay_lens=PASS
sourceSequence=13
nodes=12
edges=11
replay_source -> replay_fork -> new mission present
```

## Installed-wheel / desktop acceptance observed before commit

A wheel built from this working tree installed into isolated Python environments.

Headless/package checks:

```text
installed_imports=PASS
capt-provenance --help: PASS
installed_headless=PASS
```

Desktop toolchain qualification:

- Homebrew Python 3.14 on this host lacks `_tkinter`; that environment cannot launch Tk and is not counted as a CAPT GUI failure.
- The CAPT Python 3.12 base toolchain imports Tk successfully.
- A clean Python 3.12 venv installed from the wheel reports `installed312_tk_and_lens_import=PASS`.
- Installed `capt-provenance` Tk launch remained alive after 2 seconds against an authenticated runtime: `installed_tk_launch_smoke=PASS`.

This is a launch smoke, not a claim of exhaustive visual QA.

## Exact-head verification requirement

After the implementation/evidence commit is created, rerun:

```bash
python contracts/tools/check_drift.py
python -m pytest -q \
  tests/test_provenance_dag.py \
  tests/test_provenance_runtime_projection.py \
  tests/test_provenance_lens_layout.py
python -m pytest -q
```

Then rebuild/install the wheel from that immutable commit and repeat installed import/help/headless acceptance before changing this item to owner-review-ready.
