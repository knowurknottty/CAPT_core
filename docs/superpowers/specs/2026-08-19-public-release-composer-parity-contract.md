# CAPT Public Release Composer Parity Contract

Status: `NORMATIVE_COMPANION_TO_PUBLIC_RELEASE_DESIGN`

Parent design:
`docs/superpowers/specs/2026-08-19-public-release-quarantine-projects-council-design.md`

Base SHA: `5ec276e891cf9fbfff2ce619a742f4b0f210c1ee`
Date: 2026-08-19

## Purpose

This companion removes ambiguity from the phrase **"all of these options"** in the approved prompt-box reference.

The public CAPT composer must expose equivalents for every meaningful capability shown in the reference while preserving CAPT authority and privacy boundaries.

## Required composer inventory

```text
Search
Deep Research
Cohort Council
Attach Files
Folders / Repo Workspace
Active Apps
Screenshots
Clipboard History
Project / Shared Context
Model Selector
Voice Input
```

These are product capabilities, not necessarily one flat menu. The visual grouping may evolve, but every capability above must remain directly discoverable from the composer or its immediate capability menu.

## Search

`Search` is the lightweight retrieval mode.

It differs from Deep Research:

```text
Search
  -> bounded query/retrieval
  -> concise sourced response

Deep Research
  -> decomposition
  -> multi-source retrieval
  -> claims/evidence graph
  -> adversarial checking
  -> synthesis
```

Search must preserve source provenance but should have a substantially smaller default wall-clock/retrieval budget than Deep Research.

## Deep Research

Deep Research is governed by the parent design's workload/resource profile and research pipeline.

It is never implemented as merely adding the words "research deeply" to the prompt.

## Cohort Council

The Council control opens the Council builder.

Hard limits remain:

```text
MAX_DISTINCT_COHORTS = 10
MAX_LOGICAL_VESSELS  = 111
```

The composer may show a compact summary chip such as `Council · 4 cohorts · 12 vessels` before dispatch.

## Attach Files

Every selected regular file enters Secure Intake / Quarantine before it can become context-eligible.

There is no picker-to-model bypass.

## Folders / Repo Workspace

Folder/repository selection uses Workspace semantics, not upload semantics.

The UI should support:

```text
Choose Folder…
Choose Git Repository…
Recent Workspaces…
```

Read/write capability must be explicit; selecting a workspace does not imply write permission.

## Active Apps

The UI shows an explicit app/window selector.

No ambient access to every running application is implied.

## Screenshots

The UI should support explicit capture/selection of:

```text
Screen
Window
Region
Recent Screenshot
```

Persisted screenshot files inherit Secure Intake metadata/provenance handling.

## Clipboard History

The user explicitly selects a clipboard item.

CAPT does not silently ingest clipboard history into context.

Sensitive-item retention controls are required before persistent clipboard history is enabled by default.

## Project / Shared Context

The folder-style `Shared` concept in the reference maps to CAPT's current Project/context container.

The composer should provide immediate visibility of the current Project and a way to switch or clear it.

Suggested compact UI:

```text
[folder icon] Project Name ▾
```

The Project determines eligible instructions/files/skills/links/workspace defaults; RuntimeService still determines actual governed context.

## Model Selector

The selected model/provider remains directly visible from the composer.

For local providers, readiness state should remain visible where practical (`COLD`, `WARMING`, `WARM`, failure).

The model selector and Council selector are separate:

- model selector = single primary Cohort/model path;
- Council = multi-Cohort/multi-Vessel execution plan.

## Voice Input

The composer retains a microphone/voice-input control when the platform supports it.

Voice capture is an input modality only. Transcribed text must pass through the same visible draft/edit/approval path as typed text before consequential dispatch.

No voice recording is persisted beyond configured retention without an explicit product policy/user action.

## Capability chips

Selections that materially change execution should render as removable chips before Send, for example:

```text
[Search]
[Deep Research]
[Workspace: CAPT_core]
[2 files]
[Safari window]
[Council: 4C/12V]
[Project: Release Sprint]
```

A user should be able to inspect and remove these before submitting the prompt.

## Mutual-exclusion / precedence rules

- Search and Deep Research are mutually exclusive execution modes; Deep Research subsumes ordinary Search retrieval.
- Single-model mode and Council mode are distinct; when Council is enabled, the primary model selector may identify the default/synthesis Cohort but cannot silently collapse Council to one model.
- Project context and explicit composer context combine through ContextPack selection; neither bypasses budget/governance.
- Attach Files may be selected while scanning, but Send must not treat the file as context-eligible until disposition allows it.

## Public UX requirement

The composer must remain understandable without CAPT vocabulary knowledge.

Tooltips/secondary labels may explain `Cohort` and `Vessel`, but the normal user should be able to choose capabilities without understanding the runtime architecture.

## Acceptance checklist

- Search is present and distinct from Deep Research.
- Deep Research is present.
- Council is present and opens configurable Cohorts/Vessels.
- Attach Files routes through quarantine.
- Folder/Repo Workspace is present.
- Active Apps is present.
- Screenshots is present.
- Clipboard History is present.
- current Project/Shared context is visible/selectable.
- model selector is visible/selectable.
- voice input is present when platform support is enabled.
- active capability chips can be removed before dispatch.
- no capability selection manufactures RuntimeService authority.
