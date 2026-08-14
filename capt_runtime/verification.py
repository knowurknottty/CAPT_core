"""Verification pipeline and ClaimGuard (M0-B, ADR-0120/0126/014).

The verification pipeline INDEPENDENTLY establishes:
- repository was read successfully,
- expected analysis artifact exists,
- artifact checksum matches,
- observation corresponds to accessible source,
- no unauthorized repository writes occurred,
- no unauthorized shell or Git mutation occurred,
- capability leases covered every allowed action,
- driver did not emit authoritative CAPT state,
- completion claim is proportionate to evidence.

ClaimGuard may accept ONLY bounded statements (ADR-014). It rejects overclaims
("The issue was fixed.", "The repository was secured.", "The change was merged.",
"The code was deployed.", "All vulnerabilities were found.", "No mutation was
possible.") unless independently proven — which M0-B does not attempt.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from .contracts import digest

# Statements ClaimGuard is permitted to accept in M0-B (bounded, evidence-backed).
_ALLOWED_CLAIM_STATEMENTS = frozenset(
    {
        "Repository inspected in read-only mode.",
        "Analysis artifact produced at the recorded artifact location.",
        "No repository modification was detected by the specified verification checks.",
        "The reported observation is supported by the cited source and verification result.",
    }
)

# Overclaims ClaimGuard must reject unless independently proven (M0-B: never).
_FORBIDDEN_CLAIM_SUBSTRINGS = (
    "was fixed",
    "was secured",
    "was merged",
    "was deployed",
    "all vulnerabilities",
    "no mutation was possible",
)


class VerificationFailure(Exception):
    pass


class ClaimRejected(Exception):
    pass


def verify_repository_unchanged(
    target_path: str, before_digest: str
) -> bool:
    """Independently confirm the target repository content hash is unchanged.

    Uses a recursive, symlink-respecting content digest over the target tree.
    """
    after = _tree_digest(target_path)
    return after == before_digest


def _tree_digest(path: str) -> str:
    root = Path(path)
    if not root.exists():
        raise VerificationFailure("target path does not exist: %s" % path)
    h = __import__("hashlib").sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            try:
                h.update(p.resolve().as_posix().encode("utf-8"))
                h.update(p.read_bytes())
            except OSError:
                continue
    return "sha256:" + h.hexdigest()


_GIT_BASELINE_NOT_CAPTURED = object()


def capture_git_status(target_path: str) -> Optional[str]:
    """Capture porcelain status before a driver dispatch.

    ``None`` means the target is not readable as a Git repository.  An empty
    string is a real clean-repository baseline, not an absent baseline.
    """
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=target_path,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    return res.stdout if res.returncode == 0 else None


def verify_no_git_mutation(
    target_path: str, before_status: Any = _GIT_BASELINE_NOT_CAPTURED
) -> bool:
    """Confirm that dispatch introduced no Git-status delta.

    A supplied pre-dispatch baseline makes existing operator dirt harmless;
    only a state change after that baseline is a driver-attributable mutation.
    The omitted-baseline behavior remains the legacy absolute-cleanliness check
    for existing callers that do not own a dispatch boundary.
    """
    after = capture_git_status(target_path)
    if before_status is _GIT_BASELINE_NOT_CAPTURED:
        return after is None or after.strip() == ""
    if before_status is None:
        return after is None
    return after is not None and after == before_status


def verify_artifact(path: str, expected_digest: str) -> bool:
    p = Path(path)
    if not p.is_file():
        raise VerificationFailure("expected artifact missing: %s" % path)
    actual = "sha256:" + __import__("hashlib").sha256(
        p.read_bytes()
    ).hexdigest()
    if actual != expected_digest:
        raise VerificationFailure(
            "artifact digest mismatch: %s != %s" % (actual, expected_digest)
        )
    return True


def guard_claim(statement: str) -> str:
    """ClaimGuard: accept only bounded, evidence-backed statements.

    Returns the accepted statement; raises ClaimRejected on overclaim.
    """
    s = statement.strip()
    for bad in _FORBIDDEN_CLAIM_SUBSTRINGS:
        if bad in s.lower():
            raise ClaimRejected(
                "overclaim rejected by ClaimGuard (M0-B): %r" % s
            )
    if s not in _ALLOWED_CLAIM_STATEMENTS:
        raise ClaimRejected(
            "claim statement not in M0-B allowed set (must be evidence-backed "
            "and bounded): %r" % s
        )
    return s


def build_artifact_hash_evidence(
    mission_id: str,
    artifact_path: str,
    artifact_digest: str,
    collected_by: Dict[str, Any],
    evidence_id: str,
    task_id: Optional[str] = None,
    collected_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an authoritative EvidenceRecord (kind=artifact_hash).

    Conforms to the FROZEN evidence.schema.json EvidenceRecord contract.
    CAPT-constructed only (trust=capt_authoritative). The verification
    result cites this evidenceId in supportingEvidenceIds.
    """
    import time as _time
    return {
        "schemaVersion": "1.0.0",
        "evidenceId": evidence_id,
        "missionId": mission_id,
        "taskId": task_id,
        "evidence": {
            "kind": "artifact_hash",
            "artifactPath": artifact_path,
            "artifactDigest": artifact_digest,
        },
        "collectedBy": collected_by,
        "collectedAt": collected_at or _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "trust": "capt_authoritative",
    }


