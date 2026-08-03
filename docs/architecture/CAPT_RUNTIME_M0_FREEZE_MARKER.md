# CAPT Runtime M0 — Freeze Marker

Marker type: immutable freeze manifest document (repository convention; no GitHub
Release published — not authorized).
Date: 2026-08-03
Status: **FROZEN AND VERIFIED** under the recorded test environment.

## Final integrated SHA (at freeze record)

- Freeze record HEAD: `f76b1cb10ff3085f9b729f39e3f2fd62f6851612`
- Composed stack (implementation): M0-A `6665a6a` → M0-B `0d851c4` → freeze `f76b1cb`
- (main does not yet contain M0-A; integration pending owner merge.)

## Contract schema version

- `contractSchemaVersion`: **1.0.0** (`contracts/schema/index.json`)
- Instance `SchemaVersion` const: **"1.0.0"** (`contracts/schema/common.schema.json`)
- Generated bindings: Python `capt_contracts` + TypeScript `types.ts`, drift-clean.

## M0-A proof status

- **PROVEN.** Contract & state proof: language-neutral contracts, generated
  Python/TS bindings, aggregate ownership, transactional event ledger, outbox,
  capabilities/grants/leases/reservation/consumption/revocation, checkpointing,
  replay, idempotency, claim/evidence/verification contracts, authority
  conformance tests. HEAD `6665a6a`.

## M0-B proof status

- **PROVEN.** Read-only ExecutionDriver proof: narrow ExecutionDriver contract,
  DriverRegistry, DriverRunAggregate, read-only capability model, context
  minimization, untrusted observation ingestion, artifact/receipt validation,
  read-only repository inspection, no target-repo mutation, driver
  restart/reconciliation, replay without re-execution, truthful bounded completion
  claims. HEAD `0d851c4`. 51 M0-B targeted tests pass.

## Freeze verification status

- **PASSED.** Fresh re-run at freeze HEAD: schema generate OK, drift OK, tsc OK,
  ruff clean, 47 M0-A + 51 M0-B + 108 capt_runtime + 469 full (44 optional skips),
  10 replay/checkpoint, 23 capability-lifecycle, 10 authority-boundary, 5
  unauthorized-write. No M0-C, no RuntimeAggregate, no RuntimeManifest/Identity,
  no external OpenHarness invocation.

## Known optional CI limitation

- The "Release Security" workflow `python (3.10)` / `python (3.12)` jobs fail
  because they hard-install a **private** `anti-token-extraction` GitHub repo with
  no token (permissions: contents: read, persist-credentials: false). This is a
  pre-existing CI/environmental issue present on the M0-A base branch too; it is
  **not** an M0 product defect. The 44 local skips correspond exactly to the
  optional package's absence. Dispositioned separately (recommend splitting
  required vs optional security jobs); not modified in M0.

## Driver classification

- The M0-B ExecutionDriver (`OpenHarnessDriver`) is a **locally implemented CAPT
  reference driver inspired by OpenHarness**. It performs real read-only local
  repository inspection and writes one analysis artifact to staging. It does NOT
  import, subprocess-invoke, or call any external OpenHarness project, package,
  executable, or service. It is NOT an external OpenHarness integration and NOT an
  adapter over an installed OpenHarness runtime.

## Deferred M0-C scope

- M0-C (governed repository-write proof) has **not started**. When authorized, it
  must occur on a separate branch with explicit authorization. It is out of M0
  scope.
- RuntimeAggregate, RuntimeManifest, and RuntimeIdentity have **not been
  implemented**. RuntimeAggregate is rejected/deferred; the preferred future shape
  is a minimal immutable `RuntimeManifest` (runtimeId + epoch + DriverRegistry
  lifecycle), explicitly excluding mission/task/capability/claim/driver-run state.
  Any such contract requires a separately authorized ADR and must not duplicate
  existing aggregate ownership.

## Authoritative claim (do not overstate)

CAPT Runtime M0 architecture, contracts, authority boundaries, replay/checkpoint
semantics, and read-only reference ExecutionDriver proof are **frozen and verified**
under the recorded test environment. This is not a claim of production readiness.
