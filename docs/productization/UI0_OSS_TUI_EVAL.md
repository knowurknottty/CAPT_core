# CAPT OSS TUI Framework Evaluation (UI-0)

Detailed factsheets for TUI-framework selection. Consolidated verdict: **adopt
Textual** as the operator console; **Rich `Live`** as a read-only telemetry
sidecar. All facts from official repos/PyPI/docs (2026-08-08); nothing invented.

---

## 1. Textual (Python) — RECOMMENDED

- **License:** MIT.
- **Maintenance:** very active; v8.2.x (Apr 2026), 220+ releases, ~36.8k★, core
  team (McGugan, davep, darrenburns).
- **Language:** Python ≥3.9,<4.0 — same runtime as CAPT, no cross-language bridge.
- **Rendering:** full terminal app + optional web (`textual serve`, Textual
  Web); TCSS styling (CSS subset) with a color-blending design system.
- **Async:** asyncio-native; integrates with async libraries; `run_async`,
  `set_interval`, async event handlers. Maps one-to-one onto a Unix-socket JSON
  subscribe/consume client.
- **Widgets:** rich set — Button, Tree, DataTable, Input, TextArea, ListView,
  Digits, OptionList, Sparkline, Markdown, Tabs; Horizontal/Vertical/Grid
  layouts, Containers, Dock.
- **Theming:** predefined themes + full TCSS theming; built-in fuzzy command
  palette (Ctrl+P).
- **Accessibility:** keyboard-first with full focus/key handling; `NO_COLOR`
  monochrome. Screen-reader/braille support not yet mature (project-flagged).
- **Mouse:** enabled by default; click-drag selection, hover, `capture_mouse`.
- **Streaming/tabular:** strong — DataTable supports large/virtualized + live row
  updates; used for realtime dashboards.
- **Suitability for CAPT:** panels/tabs/grids fit missions/approvals/evidence/
  memory; keyboard-first + command palette; DataTable for tabular evidence.

## 2. Bubble Tea (Go)

- **License:** MIT. **Active:** ~44k★, v2 (2026), Charm.
- **Rendering:** high-performance cell-based renderer, color downsampling,
  alt-screen; declarative views (Elm Model/Update/View + `Cmd`/`Msg`).
- **Widgets:** minimal core; components via Bubbles (inputs, viewports, spinners,
  lists, tables) styled with Lip Gloss.
- **A11y:** no notable screen-reader support.
- **Suitability:** excellent framework but **wrong language** — Go↔Python bridge
  (reimplementing the client) required. Only sensible if CAPT were Go.

## 3. Ink (React / JS)

- **License:** MIT. **Active:** ~39.5k★.
- **Rendering:** React renderer + Yoga (Facebook) Flexbox layout in the terminal.
- **Async:** React model, hooks (`useInput`, `useEffect`, `useStdin/Out/Eerr`).
- **A11y:** **strongest of the five** — screen-reader mode (`INK_SCREEN_READER`,
  ARIA props, `useIsScreenReaderEnabled`), `useFocus` Tab/Shift-Tab.
- **Streaming:** `<Static>` for streamed logs; tables via third-party.
- **Suitability:** great for agentic CLIs (Claude Code/Gemini CLI) but needs a
  Node↔Python bridge. Not Python-native.

## 4. urwid (Python alternative)

- **License:** **LGPL-2.1** — the only copyleft of the five.
- **Active:** v4.0.x (2026), ~16 yrs maintained.
- **Rendering:** canvas-based, imperative widget tree; asyncio event-loop
  integration exists but more manual than Textual.
- **Widgets:** lower-level (Text, Edit, ListBox, Columns, Pile, Frame, GridFlow);
  no modern design system; no built-in data table.
- **A11y:** minimal; no screen-reader layer.
- **Suitability:** viable and mature, but dated API, no data table, and carries
  LGPL copyleft. Not the modern choice.

## 5. Rich `Live` (Python alternative)

- **License:** MIT. **Very active** (Rich 14.x, Textualize).
- **Rendering:** in-place live region via ANSI cursor control; optional
  alt-screen; `Live`/`LiveLog`/`LiveView`.
- **Async:** NOT an event loop — sync context manager + background refresh thread
  (default 4 fps).
- **Widgets:** renderables not widgets — Table, Panel, Progress, Status,
  `rich.layout` for composed dashboards.
- **A11y:** `NO_COLOR` monochrome; no screen reader, no keyboard focus model.
- **Mouse:** none — output-only, no interactivity.
- **Streaming/tabular:** excellent — `Table.add_row`, `Live.update`, multi-panel
  layouts.
- **Suitability:** ideal as a read-only live status/telemetry board (evidence/
  mission/memory streaming); cannot do keyboard-driven approvals/forms.

---

## Verdict

| Framework | Verdict | Reason |
|---|---|---|
| **Textual** | **Adopt** | Python-native, asyncio↔socket fit, panels/tabs/DataTable, MIT |
| **Rich Live** | Adopt (sidecar) | read-only telemetry, zero-interaction dashboard |
| Bubble Tea | Avoid | Go↔Python bridge |
| Ink | Avoid | Node↔Python bridge (best a11y, though) |
| urwid | Avoid | LGPL + dated, no data table |

Gap to plan: Textual screen-reader accessibility is maturing, not complete —
acceptable for an internal/power-user operator console; Ink would be revisited
only if a screen-reader-first terminal audience becomes a requirement.