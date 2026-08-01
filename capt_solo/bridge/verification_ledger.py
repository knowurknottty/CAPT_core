"""Verification obligation ledger — digest-bound, re-run only on real change.

Fixes the stale verification-loop behaviour: an obligation is bound to the exact
identity of what it verified. A successful result clears the obligation for that
identity, and the obligation is invalidated **only** when relevant governed source
or test configuration actually changes.

Explicitly NOT grounds for re-running:

* an unchanged file remains untracked
* a path changed earlier in the session
* a temporary verifier was removed
* evidence JSON is still present on disk
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA_VERSION = "capt.verification.obligation.v1"


def file_digest(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return ""


def digest_set(paths: Sequence[str]) -> str:
    """Order-independent digest over a set of files (path + content)."""
    entries = sorted({(os.path.abspath(p), file_digest(p)) for p in paths})
    h = hashlib.sha256()
    for p, d in entries:
        h.update(p.encode("utf-8"))
        h.update(d.encode("utf-8"))
    return "sha256:" + h.hexdigest()


def environment_identity() -> str:
    """Identity of the execution environment (not the moment in time)."""
    payload = {
        "python": sys.version.split()[0],
        "impl": platform.python_implementation(),
        "platform": platform.platform(terse=True),
        "executable": sys.executable,
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


@dataclass
class Obligation:
    """One verification obligation, bound to exact digests."""

    obligation_id: str
    source_digest: str
    test_digest: str
    environment_identity: str
    command: Tuple[str, ...]
    result: str = "PENDING"  # PENDING | PASS | FAIL
    evidence_digest: str = ""
    executions: int = 0
    invalidations: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def identity(self) -> str:
        return "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "obligation_id": self.obligation_id,
                    "source_digest": self.source_digest,
                    "test_digest": self.test_digest,
                    "environment_identity": self.environment_identity,
                    "command": list(self.command),
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

    @property
    def satisfied(self) -> bool:
        return self.result == "PASS" and bool(self.evidence_digest)

    def to_dict(self) -> dict:
        out = asdict(self)
        out["command"] = list(self.command)
        out["identity"] = self.identity()
        out["satisfied"] = self.satisfied
        return out


class ObligationLedger:
    """Persistent, digest-bound obligation store."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._obligations: Dict[str, Obligation] = {}
        self._load()

    # -- persistence --------------------------------------------------------
    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        for item in raw.get("obligations", []):
            try:
                ob = Obligation(
                    obligation_id=item["obligation_id"],
                    source_digest=item["source_digest"],
                    test_digest=item["test_digest"],
                    environment_identity=item["environment_identity"],
                    command=tuple(item.get("command", ())),
                    result=item.get("result", "PENDING"),
                    evidence_digest=item.get("evidence_digest", ""),
                    executions=int(item.get("executions", 0)),
                    invalidations=int(item.get("invalidations", 0)),
                    created_at=float(item.get("created_at", time.time())),
                    updated_at=float(item.get("updated_at", time.time())),
                )
            except Exception:
                continue
            self._obligations[ob.obligation_id] = ob

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        body = json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "obligations": [o.to_dict() for o in self._obligations.values()],
            },
            indent=2,
            sort_keys=True,
        )
        self._path.write_text(body, encoding="utf-8")
        os.chmod(self._path, 0o600)

    # -- core semantics -----------------------------------------------------
    def register(
        self,
        obligation_id: str,
        *,
        source_paths: Sequence[str],
        test_paths: Sequence[str],
        command: Sequence[str],
    ) -> Tuple[Obligation, bool]:
        """Register or refresh an obligation.

        Returns ``(obligation, must_run)``. ``must_run`` is False when a prior
        PASS exists for the exact same source+test+environment+command identity.
        """
        source_digest = digest_set(source_paths)
        test_digest = digest_set(test_paths)
        env = environment_identity()
        cmd = tuple(command)

        existing = self._obligations.get(obligation_id)
        if existing is not None:
            unchanged = (
                existing.source_digest == source_digest
                and existing.test_digest == test_digest
                and existing.environment_identity == env
                and existing.command == cmd
            )
            if unchanged:
                # Reuse prior evidence. Untracked files, earlier path changes,
                # removed temporary verifiers and lingering evidence JSON are
                # all explicitly NOT re-run triggers.
                return existing, not existing.satisfied
            # Relevant identity changed -> exactly one invalidation.
            existing.source_digest = source_digest
            existing.test_digest = test_digest
            existing.environment_identity = env
            existing.command = cmd
            existing.result = "PENDING"
            existing.evidence_digest = ""
            existing.invalidations += 1
            existing.updated_at = time.time()
            return existing, True

        ob = Obligation(
            obligation_id=obligation_id,
            source_digest=source_digest,
            test_digest=test_digest,
            environment_identity=env,
            command=cmd,
        )
        self._obligations[obligation_id] = ob
        return ob, True

    def record_result(
        self, obligation_id: str, *, passed: bool, evidence: str
    ) -> Obligation:
        ob = self._obligations[obligation_id]
        ob.result = "PASS" if passed else "FAIL"
        ob.evidence_digest = (
            "sha256:" + hashlib.sha256(evidence.encode("utf-8")).hexdigest()
        )
        ob.executions += 1
        ob.updated_at = time.time()
        return ob

    def get(self, obligation_id: str) -> Optional[Obligation]:
        return self._obligations.get(obligation_id)

    def all(self) -> List[Obligation]:
        return list(self._obligations.values())

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "obligations": [o.to_dict() for o in self._obligations.values()],
        }
