"""Runtime ownership guard — repository-scoped mutation control.

During governed execution the agent may write only inside the approved workspace
and CAPT state roots. Everything else is denied by default and produces a
``RUNTIME_OWNERSHIP_DENIAL`` receipt.

Denied by default:

* ``~/.hermes/skills/**`` — external skill mutation (self-improvement)
* global Hermes prompt/config (``~/.hermes/config.yaml``, ``AGENTS.md``, ...)
* arbitrary home-directory writes
* anything outside the approved workspace / CAPT state roots

Historical, uncontrolled side effects are recorded as
``EXTERNAL_SKILL_MUTATION_UNREVIEWED`` — **owner files are never reverted
automatically**.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

DENIAL_CODE = "RUNTIME_OWNERSHIP_DENIAL"
UNREVIEWED_CODE = "EXTERNAL_SKILL_MUTATION_UNREVIEWED"

AUTHORIZATION_ENV = "CAPT_BRIDGE_SCOPE_AUTHORIZED"

# Patterns that are denied even when nested under an otherwise-approved root.
_ALWAYS_DENY_SUFFIXES: Tuple[str, ...] = (
    ".hermes/skills",
    ".hermes/config.yaml",
    ".hermes/auth.json",
    ".hermes/plugins",
    ".hermes/memories",
    ".hermes/cron",
)


@dataclass
class OwnershipDenial:
    """A receipt. Emitted on every denied mutation."""

    code: str
    path: str
    reason: str
    operation: str = "write"
    timestamp: float = field(default_factory=time.time)
    approved_roots: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        out = asdict(self)
        out["approved_roots"] = list(self.approved_roots)
        return out

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()


class OwnershipGuardError(PermissionError):
    """Raised inside CAPT when a denied mutation is attempted."""

    def __init__(self, denial: OwnershipDenial) -> None:
        super().__init__(f"{denial.code}: {denial.reason} ({denial.path})")
        self.denial = denial


class RuntimeOwnershipGuard:
    """Deny-by-default path authorization for governed execution."""

    def __init__(
        self,
        approved_roots: Sequence[str],
        *,
        receipts_dir: Optional[Path] = None,
    ) -> None:
        self._roots: List[Path] = []
        for root in approved_roots:
            if not root:
                continue
            try:
                self._roots.append(Path(root).expanduser().resolve())
            except Exception:
                continue
        self._receipts_dir = receipts_dir
        self.denials: List[OwnershipDenial] = []
        self.unreviewed: List[OwnershipDenial] = []

    @property
    def approved_roots(self) -> Tuple[str, ...]:
        return tuple(str(r) for r in self._roots)

    # -- authorization ------------------------------------------------------
    def _explicitly_authorized(self, path: Path) -> bool:
        """Explicit, per-path scope expansion. Never inferred."""
        raw = os.environ.get(AUTHORIZATION_ENV, "")
        if not raw:
            return False
        for entry in raw.split(os.pathsep):
            entry = entry.strip()
            if not entry:
                continue
            try:
                allowed = Path(entry).expanduser().resolve()
            except Exception:
                continue
            if path == allowed or allowed in path.parents:
                return True
        return False

    def check(self, path: str, *, operation: str = "write") -> Optional[OwnershipDenial]:
        """Return a denial, or ``None`` when the mutation is permitted."""
        try:
            target = Path(path).expanduser().resolve()
        except Exception:
            target = Path(path)

        posix = target.as_posix()
        for suffix in _ALWAYS_DENY_SUFFIXES:
            if posix.endswith("/" + suffix) or ("/" + suffix + "/") in posix:
                if self._explicitly_authorized(target):
                    return None
                return self._deny(
                    target,
                    operation,
                    f"path is a protected external Hermes location ({suffix})",
                )

        for root in self._roots:
            if target == root or root in target.parents:
                return None

        if self._explicitly_authorized(target):
            return None

        return self._deny(
            target, operation, "path is outside every approved workspace / CAPT state root"
        )

    def enforce(self, path: str, *, operation: str = "write") -> None:
        denial = self.check(path, operation=operation)
        if denial is not None:
            raise OwnershipGuardError(denial)

    def _deny(self, path: Path, operation: str, reason: str) -> OwnershipDenial:
        denial = OwnershipDenial(
            code=DENIAL_CODE,
            path=str(path),
            reason=reason,
            operation=operation,
            approved_roots=self.approved_roots,
        )
        self.denials.append(denial)
        self._persist(denial)
        return denial

    # -- historical side effects (recorded, never reverted) -----------------
    def record_unreviewed(self, paths: Iterable[str], reason: str = "") -> List[OwnershipDenial]:
        out: List[OwnershipDenial] = []
        for p in paths:
            denial = OwnershipDenial(
                code=UNREVIEWED_CODE,
                path=str(p),
                reason=reason
                or "uncontrolled historical mutation observed outside governed scope; "
                "recorded for owner review, NOT reverted",
                operation="historical",
                approved_roots=self.approved_roots,
            )
            self.unreviewed.append(denial)
            self._persist(denial)
            out.append(denial)
        return out

    def _persist(self, denial: OwnershipDenial) -> None:
        if self._receipts_dir is None:
            return
        try:
            self._receipts_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            name = hashlib.sha256(
                f"{denial.code}:{denial.path}:{denial.timestamp}".encode("utf-8")
            ).hexdigest()[:16]
            path = self._receipts_dir / f"{denial.code.lower()}-{name}.json"
            body = json.dumps(
                {**denial.to_dict(), "receipt_digest": denial.digest()},
                indent=2,
                sort_keys=True,
                default=str,
            )
            path.write_text(body, encoding="utf-8")
            os.chmod(path, 0o600)
        except Exception:
            pass
