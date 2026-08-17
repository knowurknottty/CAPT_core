# TERRA PR #47 installed-wheel acceptance — 2026-08-17

## Classification

`INSTALLED_WHEEL_VERIFIED_WITH_CORRECTIONS`

Scope: exact-head installed-wheel behavior for the exercised CAPT paths only. This does not establish live-provider acceptance, cross-model restart continuity, destructive rollback, Cohort durability, #49 closure, native-desktop readiness, deployment readiness, or release readiness.

## Authority and source identity

- Repository: `knowurknottty/CAPT_core`
- PR: #47, `feat: add governed prompt assembly provenance`
- Tested PR head: `4ee85af818008c2536faaaefa0e7ec00ac2a39c4`
- Parent: `4334657a919f74803e65d9b01aa5054d6d7b9a61`
- Original PR-head parent verified: `e104c4a56dd77604b4396f4e12d62a91864670bc`
- PR base observed at verification: `533ef470f7ccaf4488922b6d39171eca9ed83a1a`; this differs from the supplied historical base SHA, `fix/v07-ouroboros-lifecycle-terra` had moved.
- Public-doc `main` observed: `cc93c4e9fb8c756d224e2f256828d648b47eedc4`
- PR #47 head was independently re-fetched before evidence creation and matched `4ee85af...`.
- Clean clone, detached then evidence branch; no source-tree import was used in installed testing.

## Correction

Defect found: `tests/capt_runtime/test_ouroboros_lifecycle.py` launched the service with `runpy.run_path('desktop/capt_runtime_service.py')`, a checkout-relative source-path assumption. The installed wheel contains the module and the public `capt start` path correctly uses `python -m desktop.capt_runtime_service`; the test harness did not.

Correction commit: `4ee85af818008c2536faaaefa0e7ec00ac2a39c4` (`test: launch runtime lifecycle through installed module`). It changes exactly that launch from `runpy.run_path(...)` to `runpy.run_module('desktop.capt_runtime_service', run_name='__main__')`. No production module changed.

The corrected exact head was rebuilt and tested in a new clean clone and a new fresh virtual environment.

## Build artifact

- Host: macOS 26.4.1 (25E253)
- Build Python: CPython 3.9.6
- Build frontend/backend: `build 1.4.4`; isolated setuptools backend required by `setuptools>=68.0`
- Project distribution/version: `capt-solo 0.5.0`
- Wheel: `capt_solo-0.5.0-py3-none-any.whl`
- Wheel SHA-256: `152febe1dab1148d007e84f4461c369533ba4628d8f6306836ffcd84dd0ec1d5`
- sdist: `capt_solo-0.5.0.tar.gz`
- sdist SHA-256: `f00b73f1506c2f8bda3ce71a4fc9443cc28d3bb3d64803c87c1522e68de273ae`
- Wheel `RECORD` captured during verification. Required installed members were present: approval dispatch/binding/planner/runtime/service/checkpoint/human-approval aggregate; desktop RuntimeService/RuntimeClient/RuntimeCommandService; generated `capt_contracts`; `capt_ui` operator and Textual TUI.

## Fresh-install provenance

Fresh venv: `/tmp/terra-pr47-wheel-rerun/installed-venv`; wheel installed non-editably with `pytest` only as the test runner and declared `textual` dependency resolved from wheel metadata. Test CWD was `/tmp/terra-pr47-wheel-rerun/sandbox`; `PYTHONPATH` was empty; `PYTHONNOUSERSITE=1`; interpreter used `-I`.

All critical imports resolved under that fresh venv’s `site-packages`, not under the repository checkout:

- `capt_runtime`; `capt_runtime.approval_dispatch`; `capt_runtime.model_approval_binding`
- `desktop.capt_runtime_service`; `desktop.desktop_runtime_client`; `desktop.m1_command_service`
- `capt_ui`; `capt_ui.operator.runtime`
- generated `capt_contracts`

`capt --help`, `capt-ui --help`, and `capt start` executed from installed console scripts. `capt start` launched the installed `desktop.capt_runtime_service` module, authenticated a `RuntimeClient`, advertised `request_model_prompt_approval`, created an approval, returned an idempotent exact retry, accepted an approval decision, persisted `HumanApprovalRequested` then `HumanApprovalDecided`, and created a checkpoint containing `humanApprovalVersions` at version 2.

## Installed functional and adversarial evidence

Installed isolated regression suite: `46 passed, 6 skipped`.

It exercised installed modules and real installed process launch for:

- prompt approval planning, durable request/decision, capability self-description, binding-field digest changes, durable one-use admission, same-use replay, different-second-use rejection, and use-time expiry;
- mismatches of mission, task, driver run, resource root, provider, model, requested context, human-verification preference, driver kind, executable selector, and prompt/assembly/dispatch digest; all asserted fail closed by the installed suite;
- conflict on request-ID recreation, stable outer-idempotency retry, and fresh idempotency identity;
- outbound dispatch digest substitution rejection immediately before driver dispatch;
- human-approval checkpoint accounting, compatible optional v1 checkpoint field, restart/reconstruction, and no unknown-human-approval aggregate failure;
- provider and prompt intelligence paths; Textual operator path including OFF -> APPROVE -> RUN, approval projection invalidation after edit/settings changes, and runtime-backed receipt behavior;
- Ouroboros lifecycle, process restart, durable idempotency, crash-boundary handling, and no repeated external work.

The 6 skips were intentionally skipped existing tests, not passes.

## Source regressions on corrected head

- approval security: `8 passed`
- focused prompt/provider/TUI/operator selection: `20 passed, 6 skipped`
- Ouroboros lifecycle: `18 passed`
- `tests/capt_runtime`: `397 passed, 12 deselected`
- full repository: `871 passed, 57 skipped, 12 deselected`
- contract generation: `files written/changed: 0`
- contract drift: `DRIFT CHECK: OK (11 generated files match the schema source)`
- `git diff --check`: exit 0

## Five-pass recursion ledger

1. Factual/source reconstruction: re-fetched PR metadata and refs; clean-cloned exact sources; inspected `pyproject.toml`, setuptools discovery, console scripts, wheel contents, sdist, and `RECORD`.
2. Authority/invariant review: traced RuntimeService/EventStore, RuntimeCommandService, checkpoint, approval-binding, provider, operator, and TUI paths; verified runtime authority rather than UI receipt authority.
3. Adversarial/failure-path review: exercised installed fail-closed binding, expiry, single-use, replay/conflict, dispatch-substitution, restart/crash, checkpoint compatibility, and TUI invalidation tests.
4. Evidence/provenance calibration: isolated environment, empty `PYTHONPATH`, `-I`, site-packages provenance assertions, artifact hashes, exact counts, skipped/deselected separation, and LOCAL-002 exclusion.
5. Simplification/final verification: removed the sole checkout-relative lifecycle-test launcher by a one-line retained regression correction, rebuilt from the correction SHA in a new clone/venv, reran installed and source gates, regenerated contracts, and checked the final diff.

## Quarantine and remaining evidence gaps

D-09 remains unchanged: Hermes LOCAL-002 identifiers remain operator-supplied, remotely absent/unverified metadata and were not used as evidence.

This gate does not prove live Ollama/OpenRouter/OpenAI-compatible authentication or transport, Model A -> shutdown/restart -> Model B continuity, destructive provider/tool-kill rollback, Cohort durability, #49 security closure, native desktop app readiness, production deployment, or public-release readiness.

## Next unresolved gate

Live intended-provider acceptance from the corrected exact PR head, with authenticated provider transport and provenance-bound behavior, remains unresolved.
