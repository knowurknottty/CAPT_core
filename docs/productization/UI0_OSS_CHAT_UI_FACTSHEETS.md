# CAPT OSS Chat-UI Factsheets (UI-0)

Detailed factsheets for the chat/web UI candidates. Consolidated verdict:
**borrow patterns, do not fork a product**; **NextChat is the most webview-
embeddable MIT UI**; **AnythingLLM / Cherry Studio** are the best governance and
provider-architecture references; **Chatbox (GPL-3.0) is not fork/embed-able**;
**Aider is the standout embeddable Python engine**. See
`UI0_OSS_SURVEY.md` for the consolidated matrix and recommendation.

Facts from official repos/docs (2026-08-08); nothing invented.

---

## NextChat (ChatGPT-Next-Web)

- **License:** MIT · ~88.5k★ · very active (v2.16.1 2025-07, pushes into 2026).
- **Stack:** Next.js (App Router) + React + SCSS; TypeScript ~92%. **Tauri**
  desktop shell (macOS/Win/Linux) + mobile.
- **Backend:** mostly client-side (localStorage + optional WebDAV sync); light
  Next.js API routes per provider. No DB, no node-server dependency for chat.
- **Local:** Ollama/LM Studio/LocalAI via OpenAI-compatible endpoint +
  `CUSTOM_MODELS`; Ollama docs exist (localhost:11434).
- **OpenRouter:** NOT a first-class `ServiceProvider` enum entry — via
  OpenAI-compatible endpoint config.
- **Plugins/theming/a11y:** plugins (network search, calculator) + MCP market;
  dark/light/custom theming; a11y not a documented priority.
- **Embedding:** **EASIEST** — runs as a static SPA; MIT permits fork/embed in a
  SwiftUI `WKWebView`. Caveats: localStorage state needs a bridge to CAPT
  storage; no native SwiftUI; take React/markup wholesale.
- **Verdict: BORROW / EMBED-REFERENCE** (fast-follow browser-view candidate).

## AnythingLLM

- **License:** MIT (core monorepo; growing commercial Pro tier) · ~64.4k★ ·
  very active (v1.15.0 2026-06).
- **Stack:** monorepo — Vite/React frontend, Node/Express server, collector,
  **Electron** desktop, LanceDB vector store.
- **Backend:** **full-stack, server required** — Express does LLM calls, vectorDB,
  document ingestion; Prisma + SQLite.
- **Local/OpenRouter:** 40+ providers incl. Ollama, **LM Studio**, LocalAI, and
  **OpenRouter** (chat + embeddings).
- **Governance relevance:** AgentFlow, MCP, custom skills, **request-approval
  hooks for skills**, workspace/retrieval model.
- **Embedding:** POOR — needs the whole Node server + DB; not a thin component.
- **Verdict: BORROW (ideas), DON'T EMBED.** Best provider-factory + skill/request-
  approval governance reference; too heavy to adopt wholesale or webview-embed.

## Chatbox (Community Edition)

- **License:** **GPL-3.0** · ~41k★ · active (v1.22.2 2026-08). OSS CE lags the
  closed-source commercial build.
