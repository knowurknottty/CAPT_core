# CAPT_AGENT_RUNNER_STATE_AUTHORITY.md

Canonical authority order for the CAPT Agent Runner. Enforced, not advisory.

## Authority order

1. Current owner directives (subject to safety and scope).
2. Verified current repository/runtime state (git SHA/branch, file evidence).
3. Valid CAPT checkpoints and receipts.
4. Protected CAPT memory.
5. Current evidence artifacts and ClaimGuard verdicts.
6. Decision and procedural memory.
7. Bounded recent interaction.
8. Archived transcript — NON-authoritative evidence only.
9. Model prior knowledge.

## Rules

- Recency alone does NOT establish authority. A newer arbitrary transcript
  statement does not automatically override validated CAPT state.
- Supersession is persisted EXPLICITLY (directive supersession record: old id,
  new id, reason, actor, evidence, timestamp).
- Conflicts between tiers are recorded (conflict_ids) and resolved by the higher
  tier; the losing record is marked rejected/superseded, never silently dropped.
- The archived transcript may inform (tier 8) but may never be promoted to an
  active instruction. Contradiction between tier 8 and tiers 1-6 → tiers 1-6 win
  and the conflict is recorded (Acceptance 3).
- Missing mandatory higher-tier records → BLOCKED (not silent downgrade to a
  lower tier).

## Directive resolution (Acceptance-3/AC materiality)

- Active directives = highest-precedence non-superseded, non-revoked directives
  for the mission, ordered by explicit precedence then recency-as-tiebreak.
- Superseded/older directive (e.g. "Pause implementation") is REJECTED when a
  newer authoritative one ("Continue without pausing") exists; rejection is
  recorded with the superseding id.
- Selected vs rejected memory ids are recorded in AgentMemoryBootTrace and must
  map back to the decision each supported (memory-influence mapping).

## Enforcement points (composition)

- Boot step 6-9 (BOOT_CONTRACT) resolves directives + supersession + conflicts.
- MemoryUseGate (step 12) refuses when required protected memory is missing.
- STATE_AUTHORITY order is applied in `capt_solo/agent/directives.py` and is the
  basis for what enters the ContextPack rendered_context that becomes the model
  request (runtime.py:676-695) — so authority is reflected in the ACTUAL request,
  not just documentation.
