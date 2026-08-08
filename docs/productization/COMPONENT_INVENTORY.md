# CAPT UI Component Inventory (D10)

A single inventory of UI components, each traceable to a concept in the shared
operator contract. Presentation differs per surface (TUI widget vs Desktop
widget vs CLI text); the component log contract is shared. **Reuse:** prefer any
existing `desktop/` rendering where it maps; generalized into `capt_ui/`.

## Top navigation / status chrome

| Component | Concept | CLI | TUI | Desktop |
|---|---|---|---|---|
| StatusBar | runtime status + active model + context | `capt status` | top bar | top bar |
| VerbosityControl | CaveCAPT mode selector | `--verbosity` | key map + menu | segmented control |
| ModelBadge | active model + LOCAL/CLOUD | `capt models use` (UI-1) | panel header | top-bar chip |
| TrafficLight | provider/health status (with text label) | `capt models test` | ●/●/● + label | dot + label |

## Navigation / organization

| Component | Concept | TUI | Desktop |
|---|---|---|---|
| MissionList | mission/session selector | left list | sidebar |
| NewMissionButton | create mission | `+` | button |
| TabBar | Memory/Evidence/Runtime/Approvals/Settings | F-keys | tabs/panels |
| Breadcrumb | current scope (provider/model/mission) | footer | header |

## Conversation / task surface

| Component | Concept | TUI | Desktop |
|---|---|---|---|
| MessageList | conversation / mission transcript | scroll pane | scroll pane |
| PromptInput | task input | input line | text area |
| StreamingOutput | model streaming output | live pane | animated block |
| SourceTag | model output vs CAPT status/evidence | prefix | styling |
| SubmitButton / Send | submit task | Enter | Send |

## CAPT-native surfaces

| Component | Concept | TUI | Desktop |
|---|---|---|---|
| ApprovalPanel | request capability/op/scope/risk + Approve/Deny | dedicated pane | modal + badge |
| EvidenceViewer | Claim→Evidence→Verification→ClaimGuard | viewer | panel/button |
| MemoryPanel | context status, triggers, search, pinned | panel | panel |
| RuntimePanel | health, mission, ledger, drivers, context | panel | dashboard |
| EventTimeline | EventStore events | events tab | runtime inspector |
| CheckpointButton | checkpoint | control | control |
| ResumeButton | resume | control | control |
| StopButton | stop runtime | control | control |
| CancelButton | cancel current task/run | Ctrl-C | control |
| ProviderSettings | provider/model config (UI-1) | model panel | settings |

## Dialogs / feedback

| Component | Concept | Notes |
|---|---|---|
| ErrorBanner | translated, actionable error + next action | every surface |
| ConfirmationDialog | destructive confirm (stop, cancel) | desktop/TUI |
| NotificationBadge | pending approvals | desktop/TUI |
| OnboardingWizard | first-run flow (D9) | desktop/TUI |
| DiagnosticView | detailed/diagnostic output | progressive disclosure |

## Reusable building blocks (borrowed/borrowable, license-aware)

| Block | Source | Why |
|---|---|---|
| Markdown message renderer | rich (Python) / existing desktop sanitizer | streaming + trust-tagging |
| Sanitizer for untrusted output | `desktop/desktop_app.py::sanitize_for_display` (reuse) | anti-spoof, proven |
| Trust-tagging | `desktop_app.py::trust_tag` (reuse) | authoritative vs untrusted |
| Provider key storage | new, key-id reference pattern | never raw keys in UI/logs |
| Terminal rendering | Textual (TUI) | keyboard-first, ssh-safe |
| Tk view-model separation | `desktop/` (reuse/migrate) | thin client pattern proven |

## Accessibility requirements (all surfaces)

- Full keyboard navigation for core controls.
- Readable contrast, scalable text.
- Reduced-motion compatibility.
- Clear focus states.
- No color-only status (traffic light always has a text label).
- Copy/export for evidence and diagnostics.
- Confirmation for destructive actions.
- Streaming distinguishes model output from CAPT status/evidence.
