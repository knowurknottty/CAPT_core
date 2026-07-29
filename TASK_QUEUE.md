# TASK_QUEUE.md — Human-Readable Task Queue

Machine-readable records live in `tasks/*.json` (schema:
`architecture/task.schema.json`). Status model:
`blocked | ready | active | verification | complete | deferred | rejected`.

## v0.5 P0 hardening

| ID | Title | Status | Evidence |
|---|---|---|---|
| TASK-100 | Universal Workspace scaffold and contracts | complete | `c34eb18` |
| TASK-101 | Workspace runtime and CLI | complete | `3b065da` |
| TASK-102 | Workspace schema and CLI tests | complete | `2814100` |
| TASK-200 | Reconcile architecture debt | complete | `572e1ad` |
| TASK-201 | Establish version `0.5.0` | complete | `30fd633` |
| TASK-202 | Refresh current release authority | active | this P0 branch |
| TASK-203 | Add I-15 canon invariant | complete | `572e1ad` |
| TASK-204 | Remove Foundry shell execution | complete | `3b065da` |
| TASK-205 | Add MIT license | complete | `c34eb18` |
| TASK-206 | Add workspace adapter pointers | complete | `c34eb18` |
| TASK-207 | Frozen-candidate release verification | active | pending |

## TASK-207 exit conditions

- wheel and sdist contain the declared public inventory and no private state;
- both artifacts install and pass the declared public profiles;
- version, authority, API, architecture, and changelog semantics agree;
- the verification-first tutorial runs from an installed artifact;
- canonical security and dependency reports are closed;
- final evidence names one frozen candidate and preserves the owner publication
  gate.

No speculative subsystems are part of this release task.
