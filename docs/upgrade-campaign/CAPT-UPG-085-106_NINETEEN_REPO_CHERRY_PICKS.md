# CAPT-UPG-085…106 — Diamonds from 19 repositories

| | |
|---|---|
| Date | 2026-10-17 |
| Target | `knowurknottty/CAPT_core` `main` @ `c1a05bb` + CAPT-Bot R5 |
| Method | Shallow clone of each repo at its default-branch HEAD (dates below); docs and source read for the parts relevant to CAPT; claims tagged **V** reproduced · **V-code** source-read · **R** reported by the project, not reproduced · **P** proposal |
| Output | 22 backlog items appended to `capt_upg_025_backlog.json` (now 75 items, `upg_queue.py validate` → valid, acyclic) |

`stablyai/orca` was listed twice; analysed once.

## 0. Licence gate (read first)

| Repo | Licence | What CAPT may take |
|---|---|---|
| microsoft/mxc, akitaonrails/ai-memory, ranxianglei/billion-context, anomalyco/opencode, stablyai/orca, zeronsh/zeron, trymirai/uzu, ruvnet/ruflo, xingkongliang/skills-manager | MIT | Code with notice |
| anthropics/claude-plugins-official, yyjeqhc/webcodex, xerj-org/xerj, android/skills, longbridge/gpui-kit | Apache-2.0 | Code with notice + NOTICE file |
| lexmount/moli | Apache-2.0 / MIT dual | Code with notice |
| cloudflare/quiche | BSD-2-Clause | Code with notice |
| hydra-db/hydradb | **AGPL-3.0** | **Design ideas only.** Copying code would impose AGPL network terms on CAPT. |
| clash-verge-rev/clash-verge-rev | **GPL-3.0** | **Design ideas only.** |
| anthropics/claude-code | **Proprietary** ("All rights reserved", Commercial Terms) | **Ideas only**; its bundled plugins are not separately licensed in that repo. The Apache-2.0 copies in claude-plugins-official are the reusable ones. |

## 1. Ranked diamonds

Ranked by (risk closed or leverage gained) ÷ (effort), against CAPT's current open gates (UPG-042 jail, R5 seam, Kanban R2, Cloud Run migration, verification honesty).

| Rank | Item | Source | Why it ranks here |
|---|---|---|---|
| 1 | **UPG-085** MXC as the jail contract | mxc | Replaces a high-risk, three-OS sandbox build (UPG-042/080) with a maintained Microsoft SDK whose core rule matches CAPT's: unenforceable policy is rejected, never silently weakened. |
| 2 | **UPG-087/088** verification panel + coverage ledger | claude-security | Direct structural fix for the pattern seen in three consecutive reviews: verification claims that outrun the mechanism. Status is stamped by code from votes; "clean" requires coverage. |
| 3 | **UPG-101** object-store writer lease + epoch fence | hydradb (ideas) | CAPT's single-writer guarantee is a local `flock`; on Cloud Run with more than one instance it is void. Until this lands, `max-instances=1` is the control. |
| 4 | **UPG-098** enforced import boundaries | webcodex | Turns R5's central invariant ("no second RuntimeService/EventStore/ToolBroker") from prose into a failing test. Small. |
| 5 | **UPG-090/096** typed Sanitized boundary + definition-owned audit policy | ai-memory, webcodex | Secrets-in-ledger becomes a type error; unknown tools audit to empty instead of raw args. CAPT descriptors currently declare no audit policy (V-code: no `audit` in `builtins.py` or `contracts/schema`). |
| 6 | **UPG-104** kill switch complete by construction | quiche | UPG-063's kill switch is only as good as its effect registry. |
| 7 | **UPG-099** shadow-git snapshots per file effect | opencode | Exact reversal handles for UPG-065, without touching the user's `.git`. |
| 8 | **UPG-089** verbatim residue | ai-memory | Cheap, zero-LLM fix for the one real weakness of UPG-072 head+tail bounding. |
| 9 | **UPG-094** reversible model-driven compression | billion-context | Reverses the earlier "defer compaction" call: in CAPT, decompress is a ledger re-selection, so the hard part (reversibility) is already solved. |
| 10 | **UPG-100** governed code mode | opencode | Many governed reads per model turn with no new authority path. |
| 11 | **UPG-102** durable remote command plane | zeron | Phone/second-device steering that rides CAPT-Bot's existing Cloudflare work, with the relay holding no authority. |
| 12 | UPG-091 handoff offer/claim-once · 092 eval-gated promotion · 093 memory aging · 095 benefit accounting · 097 model projection · 103 dispatch attempts · 105 browser + Web Bot Auth · 106 reference intake · 086 learning mode | various | Valuable, lower urgency. |

