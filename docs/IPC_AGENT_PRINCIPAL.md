# Execute-only agent principal and exact-request commitments

Status: proposed (draft PR). Additive; default behaviour is unchanged.

## Problem

Every RuntimeService connection authenticated by `runtime.token` is bound to one
principal, and every command it sends is recorded with `actor_kind="human"`
(`desktop/m1_command_service.py::_operator_metadata`). Under the stated
single-trusted-user model that is correct. It stops being correct as soon as an
agent host is allowed to connect: a process holding the token can create a mission
that requires approval and then decide that approval itself. This was reproduced
against a disposable RuntimeService (CAPT-Interop `scripts/self_approval_poc.py`).

Separately, a HumanApproval binds operations, scope, use budget and expiry, but not
the bytes a tool will write: `ToolBroker.execute` and `RuntimeService.check_lease`
never compare the request with what the human reviewed.

## Change

1. `--agent-token-file PATH [--agent-group GROUP]` issues a second credential.
   Connections presenting it are principal `agent`:
   * every read-only query is available;
   * the only command operation is `run_tool` (`desktop/ipc_principal.py`); anything
     else is refused at the IPC boundary — before any command-service subclass runs —
     with code `AGENT_PRINCIPAL_OP_DENIED` and a durable security rejection;
   * as defence in depth, agent commands carry `actor_kind="external_driver"`, an
     actor kind the authority table permits for no human act.
2. `--agent-group` sets the agent token to `0640` and the socket to `0660` with that
   group so an agent running under its own uid can connect without reading the human
   token. Token files are now created atomically with their final mode from birth
   (`write_secret_file`); previously `write_text` + `chmod` left a umask-mode window.
3. A grant whose `externalCommitments` contains `capt.tool-request.v1` entries may be
   spent only by a request whose recomputed `tool_request_fingerprint` equals one of
   them; otherwise ToolBroker records a pre-dispatch denial
   `TOOL_REQUEST_COMMITMENT_MISMATCH`. Grants without such commitments are unaffected.
4. The authentication reply gains `principal` and `features`
   (`principal.v1`, `tool_request_commitment.v1`).

## Not changed

Mission authoring and approval decisions remain human-only; the agent principal
cannot create missions. Human-token behaviour is identical apart from the two
additive reply fields. No ledger migration.

## Tests

`tests/capt_runtime/test_ipc_agent_principal.py` (real RuntimeService subprocess):
token modes, principal reporting, refusal of nine non-`run_tool` operations
including the three intercepted by command-service subclasses, agent unable to
decide a requested approval, mutated bytes denied with no file written, exact
committed request succeeds once, uncommitted grants unchanged, agent token
rejected when not configured.
