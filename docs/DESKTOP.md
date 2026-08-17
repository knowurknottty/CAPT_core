# CAPT Desktop

CAPT currently has two desktop tracks with deliberately different claims.

## Tk operator MVP

The Python/Tk surface is a real thin client/view-model proving ground over the authenticated runtime/operator boundary.

Classification: **OPERATOR MVP / reference / fallback**, not a polished native product.

It must not own RuntimeService logic, EventStore writes, capability decisions, evidence promotion, or completion state.

## SwiftUI track

`capt_ui/surfaces/desktop_swift/CAPTCoreDesktop` is a Swift Package/client contract. It models the same operator projections used by CLI/TUI while leaving CAPT authority in the existing local runtime service.

Classification: **LIBRARY / CLIENT CONTRACT**, not a shipped `.app` executable.

```zsh
cd capt_ui/surfaces/desktop_swift
swift build
```

A successful library build is not evidence of a distributable/notarized native application.

## Relationship to current TUI work

The active PR #47 cognition/provider cockpit is presently implemented in the Textual TUI path. It should inform the eventual native operator UX, but desktop parity should not be claimed until the native client implements and proves equivalent governed controls.

## Product gate

The native desktop product remains a later usability/distribution milestone. Signing, notarization, packaging, auto-update, platform acceptance, and full provider/control parity require their own evidence.