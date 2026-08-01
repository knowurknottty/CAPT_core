# CAPT Core Runtime — Portability Contract

The skill is model/runtime-agnostic except at a bounded adapter surface.

## Layer separation

- **CAPT core semantics**: checkpoint, ContextPack, MemoryUseGate, ClaimGuard,
  continuity verdict. Defined by capt-solo; the skill only invokes them.
- **Runtime adapter semantics**: how the host (Hermes / Orinth / CLI) launches
  the `capt-*.sh` scripts and parses their JSON. Bounded to the adapter table.
- **Model-specific behavior**: which LLM produces the agent's reasoning. The
  skill does not assume any model; it consumes CAPT's structured output.
- **Harness-specific behavior**: the acceptance/adversarial/replay harnesses are
  test drivers, not part of the skill's runtime contract.

## Interpreter portability

The skill NEVER relies on an activated shell or ambient venv. Interpreter
selection is explicit and recorded (`capt-select-python.sh`):
`CAPT_ACCEPT_PY` → workspace venv → PATH python3 → PATH python → fail.

## Governance portability

`capt_execution_mode: GOVERNED` = CAPT gate authorized the boot.
`hermes_session_mode: BOOTSTRAP_DEGRADED` = host tool hooks are observational.
These are reported independently; the skill never conflates them.

## What must hold on any host

1. `capt` console script resolvable from the selected interpreter's bin dir.
2. `CAPT_SOLO_HOME` isolated from owner state.
3. JSON reports conform to `schemas/boot-report.schema.json`.
4. Fresh-process resume produces a different PID and session_id.
5. No transcript is inherited into the resume process.

## What is host-specific (adapter only)

- How the host invokes shell scripts (tool-exec vs subprocess).
- How the host supplies the model and endpoint.
- How the host surfaces observational hooks (never enforcement).
