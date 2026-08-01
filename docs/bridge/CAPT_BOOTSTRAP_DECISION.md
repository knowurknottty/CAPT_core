# CAPT_BOOTSTRAP_DECISION

Decision record for the CAPT Bootstrap Bridge. Derived from
`CAPT_BOOTSTRAP_SEAM_MAP.md`; every mechanism named here was verified in source
before being chosen.

---

## D1. Where the bridge lives

**In CAPT, at `capt_solo/bridge/`. Shipped as a Hermes plugin via the existing
`hermes_plugins` entry point that `capt-solo` already declares.**

Rejected alternatives:

- *A new `~/.hermes/plugins/capt-bridge/`* — a global Hermes mutation, forbidden by
  the mission and by the Phase 7 guard this same bridge enforces.
- *Bridge logic inside the skill's shell scripts* — a skill cannot register
  middleware, so it can never suppress provider dispatch. This is precisely the
  defect being fixed.
- *Patching `conversation_loop.py`* — forking Hermes. Rejected.

The bridge is CAPT-owned code that Hermes loads through a documented, supported
extension point. Nothing outside the CAPT repository is written.

## D2. How the skill invokes it

The skill stops being an instruction manual and becomes a launcher:

```
capt --json bridge boot --workspace WS --mission M
```

One command. It returns the machine-readable `BridgeResult` (schema in
`capt_solo/bridge/contracts.py`) whose `boot_state` is one of the four required
values. The skill's operator surface is: run it, read `boot_state`, and — when the
state is not `FULL_CAPT_AGENT_RUNNER_ACTIVE` — report the block codes verbatim.

The skill must not interpret, retry, or narrate around a blocked result.

## D3. How provider ownership transfers

`capt_solo.plugin.get_plugin()` registers an `llm_execution` middleware
(`hermes_cli/plugins.py:1196`, kind valid per `middleware.py:29`). Hermes routes
**every** main-loop provider call through it at `conversation_loop.py:2285`.

The middleware holds an explicit `ProviderOwnership` state machine with the
mission's required invariant:

```
EXACTLY_ONE_PROVIDER_OWNER ∈ {
    HERMES_BEFORE_BRIDGE,          # bridge inert; middleware calls next_call()
    CAPT_AGENT_RUNNER_AFTER_READY, # middleware returns CAPT output; next_call() never called
    NONE_WHEN_BLOCKED,             # middleware returns a blocked response; next_call() never called
}
```

Transfer to `CAPT_AGENT_RUNNER_AFTER_READY` occurs only on a validated READY event
(D5). There is no other transition into that state.

## D4. How Hermes-native provider invocation is suppressed

By **not calling `next_call`** and returning a response object instead.

This is the one mechanism the seam actually supports, and the reason is recorded in
the seam map §B.3: `_run_execution_chain` (middleware.py:303-314) **catches
middleware exceptions and falls through to the provider**. Raising is fail-*open*.

Consequences, binding on the implementation:

1. No blocking path may raise. Every branch returns a `_BlockedResponse`.
2. The middleware body is wrapped in a total `try/except BaseException` whose
   handler *also* returns a blocked response. An internal bridge bug must degrade
   to BLOCKED, never to a silent Hermes provider call.
3. `next_call` is invoked in exactly one place — the `HERMES_BEFORE_BRIDGE` branch,
   before any transfer has been attempted.

## D5. What returns CAPT output to Hermes, and what makes it trustworthy

A `BridgeReadyEvent` written by the runner to a **unix domain socket in a 0700
directory** under the CAPT state root, authenticated by a nonce the *bridge*
generates and passes to the runner out-of-band (environment, never argv).

Validation requires all of:

- transport is a local unix socket owned by the invoking uid, dir mode `0700`;
- `bridge_nonce` equals the nonce the bridge minted this launch (constant-time
  compare);
- the emitting pid is the runner the bridge itself spawned;
- every required field present: `run_id`, `mission_id`, `session_id`, `intent_id`,
  `checkpoint_id`, `contextpack_digest`, `memory_use_decision_id`,
  `memory_use_gate` == `PASS`, `ctp_transaction_id`, `khsb_correlation_id`,
  `provider_owner` == `CAPT_AGENT_RUNNER`, `execution_mode` == `GOVERNED`;
- `event_digest` recomputes over the canonical field set.

Explicitly **not** accepted, each with a test in Phase 9:

- model text claiming readiness;
- substring/log-line matching;
- a hand-written JSON file on disk;
- any prompt-level claim.

The nonce never appears in argv (visible in `ps`) and is never logged.

## D6. Cancellation and exit propagation

The runner is spawned with `start_new_session=True`, giving it its own process
group. The bridge holds the pgid. `SIGINT`/`SIGTERM` at the Hermes layer forwards to
the group; the runner checkpoints through canonical CAPT and exits; the bridge
transitions to `NONE_WHEN_BLOCKED`. Runner death after READY is detected on the next
provider call and returns BLOCKED — **not** a fallback to Hermes.

Return to Hermes-native execution requires an explicit owner authorization token in
the environment (`CAPT_BRIDGE_ALLOW_HERMES_FALLBACK=1`); its use is recorded as a
receipt. Absent that token there is no path back. No silent fallback.

## D7. Architectural limitation — stated, not worked around

**Hermes can be made transport-only for provider inference. It cannot be made
transport-only for the whole agent loop.**

Hermes retains tool dispatch, the turn loop, and conversation history. It still
*constructs* `api_kwargs` (system prompt, tool schemas, transcript) on every turn;
the bridge discards them rather than preventing their construction. Auxiliary call
sites (subagents, summarisation) are separate from the main loop's :2285 and are not
covered by this bridge.

What the bridge therefore proves, and the exact wording the milestone is allowed to
use: *a fresh Hermes process transfers **provider** authority and continuity
authority to the canonical CAPT Agent Runner, and fails closed when that transfer
cannot be proven.* Any broader claim would be false.
