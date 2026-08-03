# External Driver Architecture (Gate A — OpenHarness)

## Topology

```
CAPT DriverHost (frozen M0-B orchestration)
   │  validated ExecutionDriverWorkOrder + ContextSlice
   ▼
OpenHarnessExternalDriver (capt_runtime/external_drivers/openharness/)
   │  protocol translation, env allowlisting, subprocess spawn
   ▼
genuine OpenHarness process  (oh -p "...", isolated venv py3.12)
   │  OpenAI-compatible client → localhost only
   ▼
local Ollama  (127.0.0.1:11434, model ornith-1.0-9b)
   │
   ▼  (returns analysis text)
OpenHarnessExternalDriver.normalize → untrusted CAPT records
   │  observations + artifactCandidate + receipt
   ▼
CAPT ingestion / verification / ClaimGuard  (authoritative)
```

## Package layout

```
capt_runtime/external_drivers/openharness/
  __init__.py      public surface: OpenHarnessExternalDriver, DESCRIPTOR
  adapter.py       ExecutionDriver Protocol impl; spawns oh; lifecycle
  translation.py   work_order → prompt; stdout → untrusted records
  lifecycle.py     run-state tracking; honest resume=unsupported
  sandbox.py       allowlisted subprocess env; path validation
  receipts.py      external execution receipt helper
  errors.py        adapter-specific errors
```

## Adapter responsibilities (owned)

- process invocation (subprocess.Popen of `oh`),
- environment allowlisting (strip hosted keys; set localhost Ollama),
- OpenHarness configuration (sandboxed config dir + settings.json),
- prompt/work-order translation,
- output capture (stdout/stderr),
- lifecycle inspection / cancellation forwarding,
- untrusted-record normalization,
- external-error translation.

## Adapter NON-responsibilities (CAPT owns)

- policy evaluation, capability grants, lease issuance,
- aggregate mutation, authoritative event emission,
- evidence promotion, claim verification, ClaimGuard decisions,
- task/mission completion.

## Isolation properties

- The adapter imports NO OpenHarness Python code; it shells out to the `oh`
  binary. Base CAPT runtime remains importable and usable when OpenHarness is
  absent (verified by test_base_runtime_imports_without_openharness_package).
- The external process receives only: isolated venv `oh`, sandboxed config dir,
  localhost Ollama endpoint, selected local model, read-only target repo, CAPT
  staging dir. All hosted credentials are stripped.
- Network is limited to 127.0.0.1:11434 (verified: only Ollama contacted).

## Lifecycle mapping

| CAPT DriverRunState | OpenHarness (oh -p) | Honest? |
|---------------------|---------------------|---------|
| created | process constructed | yes |
| queued | (n/a; immediate) | n/a |
| running | process alive | yes |
| suspended | not supported | declared unsupported |
| completed | process exit 0 | yes |
| cancelled | proc.terminate/kill | yes |
| failed | process non-zero exit | yes |
| reconciliation_required | process missing/unknown | yes |
| reconciled | mapped from state | yes |

`resume` is explicitly rejected (one-shot process; no fake resume).
