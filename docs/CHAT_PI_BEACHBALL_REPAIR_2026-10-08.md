# Native Chat spinning beachball during Prompt Intelligence — 2026-10-08

## Incident

User screenshot showed an existing "CAPT socket closed mid-frame" system
message and another submission in "proposal_compiling". A macOS beachball
made the native app unresponsive. Do not treat this as evidence that any
remote compiler/model stage completed.

## Observed live evidence

- Existing resident RuntimeService was HEALTHY and responsive, with no
  active TCP compiler request at inspection time. There were no
  nonterminal DriverRuns in the last runtime reconciliation check.
- Installed CAPTNativeMac pid 35973 used about 100% CPU continuously for
  minutes while RuntimeService pid 35709 was idle.
- Sampling pid 35973 for 4 seconds placed 2,798 of 2,937 main-thread
  samples in SwiftUI graph flushing, with repeated LazyVStack/
  LazySubviewPlacements placement work.
- The frozen app did not respond to TIA window activation.
- The prior "socket closed mid-frame" system message was already
  present before this analysis. The underlying socket-close cause was
  not conclusively attributed; RuntimeService restarts during the
  earlier repair period are one plausible contributor.

## Native mitigation

- Replace the transcript's unconstrained `LazyVStack` with a bounded
  regular `VStack` window, initially the last 40 message objects.
- Support "Show older messages" in 40-message increments, capped at
  500 concurrently mounted messages.
- Keep every message in the original encrypted chat session store:
  transcript windowing **does not delete history**.
- Disable whole-transcript phase-change animation and animated
  programmatic scroll requests. Retain normal scroll and stable message
  identity.
- Added deterministic transcript-window regression tests for
  stable IDs, pagination, clamps, and full-history preservation.

## Verification — staged before installation

- Swift suite: **150 passed, 9 skipped, 0 failures**, including 2 new
  transcript-window tests. Test log:
  `~/capt-node-workspace/chat-spin-swift-tests.log`.
- Signed staged app built from the clean isolated source worktree; no
  new paid model calls were issued by this acceptance.
- Old frozen app terminated only after collecting its sample.
- TIA successfully activated the staged replacement and inspected the
  same restored chat (previously not responding), then navigated to
  Missions and back to Chat. The restored chat still displayed the
  historical "CAPT socket closed mid-frame" message. It was no longer
  stuck in a live compiling phase after restart.
- Observed staged-app CPU dropped to **0% while idle** in Missions and
  again after switching back to Chat. Brief UI CPU on navigation
  returned to idle within seconds.
- This verifies recovery of responsiveness in the observed workload.
  It does not prove all older message, huge-code-block, or very-long
  transcript configurations are performance-perfect.

## Remaining limitations

- If a runtime socket closes while a remote compiler command is in
  progress, the external effect may be **indeterminate**. Never
  automatically replay the paid call without original idempotency
  lineage and a durable reconciliation check.
- Existing "Stop waiting for PI" abandons the local wait; it cannot
  guarantee the upstream provider was cancelled.
- RuntimeService currently closes an authenticated connection for
  unexpected server exceptions without returning a typed error to the
  client. Add sanitized server-side diagnostic codes and per-proposal
  receipt reattachment in a subsequent governed change. Do not log
  credentials, full prompts or provider response bodies.
- This repair targets the native Swift layout busy loop; no new
  provider invoices, new model inferences, or mission state transitions.

## Final installed-build acceptance

- Source-only fix: `e7388fd11578b402e3c61d256812ac59d5d6c9a2`.
- Rebuilt and Apple Developer-signed `~/Applications/CAPT.app` **0.5.0**
  from the exact commit; verified strict signature and byte identity with
  the clean staged executable.
- Installed executable SHA-256:
  `5389ea9eda52d37608bfbf61bf4dac95cf74585bab7bc0208f0535f6be03da1f`.
- After removing a stale duplicate app process, one installed instance
  remained. On this final installed build, TIA activated the restored
  chat, navigated Chat → Missions → Chat, and identified the existing
  **Prepare continuation in Chat** control.
- CPU returned to **0.0% idle** after that navigation; no main-thread
  layout beachball observed in the original restored chat scenario.
- Resident RuntimeService was responsive with `status=HEALTHY`,
  distribution `0.5.0`, EventStore head 23370; no daemon restart was
  required for this Swift-only layout change.
- Historical `CAPT socket closed mid-frame` system message remained
  in restored history; this message is not a claim of new IPC failure
  in the replacement build. Its original transport cause is unverified.
- No additional paid provider calls were issued as part of this fix.
