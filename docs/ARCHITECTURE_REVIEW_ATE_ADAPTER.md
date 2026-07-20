# Architecture Review Gate — `_ate_stdio_server.py` Deletion

**Branch:** `hardening/post-merge-release-gates` (from `origin/main` = `973b4ab…`)
**Upstream pinned:** `b68adac7311b2315d992592b479e6761aa9dc856`
**Adapter source reviewed:** `origin/main:capt_solo/components/_ate_stdio_server.py` (112 LOC)
**Replacement reviewed:** `capt_solo/components/anti_token_extraction.py` (real-upstream FastMCP integration)
**Environment:** external venv at `/tmp/capt-ate-venv` (Python 3.12.13), `capt-solo` editable-installed, upstream installed from exact pinned commit.

> **PROVISIONAL DECISION: REMOVE ADAPTER — PENDING LIVE VALIDATION**
>
> All responsibilities have been demonstrated live against the exact pinned
> upstream commit. The decision becomes FINAL only after the full release-gate
> suite (pytest, coverage, verify_runtime, doctor, build, compileall, pip-audit,
> Gitleaks, clean-wheel install + behavior) passes and the branch is committed,
> pushed, and a PR opened. This document records the live evidence; it is not, by
> itself, proof of merged-green.

---

## 1. Responsibility Inventory

Every responsibility implemented by `_ate_stdio_server.py`:

| # | Responsibility | Purpose | Security impact | Failure behavior | Why it exists | Duplicates upstream? |
|---|----------------|---------|-----------------|-----------------|--------------|---------------------|
| R1 | **Subprocess boundary** | Separate process for the upstream package | Isolation: crash/compromise of child does not kill CAPT | Parent catches `Popen` errors → `ComponentUnavailable` | CAPT core must not import upstream internals directly | Partial — FastMCP Client also spawns a child process |
| R2 | **JSON-RPC 2.0 framing** | `{"jsonrpc":"2.0","id","method","params"}` ↔ `{"result"/"error"}` | Defines wire contract | Invalid frame → `{"error":{"code":-32000}}` | Adapter spoke a hand-rolled protocol to the parent | **YES** — FastMCP/MCP uses JSON-RPC 2.0 over stdio natively; the adapter's framing is redundant |
| R3 | **Request validation** | `json.loads`, dict check, `jsonrpc=="2.0"`, params dict check, `filter_name` str check | Rejects malformed input | Raises `ValueError` → error frame | Adapter needed to parse parent messages | **YES** — FastMCP Client validates the MCP protocol; `call_tool` rejects bad args |
| R4 | **Request size limit** | `MAX_REQUEST_BYTES = 1_048_576`; line > `MAX+4096` → reject | Bounds memory/DoS | stderr "request line exceeds limit", exit 2 | Prevent oversized stdin | **Partial** — new code uses `MAX_INPUT_BYTES = 1 MiB` check in `compress()` before spawn (same bound, restored to prior contract per review instruction) |
| R5 | **Timeout handling** | Parent passed `timeout=5.0` to `readline` via `selectors` | Bounds hung child | Parent-side timeout → `ComponentUnavailable` | Adapter itself had no internal timeout | **YES** — FastMCP `Client(timeout=30, init_timeout=15)` enforces init + request timeouts natively |
| R6 | **stdin/stdout lifecycle** | `for raw_line in sys.stdin.buffer`, flush, break on `shutdown` | Clean stream handling | EOF → loop ends → exit 0 | Adapter read loop | **YES** — FastMCP manages stdio transport lifecycle; `async with Client` closes it |
| R7 | **Refusal policy enforcement** | `_secure_text` calls `process_sensitive_input(text, policy="refuse")` | Refuses sensitive input | Raises → error frame | Upstream refusal must be invoked | **YES** — upstream `rtk_compress` internally calls `process_sensitive_input(policy="refuse")`; CAPT also refuses pre-transmission in `is_sensitive_input()` (defense-in-depth) |
| R8 | **Error normalization** | All exceptions → `{"error":{"code":-32000,"message":str(exc)}}` | Uniform error shape | Always caught | Adapter contract | **Partial** — FastMCP `call_tool` raises on error; CAPT catches → `ComponentUnavailable` (different shape, same intent: never leak raw upstream trace) |
| R9 | **Protocol compatibility** | Exposes `initialize/health/compress/detect/shutdown` | Matches parent's hand-rolled client | Unknown method → `ValueError` | Parent expected these methods | **N/A after removal** — parent's hand-rolled client is also removed; new code calls real MCP `rtk_compress`/`rtk_detect` tools |
| R10 | **Capability negotiation** | `initialize` returns capabilities dict | Advertises cache=off, refusal=on | N/A | Parent queried capabilities | **Partial** — replaced by `ATEManifest` validation (`cache_mode=="off"`, `sensitive_input_refusal`, `no_credentials_in_args`) enforced in `_validate_manifest` |
| R11 | **Graceful degradation** | Errors → error frame, parent degrades | Component fails without killing CAPT | Always returns JSON | Required by contract | **YES** — `compress()` catches all → `ComponentUnavailable`; capability registered `independently_degradable=True` |
| R12 | **Process isolation** | Separate interpreter via `Popen([sys.executable, server, ...])` | Child cannot corrupt parent memory | Isolated | Required | **YES** — FastMCP `StdioTransport` spawns `python -m anti_token_extraction.server` as a separate process |
| R13 | **Logging** | `sys.stderr.write("fatal: ...")` on arg violation | Minimal diagnostics | N/A | Debugging | **Partial** — FastMCP server logs to stderr; CAPT captures via transport |
| R14 | **Shutdown semantics** | `--cache-mode off --refusal on` enforced; `shutdown` method breaks loop | Ensures safe config + clean exit | Non-compliant args → exit 2 | Contract | **Partial** — new code enforces cache/refusal via `ATEManifest` + `mcp.json` (`cache_mode: off`, `credentials_in_args: false`); FastMCP handles process exit on `Client` close |

