# CAPT TUI (Textual)

The CAPT Textual TUI is the interactive operator surface. It is built on the
shared `capt_ui` operator layer and is **not** a second runtime — all mutation
and authority remain in CAPT RuntimeService.

## Launch

```bash
capt-ui dashboard   # interactive Textual dashboard
```

The TUI connects to a running runtime. If none is running, start one first:

```bash
capt start
capt-ui dashboard
```

## What it shows

- **Runtime** — health, version, integrity, head sequence
- **Mission** — active mission/task state
- **Provider/model** — configured providers, health, model list
- **Approvals** — pending human approval queue (approve/deny)
- **Evidence** — evidence / verification / ClaimGuard
- **Memory** — durable memory overview
- **Logs** — operator event feed

## Governed actions

Keyboard-first. Approve/deny, checkpoint, resume, and cancel route through the
shared Operator facade into RuntimeService. The TUI never writes the
EventStore/ledger directly.

## CaveCAPT verbosity

`capt-ui verbosity` cycles presentational detail (minimal / normal / detailed /
diagnostic). It is presentation-only and never weakens governance,
verification, evidence, memory policy, or ClaimGuard.

## Honest status

- **TUI: SHIPPED MVP.** Acceptable for v0.6. Interactive keypress smoke passes.
- Cross-model continuity is **NOT** claimed by the TUI; see
  `capt_ui/ACCEPTANCE_STATUS.md`.