def build_command_exit_evidence(
    mission_id: str,
    command: str,
    exit_code: int,
    output_digest: str,
    collected_by: Dict[str, Any],
    evidence_id: str,
    task_id: Optional[str] = None,
    collected_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an authoritative EvidenceRecord (kind=command_exit).

    Conforms to the FROZEN evidence.schema.json EvidenceRecord contract.
    """
    import time as _time
    return {
        "schemaVersion": "1.0.0",
        "evidenceId": evidence_id,
        "missionId": mission_id,
        "taskId": task_id,
        "evidence": {
            "kind": "command_exit",
            "command": command,
            "exitCode": exit_code,
            "outputDigest": output_digest,
        },
        "collectedBy": collected_by,
        "collectedAt": collected_at or _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "trust": "capt_authoritative",
    }


def build_verification_result(
    target_path: str,
    before_digest: str,
    artifact_path: str,
    artifact_digest: str,
    observed_by: str,
    claim_id: Optional[str] = None,
    supporting_evidence_ids: Optional[list] = None,
    verified_at: Optional[str] = None,
    before_git_status: Any = _GIT_BASELINE_NOT_CAPTURED,
) -> Dict[str, Any]:
    """Independently verify and return a VerificationResult-shaped record.

    This is CAPT-authored (trust=capt_authoritative), not driver output.

    Returns a dict containing:
    - The contract-conforming VerificationResult (all required frozen-schema
      fields: claimId, strategy, verifiedAt; no forbidden additionalProperties).
    - A '_view' key carrying view-level annotations (checks, trust, observedBy)
      that are NOT part of the frozen contract and must NOT be passed to
      require('VerificationResult', ...). The stored/committed event payload
      uses only the contract-conforming subset; callers strip _view before
      require() or commit. The view layer merges _view into query responses.
    """
    import time as _time
    repo_unchanged = verify_repository_unchanged(target_path, before_digest)
    no_git = verify_no_git_mutation(target_path, before_git_status)
    artifact_ok = verify_artifact(artifact_path, artifact_digest)
    if not (repo_unchanged and no_git and artifact_ok):
        raise VerificationFailure(
            "verification failed: repo_unchanged=%s no_git=%s artifact_ok=%s"
            % (repo_unchanged, no_git, artifact_ok)
        )
    evidence_ids = supporting_evidence_ids or ["ev-" + digest({"artifact": artifact_digest})]
    record: Dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "verificationId": "vr-" + digest(
            {"claim": claim_id, "target": target_path, "artifact": artifact_digest}
        ),
        "claimId": claim_id,
        "strategy": "artifact_hashing",
        "status": {"kind": "verified", "supportingEvidenceIds": evidence_ids},
        "verifiedBy": {"actorId": "verification_pipeline", "kind": "verification_plane"},
        "verifiedAt": verified_at or _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
    }
    record["_view"] = {
        "observedBy": observed_by,
        "checks": {
            "repositoryUnchanged": repo_unchanged,
            "noGitMutation": no_git,
            "artifactPresent": artifact_ok,
        },
        "trust": "capt_authoritative",
    }
    return record


def build_contradicted_verification_result(
    claim_id: str,
    contradicting_evidence_ids: list,
    observed_by: str,
    verified_at: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a contract-valid persisted negative verification.

    Contradiction requires already-recorded, real evidence.  The human-readable
    reason is deliberately view metadata because the frozen status contract only
    carries stable evidence identifiers.
    """
    import time as _time
    if not contradicting_evidence_ids:
        raise VerificationFailure("contradicted verification requires evidence")
    record: Dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "verificationId": "vr-" + digest(
            {"claim": claim_id, "contradicting": sorted(contradicting_evidence_ids)}
        ),
        "claimId": claim_id,
        "strategy": "invariant_check",
        "status": {
            "kind": "contradicted",
            "contradictingEvidenceIds": list(contradicting_evidence_ids),
        },
        "verifiedBy": {"actorId": "verification_pipeline", "kind": "verification_plane"},
        "verifiedAt": verified_at or _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
    }
    record["_view"] = {
        "observedBy": observed_by,
        "trust": "capt_authoritative",
        "reason": reason,
    }
    return record


def strip_view(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return a contract-conforming copy with _view removed.

    Use before require('VerificationResult', record) or before committing
    the event payload to the EventStore.
    """
    return {k: v for k, v in record.items() if k != "_view"}
