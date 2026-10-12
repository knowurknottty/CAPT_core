# CAPT Council — TIA semantic widget parity R1

The macOS Tk 9.0 UI publishes its NSWindow title but not its ttk widgets to
AXUIElement. A small owner-only, per-PID semantic Unix socket surfaces only
named, allowlisted *real Tk widgets* for TIA, on the Tk event thread.

Boundary invariants:

- Native macOS AX must independently verify exact window title and PID
  before TIA accesses the corresponding 0600 socket.
- The socket's server and client verify local peer UID.
- Snapshot field values are redacted, including draft IDs. No screenshots.
- The only mutable fields currently exposed are Council ID, Mission ID,
  Provider, Model and Vessels.
- The only exposed press actions are Refresh models, Refresh and Reconnect.
- Approve/Deny, Launch, arbitrary execution, keyboard and pointer are forbidden.
- Setting a field changes its Tk StringVar. Press invokes the actual Tk button.
  Neither is a CAPT RuntimeService command or an approval.
- A failed exact-PID binding or ambiguous Council window fails closed.
- An autosaved draft is not execution authority; old lost runs stay
  reconciliation-required and replay-forbidden.

Verification:
- 2 dedicated test_tia_widget_surface.py tests passed including an actual
  Unix-socket request/response with UI-thread execution and 0600 permission.
- 21 targeted Council/UI tests passed.
- Live disposable Council R3 UI, pid 96537: AX-verified semantic snapshot and
  Mission ID edit, focus, read-only Refresh, restore. Before/after hashes matched
  the original state; no approval or inference ran.
- No assumption that Tk 9.0 provides native AX child elements: the supplement
  clearly identifies its own source and does not masquerade as native AX.
