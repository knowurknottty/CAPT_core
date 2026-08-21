# CAPT Desktop

CAPT has a Python/Tk reference operator surface and a native Swift macOS application line. Both remain thin clients over RuntimeService authority.

## Tk operator surface

The Python/Tk surface is a real projection/control client and remains useful as a reference/fallback. It does not own EventStore writes, capability decisions, evidence promotion, or completion authority.

## Native macOS application

`capt_ui/surfaces/desktop_swift` now contains more than a client-contract library. Current `main` builds the real `CAPTNativeMac` application target with governed chat/approval flow, runtime/provider controls, native session persistence, typed actor-boundary projections, and origin-session-bound asynchronous provider/model updates.

Fresh convergence verification:

```text
swift test                                  -> 64 tests / 7 opt-in skips / 0 failures
strict concurrency + warnings-as-errors    -> PASS
swift test --sanitize=thread                -> 64 / 7 skipped / 0 failures
swift build --product CAPTNativeMac         -> PASS
```

Native encrypted session-cache storage also has explicit private filesystem-permission regression coverage.

## Authority boundary

The app is not a second CAPT runtime and does not call a model provider as an alternate authority path. Consequential state remains admitted through authenticated RuntimeService/EventStore contracts.

The macOS ↔ RuntimeService ↔ MCP disposable-runtime acceptance proves both native Swift and MCP can observe and act on the same authoritative approval/task/DriverRun streams without manufacturing verification or duplicate provider dispatch.

## Distribution boundary

A buildable/tested native executable is **not** the same evidence class as a signed/notarized/distributed release. Final packaging, signing, notarization, update channel, and release-security gates remain separately evidenced.
