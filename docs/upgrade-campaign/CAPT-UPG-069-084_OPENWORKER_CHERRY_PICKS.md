# CAPT-UPG-069…084 — OpenWorker cherry-picks for CAPT Core / CAPT-Bot

| | |
|---|---|
| Source reviewed | `andrewyng/openworker` @ `e947e44` (2026-10-17), v0.3.4, MIT © 2024 Andrew Ng, Python ≥ 3.10, built on `aisuite>=0.2.0`; sandbox tested against NVIDIA OpenShell 0.1.2 |
| Targets | `knowurknottty/CAPT_core` @ `6f70886` (capt-solo 0.5.0) · `knowurknottty/CAPT-Bot` @ R5-stage-A (runtime tree still mirrors Core) |
| Extends | `docs/upg-025-campaign` @ `befa766` (unmerged). New items appended to `capt_upg_025_backlog.json`; `upg_queue.py validate` → **valid: 53 items, acyclic** |
| Code delivered | PR #201, merged to `main` as `a1489fa`: UPG-069 fix + `readonly_argv.py` (UPG-071 core) |
| Test delta | Full suite baseline `2092 passed / 2 failed`; branch `2174 passed / 2 failed`. The 2 failures are identical and pre-existing (`test_runtime_tool_wiring::…slice_a_registry_and_broker`, `test_capt_recover::…refuses_before_mutation`). +82 tests, 0 regressions. ruff + mypy clean on new files. |

Provenance tags follow the campaign legend: **V** reproduced · **V-code** source-read · **R** reported lead · **P** proposal.

---

## 1. What OpenWorker is, structurally

A local-first desktop agent (Tauri shell + React GUI supervising a Python sidecar, ~162 k lines) whose differentiator is **governance as product UX**: a permission engine with modes, risk classes, human-only floors, an LLM auto-approve reviewer, an approval ladder (one-off → session → run → standing rule → config allowlist), durable wait queue, attendance modes, OS sandboxes (Seatbelt / OpenShell / hidden Windows account), and an append-only hash-chained team board.

Mapped onto CAPT's planes:

| Concern | OpenWorker | CAPT Core / Bot | Verdict |
|---|---|---|---|
| Authority model | Decision engine per tool call (`permissions.py`, 998 lines) | Event-sourced acts, capability grants + leases, HumanApproval aggregate, ToolBroker with world receipts | **CAPT is stronger.** Do not import the engine; import specific floors. |
| Effect classification | `RiskClass` READ/EGRESS/WRITE_LOCAL/EXEC/EXTERNAL; MCP floored to EXTERNAL; overrides may only tighten built-ins | `effectClass` per operation, static, consequential flag must agree | Equivalent. MCP-floor rule already implied by CAPT's untrusted-driver stance. |
| Shell read-only fast path | `readonly.py` classifier behind a session grant | None: every `terminal.exec` is `durable_local` | **Pick (fixed) → UPG-071.** Biggest approval-fatigue win. |
| Deferred-execution files | `.git/hooks/`, CI configs, `.vscode/tasks.json`, `.coworker/` are human-only | Root scoping only | **Pick + extend → UPG-073** |
| Outlives-session authority | `save_skill`, schedule CRUD human-only | Separation of duties planned (UPG-026) | **Pick → UPG-074** |
| Auto-approve reviewer | Second model, one action per request, fail-closed, never reads untrusted content, deny-streak breaker | None (Council is deliberative, not admission) | **Pick as friction-only → UPG-075** |
| Attendance | attended / inbox / auto, answers-on-behalf recorded | HumanApproval durable; no attendance concept | **Pick → UPG-076** |
| Ingestion tracking / taint | `session_facts` works; board `taint` is **dead** (never set) | UPG-061 proposed | **Pick the working half → UPG-077** |
| Team board | Hash-chained log, role-scoped verbs, review→done gate, join tokens, board-as-MCP | Lab Board aggregate (anyone→done), Kanban R1 | **Pick → UPG-078, 079** |
| Sandbox | Seatbelt profile renderer, OpenShell, netproxy, credential copy-in | Docker/InversionSandbox + guardian proxy (stronger in-container), **no host-process jail** | **Pick renderer → UPG-080** (input to UPG-042) |
| SSRF | `web/guard.py`: every hop, pinned connection, mapped-IPv4 handled | Guardian pins; **misses embedded IPv4**; four separate private-range checks | **Fix → UPG-069; consolidate → UPG-081** |
| Context hygiene | `toolresult.py` head+tail spill; `compaction.py` | Unbounded tool messages; headroom finalization | **Pick → UPG-072** (compaction: deferred, see §5) |
| Headless/eval interop | `openworker run`, ATIF v1.7 export, price table | flight recorder, SOMA arena | **Pick → UPG-082** |
| Effort controls | Nearest-rank mapping, recorded requested/effective | Fail-closed, silent `max→xhigh` | **Pick the recording → UPG-083** |
| Single-writer lock | `statelock.py` | `desktop/capt_runtime_service.py` already `flock`s `runtime.lock` | Skip — already present |
| Env hygiene | Strip secret-named vars | Allowlist (`SAFE_PARENT_ENV`) | Skip — CAPT is stricter |

