---
name: capt-recovery
description: Recover CAPT Solo state after an interruption — replay CTP journal, verify integrity, restore from backup.
---

# CAPT Solo — Recovery After Interruption

Use this skill when a session or machine crashed mid-operation and you need to
confirm CAPT Solo is consistent.

## When to use
- Hermes or the machine restarted unexpectedly.
- A transaction may have been left pending.
- You suspect data corruption.

## Steps
1. Check health first:
   - Tool: `capt_health`
   - If `status: "ok"`, you are done — nothing was lost (journals are append-only
     and flushed on every write).
2. Recover pending transactions:
   - Use the engine's `CTPRuntime.recover()` via a script — it replays the journal
     and returns any tx_ids left pending (uncommitted/unaborted).
   - For each pending id, decide commit or abort and call the matching tool.
3. If memory looks wrong, verify integrity:
   - Tool: `capt_health` reports `memory_integrity`.
   - If false, restore from the latest backup:
     - Tool: `capt_import_project` after copying a `memory_backup_*.db` over the
       live `memory.db`, OR use `MemoryEngine.restore(path)`.
4. Re-run the installer's `verify.sh` to confirm all three subsystems pass.

## Pitfalls
- Never manually edit `journal.log` — it is the source of truth for recovery.
- Restoring a backup overwrites current state; export first if you want to keep it.

## Verification
After recovery, `capt_health` returns `status: "ok"` and `verify.sh` passes all
three subsystem tests.
