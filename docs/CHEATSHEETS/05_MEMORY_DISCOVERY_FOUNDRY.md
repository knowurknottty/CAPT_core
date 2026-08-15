# 05 — Memory, Discovery, Foundry, and Desktop Surfaces

## CAPT Solo memory CLI

Implementation roots: `capt_cli.py`, `capt_solo/api.py`, `capt_solo/memory/`, `capt_solo/lifecycle/`.

### Memory operations

```zsh
capt memory list [--namespace NS] [--json]
capt memory store 'text' [--namespace NS] [--tag TAG] [--provenance NAME]
capt memory inspect ID
capt memory search QUERY
capt memory candidates
capt memory conflicts
capt memory pending
capt memory promote ID --state STATE --evidence e1,e2 [--actor NAME] [--reason TEXT]
capt memory pin ID [--reason TEXT]
capt memory archive ID [--reason TEXT]
capt memory restore ID [--reason TEXT]
capt memory explain ID
```

Memory operations are CAPT Solo’s memory-engine surface. They are distinct from RuntimeService provider work and do not give a provider permission to access raw memory. `capt_runtime/context_pipeline.py` and `context_slice.py` create bounded context for governed drivers. Current caveat: `capt memory list --namespace NS` accepts the option but the current handler lists without applying that namespace filter.

### Sessions

```zsh
capt session list
capt session begin PROJECT_NAMESPACE [--objective TEXT]
capt session status ID
capt session checkpoint ID [--objective TEXT] [--progress TEXT] [--next-action TEXT]
capt session resume ID
capt session consolidate ID
capt session close ID [--outcome completed]
```

Session lifecycle is cognitive/workflow continuity, not a substitute for Core EventStore recovery or external DriverRun reconciliation.

### Procedures and prospective memory

```zsh
capt procedure list
capt procedure inspect ID
capt procedure runs ID
capt prospective list
capt prospective ready
capt prospective resolve ID
capt retrieval feedback
capt retrieval adaptation
capt retrieval reset [--namespace NS]
```

## Foundry

Implementation: `capt_solo/foundry/`.

| Command | Function |
|---|---|
| `foundry list-skills`, `skill ID`, `candidates` | inspect governed skill candidates |
| `validate ID`, `review ID`, `approve ID --reviewer NAME`, `publish ID [--ctp PATH]` | skill validation/review/promotion workflow |
| `list-caps`, `cap ID`, `verify-cap ID`, `prove-cap ID`, `govern-cap ID --approver NAME` | capability proof/governance workflow |
| `list-bubbles`, `bubble-validate ID`, `bubble-approve ID --approver NAME`, `bubble-install ID [--ctp PATH]` | knowledge-bubble workflow |
| `curate`, `audit` | curator/audit actions |

Foundry is proof-governed; it is not a provider-model selection mechanism. `validate`, `review`, `approve`, `publish`, capability proving/governing, and bubble approval/install are state-changing expert workflows; inspect their individual help and evidence state before invoking them in a production CAPT home.

## Discovery subsystem

Implementation: `capt_runtime/discovery/`.

Components:

| Module | Primary function |
|---|---|
| `models.py` | `ScanLimits`, `Candidate`, `RejectionRecord`, `GovernorDecision`, `DiscoveryResult` models |
| `scanner.py` | bounded local path scanning with root/path safety |
| `governor.py` | stopping and scope governance |
| `policy.py` | classification vocabulary and guess/terminal rules |
| `provenance.py` | run/observation provenance IDs and structures |
| `redaction.py` | text/JSON/path redaction |
| `__init__.py` | `run_discovery()` and `to_evidence()` |

Discovery findings are not automatically verified claims. They must enter the normal evidence/verification/ClaimGuard path where applicable.

## Runtime memory/context subsystem

Implementation: `capt_runtime/memory/`, `capt_runtime/context_pipeline.py`, `capt_runtime/context_slice.py`.

- `MemoryTriggerEngine`: trigger enforcement and memory use gates.
- `MemoryGovernor`: policy-level memory governance.
- Context pipeline stages: select knowledge bubbles, select records, reduce context, build ContextSlice, package ContextPack.
- ContextSlice deliberately forbids governance/policy/ledger/claim/aggregate references.
- TaskResolver returns authoritative task objective for driver execution.

A driver gets the authorized slice, not unrestricted CAPT memory state.

## Desktop/runtime service surfaces

| File | Function |
|---|---|
| `desktop/capt_runtime_service.py` | AF_UNIX authenticated RuntimeService server, query service, lifecycle orchestration, startup reconciliation, provider/Hermes runner closure |
| `desktop/m1_command_service.py` | command-envelope admission, receipt classification, allowed command relay |
| `desktop/desktop_runtime_client.py` | authenticated socket client plus safe projections for mission/task/driver/evidence/ClaimGuard |
| `desktop/desktop_app.py` | desktop/headless rendering and sanitization helpers |
| `capt_ui/operator/runtime.py` | UI `Operator` thin client facade |
| `capt_ui/surfaces/tui/app.py` | Textual cockpit rendering/interactions |

The socket server uses a token file. Do not expose or copy the token; it authenticates the local command connection.

## Learning and simulation

`capt_runtime/learning.py` contains trajectory/reward/strategy/candidate/promotion helpers and explicitly rejects live training through `assert_no_live_training()`. `capt_runtime/simulation.py` marks simulated environments and rejects treating simulation output as production authority. These are not live model fine-tuning or a permit for external provider actions.

## Package/extension surfaces

- `pyproject.toml` exposes `capt` → `capt_cli:main` and `capt-ui` → `capt_ui.operator.cli:main`.
- Textual is an installed package dependency for `capt tui`.
- `capt_solo.plugin` exposes a Hermes plugin entry point; plugin registration does not replace the governed RuntimeService/provider ExecutionDriver path.
- `contracts/schema/*.json` are the canonical frozen contract source; generated Python bindings live under `contracts/generated/python`.
