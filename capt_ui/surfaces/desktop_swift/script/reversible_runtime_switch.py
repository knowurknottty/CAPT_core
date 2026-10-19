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
    tmp = path.with_name(path.name + ".tmp")
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
        record = {"sourceSha": expected_source_sha, "stateRoot": str(active.parent),
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
