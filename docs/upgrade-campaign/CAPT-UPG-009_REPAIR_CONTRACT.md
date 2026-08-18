# CAPT-UPG-009 Repair Contract

Required authoritative lifecycle:

`PREPARE -> AUTHORIZE -> MUTATE_ISOLATED -> VERIFY -> PROMOTE/ADOPT | DISCARD`

Acceptance requires a distinct RuntimeService/EventStore promotion transaction binding staged artifact identity, exact digest, source workspace, canonical destination, verification domain/receipt, authorization identity, and idempotency identity. Helper-level `shutil.copy2()` is not authoritative adoption.