## 2. Per-repository notes

### microsoft/mxc — HEAD 2026-10-16 · MIT
**What it is.** An embeddable SDK (Rust, .NET, Node; executor binaries take JSON) for running untrusted code under a versioned containment policy, with backends Seatbelt (macOS), Bubblewrap/LXC (Linux), ProcessContainer and others (Windows). Policy 1.0.0 is "published, immutable, current stable"; versions are exact strings.

**Diamonds.**
- *Enforceability is a validation step.* Seatbelt cannot filter by hostname/IP/CIDR, so such policies are **rejected**, not approximated. The docs keep a per-backend "can and can't enforce" table. CAPT's readiness should report the same per-property truth (UPG-085).
- *AF_UNIX `connect()` follows filesystem write grants on Seatbelt.* A broad readwrite root therefore lets the sandbox talk to any listener under it — docker, ssh-agent, gpg-agent, and CAPT's own runtime socket. That is the precise mechanism behind UPG-042's "connecting to runtime.sock fails" criterion.
- *`hostLoopback` trap.* `localhost` in Seatbelt means every address the host is bound to, LAN included; egress-allow without explicit ingress silently blocks your own dev server.
- *`deniedPaths` names `file-read-metadata` explicitly* so a denial outranks the always-on metadata grant — this closes the existence-oracle gap found in OpenWorker's profile.
- *Learning mode*: deny-and-record vs permissive audit; the permissive mode's security warning is returned to the caller, never written into the embedding process's terminal (UPG-086).

**Stress.** Seatbelt (`sandbox-exec`) remains an Apple-deprecated interface; MXC inherits that. Python has no first-party MXC SDK, so CAPT shells out to the executor — pin it by sha256 and treat it as a driver. Windows backends marked experimental are out of scope.

### anthropics/claude-plugins-official — HEAD 2026-10-15 · Apache-2.0
**What it is.** The official plugin marketplace (315 entries; external plugins pinned by `ref` + `sha`; immutable slugs with a `renames` map).

**Diamonds.**
- *claude-security's verification architecture*: inventory → researchers → three-voter refutation panel (one lens each, tally in code, severity can only go down, votes must cite `file:line`) → redactor → renderer that stamps verification status from the vote record. Patch verifier defaults to REJECT. Coverage reports name every directory neither scanned nor skipped and every researcher that didn't return (UPG-087/088).
- The plugin's README states plainly that `.git/config`, `.claude/` hooks and `CLAUDE.md` of a scanned repo all apply, and recommends a sandbox for untrusted repos — the same class as the git-config execution fixed in PR #201.

**Already present in CAPT.** Pinning: `CAPT_Skills.lock.json` already pins `commit`, `tree` and per-skill `sha256`, so no item was added for that.

### akitaonrails/ai-memory — HEAD 2026-10-16 · MIT
**What it is.** Cross-harness long-term memory: lifecycle-hook capture, git-backed markdown as source of truth, SQLite as rebuildable index, zero-LLM default path.

**Diamonds.** Typed `Sanitized<T>` boundary (090); handoff claimed exactly once, moved to offer-mode after a real incident where an unrelated session consumed the baton (091); executable eval gate with before/after bodies and base sha256 (092); rule-promotion budget ("would removing this cause a mistake?") (092); retention formula with access weighting and LLM-free tier-down (093); verbatim residue of literal tokens from dropped text (089).

**Overlap.** Its "markdown is truth, DB is derived" mirrors CAPT's "ledger is truth, projections are derived" — validation, not a pick.