---

## 2. Confirmed defects

### 2.1 CAPT Core: guardian platform-deny bypass via IPv4-embedded IPv6 — **UPG-069, P0, V, fixed in PR #201 (`a1489fa`)**

`destination_allowed()` skipped every deny CIDR whose IP version differed from the resolved address. A dual-stack socket connects `::ffff:a.b.c.d` over IPv4.

```
unrestricted ::ffff:169.254.169.254  True   ← cloud metadata
unrestricted ::ffff:127.0.0.1        True
unrestricted 64:ff9b::a9fe:a9fe      True   ← RFC 6052 NAT64
unrestricted 2002:a9fe:a9fe::1       True   ← 6to4
allowlist    (same set)              True
```

Fix: an immutable builtin floor applied in every mode, judged against `ipv4_mapped`, `sixtofour`, `teredo` and NAT64-embedded addresses; profile `platformDeny` is also judged against embedded IPv4. The floor sits outside `canonical()` so profile and lease digests are unchanged.

**Failure narration.** (1) Persistent leases created before the fix keep the old guardian source until recycled — `guardianSourceDigest` is recorded but never re-checked → UPG-070. (2) Developer-visible: refusals still surface as the guardian's 403; there is no reason code distinguishing "builtin floor" from "profile deny" — add one when UPG-054 lands. (3) Network-layer exploitability additionally requires the guardian container to resolve AAAA records (Docker embedded DNS does) and allow an AF_INET6 socket (succeeds even with `disable_ipv6=1` on most kernels; not verified on Cloud Run's gVisor sandbox — test before relying on that as a mitigation).