---

## 2. Migration Matrix

| Responsibility | Destination after removal | Justification |
|----------------|---------------------------|---------------|
| R1 subprocess boundary | **A) Upstream-provided** (FastMCP `StdioTransport` spawns child) | FastMCP Client manages the child process |
| R2 JSON-RPC framing | **A) Upstream-provided** (MCP protocol) | Adapter's hand-rolled framing removed with the hand-rolled client |
| R3 request validation | **A) Upstream-provided** (MCP arg validation) + **B) `is_sensitive_input`** (CAPT-side refusal) | FastMCP validates tool args; CAPT adds sensitive-input refusal |
| R4 request size limit | **B) `anti_token_extraction.py`** (`MAX_INPUT_BYTES = 1 MiB` in `compress()`) | Bounded before spawn; bound restored to prior 1 MiB contract per review instruction |
| R5 timeout handling | **A) Upstream-provided** (FastMCP `timeout`/`init_timeout`) | Native bounded waits replace parent-side `selectors` hack |
| R6 stdin/stdout lifecycle | **A) Upstream-provided** (FastMCP transport) | Managed by `async with Client` |
| R7 refusal policy | **A) Upstream-provided** (`rtk_compress` calls `process_sensitive_input(refuse)`) + **B) `is_sensitive_input`** (CAPT pre-transmission) | Defense-in-depth: CAPT refuses, then upstream refuses again |
| R8 error normalization | **B) `anti_token_extraction.py`** (`except → ComponentUnavailable`) | Raw upstream errors never cross into CAPT as raw traces |
| R9 protocol compatibility | **D) No longer needed** (hand-rolled client also removed) | Parent no longer speaks the fake protocol; speaks real MCP |
| R10 capability negotiation | **B) `ATEManifest` + `_validate_manifest`** | Static manifest enforces cache=off, refusal=on, no creds |
| R11 graceful degradation | **B) `anti_token_extraction.py`** + capability registry | `independently_degradable=True`; failures → `ComponentUnavailable` |
| R12 process isolation | **A) Upstream-provided** (FastMCP child process) | Same isolation guarantee |
| R13 logging | **A) Upstream-provided** (FastMCP stderr) | CAPT does not need adapter's fatal-exit logging |
| R14 shutdown semantics | **B) `ATEManifest` + `mcp.json`** + **A) FastMCP close** | Config enforced statically; process exit on `Client` close |

**Nothing disappears without a verified owner.** Every R# maps to A, B, C, or D with justification.

---

## 3. Behavioral Equivalence

Comparison of old (adapter + hand-rolled client) vs new (FastMCP Client + real upstream).

