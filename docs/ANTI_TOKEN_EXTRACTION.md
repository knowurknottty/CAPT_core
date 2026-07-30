# Anti-Token-Extraction Component (v0.4.1)

Optional, independently degradable capability. Runs as a **local child process
over stdio** (JSON-RPC 2.0). No network, no embedding into CAPT memory/CTP/KHSB.

## Design constraints (hard requirements)

| Requirement | Implementation |
|-------------|----------------|
| Optional, independently degradable | Registered as `anti-token-extraction` capability in `candidate` lifecycle; failure degrades ONLY this capability via `reg.degrade(..., affected_scope="anti-token-extraction")` |
| Local child-process stdio only | `AntiTokenExtractionComponent` spawns the REAL upstream package via `python -m anti_token_extraction.server` (FastMCP stdio); `rtk_compress` over stdio |
| Cache mode off | `ATEManifest.cache_mode == "off"` enforced by `save_manifest` (`_validate_manifest`) and re-checked in `compress()` |
| Sensitive-input refusal enabled | `is_sensitive_input()` refuses credential *assignments* (password=, api_key=, bearer, private key, recovery code, seed phrase, env secret). Bare tokens (AKIA…, ghp_…) are extraction targets, NOT refused |
| No credentials in MCP arguments | Spawn args carry only `--cache-mode off --refusal on`; no secrets ever passed |
| No embedding into memory/CTP/KHSB | Component lives in `capt_solo/components/`; never writes to those stores |
| Pinned upstream recorded | `UPSTREAM_REPO` + `PINNED_COMMIT` in `ATEManifest`; `verify_pinned_commit()` confirms install matches |
| Legacy cache purge on bootstrap | `purge_legacy_cache()` removes `ate_cache/` etc. during `bootstrap()` |
| Failure degrades only ATE | `extract()` raises `ComponentUnavailable`; caller degrades only this capability |

## Files

- `capt_solo/components/__init__.py` — public exports
- `capt_solo/components/anti_token_extraction.py` — `AntiTokenExtractionComponent`, `ATEManifest`, `register_capability`, `bootstrap_anti_token_extraction`, `purge_legacy_cache`
- `capt_solo/components/anti_token_extraction.mcp.json` — Hermes MCP template (stdio, cache off, refusal on, no creds)

## Lifecycle

1. `bootstrap()` — idempotent. Purges legacy cache, writes manifest with
   `installed_commit = PINNED_COMMIT`. Second call is a no-op.
2. `discover()` — reports `absent` / `present-unverified` / `present-ok`.
3. `health_check()` — spawns the child process, confirms `rtk_compress` tool.
4. `compress(text)` — refuses sensitive input, spawns the real upstream
   `python -m anti_token_extraction.server`, calls `rtk_compress`, returns
   `{"ok": true, "output": "<compressed>", "component": "anti-token-extraction",
   "filter": "auto"}`. Raises `ComponentUnavailable` on any failure.
   `extract(text)` is a deprecated alias that calls `compress()` and never
   returns credential matches.

## Capability registration

`register_capability(reg)` registers `anti-token-extraction` as `candidate`,
`optional=True`, `independently_degradable=True`, with the pinned upstream
metadata. It is NOT auto-verified; verification requires proof evidence.

## Degradation scope

When the component fails, the caller (plugin/CLI/release) calls:

```python
reg.degrade("anti-token-extraction", "component_degraded",
            affected_scope="anti-token-extraction")
```

ClaimGuard then reports the capability as "degraded on anti-token-extraction
only … not globally revoked". Other capabilities (memory, CTP, KHSB, governance,
ClaimGuard, plugin loading, core runtime) remain fully operational.

## Verification

`tests/test_v04_anti_token_extraction.py` covers the 9 required scenarios:
component absent, healthy installation, incorrect commit/version, MCP startup
failure, unsafe cache configuration, secret-bearing schema rejection, scoped
degradation, bootstrap idempotency, legacy-cache purge behavior.

`verify_runtime.py` runs 8 `component.ate_*` checks (warn-only, so an absent or
degraded component never blocks core verification). `doctor.sh` emits
`v04.anti_token_extraction` (pass when healthy+pinned; warn when absent/degraded).

## Known limitations

- The component invokes the REAL upstream `anti_token_extraction` package
  (`python -m anti_token_extraction.server`, FastMCP stdio). The canonical
  source is `https://github.com/knowurknottty/anti-token-extraction@b68adac…`,
  pinned and provenance-verified via `direct_url.json` at install time.
- Compression uses the upstream RTK algorithm; false negatives are possible.
- No cryptographic attestation of the installed child process beyond commit pin.
