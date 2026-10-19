"""Reversible CAPT runtime directory switch. No standalone activation CLI.

Only a governed release controller may call this module: it must obtain a
fresh authenticated quiescence/checkpoint witness and supply independent
authenticated post-release verification. Neither callback may be a local
boolean flag or an untrusted JSON file.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
from typing import Callable, Any
from uuid import uuid4

class ReleaseBlocked(RuntimeError):
    pass

def _durable_json(path: Path, value: dict[str, Any]) -> None:
    # A process may die while writing the temp file. Unique names keep that
    # abandoned file from permanently blocking the next governed recovery.
    tmp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with tmp.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def _validate_candidate(candidate: Path, source_sha: str) -> None:
    if candidate.is_symlink() or not candidate.is_dir():
        raise ReleaseBlocked("CANDIDATE_NOT_A_DIRECTORY")
    marker = candidate / "CAPT_SOURCE_HEAD"
    if not marker.is_file() or marker.is_symlink():
        raise ReleaseBlocked("CANDIDATE_SOURCE_MARKER_MISSING")
    if marker.read_text().strip() != source_sha:
        raise ReleaseBlocked("CANDIDATE_SOURCE_IDENTITY_MISMATCH")
    cli = candidate / "bin" / "capt"
    if not cli.is_file() or cli.is_symlink():
        raise ReleaseBlocked("CANDIDATE_CLI_MISSING")

def switch_runtime(
    active: Path,
    candidate: Path,
    backup_root: Path,
    expected_source_sha: str,
    governed_preflight: Callable[[], dict[str, Any]],
    authenticated_postcheck: Callable[[], dict[str, Any]],
    quiesce_failed_release: Callable[[], bool],
) -> Path:
    """Swap directories only under an independently verified release gate.

    A success returns the retained backup path. On failure, restore the
    original active venv. The caller owns daemon shutdown/restart; this
    module never kills a process, rotates credentials or edits a ledger.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", expected_source_sha):
        raise ReleaseBlocked("INVALID_SOURCE_SHA")
    if not all(callable(x) for x in (governed_preflight, authenticated_postcheck, quiesce_failed_release)):
        raise ReleaseBlocked("AUTHENTICATED_RELEASE_CALLBACKS_REQUIRED")
    active, candidate, backup_root = map(Path, (active, candidate, backup_root))
    if active.is_symlink() or not active.is_dir():
        raise ReleaseBlocked("ACTIVE_RUNTIME_NOT_A_DIRECTORY")
    _validate_candidate(candidate, expected_source_sha)
    if backup_root.is_symlink():
        raise ReleaseBlocked("BACKUP_ROOT_SYMLINK")
    backup_root.mkdir(parents=True, exist_ok=True)
    if len({active.resolve(), candidate.resolve(), backup_root.resolve()}) != 3:
        raise ReleaseBlocked("RELEASE_PATH_COLLISION")
    if len({os.stat(p).st_dev for p in (active, candidate, backup_root)}) != 1:
        raise ReleaseBlocked("RELEASE_NOT_SAME_FILESYSTEM")
    lock_path = active.parent / ".capt-runtime-release.lock"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        gate = governed_preflight()
        if not isinstance(gate, dict) or any(gate.get(k) is not True for k in
            ("authenticatedRuntimeService", "quiescent", "checkpointVerified", "runtimeStopped")):
            raise ReleaseBlocked("GOVERNED_RELEASE_PREFLIGHT_REQUIRED")
        if gate.get("stateRoot") != str(active.parent) or (
            not isinstance(gate.get("checkpointHeadSequence"), int)
            or gate["checkpointHeadSequence"] < 1
            or not str(gate.get("checkpointChainDigest", "")).startswith("sha256:")
        ):
            raise ReleaseBlocked("CHECKPOINT_OR_STATE_ROOT_MISMATCH")
        release_id = expected_source_sha[:12] + "-" + uuid4().hex[:8]
        journal_dir = backup_root / release_id
        journal_dir.mkdir(mode=0o700)
        retained = journal_dir / "runtime-venv-before"
        previous_marker = active / "CAPT_SOURCE_HEAD"
        if previous_marker.is_symlink() or not previous_marker.is_file():
            raise ReleaseBlocked("ACTIVE_SOURCE_MARKER_MISSING")
        previous_source = previous_marker.read_text().strip()
        if not re.fullmatch(r"[0-9a-f]{40}", previous_source):
            raise ReleaseBlocked("ACTIVE_SOURCE_MARKER_INVALID")
        record = {"previousSourceSha": previous_source, "sourceSha": expected_source_sha, "stateRoot": str(active.parent),
                  "checkpointHeadSequence": gate["checkpointHeadSequence"],
                  "checkpointChainDigest": gate["checkpointChainDigest"], "phase":"prepared"}
        journal = journal_dir / "release.json"
        _durable_json(journal, record)
        old_moved = False
        new_moved = False
        try:
            os.replace(active, retained)
            old_moved = True
            record["phase"] = "old_preserved"
            _durable_json(journal, record)
            os.replace(candidate, active)
            new_moved = True
            record["phase"] = "candidate_activated"
            _durable_json(journal, record)
            proof = authenticated_postcheck()
            if not isinstance(proof, dict) or any(proof.get(k) is not True for k in
                ("authenticatedRuntimeService", "sourceDigestsVerified",
                 "eventStoreContinuityVerified", "processHealthy")):
                raise ReleaseBlocked("POST_RELEASE_AUTHENTICATED_VERIFICATION_FAILED")
            if proof.get("sourceSha") != expected_source_sha or proof.get("stateRoot") != str(active.parent):
                raise ReleaseBlocked("POST_RELEASE_SOURCE_OR_STATE_ROOT_MISMATCH")
            record["phase"] = "verified"
            _durable_json(journal, record)
            return retained
        except Exception:
            try:
                if new_moved and quiesce_failed_release() is not True:
                    record["phase"] = "manual_reconciliation_required"
                    _durable_json(journal, record)
                    raise ReleaseBlocked("FAILED_RELEASE_NOT_QUIESCENT")
                if new_moved:
                    os.replace(active, candidate)
                if old_moved:
                    os.replace(retained, active)
                record["phase"] = "rolled_back"
                _durable_json(journal, record)
            except Exception as restore_exc:
                raise ReleaseBlocked("ROLLBACK_INCOMPLETE_MANUAL_RECONCILIATION_REQUIRED") from restore_exc
            raise

