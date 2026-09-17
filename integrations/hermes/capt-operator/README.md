# CAPT Operator for Hermes

This directory is the canonical source for the Hermes → CAPT operator plugin.

Authority boundary:

- `capt_runtime` / RuntimeService / EventStore remain the only CAPT authority.
- This plugin talks to RuntimeService over `~/.capt/runtime.sock`; it never opens the ledger database.
- It must not import or construct `capt_solo.runtime.CAPTRuntime`.
- `CAPT_STATE_DIR` may relocate the Core state root. Legacy `CAPT_SOLO_HOME` is intentionally ignored.
- CAPT → Hermes bounded execution remains `capt_runtime.drivers.hermes.HermesDriver`; this plugin is the complementary Hermes → CAPT operator/projection surface, not a second ExecutionDriver.

The historical `capt-solo` Hermes plugin is not part of the supported Core integration and should remain disabled.
