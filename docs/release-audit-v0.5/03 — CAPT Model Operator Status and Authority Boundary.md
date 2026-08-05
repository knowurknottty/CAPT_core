# CAPT Model Operator Status and Authority Boundary

## Real Hermes Driver — PROVEN_BY_INSTALLED_ARTIFACT
A packaged HermesDriver exists in capt_runtime/drivers/hermes.py. The governed command run_approved_hermes_inspection was proven through the installed wheel with a REAL Hermes 0.20.0 subprocess. 3 real model artifacts with sha256 digests were produced. CAPT owns runtime/lifecycle; the backend owns inference only.

## Source-Side Hermes Process Proof — PROVEN_BY_SOURCE
The Hermes driver was tested source-side in tests/capt_runtime/test_hermes_driver.py with @requires_hermes marker (deselected in default suite but individually proven in prior sessions). The driver dispatches a real Hermes subprocess, receives observations as untrusted (trust=untrusted), ingests them, and produces verification results.

## Local LM Studio Endpoint Availability — REPORTED_ONLY
LM Studio endpoint (http://127.0.0.1:1234/v1) was live during the installed lifecycle proof but is NOT wrapped in a packaged CAPT ExecutionDriver. No installed or source-level proof of a CAPT driver using this endpoint exists.

## Lack of Packaged OpenAI-Compatible CAPT Driver — NOT_PROVEN
No generic OpenAI-compatible packaged CAPT driver exists. The only model-capable packaged driver is HermesDriver (requires Hermes CLI installation). This is a documented limitation, not a defect.

## Frozen ContextSlice and ExecutionDriverWorkOrder Restrictions — PROVEN_BY_SOURCE
Both contracts have additionalProperties: false. No free-text objective field. The objective travels by missionId/taskId reference. The frozen work order carries existing missionId/taskId; TaskResolver.resolve_for_execution resolves the authoritative Task inside CAPTs trusted boundary.

## Rejected Out-of-Band Objective Paths — PROVEN_BY_SOURCE
The TERRA directive prohibits: second objective authority, out-of-band transport, free-text fields on frozen contracts, new IPC protocol, bytecode, dual-layer encryption, ECP runtime integration. All verified absent from the source.

## Authoritative Task-Reference Resolution — PROVEN_BY_INSTALLED_ARTIFACT
TaskResolver.resolve_for_execution was proven in the installed lifecycle: the model objective was persisted in the CAPT Task aggregate; the frozen work order carried missionId/taskId; the resolver fetched the authoritative task inside CAPTs trusted boundary; the bounded prompt was derived inside CAPT.

## Implementation vs Analysis — IMPLEMENTED
The TaskResolver path was implemented (commit 7475dcf) and proven through the installed wheel.

## Current Operational Consequence
CAPT standalone lifecycle IS proven (installed, authenticated, governed, real model backend, checkpoint/restart/resume, adversarial authority). However, GENERAL model-driven engineering remains unproven — the proven model task is a bounded read-only repository inspection, not arbitrary engineering work. The ClaimGuard accepts only the bounded M0-B allowlisted statements.

State plainly: CAPT standalone lifecycle may be proven while general model-driven engineering remains unproven.

Do not mark the model operator complete unless installed authenticated capt harness run evidence exists with the REPAIRED verification contract (b79c4f0 or later). The current installed proof used the b45c4b0 wheel, which predates the verification-contract repair.
