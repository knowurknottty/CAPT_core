# Candidate Freeze Protocol (Option A: Source + Metadata Commit)

Status: APPROVED — owner decision 2026-07-30
Applies to: CAPT Core v0.5 release hardening

## Why a commit cannot contain its own Git SHA

A Git commit ID (SHA-1) is computed from the commit metadata (author, committer,
message, parents) AND the tree object — the complete set of file blobs and their
paths, including the manifest file that records `candidate_sha`.

If you write `candidate_sha = <this commit's SHA>` into the manifest and commit,
the tree changes, so the resulting commit ID is different from the value you just
wrote. There is no fixed point. Any process that tries to make
`candidate_sha == HEAD` inside the same commit enters an infinite amend loop.

This is a mathematical property of Git object hashing, not a CAPT defect.

## Definitions

### Source Commit

The immutable commit containing implementation, tests, documentation, manifests,
and release content. This is the software being released. `candidate_sha` names
this commit.

### Metadata Commit

A commit created immediately on top of the source commit that contains ONLY
release metadata:

* frozen candidate metadata
* release evidence references
* generated hashes
* release timestamps
* generated manifests / SBOM / reports

It MUST NOT modify implementation, tests, APIs, schemas, runtime behavior, or
implementation documentation.

## Freeze sequence

1. Complete and verify the source commit (all tests green, clean tree).
2. On a fresh metadata commit, set `candidate_sha` in
   `docs/release/PUBLIC_API_MANIFEST_V0.5.json` to the SOURCE commit SHA.
3. Commit as metadata-only.
4. Run `capt release validate --final`. It must report `ok: true`.

## Validation sequence

The validator detects context automatically:

* If `candidate_sha == HEAD` → validating the SOURCE commit (source context).
* If `candidate_sha` is an ancestor of HEAD → validating a METADATA commit; the
  named SHA is the source ancestor, never the metadata commit's own SHA.

`candidate.sha_match` passes when `manifest.candidate_sha` equals the expected
target for the detected context. `candidate.clean_tree` must be clean.
`candidate.manifest_state` must not be `UNFROZEN` under `--final`.

## Recovery procedure

If a freeze attempt produces a commit/amend loop:

1. Stop. Do not keep amending.
2. Create a safety branch at the current HEAD.
3. `git bundle create` of `--all` for immutable backup.
4. Reset the release branch to the last known-good source commit.
5. Re-create ONE metadata commit with `candidate_sha` = source SHA.
6. Verify `capt release validate --final` passes.

## Invalidation rules

A release candidate is INVALID if:

* `candidate_sha` is `UNFROZEN` under `--final`
* `candidate.sha_match` fails
* `candidate.clean_tree` fails (dirty tree)
* the metadata commit contains implementation changes
* `candidate_sha` is not an ancestor of HEAD
* hashes in evidence do not match built artifacts

To fix: return to the source commit, apply the change, rebuild, create a NEW
metadata commit. Never amend the source commit's history.
