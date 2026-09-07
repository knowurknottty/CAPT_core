# CAPT macOS GUI Control Center Design

## Goal
Turn the regular CAPT macOS app into a truthful operator control center: governed Prompt Intelligence, usable Skills, real Settings-backed execution authority, hierarchical Missions, and a later Inversion Labs visual-language pass.

## Authority invariant
SwiftUI preferences are never authority. The UI may express operator intent only. RuntimeService validates that intent, freezes it into HumanApproval/execution binding, and dispatch revalidates the frozen authority before any provider or ToolBroker boundary is crossed.

## Skills
- Keep the verified managed skill pack as source of truth.
- Expose metadata only to the GUI; skill bodies remain runtime-owned.
- Modes: `auto`, `manual`, `off`.
- Manual mode freezes explicit skill names + pack root into approval; auto mode delegates contextual selection to the runtime; off explicitly disables managed skills.
- Skills surface supports search, selection, pack integrity/provenance, refresh, and later import/create actions using real managed-skill APIs only.

## Settings authority profile
Persist one operator profile with these independent controls:
- Filesystem scope: `project`, `custom`, or `full` plus canonical root.
- File mutation: separate boolean, default false.
- Shell execution: separate boolean, default false.
- Provider network: `local_only` or `remote_allowed`.
- Remote Prompt Intelligence compilation: separate boolean, default false.

`project` uses the chat/project root. `custom` requires a configured existing directory. `full` resolves to `/` and must be visually high-risk. Settings changes invalidate any local proposal/approval cursor whose execution binding was created under a different profile.

## Execution binding
Add a normalized `ModelAuthorityProfile` on the runtime side. Approval creation:
1. validates filesystem root and provider endpoint against the profile;
2. derives permitted tool operations;
3. includes the normalized profile in the approval binding and prompt digest;
4. creates one-use HumanApproval with risk derived from the requested authority.

Preparation/dispatch re-derives and compares the same profile. No widening after approval is permitted.

## Tool execution
ProviderDriver gains a bounded OpenAI-compatible tool loop when approved authority exposes tools. Tool calls are translated into canonical CAPT `ToolRequest` objects and executed only through ToolBroker. File reads/searches are pure-read operations; file writes/patches and shell execution require consequential capability leases and retain ToolBroker settlement/world-receipt behavior. No direct `subprocess`, `Path.write_*`, or ad-hoc filesystem execution is allowed from the provider loop.

For Ollama, use `/api/chat` when tools are enabled; for other OpenAI-compatible providers use `/chat/completions`. If a selected model/provider does not return valid tool-call structure, surface an execution failure rather than silently granting an alternate path.

Provider-network authority controls whether a remote provider endpoint may be used. It does not pretend to be arbitrary HTTP/web-fetch authority; generic web egress remains a separate future tool family.

## Missions
Default view shows multi-task/mission-grade work, expandable into every task and DriverRun. Historical one-turn activity remains available in `All activity`; it is not deleted or reclassified in the ledger.

## Visual pass
Only after functional gates are green: apply an Inversion Labs visual system across Chat, Missions, Skills, Settings, sidebar, cards, typography, spacing, motion, and density. Preserve macOS desktop conventions, semantic colors/materials, keyboard access, and readable information hierarchy.

## Verification gates
- Python tests for skill query, authority normalization, approval binding, provider-network denial, ToolBroker-only tool execution, scope escape rejection, and file-write/shell authority denial.
- Swift tests for skill decoding/selection intent, settings profile serialization/validation, approval payload propagation, mission task hierarchy, and navigation contracts.
- Full Python targeted runtime suite and Swift package suite green.
- Live smoke test against a disposable directory: read succeeds within scope; escape fails; write fails when mutation off and succeeds when on; shell fails when off and succeeds when on; remote provider fails under `local_only` before network dispatch.
- Do not replace the user's installed CAPT.app until all gates above are green.
