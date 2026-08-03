# ADR: External Execution Driver Selection (Gate A)

- Status: ACCEPTED
- Date: 2026-08-03
- Deciders: CAPT Runtime program (owner-authorized Gate A)
- Supersedes: none
- Superseded by: none

## Context

Gate A requires proving that ONE genuine external agent harness can execute real
work through the frozen CAPT ExecutionDriver boundary while CAPT retains exclusive
authority over governance, capabilities, task/mission state, events, evidence,
verification, ClaimGuard, checkpointing, replay, and completion.

The local CAPT reference driver (M0-B) is NOT sufficient for Gate A — it is a
CAPT-authored reference, not an external harness. A genuine third-party harness
must be selected and executed.

## Decision

Select **OpenHarness** (`openharness-ai==0.1.9`, MIT, HKUDS/OpenHarness) as the
Gate A external harness.

Execute it as a **separate sandboxed subprocess** (`oh -p`) with:
- an isolated Python 3.12 venv (no global install),
- `api_format: openai` forced via a sandboxed config dir,
- `base_url` pointed at a local Ollama OpenAI-compatible endpoint
  (`http://127.0.0.1:11434/v1`),
- a local Ollama model (`ornith-1.0-9b`),
- an allowlisted subprocess environment that STRIPS all hosted credentials,
- `--permission-mode default` (write/shell tools denied in non-interactive mode).

## Constraints considered

- OpenHarness requires Python >=3.10; the system Python is 3.9.6. Resolved with an
  isolated venv (py3.12). This satisfies "isolated environment, no global
  installation" and keeps system Python unchanged.
- DeepAgents (>=3.11) and OpenAI Agents SDK (>=3.10) were not needed because
  OpenHarness executed successfully as candidate 1.

## Consequences

Positive:
- Genuine external execution proven (real `oh` subprocess, local Ollama model).
- CAPT authority boundary preserved (harness returns only untrusted records).
- Reproducible: pinned version, lockfile, local model, no hosted keys.

Negative / residual:
- The external harness is third-party code run with least authority; it is not
  audited line-by-line. Mitigated by subprocess isolation + env stripping + read-
  only task + digest verification.
- `verify_lease` does not enforce max-use exhaustion (frozen M0-B gap). Recorded
  as a residual finding; fixing requires a separate ADR + owner authorization.
- `resume` is not supported by the one-shot `oh -p` execution model; the driver
  descriptor honestly declares `resumeSupported: false`.

## Provenance

- Package: openharness-ai==0.1.9
- Source: https://github.com/HKUDS/OpenHarness (MIT)
- Wheel RECORD hashes captured in SOURCE_AND_LICENSE_EVIDENCE.md
- Dependency lock: external_driver_requirements.lock (pip freeze, 77 packages)
