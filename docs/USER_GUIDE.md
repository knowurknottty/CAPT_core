# CAPT User Guide

This guide uses public operator surfaces and describes merged operator workflows as of 2026-09-15; release and live-provider acceptance require separate evidence.

Prerequisite: complete [`START_HERE.md`](../START_HERE.md).

## Runtime lifecycle

```zsh
capt start
capt status
capt evidence
capt checkpoint --idempotency-key work-cp
capt stop
capt start
capt resume --idempotency-key work-resume
```

CAPT's EventStore and checkpoint/recovery path are responsible for continuity; a model transcript is not.

## Durable memory

```zsh
capt memory store "A durable project decision." --namespace project
capt memory search "project decision"
capt memory list
```

These commands use the standalone Solo MemoryEngine under `~/.capt-solo` (`CAPT_SOLO_HOME` overrides it), not RuntimeService memory under `CAPT_STATE_DIR`. A successful store does not establish runtime memory admission or inclusion in a model's ContextPack. Runtime Memory Governor/ContextPack state is a separate layer.

## TUI operator workflow

```zsh
capt start
capt tui
```

The merged TUI exposes runtime, mission, memory/context, provider/model, approvals, evidence, and logs. Governed approve/deny/checkpoint/resume/cancel actions route through the shared operator/runtime boundary.

For a noninteractive summary, use `capt-ui dashboard`; it does not launch the TUI.

### Merged cockpit and prompt review

PR #117 reconciled the formerly stacked cockpit/provider work into an integrated run surface with:

- provider/model choice;
- response modes `MAX`, `SPOCK`, `CAVE CAPT`, `MIN`;
- requested context budgets from 32K to 256K;
- prompt-enhancement choices `OFF`, `AUTO`, `OMNI`, `META`, `FORGE`, `SIGMA`;
- explicit human review/approval when required;
- requested/effective context and prompt-assembly provenance.

These controls are merged into `main`. Later work adds durable prompt proposals: review the original/proposed/edited selection before approval. The runtime compiler's AUTO routing recognizes actionable research requests subject to a four-word minimum and the operator-selected engine/mode; software and reconciliation signals select additional FORGE/SIGMA stages. This routing does not establish a Search/Deep Research product surface. A proposal is advisory until its exact revision and execution scope are approved.

Native/TUI authority controls expose filesystem scope, file mutation, shell access, and local/remote provider policy. Native Settings and Skills support governed configuration and managed-skill install/authoring/selection. These controls do not bypass runtime admission. Native answers and expandable execution receipts are displayed separately.

Model Council alpha is merged with durable state and Chamber projection; its analysis is not verification or a live-provider quality guarantee.

## Governed execution model

The conceptual path is:

```text
operator request
 -> mission/task
 -> policy / approval / capability / lease
 -> bounded driver dispatch
 -> untrusted observation/artifact candidate
 -> evidence admission
 -> verification
 -> ClaimGuard / completion decision
```

A driver returning successfully is not itself task completion.

## Provider execution boundary

Merged `main` supports bounded Ollama and local/authenticated OpenAI-compatible execution. PR #117 includes the provider-model coherence semantics from closed-unmerged PR #118; later operator controls bind effective configuration and reject stale revisions.

Its controlled HTTP tests validate protocol shape, provenance/digests, cancellation truthfulness, reconciliation, and secret exclusion. Live-provider exact-head installed-runtime acceptance remains a separate gate.

## Evidence inspection

```zsh
capt evidence
```

Runtime read projections also expose approvals, missions, tasks, and checkpoints. UPG-024 adds `capt-debt` for concrete cognitive-debt inspection; absence of reported debt does not prove correctness.

Use evidence to answer *what was observed?*, verification to answer *what did the evidence establish?*, and ClaimGuard/completion state to answer *what may CAPT truthfully claim?*

## Expert integration

Use `capt harness ...` and the runtime/integration guide only when you need explicit socket/token/ledger control or governed command operations. Normal users should not need those details for first success.
