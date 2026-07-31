# CAPT_AGENT_RUNNER_CONTEXT_POLICY.md

Context-budget and consolidation policy. The runner MUST NOT depend on native
transcript compaction.

## Model-aware percentage thresholds

Thresholds are % of the provider's context limit (`ModelIdentity.context_limit`),
not a universal token count.

- 50-60% — prepare consolidation (mark candidates; no eviction yet).
- 65-75% — persist decisions, directives, unresolved work, evidence.
- 75-85% — finish only the current atomic operation; stop broadening scope.
- Before provider-native compaction / context overflow — checkpoint, verify
  reload, exit, resume in a fresh process.

## Transactional consolidation (CTP)

```
BEGIN
 → extract state (active directives, decisions, facts, unresolved work,
   failures, evidence links, contradictions)
 → persist memory
 → verify retrieval  (read back what was persisted)
 → checkpoint
 → COMMIT
 → evict old active context
```

Abort eviction if persistence OR retrieval verification fails. Never evict
before COMMIT. Never evict unverified state.

## OutputPolicy (CaveCAPT) — runtime-owned, V1

The runtime renderer — NOT the model — owns visible output. The provider/model
may return a structured envelope; CAPT separates internal machine-readable state,
persisted governance evidence, and user-visible response. Private
chain-of-thought is never exposed.

```python
@dataclass(frozen=True)
class OutputPolicy:
    mode: str                    # cave | normal | verbose | silent | audit
    max_visible_tokens: int
    narrate_planning: bool
    narrate_tools: bool
    emit_progress: bool
    ask_only_when_blocked: bool
    emit_final_summary: bool
```

### Mode defaults

| mode | max_visible | narrate_planning | narrate_tools | emit_progress | ask_only_when_blocked | emit_final_summary |
|---|---|---|---|---|---|---|
| cave (DEFAULT) | 80 | false | false | false | true | true |
| normal | 400 | false | false | true | true | true |
| verbose | 4000 | true | true | true | false | true |
| silent | 0* | false | false | false | true | false |
| audit | 300 | false | false | false | true | true |

\* silent emits ONLY: blocker, mandatory-gate failure, security warning, final
result (these bypass the numeric cap — see safety rule).

### Cave output style

Short declarative sentences; exact status; no social filler; no repeated
mission; no visible planning monologue; no obvious tool-sequencing explanation;
no "I am going to…" narration; no token-budget commentary; no congratulatory
prose. Emit only: meaningful state transition, finding, blocker, required owner
decision, phase completion, final evidence-backed result.

Example (cave):
```
Mission resumed.
Current milestone: CAPT Agent Runner implementation.
Next action: add canonical boot path.
```

### Audit output

claim; verdict; evidence IDs; transaction; checkpoint; missing requirement.

## Hard safety rule

Output caps MUST NOT truncate or weaken required safety warnings, security
findings, blockers, or failed-mandatory-gate messages. These always emit in full
regardless of mode or `max_visible_tokens`. No completion claim without a
ClaimGuard verdict.

## Persistence

Output mode is persisted in mission/session state and checkpointed. CLI override
`--output-mode cave|normal|verbose|silent|audit`; session override `/capt mode
<mode>` takes effect on the next turn. Resumed sessions retain the selected mode.
Provider/model output cannot bypass the runtime renderer.
