# milestone-language.md

Exact vocabulary. Use these tokens verbatim; do not invent variants, do not
soften, do not upgrade.

## 1. Execution modes

| mode | meaning |
|---|---|
| `GOVERNED` | every mandatory control executed and passed; boot returned GOVERNED with `gate_result: PASS` |
| `BOOTSTRAP_DEGRADED` | some controls operational, others prompt-enforced or absent; **requires** the durable marker `BOOTSTRAP_DEGRADED_AUTHORIZED` in checkpoint state when CAPT assigns it |
| `BLOCKED` | a mandatory control failed; no consequential work, no provider invocation |

Two modes are always reported separately:

```
capt_execution_mode:  <returned by capt agent status/start for the CAPT turn>
hermes_session_mode:  <this Hermes session — default BOOTSTRAP_DEGRADED>
```

A Hermes session is not GOVERNED merely because a CAPT subprocess printed
GOVERNED. See `security-boundaries.md` §7.

## 2. Component states

| state | required evidence |
|---|---|
| `ACTIVE_PRODUCTION_PATH` | an artifact from a real run shows it executed on the production path |
| `ACTIVE_GOVERNANCE_PATH` | it gated, blocked, or recorded a real decision in a real run |
| `TEST_ONLY` | exercised only by tests/fixtures |
| `AVAILABLE_NOT_WIRED` | importable/constructible; no production call site proven |
| `DEPRECATED` | superseded; retained for compatibility |
| `DEAD_CODE_CANDIDATE` | no call site found, no evidence of use |

An import, a class definition, a passing unit test, a docstring, or a registered
hook proves at most `AVAILABLE_NOT_WIRED`.

## 3. Milestones and their predicates

Advance only when every predicate is satisfied by persisted evidence.

### `GOVERNED_RUNTIME_PROVEN`
- `CAPTRuntime` loads as the single composition root (`single_composition_root: true`).
- A real operation ran inside a committed CTP transaction.
- KHSB durable events recorded for it (or KHSB explicitly disabled and declared).
- Evidence artifact written with a matching `.sha256`.

### `GOVERNED_MODEL_EXECUTION_PROVEN`
- A real provider was invoked through `CAPTRuntime.execute_model_task`.
- MemoryUseGate ran and PASSed **before** the invocation.
- Provider invocation count == 1 per governed task.
- Request and response artifacts persisted; recomputed sha256 matches the receipt.
- ContextPack digest recorded and matching between receipt and checkpoint.
- Memory-derived answers absent from the immediate prompt (the model got them
  from the pack, not the question).
- Selected and rejected records present in the model-facing ContextPack.
- CTP transaction committed.
- Reproducible: more than one independent pass.

### `HERMES_CAPT_PLUGIN_HOOKS_PROVEN`
- Plugin discovered and `enabled` in `hermes plugins list`.
- `register(ctx)` executed in a real Hermes session.
- Hooks **fired** in the live path with evidence (KHSB events / artifacts) — not
  merely registered.
- Installed plugin digest matches the repository source.

### `GOVERNED_AGENT_BOOT_PROVEN`
- Boot ran through the canonical Agent Runner.
- Mission resolved by declared precedence (never recency).
- Checkpoint validated: identity, digest, workspace, required fields.
- Directives split into active vs superseded.
- ContextPack built with a real digest; MemoryUseGate PASS.
- Boot trace persisted with a matching `.sha256`.
- Execution mode assigned from real gate output.

### `GOVERNED_AGENT_CONTINUITY_PROVEN`
- Checkpoint written and verified to reload.
- A **fresh process** with no transcript inheritance recovered the mission from
  CAPT state alone.
- Recovered mission/session/checkpoint identity matches.
- New ContextPack built and gate PASSed on resume.
- Recovered state consistent with repository evidence; divergence reported.
- Recovery report persisted with a matching `.sha256`.

### `GOVERNED_TOOL_LOOP_PROVEN`
- A tool intent was **authorized or refused by the runtime** before execution.
- The refusal path is proven (an unauthorized intent was actually blocked).
- Tool results captured as governed evidence.
- The loop ran inside a committed CTP transaction.

**Current status of this milestone: NOT PROVABLE in a Hermes session.** The
plugin's `pre_tool_call`/`post_tool_call` hooks are observational only. Claiming
it from hook registration is prohibited.

## 4. Prohibited advancement bases

Never advance a milestone on: documentation, a class existing, an import
succeeding, a hook being registered, a test fixture passing, a plan, a design
doc, an object being constructed, or a previous session's claim.

## 5. Claim language

| verdict | phrasing |
|---|---|
| supported by artifacts | "PROVEN — evidence: `<path>` sha256 `<digest>`" |
| ran but unverified | "EXECUTED — verification NOT_PROVEN" |
| exists but unexercised | "AVAILABLE_NOT_WIRED" |
| failed | "FAILED — `<code>`, evidence preserved at `<path>`" |
| not attempted | "NOT_PROVEN — not attempted" |

Never write "should work", "appears to work", "is now governed", "fully
integrated", or "complete" without a named artifact.

## 6. Completion boundary

Do not claim, unless independently proven:
- Hermes is universally CAPT-governed;
- the governed tool loop is proven;
- every provider is supported;
- all legacy skills are obsolete;
- memory is used by every model;
- the CAPT Space compiler is complete.
