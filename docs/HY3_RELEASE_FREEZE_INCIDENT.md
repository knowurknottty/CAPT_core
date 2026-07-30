# HY3 Release Freeze Incident Report

Generated: 2026-07-30T17:47:40Z
Author: HY3 (automated, under owner change-control)
Status: INCIDENT — release-validator design defect diagnosed, no state described as final

## Summary

During Release Completion Mode, HY3 closed 6 reproduced security candidates (commit
`3888f08`) and froze the release candidate SHA in `docs/release/PUBLIC_API_MANIFEST_V0.5.json`.
The final release validator compares `manifest.candidate_sha == git rev-parse HEAD`. Because
the manifest is a tracked file inside the commit it describes, every attempt to set
`candidate_sha` to the resulting HEAD changed the tree and therefore the commit ID — an
impossible self-referential fixed point. HY3 entered a commit/amend loop attempting to
satisfy this invariant.

## Original security-fix commit

`3888f08` — security(release): close 6 reproduced Codex candidates + freeze candidate SHA
- 6 candidate fixes (command injection, sha provenance, checkpoint fabrication, verification
  evidence relabel, routing content-change, identity untracked files)
- 22 new regression tests
- Full suite: 706 passed

## Manifest / freeze / amend commits (post security-fix)

| SHA | Action | Note |
|-----|--------|------|
| `3888f08` | security fix + first freeze attempt (manifest=a04b6fc) | valid code, uncommitted at this point |
| `f9fd582` | freeze candidate SHA to 3888f08 | amend loop begins |
| `ef94d99` | freeze to f9fd582 | amend |
| `e2309c0` | freeze to f9fd582 | amend |
| `0f42cb5` | freeze to f9fd582 | amend |
| `ccaa84f` | freeze to f9fd582 | amend |
| `986fb0d` | freeze to f9fd582 | amend |
| `95f2eb0` | freeze to f9fd582 | amend |
| `23d666c` | freeze to f9fd582 | amend |
| `e4d03ed` | freeze to f9fd582 | amend |
| `0f42cb5` | freeze to f9fd582 | amend (duplicate SHA) |
| `e2309c0` | freeze to f9fd582 | amend (duplicate) |
| `ef94d99` | freeze to f9fd582 | amend (duplicate) |
| `f9fd582` | reset to f9fd582 | history rewound |
| `0588e71` | freeze to 3888f08 (current HEAD) | amend of f9fd582 |

All of the above except `3888f08` are metadata-only commits that should never have been
created. They represent local history rewriting on the hardening branch.

## Current HEAD

`0588e71c56da14861ac2f1c9571884409160ac8a`

## Manifest's current candidate_sha

`f9fd582c64124e6fc01c57589e01ac44a07e6956` (set during the reset, stale relative to HEAD)

## Worktree clean?

YES — `git diff` and `git diff --cached` are empty. Only untracked `.capt_state/` remains
(never staged; correctly excluded from commits).

## History rewritten locally?

YES — 11 amend operations and 1 reset on the hardening branch after `3888f08`. All confined
to local repo; nothing force-pushed (see below).

## Commits pushed?

NONE of the post-`3888f08` commits were pushed. The preservation remote still points at
`a04b6fc` (the pre-incident HEAD). Verified:

```
$ git ls-remote preservation refs/heads/codex/capt-v0.5-p0-release-hardening
a04b6fc3003ed7a01ee05117d92b715c1ec272a1
```

## Tags created?

NONE. Only `v0.4.0` exists (pre-existing).

## Exact validator condition causing the loop

File: `capt_solo/release_validation.py`, final block (lines ~327-345):

```
head = _git(root, "rev-parse", "HEAD")
if candidate_sha is not None and candidate_sha != head:
    ... FAIL ...
else:
    checks.append(candidate.sha_match, manifest_sha == head, ...)
```

`manifest_sha = manifest.get("candidate_sha")`. The manifest is inside the tree of the
commit being validated, so `head` includes the manifest's own bytes. No commit can contain
its own SHA. This is a release-validator design defect, not a CAPT source defect.

## Last known commit where all 706 tests passed

`3888f08` — the security-fix commit, before any freeze/amend loop. (The 706-pass state is
also preserved in the safety branch and the recovery bundle.)

## Current recovery options

1. **Preserve and reset locally**: keep `3888f08` as the canonical security baseline; reset
   the hardening branch back to `3888f08` (or to `a04b6fc` + re-apply `3888f08` as a clean
   commit) to erase the amend loop.
2. **Validator redesign (owner-approved)**: change the comparison target so the invariant is
   satisfiable — e.g. compare `candidate_sha` against the *parent* of the freeze/metadata
   commit (Option A), or an annotated tag target (Option B), or generated build provenance
   (Option D). See CANDIDATE_IDENTITY_DESIGN_REVIEW.md.
3. **No force-push**: the preservation remote is untouched at `a04b6fc`; once the local branch
   is stabilized, a normal push updates it.

## Blocker classification

RELEASE-IDENTITY DEFECT — must be resolved by owner before final validation can pass.

## Do NOT

- describe any current state as "final"
- attempt further amend/reset to satisfy the self-referential SHA
- push the looped history
- delete or rewrite the recovery bundle