- **Stack:** React/TS; **Tauri** desktop (the product's core), Capacitor mobile;
  thin BYOK client, local-first.
- **Local/OpenRouter:** Ollama listed; OpenRouter first-class
  (`https://openrouter.ai/api/v1`); LM Studio via OpenAI-compatible endpoint.
- **Plugins/theming:** MCP client support; dark/light + themes.
- **Embedding:** **GPL-3.0 is a decisive blocker** for forking/embedding into a
  closed CAPT build; it is also a standalone app, not a component.
- **Verdict: AVOID (fork/embed).** Borrow only its **Tauri macOS-shell pattern**
  (clean-room re-implementation).

## Enchanted

- **License:** Apache-2.0 · **stale** (last push 2025-03; release v1.7.0 2024-05).
- **Stack:** native **SwiftUI**, single Apple codebase (iOS/macOS/visionOS);
  `OllamaService` (URLSession SSE), `AppStore` (Combine), `SwiftDataService`.
- **Local/OpenRouter:** **Ollama-only**; no OpenRouter; no plugins; system dark/
  light only; macOS+iOS only.
- **Embedding:** not a component — a full Ollama-only native app.
- **Verdict: AVOID** for adoption/embedding (narrow, stale, single-maintainer).
  **Borrowable:** the SwiftUI + Ollama-connectivity pattern (SSE streaming
  client, SwiftData) if shipping a native Apple client.

## Msty

- **License:** **Proprietary (closed source).** Commercial (free tier + Aurum).
- **Architecture:** self-contained native desktop (macOS/Win/Linux); bundles
  renamed-Ollama (`msty-local`), an **MLX** service, and a **LLaMA.cpp** service
  behind local HTTP ports; local RAG ("Knowledge Stacks"); MCP.
- **Local/OpenRouter:** local-first; OpenRouter availability not verified; cannot
  audit internals.
- **Verdict: AVOID** (closed source — CAPT cannot inspect, govern, or embed it).
  Useful only as a UX reference (split-pane multi-model comparison, bundled
  local-inference UX).

## Cherry Studio

- **License:** **AGPL-3.0** (Community Edition) · ~50k★ · very active (~263
  releases).
- **Stack:** Electron monolith (main + renderer + preload), documented
  multi-process architecture. Renderer: React 19 + Shadcn UI + Tailwind + TipTap;
  streams via Vercel AI SDK with typed message blocks. `src/shared/` cross-process
  typed schemas.
- **Local/OpenRouter:** Ollama + **LM Studio** local; **OpenRouter first-class**
  (OpenAI-compatible + Anthropic "skin" `/api`).
- **Extensibility:** strong — plugin system, **MCP client + Marketplace**,
  mini-programs, native tool/function calling, agent-skills.
- **Embedding:** whole Electron app — not a drop-in library. Source readable and
  well-architected for **borrowing** (provider middleware chain, MCP plumbing,
  RAG, shared-typed IPC).
- **Verdict: BORROW / study (strong).** AGPL copyleft caution: direct
  adoption/derivation may force AGPL on CAPT source; borrow architecture patterns,
  not the Electron shell.

## Continue.dev

- **License:** Apache-2.0 · ~35k★ · **FROZEN / read-only** (README: repo no longer
  actively maintained; final 2.0.0 release).
- **Architecture:** TS monorepo — shared `core` orchestrator + IDE adapters
  (VS Code, JetBrains, CLI); typed message-passing (core↔IDE, IDE↔React webview);
  LanceDB indexer; config-as-code; MCP manager; agent skills.
- **Local/OpenRouter:** Ollama native (`AUTODETECT`, `ollama/deepseek-r1-32b`);
  OpenRouter first-class with capability overrides.
- **Verdict: AVOID as a dependency** (frozen); **borrow architecture** (core +
  message-passing, block config, skills, MCP, LanceDB indexing).

## Aider + Aider UI wrappers

- **License:** **Apache-2.0** · ~48k★ · **very active** · Python.
- **Architecture:** layered Python — central `Coder` orchestrator (factory by
  `edit_format`), `Model` via **litellm** (massive provider coverage), terminal
  UI, GitRepo auto-commit, commands, repo-map. **No plugin API** — integration
  via the (unofficial, pin-version) Python `Coder.create()` API + built-in slash
  commands + MCP-capable tools.
- **Local/OpenRouter:** Ollama (`ollama_chat/<model>`), LM Studio/any
  OpenAI-compatible local; OpenRouter (`openrouter/<provider>/<model>`).
- **EMBEDDABILITY:** yes — Python library engine (`from aider.coders import
  Coder`), Apache-2.0. **Standout asset for CAPT's real-model governed
  execution.**
- **Wrappers:** Aider WebUI (NiceGUI, Alpha, 0★), aider-web (Node/Express+xterm,
  no auth), Newrev (Apache-2.0, Beta), AiderDesk (React 19 + Tailwind
  orchestration layer with lifecycle hooks + MCP + theming; best governance case
  study). **All immature — pattern references only, not dependencies.**
- **Verdict: ADOPT/EMBED Aider's engine** behind CAPT's bounded-driver boundary
  (pin version, preserve Apache-2.0 NOTICE). Borrow wrapper patterns only.

---

## License compliance summary

| Source | License | Fork/embed? |
|---|---|---|
| NextChat | MIT | ✅ |
| AnythingLLM | MIT (core) | ✅ (but full-stack heavy) |
| Aider | Apache-2.0 | ✅ (engine) |
| Open WebUI | custom | ⚠️ review terms |
| LobeChat | Apache-2.0 | ✅ |
| Continue | Apache-2.0 | ✅ (but frozen) |
| Enchanted | Apache-2.0 | ✅ (but stale/narrow) |
| LibreChat | MIT | ✅ |
| Chatbox | GPL-3.0 | ❌ |
| Cherry Studio | AGPL-3.0 | ❌ (patterns only) |
| urwid | LGPL-2.1 | ⚠️ |
| Msty | Proprietary | ❌ |