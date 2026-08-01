# CAPT Bootstrap Bridge — Operator & Recovery Workflow

## What this is

A minimal launcher/operator surface that performs a **real runtime handoff** from
Hermes to the canonical CAPT Agent Runner. It does **not** reimplement memory,
ContextPack, MemoryUseGate, CTP, KHSB, checkpointing, or provider logic — all of
that stays inside CAPT. The bridge only proves those happened, via an
authenticated READY event.

## Boot states

| State | Meaning |
|-------|---------|
| `FULL_CAPT_AGENT_RUNNER_ACTIVE` | READY validated; provider owner = CAPT_AGENT_RUNNER |
| `CAPT_RUNNER_PARTIALLY_ACTIVE` | CAPT present but governed chain incomplete; provider blocked |
| `SKILL_LOADED_CAPT_RUNNER_NOT_ACTIVE` | skill loaded, no runner (the original defect) |
| `CAPT_UNAVAILABLE` | no resolvable CAPT source |

## Provider ownership (invariant: EXACTLY_ONE_PROVIDER_OWNER)

- `HERMES_BEFORE_BRIDGE` — bridge inert; Hermes owns the provider.
- `CAPT_AGENT_RUNNER_AFTER_READY` — validated READY; CAPT owns the provider.
- `NONE_WHEN_BLOCKED` — transfer failed; provider blocked, no silent fallback.

A transition back to Hermes-native execution requires explicit owner
authorization (`CAPT_BRIDGE_ALLOW_HERMES_FALLBACK=1`). It is never automatic.

## Commands

```bash
# Resolve + doctor + launch runner + validate READY (proves the handoff)
python capt_cli.py --json bridge boot --workspace . --mission <id> --timeout 90

# Runner-side: boot, emit READY, serve governed turns (used by the launcher)
python capt_cli.py bridge serve --workspace . --mission <id> --mode resume

# Report boot states and provider-owner values
python capt_cli.py --json bridge status
```

## Hermes integration

Register the plugin (`capt_solo/bridge/hermes_plugin.py`) with Hermes. It installs
an `llm_execution` middleware. Until a validated bridge boot occurs, the middleware
is **inert** and passes every provider call straight through to Hermes. After a
validated READY, it returns CAPT output and suppresses Hermes-native dispatch.

**Critical contract:** the middleware blocks by *returning* a synthetic response.
Hermes' `_run_execution_chain` treats a *raising* middleware as fail-open (it falls
through to the provider). Therefore the bridge never raises on the provider path.

## Failure modes (all fail closed)

- missing mission → `MISSION_REQUIRED`, provider blocked.
- incomplete CAPT source (no Agent Runner / import fails) → `CAPT_SOURCE_INCOMPLETE`.
- doctor gate fails → `CAPT_DOCTOR_FAILED`, runner not launched.
- runner dies / times out before READY → `RUNNER_DIED` / `RUNNER_STARTUP_TIMEOUT`.
- forged / tampered / unauthenticated READY → `READY_UNAUTHENTICATED` / `READY_MALFORMED`.
- MemoryUseGate not PASS → READY not emitted; provider blocked.

In every failure mode: **no provider call, no Hermes fallback** (unless explicitly
authorized), exact blocked state reported.

## Recovery

1. Read `bridge status` and the last `bridge boot --evidence-dir` result.
2. If `CAPT_SOURCE_INCOMPLETE`: point `CAPT_BRIDGE_SOURCE_ROOT` at a complete
   capt_solo tree (must contain `capt_solo/agent/` and import cleanly).
3. If `CAPT_DOCTOR_FAILED`: resolve the doctor report; the bridge will not launch
   the runner past a failed gate.
4. If `RUNNER_DIED`: inspect the runner stderr captured by `launch_runner`; the
   duplicate-runner lock (`.capt/bridge/runner-<mission>.lock`) is released on
   clean shutdown and reclaimed if stale.
5. Continuity: the durable CAPT session id is stored in a sidecar
   (`.capt/bridge/session-<mission>.sid`), outside the integrity-digested
   checkpoint body, so a fresh process resumes the same session.

## Ownership guard

During governed execution, writes outside the approved workspace / CAPT state roots
are denied by default, including `~/.hermes/skills/**`, global Hermes config, and
arbitrary home-directory writes. Denials emit `RUNTIME_OWNERSHIP_DENIAL` receipts.
Historical uncontrolled side effects are recorded as
`EXTERNAL_SKILL_MUTATION_UNREVIEWED` and **never auto-reverted**. Scope expansion
requires explicit authorization (`CAPT_BRIDGE_SCOPE_AUTHORIZED`).
