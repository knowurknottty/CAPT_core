# CAPT Standalone Harness v0.5 — Version Map (version-axis authority)

SHA-bound to: b45c4b005c9171172d055697a55034006bb0f2fe
Date: 2026-08-05

## Declared versions
| Axis | Value | Declared in | Intent |
|------|-------|-------------|--------|
| Product/package | 0.5.0 | pyproject.toml project.version; capt_solo/__init__.py __version__; capt_cli.py --version "capt-solo 0.5.0"; capt_solo.egg-info/PKG-INFO | Release identity of the installable harness |
| Runtime implementation | 0.1.0 | capt_runtime/__init__.py RUNTIME_VERSION; checkpoint manifest runtimeVersion; health identity runtimeVersion | Version of the CAPT runtime core implementation (event-sourced runtime, aggregates, EventStore). Independently low because the runtime core predates the v0.5 product packaging; it is the runtime's own implementation axis, not the product axis |
| Contract schema | 1.0.0 | contracts/schema/*.json; health identity contractSchemaVersion | Wire/contract schema for OperatorMissionIntent, ExecutionDriverWorkOrder, CommandMetadata, claims, checkpoints, envelopes |
| Plugin axis | NOT ESTABLISHED | — | No plugin registry/axis is declared or enforced in v0.5; documented gap for v0.6 (see backlog) |

## Intentionality of runtimeVersion=0.1.0 vs product 0.5.0
The product version (0.5.0) is the version of the SHIPPED standalone
harness package. The runtime version (0.1.0) is the version of the
capt_runtime core implementation. They are DIFFERENT axes by design:
the runtime core is reusable and versioned independently of the product
packaging. Health/capabilities/checkpoints report runtimeVersion=0.1.0
to identify the runtime implementation, and contractSchemaVersion=1.0.0
to identify the wire schema. The product version is reported by the
package metadata and CLI --version.

This axis split was INDEPENDENTLY CONFIRMED by the real model backend in
the installed lifecycle proof (model task 1): the model enumerated all
public version declarations, found all product-level declarations agree
on 0.5.0, and correctly classified capt_runtime's RUNTIME_VERSION=0.1.0
as the runtime implementation axis (not a product mismatch). Evidence:
artifacts/hermes-analysis-dr-model-cmd-51ff69b208ea8412.md.

## Authority matrix note (raw)
Adversarial installed evidence (battery) confirms identity-binding,
schema, operation, and idempotency enforcement at the transport and
runtime layers. See evidence-manifest.md section 5.
