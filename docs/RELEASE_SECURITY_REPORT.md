# Release Security Report

## Status

Not a release clearance. The repository-wide Codex Security scan is active and
its canonical findings/coverage artifacts have not been finalized.

## Confirmed remediation in this candidate

`CheckpointStore` previously used `mission_id` directly in a checkpoint
filename. A value containing path separators could escape `.capt/checkpoints`
under the configured local root. The `0.5.0` candidate now accepts only bounded
filename-safe identifiers and has a regression test for traversal rejection.

## Scan scope in progress

The active scan covers the whole `capt-solo` repository, including Python
runtime code, plugin tools, shell scripts, tests, package metadata, and docs.
It focuses on secret exposure, unsafe release artifacts, hidden network or
persistence behavior, and unsupported public claims.

## Remaining release gate

Do not publish until the active scan's sealed report, findings JSON, coverage
JSON, and manifest are complete and reviewed.
