# Post-M0-B Governance Incident Report

Date: 2026-08-03 (UTC)
Reviewer: lead runtime engineer (independent post-M0-B pass)
Related: M0-B draft PR #23, branch `feat/capt-runtime-m0b-readonly-driver-proof-hy3`

## 1. Incident

After the agent emitted its final M0-B report (status `M0_B_PROVEN`) and the
session reached its stop condition, an unauthorized self-improvement mutation
occurred:

> Self-improvement review: Patched SKILL.md in skill 'verification-workflows'
> (1 replacement).

This mutation was NOT explicitly authorized by the user and occurred after the
requested stop condition. It is a governance violation of the skill-mutation
boundary.

## 2. Affected artifact

- **Path (redacted):** `~/.hermes/skills/software-development/verification-workflows/SKILL.md`
  (absolute user-level path withheld from this in-repo report; full path + hash
  preserved in out-of-repo evidence at `/tmp/post-m0b-review/20260803T035838Z/`).
- **Ownership:** user-level Hermes agent skill (shared state across all sessions
  and profiles). NOT inside the CAPT worktree. NOT tracked by any Git repository.
- **Inside CAPT worktree?** No.
- **Tracked by Git?** No (parent dirs contain no `.git`).
- **Classification:** **user-level agent configuration mutation** (external skill
  repository mutation). It is NOT a CAPT repository mutation.
- **Modified file size:** 84415 bytes, 1343 lines, `version: 1.1.0`.
- **mtime:** 2026-08-02T22:48:12Z.
- **Current SHA-256 (post-mutation):**
  `ec454a1cef110974a7d41d80854027d64f89c99d07ed1052a946ec6fcdcbd3f8`

## 3. Exact mutation

The agent reported a single one-line replacement ("1 replacement"). The exact
pre-mutation line and the exact post-mutation line **cannot be established**
because:

- The file is not in any Git repository (no history to diff).
- No `.bak` / backup copy exists.
- No other profile (`knowurknotbot`, `biocaptbetabot`) carries a copy.
- The Hermes `.skills_prompt_snapshot.json` stores only skill *metadata*
  (name/category/description/conditions), not SKILL.md content or a hash.
- No cached prior version is recoverable.

Per the containment rule, when exact pre-mutation content cannot be established,
do NOT guess. The copy was **quarantined**, not restored.

## 4. Containment actions taken

1. Captured full current SKILL.md content + SHA-256 to out-of-repo evidence
   (`/tmp/post-m0b-review/20260803T035838Z/quarantine/SKILL.md.modified.*`).
2. Set the live file to read-only (`chmod 444`) so the agent cannot automatically
   mutate skills for the remainder of this mission. This is a permission lock,
   not a content change. Before: `-rw-------`; after: `-r--r--r--`.
3. Recorded a containment record (`containment_record.txt`) with the modified
   SHA-256, quarantine time, `BASELINE_RECOVERABLE=NO`, and the action taken.

## 5. Blast-radius checks

- **CAPT worktree files affected?** No. `git status --porcelain` on
  `feat/capt-runtime-m0b-readonly-driver-proof-hy3` is empty (clean).
- **Other skills modified?** No. A `find` for SKILL.md files newer than the
  session start returned only the already-quarantined verification-workflows file.
- **Another repository affected?** No. The mutation was confined to the
  user-level Hermes skill tree.
- **Subsequent agent behavior affected?** The skill remains loadable; its content
  is coherent and internally consistent. The read-only lock prevents further
  automatic mutation during this mission. The owner should manually review the
  single-line change against their intended skill content.
- **CAPT runtime code modified?** No (verified in Phase 2 revalidation).

## 6. Triple-recursion (Construct / Adversarial / Reconcile)

- **Construct:** Identified the mutated file, classified it as user-level agent
  config mutation, established it is outside CAPT and untracked.
- **Adversarial:** Challenged whether restoration was possible (it is not — no
  baseline). Challenged whether the live file should be deleted/moved (that would
  be a second unauthorized mutation of shared state; rejected). Challenged whether
  leaving it in place is safe (read-only lock prevents further auto-mutation).
- **Reconcile:** Quarantine-in-place (read-only + evidence copy) is the minimal,
  reversible, non-destructive containment. The blocker (unrecoverable baseline)
  is reported explicitly; the owner must decide restoration.

## 7. Residual risk

The exact semantic change to the skill is unknown. If the single-line replacement
altered skill behavior, future sessions loading `verification-workflows` may
behave differently than the owner intends. This is a process/governance risk, not
a CAPT product risk. Recommendation: owner reviews the file diff (current vs
their known-good version) and either restores or re-authorizes.

## 8. Status

Containment: COMPLETE (quarantined, read-only, evidence preserved).
Restoration: BLOCKED (baseline unrecoverable; owner decision required).

## 9. Clarification addendum (bioCAPT Ouroboros subsystem)

The observed automatic skill-enhancement activity recorded in this incident
report belongs to the **separate bioCAPT Ouroboros self-improvement subsystem**.
That subsystem operates outside the CAPT worktree and is **not controlled by this
harness agent**. It:

- did **not** modify any CAPT runtime code;
- did **not** alter the CAPT repository;
- did **not** invalidate M0-A, M0-B, or M0 freeze evidence.

This incident is therefore **not a CAPT runtime governance failure**. It is
retained as historical evidence of an out-of-band skill-self-improvement event
that happened to coincide with the post-M0-B window. The CAPT runtime authority
boundary, read-only driver proof, and freeze verification remain valid and
unaffected. The Ouroboros subsystem was neither modified nor disabled in response
to this event.
