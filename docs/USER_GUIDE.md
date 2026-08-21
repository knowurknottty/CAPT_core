# CAPT User Guide

This guide uses public operator surfaces and separates merged workflows from active integration work.

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

Persistent memory and the Runtime Memory Governor/ContextPack are separate layers: durable storage is not the same thing as the bounded context sent to a model.

## TUI operator workflow

```zsh
capt start
capt-ui dashboard
```

The merged TUI exposes runtime, mission, memory/context, provider/model, approvals, evidence, and logs. Governed approve/deny/checkpoint/resume/cancel actions route through the shared operator/runtime boundary.

### Terminal convergence cockpit

PR #117 reconciles the formerly stacked cockpit/provider work into an integrated run surface with:

- provider/model choice;
- response modes `MAX`, `SPOCK`, `CAVE CAPT`, `MIN`;
- requested context budgets from 32K to 256K;
- prompt-enhancement choices `OFF`, `AUTO`, `OMNI`, `META`, `FORGE`, `SIGMA`;
- explicit human review/approval when required;
- requested/effective context and prompt-assembly provenance.

The convergence candidate has terminal source/integration acceptance, but it remains distinct from protected `main` and release authorization until the Security Closure Cockpit gate is satisfied.

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

Protected `main` supports provider registration/health/model-list foundations. Terminal PR #117 integrates bounded Ollama and local/authenticated OpenAI-compatible execution; PR #118 fixes coherent global/session provider-model selection on that line.

Its controlled HTTP tests validate protocol shape, provenance/digests, cancellation truthfulness, reconciliation, and secret exclusion. Live-provider exact-head installed-runtime acceptance remains a separate gate.

## Evidence inspection

```zsh
capt evidence
```

Use evidence to answer *what was observed?*, verification to answer *what did the evidence establish?*, and ClaimGuard/completion state to answer *what may CAPT truthfully claim?*

## Expert integration

Use `capt harness ...` and the runtime/integration guide only when you need explicit socket/token/ledger control or governed command operations. Normal users should not need those details for first success.