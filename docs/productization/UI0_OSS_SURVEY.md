# CAPT OSS Survey — UI/UX Reuse Investigation (UI-0)

Purpose: determine whether adapting an existing open-source chat UI or TUI
framework saves substantial engineering effort for CAPT's operator console,
without copying another product or breaking CAPT's architecture/authority.

Research date: 2026-08-08. Facts sourced from official repos/docs/PyPI; items
marked "unverified" could not be confirmed from primary sources and are not
asserted.

Verdict options: **Adopt / Fork / Embed / Borrow patterns / Avoid.**

---

## A. Chat / web UIs

| Project | License | Maintenance | Stack | Backend assumption | Local (Ollama/LM Studio) | OpenRouter | Plugins/MCP | Embeddable in macOS SwiftUI/wv | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **Open WebUI** | Open WebUI License (custom, NOT MIT) | Very active, ~148k★ | SvelteKit + FastAPI + SQLite | Self-hosted server (Docker/pip), RAG-native | ✅ Ollama-native | ✅ | Pipelines + MCP + Model Builder | ❌ needs full server; web app not a native component | **Borrow** (patterns) |
| **LibreChat** | MIT | Very active, ~42k★ (ClickHouse-backed) | React + Node/Express + MongoDB+Redis | Multi-service server, enterprise | ✅ | ✅ | MCP + agents + Code Interpreter | ❌ heavyweight multi-service | **Borrow** (provider breadth) |
| **LobeChat** | Apache-2.0 | Very active, ~80k★ | Next.js + TS + Lobe-UI | Full-js, self-host; model-first | ✅ Ollama | ✅ | Plugin market + MCP market | ❌ full-js server; PWA/web | **Fork/orient? no — Borrow** |
| **NextChat** | MIT | Very active, ~88.5k★ | Next.js + React SPA, **Tauri** desktop | Mostly client-side, localStorage+WebDAV | ✅ (OpenAI-compat endpoint) | ⚠️ not first-class (endpoint) | Plugins + MCP market | ✅ **best webview-embeddable MIT UI** | **Embed / Borrow** |
| **AnythingLLM** | MIT (core; commercial Pro tier) | Very active, ~64k★ | Vite/React + Node/Express + LanceDB, **Electron** | Full-stack server required | ✅ | ✅ chat+embed | Agents/Skills/MCP/request-approval | ❌ needs whole Node server | **Borrow** (governance/provider factory) |
| **Chatbox (CE)** | **GPL-3.0** | Active, ~41k★ | React/TS, **Tauri** desktop, thin BYOK | Thin client direct-to-provider | ✅ Ollama + LM Studio (via endpoint) | ✅ first-class | MCP client | ⚠️ GPL blocks closed fork/embed | **Avoid** (license) / borrow Tauri pattern |
| **Enchanted** | Apache-2.0 | **Stale** (last push 2025-03) | SwiftUI native, Ollama-only | Thin client | ✅ (Ollama only) | ❌ | ❌ none | native Apple; single-purpose | **Avoid** (stale/narrow) / borrow SwiftUI+SSE |
| **Msty** | **Proprietary** | Commercial, active | closed source desktop | Self-contained | ✅ | unverified | MCP (closed) | ❌ no source | **Avoid** (closed) |
| **Cherry Studio** | **AGPL-3.0** | Very active, ~50k★ | Electron + React 19 + Shadcn + TipTap | Electron main proc; local-first | ✅ Ollama + LM Studio | ✅ first-class + Anthropic "skin" | plugins + MCP + marketplace | ❌ Electron app (patterns only) | **Borrow** (architecture patterns) |
| **Continue.dev** | Apache-2.0 | **Frozen/read-only** (final 2.0.0) | TS core, React webview, LanceDB | IDE extension + core | ✅ Ollama | ✅ | skills + blocks + MCP | ⚠️ frozen baseline | **Avoid** as dep / borrow architecture |
| **Aider** | Apache-2.0 | **Very active**, ~48k★ | Python + **litellm**; terminal + experimental Streamlit | Local terminal app, embeddable Python | ✅ Ollama + LM Studio | ✅ | no plugin API (Python Coder API + MCP) | ✅ **embeddable Python engine** | **Adopt/embed** (engine) |
| **Aider WebUI / aider-web / Newrev / AiderDesk** | MIT / MIT / Apache-2.0 / (check) | Alpha/Beta, few stars | NiceGUI / Node+xterm / Python+Node / React+Tailwind | wrap Aider CLI | ✅ (Newrev Ollama) | varies | MCP (varies) | immature | **Borrow patterns only** |

## B. TUI frameworks

| Framework | License | Maintenance | Language | Rendering | Async | Widgets | Theming | A11y | Streaming/tabular | Suitability | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Textual** | MIT | Very active (v8.2.x, ~37k★) | Python | full app (+web serve) | asyncio-native | rich set incl. DataTable, Tree, Markdown | TCSS themes + palette | keyboard-first; screen-reader maturing | strong DataTable | **Excellent** — Python-native, async, panels/tabs | **ADOPT** |
| **Bubble Tea** | MIT | Very active (~44k★) | Go | cell renderer | Elm architecture | minimal + Bubbles/Lip Gloss | per-widget | none notable | good | excellent but Go↔Python bridge needed | **Avoid** (language) |
| **Ink** | MIT | Active (~40k★) | TS/JS | React + Yoga flexbox | React model | minimal + ecosystem | inline/chalk | **best screen-reader** | via 3rd-party | great but Node↔Python bridge | **Avoid** (language) |
| **urwid** | **LGPL-2.1** | Active | Python | canvas, imperative | asyncio manual | lower-level | palettes (dated) | minimal | no data table | viable but LGPL + dated | **Avoid** (license/age) |
| **Rich Live** | MIT | Very active | Python | live region ANSI | background thread (not loop) | renderables | Rich styles | NO_COLOR only | **excellent** read-only | read-only telemetry only, no interactivity | **Adopt as sidecar** |