def recover_interrupted_switch(
    active: Path,
    candidate: Path,
    backup_root: Path,
    governed_preflight: Callable[[], dict[str, Any]],
    authenticated_restoration_check: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Recover an interrupted, unverified switch without resurrecting execution.

    Operator-invoked only. The preflight must independently authenticate a
    stopped/quiescent RuntimeService and match the checkpoint pinned by the
    switch's journal. Recovery restores bytes; only a separate authenticated
    postcheck can establish process and EventStore continuity.
    """
    if not callable(governed_preflight) or not callable(authenticated_restoration_check):
        raise ReleaseBlocked("AUTHENTICATED_RECOVERY_CALLBACKS_REQUIRED")
    active, candidate, backup_root = map(Path, (active, candidate, backup_root))
    if any(p.is_symlink() for p in (active, candidate, backup_root)):
        raise ReleaseBlocked("RECOVERY_SYMLINK_FORBIDDEN")
    if not backup_root.is_dir() or not active.parent.is_dir():
        raise ReleaseBlocked("RECOVERY_PATH_MISSING")
    lock_path = active.parent / ".capt-runtime-release.lock"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        pending = []
        for journal in sorted(backup_root.glob("*/release.json")):
            if journal.is_symlink() or journal.parent.is_symlink():
                raise ReleaseBlocked("RECOVERY_JOURNAL_SYMLINK")
            record = json.loads(journal.read_text())
            if record.get("phase") not in ("verified", "rolled_back"):
                pending.append((journal, record))
        if not pending:
            return {"status": "nothing_pending"}
        if len(pending) != 1:
            raise ReleaseBlocked("MULTIPLE_PENDING_RELEASES")
        journal, record = pending[0]
        expected_new = record.get("sourceSha", "")
        expected_old = record.get("previousSourceSha", "")
        if any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{40}", v)
               for v in (expected_new, expected_old)):
            raise ReleaseBlocked("RECOVERY_SOURCE_IDENTITIES_MISSING")
        if record.get("stateRoot") != str(active.parent):
            raise ReleaseBlocked("RECOVERY_STATE_ROOT_MISMATCH")
        gate = governed_preflight()
        if not isinstance(gate, dict) or any(
            gate.get(k) is not True for k in (
                "authenticatedRuntimeService", "quiescent", "checkpointVerified", "runtimeStopped"
            )
        ):
            raise ReleaseBlocked("RECOVERY_GOVERNED_PREFLIGHT_REQUIRED")
        if (gate.get("stateRoot") != str(active.parent)
                or gate.get("checkpointHeadSequence") != record.get("checkpointHeadSequence")
                or gate.get("checkpointChainDigest") != record.get("checkpointChainDigest")):
            raise ReleaseBlocked("RECOVERY_PINNED_CHECKPOINT_MISMATCH")
        retained = journal.parent / "runtime-venv-before"
        for p in (active, candidate, retained):
            if p.is_symlink():
                raise ReleaseBlocked("RECOVERY_SYMLINK_FORBIDDEN")
        def marker(p: Path) -> str | None:
            if not p.is_dir():
                return None
            m = p / "CAPT_SOURCE_HEAD"
            if not m.is_file() or m.is_symlink():
                raise ReleaseBlocked("RECOVERY_SOURCE_MARKER_INVALID")
            return m.read_text().strip()
        a, n, old = marker(active), marker(candidate), marker(retained)
        if old is not None and old != expected_old:
            raise ReleaseBlocked("RECOVERY_BACKUP_IDENTITY_MISMATCH")
        # The candidate may be on its original path or may have been moved to
        # active. Any third identity is an unexpected concurrent mutation.
        if a not in (None, expected_old, expected_new):
            raise ReleaseBlocked("RECOVERY_ACTIVE_IDENTITY_MISMATCH")
        if n not in (None, expected_new):
            raise ReleaseBlocked("RECOVERY_CANDIDATE_IDENTITY_MISMATCH")
        if old is not None:
            if a == expected_new and n is None:
                os.replace(active, candidate)
            elif a is not None:
                raise ReleaseBlocked("RECOVERY_AMBIGUOUS_ACTIVE_AND_BACKUP")
            os.replace(retained, active)
        elif a != expected_old or n != expected_new:
            raise ReleaseBlocked("RECOVERY_PREVIOUS_RUNTIME_UNAVAILABLE")
        # A process crash during the postcheck must remain recoverable.
        record["phase"] = "restored_pending_authentication"
        _durable_json(journal, record)
        proof = authenticated_restoration_check()
        if not isinstance(proof, dict) or any(
            proof.get(k) is not True for k in (
                "authenticatedRuntimeService", "sourceDigestsVerified",
                "eventStoreContinuityVerified", "processHealthy"
            )
        ):
            raise ReleaseBlocked("RECOVERY_AUTHENTICATED_POSTCHECK_REQUIRED")
        if proof.get("sourceSha") != expected_old or proof.get("stateRoot") != str(active.parent):
            raise ReleaseBlocked("RECOVERY_PREVIOUS_SOURCE_IDENTITY_MISMATCH")
        record["phase"] = "rolled_back"
        record["recoveryAuthenticated"] = True
        _durable_json(journal, record)
        return {"status": "rolled_back", "sourceSha": expected_old, "journal": str(journal)}
