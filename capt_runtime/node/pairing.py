from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from enum import Enum

from .identity import ControllerIdentity, NodeIdentity


class PairingState(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


def pairing_short_code(node_public: bytes, controller_public: bytes) -> str:
    digest = hashlib.sha256(node_public + controller_public).digest()
    value = int.from_bytes(digest[:4], "big") % 1_000_000
    return f"{value:06d}"


@dataclass(frozen=True)
class PairingRecord:
    node_id: str
    controller_id: str
    node_public_key: bytes
    controller_public_key: bytes
    short_code: str
    state: PairingState
    reason: str | None = None
    execution_authority: bool = False

    @classmethod
    def pending(cls, node: NodeIdentity, controller: ControllerIdentity) -> "PairingRecord":
        return cls(
            node_id=node.node_id,
            controller_id=controller.controller_id,
            node_public_key=node.public_key_bytes(),
            controller_public_key=controller.public_key_bytes(),
            short_code=pairing_short_code(node.public_key_bytes(), controller.public_key_bytes()),
            state=PairingState.PENDING,
        )

    def activate(self, code: str) -> "PairingRecord":
        if self.state is PairingState.REVOKED:
            raise ValueError("pairing_terminal")
        if self.state is not PairingState.PENDING:
            raise ValueError("pairing_not_pending")
        if code != self.short_code:
            raise ValueError("pairing_code_mismatch")
        return replace(self, state=PairingState.ACTIVE)

    def suspend(self, reason: str) -> "PairingRecord":
        if self.state is not PairingState.ACTIVE:
            raise ValueError("pairing_not_active")
        return replace(self, state=PairingState.SUSPENDED, reason=reason)

    def revoke(self, reason: str) -> "PairingRecord":
        if self.state is PairingState.REVOKED:
            return self
        return replace(self, state=PairingState.REVOKED, reason=reason)

    def require_active(self) -> None:
        if self.state is not PairingState.ACTIVE:
            raise PermissionError(f"pairing_{self.state.value}")