---

## C. Recommendation (evidence-based)

### 1. TUI — **adopt Textual** (Python, MIT, asyncio-native).
Fits the existing Python runtime (`capt_runtime`), maps cleanly onto the
Unix-socket JSON `RuntimeClient` (asyncio subscribe→widget), and has the panel/
tabs/DataTable/markdown components the operator console needs. Keyboard-first +
command palette. **Ship Rich `Live` as a read-only status/telemetry sidecar** (it
is already in the Textual lineage). Bubble Tea and Ink are excellent but require
Go/Node↔Python bridges; urwid carries LGPL and is dated. *(Full TUI factsheets:
`UI0_OSS_TUI_EVAL.md`.)*

### 2. Desktop — **do not restart from zero.**
The existing thin Tk `desktop/desktop_app.py` + `RuntimeClient` is already a
working, authority-correct v0.6 desktop MVP (headless + GUI). Strategy:
- **Now:** keep the Tk MVP (satisfies v0.6 UI gate).
- **Native macOS path:** a **thin SwiftUI client** over the same `RuntimeClient`
  contract (mirrors Enchanted's proved SwiftUI+SSE/client pattern, Apache-2.0,
  permissive). This is the v0.6/v0.7 upgrade path.
- **Cross-platform option:** **Tauri** shell (Rust) — the pattern proven by
  NextChat (MIT) and Chatbox; embed a light SPA or webview. Evaluate only if
  macOS-first pivots to cross-platform.
- **Do NOT** adopt an Electron/closed GUI as the default (heavy, and closed
  sources like Msty cannot be audited).

### 3. Chat-shell UX — **borrow patterns, do not fork a product.**
- **NextChat (MIT)** is the most webview-embeddable MIT SPA and the easiest to
  fork/embed as a chat shell; but it is largely client-side/localStorage and
  cloud-endpoint-biased, and OpenRouter is not a first-class provider. Strong
  fast-follow candidate if a browser view is ever wanted.
- **AnythingLLM / Cherry Studio (AGPL)** are the best **governance references**:
  provider-factory, MCP, request-approval hooks, skills. Study and re-implement
  the *patterns*, do not copy (AGPL/Cherry and the Open WebUI custom license are
  not suitable for a proprietary/closed governed layer).
- **Chatbox is GPL-3.0 — do not fork/embed**; borrow only its Tauri macOS shell
  pattern (clean-room).
- **Aider is the standout runtime-adjacent asset:** Apache-2.0, active, and its
  **Python `Coder` engine is directly embeddable** — this could substantially
  accelerate CAPT's model-backed governed execution with OpenRouter/Ollama/
  local out of the box (pin the version; no plugin API).

### 4. Provider layer — the single most reusable upstream idea.
Across Open WebUI, LibreChat, AnythingLLM, Cherry Studio, and Aider, the common
win is a **provider registry + OpenAI-compatible endpoint abstraction**. This
validates the UI-1 provider abstraction in the main spec and strongly suggests
**LM Studio/Ollama/llama.cpp/vLLM all collapse to one OpenAI-compatible
adapter**, with native discovery only where cheap (Ollama `/api/tags`, LM Studio
`/v1/models`).

---

## D. License compliance guardrail

- Prefer **MIT / Apache-2.0** for anything incorporated or embedded.
- **GPL/AGPL (Chatbox, Cherry)**, the **Open WebUI custom license**, and
  **LGPL (urwid)** are incompatible with embedding into CAPT's governed layer
  without releasing CAPT source under the same terms — **avoid copying code**,
  and treat them as pattern references only.
- For `Aider` (Apache-2.0) embedding, preserve the license/NOTICE per Apache-2.0
  §4 and pin the dependency.
- Do not copy code without confirming license + attribution requirements per the
  UI_UX doc §4.

---

## E. Recommended build strategy (minimal engineering)

1. **TUI (UI-3):** Textual app on `capt_ui/operator` + `RuntimeClient`. Direct,
   no fork.
2. **Desktop MVP (UI-4):** ship the existing Tk client; add a thin SwiftUI
   client on the same contract for macOS-native polish.
3. **Chat shell UX:** borrow NextChat/AnythingLLM information-architecture and
   interaction patterns (progressive disclosure, provider panel, evidence
   "why complete?"), re-implemented natively — no copy.
4. **Model-backed execution:** evaluate embedding **Aider's** Python engine
   behind CAPT's bounded-driver boundary (future UI / release-gate work) as a
   way to get OpenRouter/Ollama/local real-model governed missions quickly.
5. **Provider layer (UI-1):** one OpenAI-compatible adapter + lightweight native
   discovery; local/cloud labeling; key-id reference storage.

Full per-candidate factsheets (NextChat/AnythingLLM/Chatbox) are preserved in
`UI0_OSS_CHAT_UI_FACTSHEETS.md`; TUI evaluation in `UI0_OSS_TUI_EVAL.md`.