**Pattern call-out.** This was found in the 2026-10-09 CAPT-Bot review, never entered the 2026-10-12 UPG-025 backlog (that review targeted Core, and Bot's runtime was byte-identical, so the finding fell between the two), and UPG-025 itself is still on an unmerged branch. Third instance of the recurring shape: findings and evidence documents accumulate faster than they land. UPG-084's disclosure and the queue status `in_review` for 069 are meant to force closure.

### 2.2 OpenWorker upstream (relevant because they shape what we port) — **UPG-084, V**

Reproduced against `e947e44`, git 2.43.0:

| # | Input | `is_readonly_command` | Actual effect |
|---|---|---|---|
| a | `uniq in.txt out.txt` | True, targets in-root | Writes `out.txt`; can overwrite `.git/config` or an existing executable hook (mode preserved on truncate) |
| b | `actionlint -shellcheck=/tmp/x/evil` | True, targets `[]` | Executes the path |
| c | `git status` / `diff` / `log -p` / `show` / `blame` / `grep` in a repo with hostile `.git/config` | True | Executes `core.fsmonitor`, `filter.*.clean`, `diff.external`, `diff.*.textconv`, `post-index-change` via `core.hooksPath` |
| d | Seatbelt profile | — | Allows `file-write*` on all writable roots, no deny for `.git/hooks` etc.; floor exists only in the permission layer |
| e | Board `taint` | — | Plumbed through store/tools/MCP but `engine.tainted` is never assigned; always False |

(a)+(c) chain: two commands, both inside a session read-only grant, no approval card, yield code execution — **if** an in-root file already contains a valid git-config payload (a malicious repo can ship one as a fixture). Honest severity: high for "prompt injection in a cloned repo", low otherwise.

These are in scope per their SECURITY.md ("bypasses of the human-only floors or approval gates … high severity").

---

## 3. The picks, with the design adapted to CAPT's invariants

### UPG-071 — `terminal.inspect` (code delivered: `capt_runtime/tools/readonly_argv.py`)

Why not "downgrade the effect class per call" as OpenWorker does: ToolBroker validates that `consequential` matches the *declared* effect class; a per-call downgrade means a classifier sits inside the authority path and any classifier bug becomes an authority bug. A separately declared `pure_read_only` operation whose adapter refuses before spawn keeps the classifier on the *execution* side of the boundary: a classifier bug yields a refused read, not an unreviewed write.

Design deltas versus upstream:

- **argv only.** No `shlex`, no pipeline grammar, no `$` tracking. CAPT's terminal contract is already argv; pipelines become several governed calls. Removes the parsing surface that most upstream fixes were patching.
- **git rewritten, not trusted.** Every git plan prepends `-c core.fsmonitor=false -c core.hooksPath=/dev/null -c diff.external= -c log.showSignature=false -c gpg.{,ssh.,x509.}program=false -c protocol.allow=never -c core.sshCommand=false --no-pager --no-optional-locks`, appends `--no-ext-diff --no-textconv` (diff/log/show) or `--no-textconv` (blame/grep), and sets `GIT_CONFIG_NOSYSTEM=1 GIT_NO_LAZY_FETCH=1 GIT_TERMINAL_PROMPT=0 GIT_OPTIONAL_LOCKS=0`.
- **Filter drivers can't be neutralized generically** (`-c filter.X.clean=` needs X). Worktree-reading verbs (`status diff blame grep`) set `needs_filter_probe`; the adapter runs `GIT_PROBE_ARGV` (itself hardened) and `finalize_git_argv` neutralizes each configured driver. Test proves both halves: raw verbs execute the hostile stubs; hardened plans execute nothing.
- **Flag-value files are read targets** (`grep -f`, `rg --ignore-file`, `jq --rawfile`, `blame --ignore-revs-file`, `git -C`). Upstream missed `grep --file=/etc/shadow`.
- `uniq`/`xxd` capped at one operand; `actionlint`, `yamllint`, `echo`, `env`, `tr`, `tail -f` dropped.

Known limits (record in ADR-0130): `GIT_NO_LAZY_FETCH` is honored from git 2.44 only — partial clones on older git can still lazy-fetch (network, not exec; `protocol.allow=never` then blocks the transport). LFS content renders as pointers because the lfs filter is neutralized.

### UPG-072 — bounded tool results
`drivers/provider.py:532-542` appends `json.dumps(tool_result)` unbounded. Port `toolresult.py` semantics, but spill to a **content-addressed artifact referenced from the ledger** instead of a temp file, so the full output stays evidence. Keep the marker timestamp-free — prompt-cache stability is a cost line item under the resource governor.

### UPG-073 / 074 — floors
Extend OpenWorker's deferred-execution list with **`.git/config` and `.git/info/attributes`** (finding 2.2c makes them exec vectors) and `.envrc` (direnv). Enforce twice: adapter (refuse without a value-digest HumanApproval) and jail profile (kernel). OpenWorker enforces once, which is finding 2.2d.

### UPG-075 — friction-only reviewer (Engage → Extend → Stress → Synthesize)

- **Engage.** The reviewer's real insight isn't "an LLM approves things" — it's the *input discipline*: it sees only the human's own messages, a frozen known-world snapshot, and one action. The attacker can address the agent but never the judge. Plus asymmetric costs encoded in the prompt and fail-closed parsing.
- **Extend.** In CAPT, the verdict becomes a typed record (`approvalOrigin=reviewer`, model id, prompt digest, known-world digest) usable as evidence in UPG-064's oversight-quality projection. Shadow mode first gives a measured agreement rate against real human decisions before any enablement — a calibration curve, not a vibe. Council (`council.py`) can serve as the reviewer for high-tier asks: dissent routes to the human (fits UPG-067).
- **Stress.** (1) The reviewer is still a model reading attacker-shaped *arguments* (a URL query string, a commit message). OpenWorker relies on the prompt's "data not instructions" rule — that's a mitigation, not a boundary. (2) Correlated failure: same provider family as the agent → same blind spots; require a different model family. (3) Error-unsures during an outage silently convert to human prompts → fatigue spike exactly when people are least attentive; OpenWorker tracks `error=True` separately for this reason. (4) R5 §4.6 says trust changes friction, never proof: any path where a reviewer allow satisfies HumanApproval violates a core invariant.
- **Synthesize.** Ship only after 064 (tiers) and 041 (presence attestation); reviewer scope = batchable low tiers; floors 073/074 untouchable; enforcement of "reviewer ≠ HumanApproval" lives in `authority.py`, not the reviewer.

### UPG-076 — attendance
Scheduled and headless missions currently have only two outcomes for an approval: block forever or fail. `auto` attendance adds the third: answer by fixed least-destructive rule and record every answer-on-behalf as evidence. This is what makes CAPT-KRONOS-style scheduled runs safe to leave unattended.

### UPG-077 — taint from evidence, not self-report
The cautionary tale is OpenWorker's own board: a `taint` column, propagated through API and MCP, rendered by readers — and never set. That's the "verification outpacing mechanism" pattern in someone else's code. CAPT's ToolBroker already knows every executed operation and its backend; derive `ingestedSources[]` there.

### UPG-078 / 079 — board
CAPT-Bot `lab_board.py` lets any non-human actor go `active → done`. Adopt OpenWorker's rule set (review→done only, workers can't close) and its hash-only join tokens + board-MCP so VESPER/AXIOM/Hermes join the Lab Board as role-bound actors. This is the shortest path to the open **Kanban R2 durable multi-actor write/claim** gate.