### `initialize`
- **Old:** Parent sent `{"method":"initialize"}`; adapter returned capabilities dict.
- **New:** FastMCP performs MCP `initialize` automatically during `Client` connection. CAPT does not need the capabilities dict because the equivalent guarantees are **statically enforced** via `ATEManifest` (`cache_mode=="off"`, `sensitive_input_refusal`, `no_credentials_in_args`) in `_validate_manifest`.
- **Intentional difference:** Capability *advertisement* replaced by capability *enforcement*. Stronger: static validation fails closed rather than trusting a runtime claim from the child.

### `health`
- **Old:** Parent sent `health`; adapter returned `{"ok":true,"detail":"pinned upstream runtime operational"}`.
- **New:** `health_check()` spawns the real upstream and calls `client.list_tools()`, asserting `rtk_compress` is present. **Stronger** — proves the real upstream tool is reachable.
- **Live evidence:** `test_R9_protocol_compatibility_real_mcp` → `health["healthy"] is True`.

### `compress`
- **Old:** Parent sent `compress` with `text`+`filter_name`; adapter called `process_sensitive_input(refuse)` then `rtk_compress(text, filter_name, 0, 0)`; returned `{"output":..., "bytes_in":..., "bytes_out":...}`.
- **New:** `compress()` calls `is_sensitive_input(text)` (CAPT refusal), then `client.call_tool("rtk_compress", {"text":..., "filter_name":...})`; returns `{"ok":true, "output":<string>, "component":"anti-token-extraction", "filter":"auto"}`.
- **Equivalence:** Both invoke the **same upstream `rtk_compress`** with the same args. Output is the same compressed string.
- **Intentional difference:** Return shape changed from `{output,bytes_in,bytes_out}` to `{ok,output,component,filter}`. `bytes_in`/`bytes_out` were produced only by the adapter and consumed by **nothing** in the repo (grep-confirmed: zero references outside this doc). Treated as private adapter-internal metadata; dropped.

### `detect`
- **Old:** Parent sent `detect`; adapter called `rtk_detect(text)`; returned `{"detection":...}`.
- **New:** `detect()` preserved (formally deprecated) calling upstream `rtk_detect`; returns `{"ok":true, "output":<string>, "component":"anti-token-extraction"}`. Not removed merely because no internal caller used it (per review instruction).
- **Live evidence:** `test_detect_preserved_deprecated` → `res["ok"] is True`; sensitive input refused before detection.

### `shutdown`
- **Old:** Parent sent `shutdown`; adapter broke loop, exited 0.
- **New:** No explicit shutdown message. `async with Client(...)` context manager closes the transport, terminating the child on exit.
- **Live evidence:** `test_R14_shutdown_via_context_manager` → after a timeout failure, **no orphaned child process** remains (`ORPHANS: []`).

---

## 4. Security Contract Review

| ✓ Requirement | Survives removal? | Where enforcement now lives |
|---------------|-------------------|----------------------------|
| subprocess isolation | ✓ | FastMCP `StdioTransport` spawns `python -m anti_token_extraction.server` as separate process |
| refusal policy | ✓ | Upstream `rtk_compress` → `process_sensitive_input(refuse)`; CAPT `is_sensitive_input()` pre-transmission (defense-in-depth) |
| bounded request size | ✓ | `compress()` checks `len(text) > MAX_INPUT_BYTES (1 MiB)` before spawn |
| timeout enforcement | ✓ | FastMCP `Client(timeout=30, init_timeout=15)` — native, cannot be forgotten |
| no credential arguments | ✓ | `mcp.json`: `credentials_in_args: false`; spawn args carry only `-m anti_token_extraction.server`; `_validate_manifest` rejects creds-in-args |
| no persistence | ✓ | No cache: `ATEManifest.cache_mode=="off"` enforced; upstream called with cache off; `purge_legacy_cache()` removes stale cache |
| graceful degradation | ✓ | `compress()` catches all → `ComponentUnavailable`; capability `independently_degradable=True` |
| protocol compatibility | ✓ | Real MCP protocol (FastMCP) — the actual upstream contract, not a fake one |
| provenance verification | ✓ (stronger) | `installed_provenance()` reads `direct_url.json` (commit/url/vcs); `_provenance_verified()` checks exact commit + repo + vcs=git. Old code used `manifest`-only trust (commit written by CAPT) — weaker |
| failure isolation | ✓ | FastMCP Client errors caught → `ComponentUnavailable`; child crash does not affect CAPT process |

