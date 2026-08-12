# CAPT Discovery Subsystem (v0.7)

`capt_runtime/discovery/` — a governed, evidence-producing discovery capability.
Turns the Chest `MODULE_WISHLIST` items (CAPT Discovery Governor + Project SEAL
Local Discovery) into real, bounded, tested CAPT code.

## Purpose

Resolve "where is the source / which path is the right target?" without repeated
path guessing, circular repository discovery, or confusing a compiled bundle for
editable source. Discovery is a **governed observation**, never authority.

## Threat model

- **Unbounded scans**: bounded by `ScanLimits` (depth/files/dirs/bytes/candidates/
  timeout); no unbounded recursive walks.
- **Escape**: every tokenized path is realpath-resolved and must resolve beneath
  an allowed root, else rejected (`outside_allowed_root` / `symlink_escape`).
- **Mutation**: the scanner's API performs no write/rename/unlink/chmod/execute/
  upload.
- **Capability escalation**: discovery NEVER creates or enlarges a lease. The
  subsystem exposes no grant/issue API; it only RECOMMENDS the next strategy.
- **Secret leakage**: all serialized evidence passes through bounded redaction.
- **Tireless guessing**: the governor forces a mechanism change after three failed
  direct guesses.

## Architecture

```
mission/task
  -> DiscoveryGovernor          (strategy state machine)
  -> bounded discovery strategy
  -> BoundedLocalScanner (SEAL) (read-only, allow-listed, symlink-safe)
  -> candidate observations + provenance + rejection ledger
  -> EvidenceRecord / verification boundary (RuntimeService.record_evidence)
```

## Allowed roots

`BoundedLocalScanner(allowed_roots=(...))` or
`run_discovery(allowed_roots=..., enumeration_root=...)`. Every discovered path
must resolve beneath one declared root. If no roots are declared, the single
explicit scan root acts as its own allowlist.

## Bounds

`ScanLimits` defaults (conservative): max_depth 12, max_files 2000,
max_directories 500, max_bytes_per_file 8 MiB, max_total_bytes 64 MiB,
max_candidates 2000, timeout 30 s. `git status` and other heuristics never
loosen a bound.

## Strategy ladder (escalation)

```
KNOWN_PATH -> FILESYSTEM_ENUMERATION -> CONTAINER_METADATA -> BIND_MOUNTS_AND_VOLUMES
-> IMAGE_LAYERS -> HOST_CHECKOUT -> REGISTRY_OR_REPOSITORY_LOOKUP
-> OWNER_CLARIFICATION -> STOP
```

Unsupported remote strategies (container/image/registry) return an explicit
bounded result (`unavailable`, `not_applicable`, `not_found`, `ambiguous`,
`exhausted`) rather than silently falling through. The governor's position is
monotonic; it terminates at STOP (never loops).

## Three-guess rule (code-level invariant)

After **three failed direct guesses**, the governor forces `FILESYSTEM_ENUMERATION`
— the fourth operation is never another direct guess:
`policy.is_guess()` + `governor.observe()` enforce this and `_forced` latches so
post-force calls cannot re-enter the guess phase. Tested in
`tests/test_discovery_governor.py::test_case_b_*`.

## Candidate vs rejection semantics

- **Candidate** = an observation with conservative `classification`
  (`source_present`, `possible_repository`, `compiled_artifact_only`, ...),
  `confidence`, `evidence`, `provenance`, `redactions`. Never a conclusion.
- **Rejection** = deterministic serializable reason (`outside_allowed_root`,
  `symlink_escape`, `size_limit`, `depth_limit`, `file_count`, `not_source_tree`,
  `unreadable`...). Both are produced as deterministic JSONL-style ledgers.

## Redaction

All serialized evidence passes through `redact_text` / `redact_json` which marks
credential-shaped patterns (API keys, Bearer, private keys, password-like
assignments, `*_TOKEN`/`*_KEY`, GitHub/OpenAI/AWS tokens). Classified as
"redacted potential secret", never "all secrets removed".

## No-remote-upload

`remote_export = disabled` by default. The scanner never initiates remote
transfer.

## No-capability-grant invariant

Proven by `test_authority_no_capability_grant_in_output`: the module exposes no
grant/issue/lease API, and `run_governed_discovery` on `RuntimeService` performs
no aggregate transition, appends no event, and does not enlarge any lease. It
returns evidence-shaped output the caller routes through the canonical
`record_evidence` path.

## Integration point

`RuntimeService.run_governed_discovery(request, metadata)` (additive, read-only)
admits a human/system request, validates roots, runs discovery, and returns a
`DiscoveryResult` + an `EvidenceRecord`-shaped payload (validated against the
frozen `1.0.0` contract), which the caller persists via the normal evidence path.
Frozen contracts are not modified.

## Known limitations

- Container/image/registry enumeration returns explicit `unavailable` on this
  host; it does not attempt a Docker layer walk. Docker availability is not a
  test-suite failure.
- Source classification is heuristic and intentionally conservative: a lone
  `package.json` yields `possible_repository`, not a strong "target found".
- Redaction is best-effort, not exhaustive secret detection.
