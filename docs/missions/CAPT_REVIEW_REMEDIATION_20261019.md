# CAPT Core — independent-review remediation and live release evidence

**Assessment basis:** independent source-review dossier dated 2026-10-18, pinned `40e9a964be9b3bf5480ffd04ebc62364988b978b`. This follow-up is dated 2026-10-19 UTC. The original dossier concluded **PARTIAL_OR_UNVERIFIED** for whole-source review; **that verdict is NOT upgraded here**.

## Remediation matrix

| Dossier item | Merge / tracked fix | Verification achieved | Explicit remaining boundary |
|---|---|---|---|
| R1: forged zero-source RRDS classification | [#230](https://github.com/knowurknottty/CAPT_core/pull/230), merge `7079b84eceb85ac6aa7719545f6bacb43894ba70` | Gate now uses independently refreshed source/risk/directory metadata. 15 RRDS tests passed, including fabricated zero-source and risk suppression | Node read receipts still contain externally supplied evidence references. Full 681-source-file inspection and read-source authentication remain unproven. |
| R2: concurrent Keychain state-key replacement | [#231](https://github.com/knowurknottty/CAPT_core/pull/231), merge `8b220a75c38e11a738e95d16c7af82ebd6d2ba16` | Create-only macOS Keychain initialization, winner reread, fail-closed errors and process-local lock. 35 security tests passed. Disposable macOS Keychain verified missing=44, duplicate-create=45, original key preserved; clean-release code successfully decrypted an existing production event **read-only** | Do not rotate live keys; no intentional production first-start race or corruption drill. |
| R3: memory-trigger authority erosion | [#233](https://github.com/knowurknottty/CAPT_core/pull/233), merge `982af9eb577aa1c1feffa3dd797df4775457a96a` | Inherited higher source retained through lower-authority policy updates, safe ceiling explicitly checked. 67 policy and trigger tests passed with 2-step escalation and serialization fixture | Per-field authority provenance lattice and independent policy admission proof remain future work. **Memory-trigger steps do not constrain actual provider model context-window capability.** |
| R4: blocking Swift RuntimeService IPC | [#235](https://github.com/knowurknottty/CAPT_core/pull/235), merge `3f11800c31252b8e9d2037fc29cf3c195dcfb7f4` | Monotonic connect/frame deadlines, kernel send/receive timeout, independent interrupt hook, no automatic command replay. `swift test`: 171 executed, 9 skipped, 0 failures. Socket-pair fixtures proved partial-header/body stalls fail boundedly | Native Swift app was **built/tested**, not independently installed or exercised through the currently running GUI. |
| R5: unsupported Python 3.8/3.9 promise | [#234](https://github.com/knowurknottty/CAPT_core/pull/234), merge `c5b6f6afcb280f325af9746ba9beebad0df143f6` | `pyproject.toml` now advertises `>=3.10`, consistent with `str.removeprefix` and CI coverage. 48 relevant security/model tests passed. | No Python 3.8/3.9 support claim; verify packaged install separately. |
| Extra: `FrozenDict |=` mutation | Same PR #234 | Rejects in-place union, with root/nested mutation regression and JSON serialization tests | It remains a `dict` subclass: deliberate calls to base `dict` mutators may bypass subclass overrides. A truly immutable mapping plus canonical serialization/dispatch digest revalidation is a separate gate; **do not present R5 as a cryptographic approval-binding proof**. |

All five code PRs above passed GitHub CI checks before merge (11 checks for #230, #231, #233 and #234; 12 for #235). A combined clean-release Python regression run passed **154/154** selected cases covering RRDS, Keychain, MemoryTrigger, FrozenDict, release security, and provider driver. Previously merged provider/bridge reliability fixes remain described in `docs/missions/CAPT_CROSS_PLANE_ROOT_CAUSE_AUDIT_20261019.md`.

## Live RuntimeService promotion

- Release source checkout: `/Users/knowurknot/capt-node-workspace/capt-runtime-release-20261019`, **detached, clean**, pinned `3f11800c31252b8e9d2037fc29cf3c195dcfb7f4`.
- New launchd label `online.inversionlabs.capt-runtime-r20261019`. At initial verification, PID `58567` matched `~/.capt/runtime.pid`.
- RuntimeService authoritative snapshot reported `connected=true`, `source=RuntimeService`, ledger `integrity=ok`, head sequence **27227**.
- Inversion Commander bridge stayed connected; CAPT Workspace MCP exposed **33 runtime tools**. CAPT Node remained connected and scoped.
- Goal watchdog's `PYTHONPATH` now points to the same clean, pinned release source. Its pre-promotion `.plist` was backed up in `/Users/knowurknot/capt-node-workspace/runtime-release-20261019/watchdog-before-runtime-promotion.plist`; promotion receipt in `promotion-receipt.json`.
- The prior runtime label was retired after a bounded healthy-start observation. Rollback must restore the watchdog plist, retire the new runtime job, and restart the old label from the preserved checkout; **do not replace or reconstruct the ledger**.
- Original `/Users/knowurknot/CAPT_core` still has unrelated documentation edits and untracked review evidence; no stash, reset, force-push or overwrite was performed.
- No provider inference or paid model call was dispatched as part of this promotion; existing lost/indeterminate DriverRuns were not replayed.

## Open work and quality limits

1. **Not fully reviewed:** the original RRDS-1 dossier covers only 37 of 681 source files across 11/47 source directories. Coverage numerator/denominator are corrected, but a fake `node_evidence_ref` string has not been independently proven to match a real Node read event.
2. **Not fully frozen:** `FrozenDict` blocks the demonstrated `|=` operator but is still built on mutable `dict`; consumers should validate the approval-bound digest at the ultimate driver boundary and migrate to a real immutable value object.
3. **Not fully attributed:** the policy fix preserves the higher-level effective authority but lacks independent, per-field provenance for overlapping policy providers and source changes.
4. **Native desktop not deployed:** launchd RuntimeService runs current Python; the new Swift transport remains source-tested until a separately governed native-app build/install/GUI certification.
5. **TIA/CAPT Bot UI gap:** last read-only TIA DOM snapshot remained connected but showed a stale `[Errno 2] No such file or directory` conversation note. No evidence says this is caused by the new RuntimeService release; investigate independently.
6. **Provider settlement unknowns:** historic lost DriverRuns and the DeepSeek 4.1 Flash 1017 lost attempt retain `reconciliation_required`; no speculative completion or automatic chargeable replay.

**Certifiable statement today:** five targeted issues remediated in GitHub source and CI; authoritative Python RuntimeService deployed from an independently checked pinned source; overall CAPT Core whole-source review, cross-client recovery and installed native app remain **PARTIAL**, not fully certified.