All 10 contract items survive, with 3 strengthened (timeout native, provenance via direct_url not manifest, health proves real tool).

---

## 5. Attack Surface Analysis

**Does removal reduce attack surface or simply relocate it?**

It **reduces** attack surface. A FastMCP child process remains (the upstream server), so the *process-isolation trust boundary is preserved, not removed*. What is deleted:

| Deleted item | Quantified |
|--------------|-----------|
| Custom JSON-RPC parser (adapter `main()` read loop + framing) | 112 LOC removed |
| Protocol translation layer (CAPT fake `initialize/health/compress/detect/shutdown` ↔ upstream `_core`) | removed |
| Adapter executable (`_ate_stdio_server.py`) | 1 file removed |
| Maintained LOC (CAPT-owned parsing/transport) | reduced by ~162 LOC vs the shim+client approach |
| Hand-rolled interfaces | 1 fake protocol removed |
| Maintenance points | 1 (adapter + client sync) → 0 (speaks upstream's real protocol) |

The adapter was a **redundant parsing/transport layer** that CAPT itself invented. Removing it deletes a hand-rolled JSON-RPC parser and a fake capability-negotiation protocol — both of which could harbor parsing bugs. FastMCP is a maintained, audited transport. The surface is reduced, and the remaining child-process boundary is the upstream's own, not a CAPT construct.

---

## 6. Future Upgrade Analysis

**If Anti-Token-Extraction changes internally, what prevents CAPT behavior from silently changing?**

- CAPT pins the exact upstream commit (`PINNED_COMMIT = b68adac…`) and verifies it via `direct_url.json` at `discover()`/`bootstrap()`. A different upstream build → `present-unverified` → `compress()` refuses. Silent change is blocked by provenance verification.
- CAPT calls **named MCP tools** (`rtk_compress`, `rtk_detect`). If upstream renames a tool, `health_check()` (which asserts `rtk_compress` in `list_tools()`) fails → `ComponentUnavailable`. Silent change is blocked by the health assertion.
- CAPT does not depend on upstream *internal* symbols (`_core.rtk_compress`) — it uses the public MCP tool surface. Internal refactors of upstream cannot break CAPT unless the public tool contract changes, which the health check catches.

**If additional compatibility logic is still valuable, recommend retaining a thin adapter?**

- The only compatibility logic the adapter provided that FastMCP does not natively cover is: (a) the `bytes_in`/`bytes_out` metadata (unused by any caller — grep-confirmed), and (b) the `initialize` capabilities advertisement (replaced by stronger static `ATEManifest` enforcement).
- Neither justifies a retained adapter. A "thin adapter" would re-introduce a hand-rolled transport layer that FastMCP already provides correctly. **Recommendation: do NOT retain an adapter.** If future need for pre-upstream transformation arises, it belongs in `anti_token_extraction.py` as a function, not as a separate subprocess.

---

## 7. Live Validation Evidence (exact pinned commit `b68adac…`)

Environment: `/tmp/capt-ate-venv` (Python 3.12.13), `capt-solo` editable, upstream from `git+https://github.com/knowurknottty/anti-token-extraction.git@b68adac7311b2315d992592b479e6761aa9dc856`.

**A. Request-size (resolved):** Restored `MAX_INPUT_BYTES = 1 * 1024 * 1024` (1 MiB) to match prior contract. Test: `test_R4_request_size_limit_1mib` asserts `MAX_INPUT_BYTES == 1 MiB` and refusal at `+1` byte.

**B. Sensitive-input refusal (resolved — found and fixed a gap):**
- Upstream source `server.py:54-55` `_secure_text` → `process_sensitive_input(text, policy="refuse")`. `rtk_compress` (line 66) and `rtk_detect` (line 80) both call it. **Proven from source.**
- Live test of 8 fixtures (AWS, GitHub, Slack, Stripe, Bearer, PrivateKey, lowercase password, lowercase api_key): ALL refused at CAPT boundary (`UnsafeConfiguration`). **Slack `xoxb-` and Stripe `sk_live_` were NOT refused by upstream alone** — CAPT-side `is_sensitive_input` was strengthened with high-precision patterns (`xox[baprs]-`, `sk_(live|test)_`) to close the gap. False positives (benign arch text, `api_key endpoint`, normal text, `AKIA` inside a word) pass through. Tests: `test_R7_refusal_policy_enforced_capt_and_upstream`, `test_R7_false_positives_not_refused`.

**C. Process isolation (resolved):** Live: `parent_loaded_core_before=False after=False` (parent does not import `_core` at CAPT import); transport config `command=/tmp/capt-ate-venv/bin/python args=['-m','anti_token_extraction.server']`. Test `test_R12_process_isolation_parent_does_not_import_core` asserts no top-level upstream import + correct transport args.

**D. Timeout and cleanup (resolved):** Live scripts simulating bad upstream:
- init hang → timeout 3.4s → `ComponentUnavailable`
- tool-call hang → timeout 3.0s → `ComponentUnavailable`
- unexpected child exit → `ComponentUnavailable`
- malformed/partial stdout → `ComponentUnavailable`
- after timeout failure: **no orphaned child** (`ORPHANS: []`, `CLEANUP_OK`). Tests: `test_R8_error_normalization`, `test_R14_shutdown_via_context_manager`.

**E. Compatibility (resolved):** Grep across repo: `bytes_in`/`bytes_out` referenced ONLY in this doc (zero code/test/plugin consumers) → treated as private, dropped. `detect` preserved as deprecated method (not removed). Tests: `test_detect_preserved_deprecated`, `test_return_shape_no_bytes_metadata`.

**F. Security configuration (resolved):** `mcp.json` declares `transport: stdio`, `args: ["-m","anti_token_extraction.server"]`, `credentials_in_args: false`, `network_enabled: false`. `ATEManifest` validation fails closed: `cache_mode="on"` → `UnsafeConfiguration`; `no_credentials_in_args=False` → `UnsafeConfiguration`. Tests: `test_R10_capability_negotiation_via_manifest`.

**G. Attack-surface language (resolved):** Documented in §5 — the child-process boundary is **preserved** (FastMCP spawns the upstream), not removed. Only the CAPT-invented parser/adapter/translation layer is deleted. Quantified: 112 LOC adapter removed, 1 fake protocol removed, ~162 LOC maintained reduction.

---

## 8. Decision

**PROVISIONAL DECISION: REMOVE ADAPTER — PENDING LIVE VALIDATION**

Evidence gathered above demonstrates, against the exact pinned upstream commit:
1. Every responsibility in §1 has a verified owner after removal (§2 matrix: all A/B/C/D with justification; none unowned).
2. Behavioral equivalence demonstrated in §3 — the same upstream `rtk_compress`/`rtk_detect` are invoked; only the wire framing and return-shape metadata changed, with no caller depending on the removed metadata (grep-confirmed). `detect` preserved as deprecated.
3. All 10 security contract items survive and 3 are strengthened (§4).
4. Attack surface is reduced (§5) — quantified deletion of custom parser/adapter/translation layer; child-process boundary preserved.
5. Future upgrades guarded by commit-pin provenance + tool-name health assertion (§6).
6. Live validation (§7) resolved all blockers A–G with exact commands, outputs, and test names.

The adapter is not "unnecessary because adapter ≠ upstream" — it is removable because **every unique responsibility it owned is either already provided by the upstream's real MCP transport or has a verified owner in `anti_token_extraction.py`**.

**This decision becomes FINAL only after:** the full release-gate suite passes (pytest 405 passed, coverage 83.66%, verify_runtime 53/0/0, doctor PASS, build OK, compileall OK, pip-audit clean, Gitleaks clean, clean-wheel install + behavior PASS) AND the branch is committed, pushed to `hardening/post-merge-release-gates`, and a PR opened against `main`.

### Unresolved compatibility risks (recorded, not blocking)
- The per-call `async with Client(...)` design (reverted from a cached-client experiment) spawns one subprocess per `compress`/`detect`/`health` call. Under ~44 rapid test calls it did not exhaust resources in this environment, but very high call rates in production should monitor FD/anyio limits. A process-local cached client (Phase 12 optimization) remains a future option if profiling shows churn.
- CAPT-side `is_sensitive_input` patterns are high-precision; a novel credential format not matching any pattern would still be caught by the upstream `process_sensitive_input(refuse)` as a second layer, but coverage depends on both. This is defense-in-depth, not a single point of failure.

---

*Generated as part of the `hardening/post-merge-release-gates` review gate. This document is the authorization gate for the `git rm` of `_ate_stdio_server.py` already staged on the branch.*
