"""CAPT UI operator package.

The UI foundation builds one shared operator layer that every surface
(CLI, TUI, Desktop, future Web) consumes. It is a THIN projection and control
layer over CAPT RuntimeService. It never duplicates runtime logic, never
fabricates authoritative state, and never writes the ledger directly.

Authority chain (unchanged):
    RuntimeService
      -> EventStore
      -> Memory
      -> Governance
      -> Drivers

All mutations here go through governed command ops on RuntimeClient.
"""