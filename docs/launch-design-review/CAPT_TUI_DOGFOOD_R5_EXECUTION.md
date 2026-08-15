# CAPT TUI Dogfood - R5 Execution Record

Workflow provenance: Treasure Chest `workflow/capt-tui-dogfood-inversionlabs-r5`, commit `25ab68f5a0ef1f536e9d763a4233d02ad17bde6f`.

Implementation authority: CAPT Core PR #46. Starting CAPT Core SHA: `7cd202c86278b10bd7f3287ac59a30720fa4a762`.

## Reconstruction classification

| Observed specimen symptom | Classification | Source-grounded result |
|---|---|---|
| Header showed `Model ?` after a valid provider/model selection | Confirmed defect | `action_refresh()` rendered `ModelManager.active()` persisted preference, while RUN used widget values. Header, selected widget, and command payload had independent sources. |
| DeepSeek selection later showed an Ollama model | Confirmed defect | `_refresh_models()` always refreshed Ollama on dashboard refresh and always selected the first inventory model, regardless of current provider/widget state. |
| Provider/model switch could retain incompatible state | Confirmed defect | Model list was updated without an explicit scope-bound selection state or invalidation rule. |
| RUN remained visually busy/depressed while no result was visible | Confirmed UI defect with implementation risk | Runtime socket work was performed synchronously in a Textual button callback. The event loop could not render/recover during a long external dispatch, and there was no explicit busy ownership/release path. |
| `p` did not provide obvious Providers navigation | Confirmed affordance defect | The binding called dashboard refresh rather than focusing a provider control. `m` rang the terminal bell only. |
| `p` pressed while prompt had focus did not navigate | Expected behavior / operator interaction | Printable input must remain text input while the prompt editor owns focus. This was not a bug, but the old footer did not make focus behavior clear. |
| `Ollama green` implied a successful provider execution | Projection ambiguity, not evidence of execution | Provider health is an availability probe. DriverRun, task state, evidence, verification, and ClaimGuard remain RuntimeService/EventStore authority. |
| Historical evidence/ClaimGuard appeared to describe current work | Confirmed presentation defect | Dashboard projections were not correlated to the operator’s latest receipt/DriverRun. |

## Implemented correction

`capt_ui/surfaces/tui/app.py` now has one explicit interaction state for the active provider/model. It is the only source used by the header, current-run pane, and command payload.

- Provider is the model inventory scope.
- A provider switch clears the filter and invalidates incompatible model selection immediately.
- Inventory refresh has a generation check so an obsolete refresh cannot mutate a newer provider view.
- The model filter is scoped to the selected provider.
- RUN dispatch executes through a Textual worker, while RuntimeService remains the only command/lifecycle authority.
- Every normal completion and exception path releases busy state and reenables RUN.
- Current Run retains provider/model, receipt status, mission/task, DriverRun ID, and outcome where supplied.
- Evidence is labeled as a latest authoritative projection and tells the operator to correlate it by DriverRun ID.
- Footer bindings now match the screen: provider focus, model focus/filter, prompt focus, checkpoint, projection refresh, and quit.
- Prompt focus retains printable text input. A mouse action can be followed by `p` to recover focus to provider selection.

No TUI callback dispatches a provider request directly, writes EventStore state, manages capabilities/leases, or receives a raw provider credential.

## Added discriminating tests

`tests/test_tui_dogfood.py` covers:

1. Ollama -> OpenRouter -> Ollama provider/model rebinding.
2. Provider-scoped filtering and model invalidation.
3. Selected provider/model equals governed command payload.
4. Successful receipt clears busy state and renders DriverRun/output.
5. Failure clears busy state and renders a safe failure detail.
6. Prompt text consumes printable `p` rather than a global binding.
7. Mouse-to-keyboard recovery with `p` focusing provider selection.

## Validation

```text
Focused dogfood/UI/provider tests: 28 passed
Canonical runtime suite: 373 passed, 12 deselected
Broader tracked suite: 885 passed, 13 skipped, 12 deselected
Clean wheel import outside source tree: passed
Clean wheel `capt --help` includes `tui`: passed
Clean wheel `capt-ui providers --help` includes `--key-ref`: passed
```

## Live governed TUI acceptance

The runtime was restarted from the current installed operator package before live acceptance. No credential value was printed, persisted, or placed in this record.

```text
Ollama
  selected model: muse-glimmer:30b-mlx
  result: accepted
  DriverRun present: yes
  rendered output: CAPT OLLAMA ALIVE

OpenRouter
  selected model: deepseek/deepseek-v4-flash-0731
  result: accepted
  DriverRun present: yes
  rendered output: CAPT OPENROUTER ALIVE
```

Both runs were dispatched through the TUI’s RuntimeService command path. They are not UI-invented completion claims. The result receipt carried the current provider/model and DriverRun correlation identity; authoritative evidence/verification state is available via CAPT projections.

## Remaining rough edges

- OpenRouter uses the intentionally small resolved text catalog. It does not guess provider IDs for catalog labels.
- The dashboard exposes latest authoritative projections, not a bespoke per-DriverRun historical browser. The current receipt makes correlation explicit; a richer correlated-history view is future product work, not an authority workaround.
- The TUI uses Textual-native focus traversal rather than a copied command palette or provider-browser layout.

Final classification: `TUI_DOGFOOD_INVERSIONLABS_ACCEPTANCE_PROVEN`
