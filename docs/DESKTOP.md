# CAPT Desktop

CAPT has two desktop tracks. Their statuses are deliberately distinct.

## Tk desktop — DESKTOP_OPERATOR_MVP

A thin Tk client over the `RuntimeClient`/operator surface. It is a
reference/debug/client/fallback and view-model proving ground, **not** a native
desktop product. It renders runtime status and operator actions through the
shared operator layer.

## Native SwiftUI — LIBRARY ONLY (not yet a shipped app)

`capt_ui/surfaces/desktop_swift/CAPTCoreDesktop` is a Swift Package that
declares a **library** product (`Package.swift` → `.library`), not an
executable/app. It defines value-type projections of the same operator concepts
the CLI/TUI consume (a renderer contract and view-model shape), and builds
cleanly:

```bash
cd capt_ui/surfaces/desktop_swift
swift build     # builds the library
```

**Status: NATIVE_DESKTOP_TRACK_INITIATED.** There is no `.app`/executable
target yet; it must not be represented as a shipped native desktop product.

## Angular truth

No desktop surface is a second runtime. All mutation and authority remain in
CAPT RuntimeService / EventStore.