### ranxianglei/billion-context — HEAD 2026-10-17 · MIT
**What it is.** A proxy/plugin that injects `compress` / `decompress` / `search_context` / `acp_status` tools so the model folds consumed ranges itself, keeping the prefix cache intact. Accompanied by a paper with an explicit claims register ([V]/[A]/[P] — the same discipline as CAPT's legend).

**Diamonds.** Reversible, model-driven, incremental compression (094); content-hash message identity as the cross-turn join key; benefit counters that accrue only while coverage evidence holds (095).

**Stress.** Several client integrations work by installing a MITM certificate. CAPT must not copy that path; it owns its provider drivers, so it needs no proxy at all. Production numbers (174,327 calls, zero window violations) are **R**: self-reported.

### yyjeqhc/webcodex — HEAD 2026-10-16 · Apache-2.0
**What it is.** Self-hosted Server/Runner tool runtime: the Runner on the repo's machine connects out over QUIC/WebSocket; jobs survive disconnects.

**Diamonds.** Definition-owned audit/privacy policy with fail-closed-to-empty (096); model-facing contract rules (097); `workspace-boundaries.toml` layer enforcement (098); "a disconnect is a liveness fact, not a lost-work fact … reconnection never authorizes replay" (already CAPT doctrine as R5 4.7 — validation); computer-use scopes split into read/control/launch.

### anomalyco/opencode — HEAD 2026-10-17 · MIT
**Diamonds.** Shadow-git snapshot service (099); `@opencode/codemode` capability-free interpreter (100); per-path keyed mutex around read-prepare-write file mutations (fold into 099 implementation); tool output spill at 2,000 lines / 50 KiB with 7-day retention (corroborates UPG-072 thresholds).

### hydra-db/hydradb — HEAD 2026-10-15 · AGPL-3.0 (ideas only)
**Diamonds.** Durable writer lease via object-store CAS, expiry by the store's clock, writer epoch as the final split-writer fence; indexes as accelerators never truth; explicit failure when a budget is exceeded instead of unmarked partial data (101). Directly addresses the GCP Cloud Run migration.

### zeronsh/zeron — HEAD 2026-10-15 · MIT
**Diamonds.** Durable command entries executed only by the owning engine, marked processed before execute (102); `AuthState` vs immutable `WorkspaceScope`; repository identity = trunk root commit (stable across renames and clones — useful for CAPT's canonical workspace identity); and an honest boundary statement: a UI filter is not a security control and a filename denylist would promise a guarantee it can't keep.

### stablyai/orca — HEAD 2026-10-17 · MIT
**Diamonds.** Run/Task/Dispatch attempt authority and "only positive proof of exit authorizes stop/abandon/retry" (103); best-of-N worktree fan-out; durable writes that fsync file and directory plus a `.bak` ring (small hygiene item for CAPT's non-SQLite state files).

### cloudflare/quiche — HEAD 2026-10-16 · BSD-2
**Diamonds.** `task-killswitch` (104). `tokio-quiche` is a credible transport for ClawRoulette P2P if it moves to QUIC; `qlog` is a standard structured event schema worth mirroring in flight-recorder exports; `h3i` (a protocol-bending HTTP/3 client) is the model for an adversarial guardian fuzz client under UPG-053.

### lexmount/moli — HEAD 2026-10-17 · Apache-2.0/MIT
**Diamonds.** Structure-first headless browser (layout/paint only on demand), single binary, CDP/WebDriver; `moli-url-policy` separates "URL parses" from "this subsystem may load it"; Web Bot Auth (RFC 9421) request signing (105). The README calls it production-ready; that claim is **R**.

### xerj-org/xerj — HEAD 2026-10-17 · Apache-2.0
**Diamonds.** Reference-coding workflow and counted savings (106); token-cost decomposition (envelope + answer + materialized intermediates) used in 097; the security model's "absent guard means allow" lesson for spawned work. Checked: CAPT uses no `contextvars`, so the specific hazard does not exist today; the rule is recorded for future code.

**Note.** The README contains agent-directed install prompts; treated as data.

### ruvnet/ruflo — HEAD 2026-10-14 · MIT
**Assessment.** Large and marketing-heavy; most claims are **R**. Two real things: (1) `ruflo-agntcy`'s CASA envelope — objective compiled once into allow/deny/budget/expiry, enforced by a pure function with no model call at invocation — *validates* CAPT's existing mission authority design rather than adding to it; (2) `ruflo-watermark` (2,627 lines, 41 tests) — keyed SynthID-style text watermarking. Possible future provenance signal for CAPT's local-model outputs; not added to the backlog. Its federation auto-upgrades and auto-downgrades trust "no human in the loop", which conflicts with CAPT's human-only states — rejected.

### anthropics/claude-code — HEAD 2026-10-16 · proprietary (ideas only)
**Ideas.** `hookify` turns observed user corrections into enforcement rules — the CAPT equivalent is a correction → rule *candidate* through the UPG-092 gate, never a direct rule. `security-guidance` layers regex warnings on write, an LLM diff review at turn end, and an agentic review at commit — a three-tier shape for CAPT's verification plane on code effects.

### trymirai/uzu — HEAD 2026-10-17 · MIT
**Assessment.** Rust/Metal on-device inference engine with exact model identity strings (vendor:model:size:quant). A candidate local driver beside MLX; its "traceable computations against the source-of-truth implementation" claim is **R** (tooling present, validation path not verified here). Watch, no item.

### longbridge/gpui-kit — HEAD 2026-10-17 · Apache-2.0
**Assessment.** Rust desktop UI framework; CAPT's UI is Swift. Transferable idea: `gpui-shell` loads JS extensions whose fs/process access is denied unless the manifest grants the narrowest path — matches CAPT plugin direction. No item.

### clash-verge-rev/clash-verge-rev — HEAD 2026-10-17 · GPL-3.0 (ideas only)
**Assessment.** Privileged service IPC binds the owner's uid/gid (or SID + token on Windows); config candidates are validated by the core before apply, with last-good retained. Both reinforce UPG-043 (peer verification on the authority socket). The README carries paid promotions. No new item.

### android/skills — HEAD 2026-10-14 · Apache-2.0
**Assessment.** SKILL.md with `metadata.last-updated` and keywords; explicitly prioritised by "where evaluations show LLMs underperform". The selection rule is worth adopting for CAPT_Skills authoring; no code item.

### xingkongliang/skills-manager — HEAD 2026-10-17 · MIT
**Assessment.** One central skill library deployed to many agents; agents manage skills through the manager instead of writing into folders behind its back (single write path); skill-format detection spec. Useful when CAPT imports third-party skills into Skill Workshop; no item.

## 3. Cross-cutting patterns across the 19

1. **Unenforceable means rejected.** MXC, WebCodex (unknown tool → empty audit), billion-context (no coverage → no accrual), claude-security (no votes → unverified). Every mature project converged on "fail to the honest state". CAPT already says this; items 085/088/095/096 make it mechanical in four more places.
2. **Status is stamped by code from records, never by a model.** claude-security's renderer, Orca's Dispatch authority, ai-memory's claim guards. UPG-087 adopts it for CAPT's verification plane.
3. **Repository config is executable.** Both claude-security's README and opencode's shadow-repo design route around it; CAPT PR #201 now does too.
4. **Authority in a relay or UI is not authority.** Zeron's DO relay, Orca's terminal titles, WebCodex's reconnects. CAPT's EventStore-as-sole-writer is the right shape; UPG-101 extends it to multi-instance cloud.

## 4. Epistemic status

- **V-code:** CAPT has no audit policy on tool descriptors; CAPT's single-writer is a local flock; CAPT uses no contextvars; CAPT skill lock already pins commit/tree/sha256.
- **R (project-reported, not reproduced here):** billion-context production numbers, XERJ's 2.7× token result, moli "production-ready", uzu traceability, ruflo federation claims.
- **Read depth:** MXC policy, Seatbelt and learning-mode docs read in full; claude-security agents/specs read in part; ai-memory architecture invariants and four design docs; billion-context README, technical notes and paper outline; WebCodex architecture/auth; HydraDB architecture; Zeron architecture §1–2; Orca orchestration guide; others at README/manifest/key-module depth. No repo's test suite was run in this wave.
