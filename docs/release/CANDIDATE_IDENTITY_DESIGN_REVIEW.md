# Candidate Identity Design Review

Generated: 2026-07-30T17:48:28Z
Context: HY3 release-freeze incident (see ../HY3_RELEASE_FREEZE_INCIDENT.md)
Status: DESIGN REVIEW — owner approval required before any validator change

## The invalid invariant

The final release validator (`capt_solo/release_validation.py`) asserts:

```
manifest.candidate_sha == git rev-parse HEAD
```

where the manifest is a tracked file inside the validated commit. A Git commit ID is a
SHA-1 over the commit metadata AND the tree object — which includes the manifest file's
bytes. Changing the manifest changes the tree, which changes the commit ID. Therefore no
commit can contain its own SHA. The loop HY3 hit is mathematically unavoidable under this
rule.

This is a **release-validator design defect**, not a CAPT source defect. The six security
fixes in `3888f08` are valid and unaffected by this defect.

## Intended identity model in the repository

Evidence found:
- `docs/release/PUBLIC_API_MANIFEST_V0.5.json` carries `candidate_sha` as the release
  provenance pointer.
- `RELEASE_STATE.md` documents `candidate_sha: UNFROZEN` as the pre-freeze state and
  `release_status: HARDENING — NOT RELEASE READY`.
- No CI workflow, no tag-generation script, no signed-manifest procedure exists in the repo.
- The validator's `candidate.manifest_state` check requires `candidate_sha != UNFROZEN`
  when `final=True`; the `candidate.sha_match` check requires `manifest_sha == head`.

The repository has NO explicit design document stating whether `candidate_sha` should name
the source commit, a metadata commit, a tag, or external evidence. The validator silently
assumed "the commit containing the manifest," which is impossible.

## Options compared

### Option A — Source commit + metadata commit

The manifest lives in a *metadata* commit whose parent is the immutable source/code commit.
Validation compares:

```
candidate_sha == git rev-parse HEAD~1     # parent of the freeze commit
```

- Pros: smallest change; keeps the manifest tracked; no external artifacts.
- Cons: requires the freeze commit to be a strict child of the code commit; the validator
  must know it is running from a metadata commit (or compare against `HEAD~1` always, which
  breaks if someone validates from the code commit directly).
- Risk: fragile if the metadata commit is ever squashed or rebased.

### Option B — Annotated tag identity

An annotated (optionally signed) tag `v0.5.0-candidate` points to the source commit. The
manifest records `candidate_sha = <tag target>`. Validation confirms:

```
tag_target == source_commit
manifest.candidate_sha == tag_target
```

- Pros: tags are the natural Git identity for releases; immutable; survives rebases; can be
  signed for supply-chain integrity.
- Cons: introduces a tag-creation step into the release protocol (currently absent); the
  validator must resolve the tag.
- Risk: low; aligns with standard release practice.

### Option C — External generated evidence

The tracked manifest stays `UNFROZEN` (or omits `candidate_sha`). A *generated*,
out-of-tree release-evidence artifact (e.g. `release-evidence.json`) records the checked-out
source SHA after a clean checkout + build. Validation reads the generated artifact, not the
tracked manifest.

- Pros: no self-reference; clean separation of source vs release metadata.
- Cons: the tracked manifest no longer carries the frozen identity (loses in-repo provenance);
  requires a build step to emit evidence.

### Option D — Build provenance identity

The release bundle / wheel build metadata records the checked-out source SHA in generated
build provenance (e.g. `capt_solo-0.5.0.dist-info/release-metadata.json`). The source commit
does not need to contain itself.

- Pros: follows SLSA / build-provenance norms; decouples source from release metadata.
- Cons: requires build-system changes; validation must read installed dist-info, not the
  source manifest.

## Recommendation

**Option A is the smallest correction consistent with the existing design** — the manifest
is already a tracked file and the validator already reads it. The fix is to change the
comparison target from `HEAD` to the *source/code commit* that the freeze commit describes.

Concretely, the cleanest form of Option A that avoids the `HEAD~1` fragility:

- Keep the security-fix commit `3888f08` as the immutable **source/candidate commit**.
- Create ONE metadata commit on top of it that sets `candidate_sha = 3888f08` and contains
  only the manifest edit.
- Validator compares `manifest.candidate_sha == git rev-parse HEAD~1` (the parent of the
  metadata commit) OR, more robustly, `manifest.candidate_sha == <the commit that is the
  source>` resolved via a documented convention (e.g. the most recent commit before the
  metadata commit, or a tag).

If the owner prefers standard release semantics and supply-chain signing, **Option B
(annotated tag)** is the more durable choice and is recommended if a tag step is acceptable.

## What must NOT change without approval

- `candidate_sha` semantics
- `final`-validation behavior
- tag semantics
- metadata-commit behavior
- validator comparison target

HY3 will not implement any of these until the owner selects an option.