### UPG-080 — jail renderer
OpenWorker's Seatbelt profile is the most directly reusable code for UPG-042 on the Swift app's host OS. Two fixes on import (deferred-exec denies; metadata existence oracle). `sandbox-exec` has been documented as deprecated by Apple for years yet remains shipped and used by Chromium and Bazel; the ADR must treat it as a defense layer with a live self-test, not the sole control. Linux: Landlock ABI ≥ 4 (kernel ≥ 6.7) for TCP-connect restriction; below that report `unconfined`.

---

## 4. Deliberately not picked

| OpenWorker feature | Reason |
|---|---|
| Permission engine wholesale, modes `bypass-approvals` / `dangerously-bypass-approvals` | Contradicts CAPT's single authority plane; a mode that clears floors is exactly what R5 §4.4 forbids |
| Session/"always allow" grants that replay exact command text | CAPT grants are leases with scope + expiry; exact-text replay is weaker |
| 25+ connectors, OAuth broker cloud service | Breadth play; each connector is an untrusted driver CAPT would have to govern — add on demand via MCP + `mcp.py` |
| Personas marketplace (git-URL install with consent summary) | Interesting, but CAPT's managed/authored skills + Skill Workshop already own this lifecycle; revisit after UPG-026 |
| Slack mention router, channel subscriptions | Useful for parked approvals later (UPG-076 relay); not a Core concern now |
| Context compaction (`compaction.py`) | Valuable, but CAPT's `continuation_context.py` reconstructs from the ledger by design; a model-written summary entering context must be labeled `unverified` and kept out of claim evidence. Revisit after 072 shows whether bounding alone suffices |
| Tauri GUI, STT sidecar, aisuite provider router | Surface/provider layers CAPT already has (Swift app, provider drivers) |

---

## 5. Sequencing

The extended DAG puts **069 (in review) → 070** first: both P0, both small. **072, 076, 083, 084** are immediately ready (no deps). **071** waits on 030 (process-group reaping) because an inspect call that orphans a child is still an ungoverned process. **080** feeds **042**; **073** needs 044 (descriptor-relative FS ops). **075** is last by construction — it depends on tiers, attestation and both floors.

`upg_queue.py ready` now lists 072/076/083/084 alongside the existing P0s; it also reports 028 and 053 as waiting on in-flight 069 because of file-footprint overlap with the guardian.

---

## 6. Cross-domain and provocations

- **Approval fatigue is an attention-economics problem with a known signal-detection shape.** A reviewer that converts the bulk of low-tier asks frees human attention for high-tier ones; the oversight-quality projection proposed on 2026-10-09 (dwell vs review-load) is the measurement that tells you whether it worked. Ship 075 in shadow mode and plot hit/false-alarm against human decisions — an ROC curve per tier.
- **SynSync Pro carry-over.** The same "floors outside the canonical policy" pattern fits the entrainment safety envelope: hard limits (photic flicker in the most provocative 15–25 Hz band per Fisher et al., *Epilepsia* 2005;46(9):1426–1441; peak SPL) as a non-configurable floor beneath user presets, so a preset or a remote config can never narrow them. Same digest-stability trick: the floor isn't part of the preset hash.
- **Publish the delta.** A short public note — "what we changed when porting an Andrew Ng-backed agent's read-only classifier into a governed runtime, and four bugs we reported upstream" — after their fix ships, is a stronger credibility signal than the audit-theater split, because it's adversarial work on someone else's well-funded code with reproducible PoCs.

---

## 7. Epistemic status

- **High confidence:** findings 2.1 and 2.2a–e (reproduced; commands in backlog `evidence`). Test counts (run here, Python 3.13, git 2.43.0).
- **Medium:** network-layer exploitability of 2.1 on Cloud Run/gVisor (policy layer confirmed, socket behavior not tested there).
- **Not verified:** ATIF v1.7 spec details beyond OpenWorker's own docstring (UPG-082 says so); OpenShell internals; OpenWorker's GUI and Rust STT (not read).
- **Read depth:** OpenWorker — permissions, risk, readonly, reviewer (prompt + engine wiring), provenance, audit, session_facts, toolresult, compaction API, unattended, inbox, web guard, netproxy, seatbelt profile, teams model/store/tools/tokens, personas docstrings. Not read line-by-line: engine.py (3004 lines, targeted sections only), connectors, server/manager.py, GUI.
