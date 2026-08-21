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

- **Candidate** = an OBSERVATION with conservative, observation-level
  `classification` (`source_file_present`, `project_marker_present`,
  `compiled_artifact_only`, ...), `confidence`, `evidence`, `provenance`,
  `redactions`, `accepted`. A candidate says WHAT was observed — it never
  claims the requested target repository is located. Target-match is a
  SEPARATE aggregate-level conclusion (`source_present` /
  `possible_repository`). HARD INVARIANT: no candidate observation makes a
  stronger target claim than the aggregate supports.
- Each candidate carries durable **provenance**: run_id, strategy, scanned root,
  classification, confidence, accepted — so a candidate removed from the
  enclosing result still answers which run/strategy/root produced it.
- **Rejection** = deterministic serializable reason (`outside_allowed_root`,
  `symlink_escape`, `size_limit`, `depth_limit`, `file_count`, `not_source_tree`,
  `unreadable`...). Both are produced as deterministic JSONL-style ledgers.

## Target criteria (`expected_markers`)

`expected_markers` is **target-corroboration evidence, NOT repository identity
proof.** Conservative v0.7 contract: "any listed exact filename found within the
approved bounded scan (any depth, case-sensitive, subject to ALL bounds)". If
none of the listed markers is observed, a repo-like dir is classified
`possible_repository`/low (Case D) rather than a terminal `source_present`.

Limitations (documented, not silent): monorepos with multiple same-name markers,
markers in vendored / node_modules / dist / nested projects, and symlinked
markers all resolve to the same filename-coincidence test — none implies
identity. A marker beyond discovery bounds is never seen, and a marker symlinked
outside an allowed root is rejected (symlink_escape). Do not treat the marker
mechanism as proof of repository identity.

## Evidence trust semantics

`to_evidence` sets `trust = "capt_authoritative"`. Per the frozen EvidenceRecord
contract this is the ONLY permitted value and means: **CAPT authoritatively
records/holds this evidence** — NOT that the observed claim is verified-true.
Discovery observations are converted to evidence shape (with `sourceObservationId`
retained) and are not themselves verification. Discovery ≠ conclusion; a project
marker ≠ repository identity; consensus/heuristic ≠ proof.

## Redaction

All serialized evidence passes through `redact_text` / `redact_json` which marks
credential-shaped patterns (API keys, Bearer, private keys, password-like
assignments, `*_TOKEN`/`*_KEY`, GitHub/OpenAI/AWS tokens). Classified as
**BEST_EFFORT_REDACTION** — "redacted potential secret", never "all secrets
removed". Discovery never reads or persists file bodies.

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
