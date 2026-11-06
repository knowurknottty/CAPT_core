from __future__ import annotations

import base64
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def _raw_private(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _raw_public(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _private_from_bytes(raw: bytes) -> Ed25519PrivateKey:
    if len(raw) != 32:
        raise ValueError("ed25519_private_key_must_be_32_bytes")
    return Ed25519PrivateKey.from_private_bytes(raw)


@dataclass(frozen=True)
class NodeIdentity:
    node_id: str
    device_name: str
    _private_key: Ed25519PrivateKey

    @classmethod
    def generate(cls, node_id: str, device_name: str) -> "NodeIdentity":
        return cls(node_id=node_id, device_name=device_name, _private_key=Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, node_id: str, device_name: str, raw: bytes) -> "NodeIdentity":
        return cls(node_id=node_id, device_name=device_name, _private_key=_private_from_bytes(raw))

    def private_key_bytes(self) -> bytes:
        return _raw_private(self._private_key)

    def public_key_bytes(self) -> bytes:
        return _raw_public(self._private_key.public_key())

    def public_dict(self) -> dict[str, str]:
        return {
            "nodeId": self.node_id,
            "deviceName": self.device_name,
            "publicKey": base64.b64encode(self.public_key_bytes()).decode("ascii"),
        }


@dataclass(frozen=True)
class ControllerIdentity:
    controller_id: str
    label: str
    _private_key: Ed25519PrivateKey

    @classmethod
    def generate(cls, controller_id: str, label: str) -> "ControllerIdentity":
        return cls(controller_id=controller_id, label=label, _private_key=Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, controller_id: str, label: str, raw: bytes) -> "ControllerIdentity":
        return cls(controller_id=controller_id, label=label, _private_key=_private_from_bytes(raw))

    def private_key_bytes(self) -> bytes:
        return _raw_private(self._private_key)

    def public_key_bytes(self) -> bytes:
        return _raw_public(self._private_key.public_key())

    def sign(self, payload: bytes) -> bytes:
        return self._private_key.sign(payload)


@dataclass(frozen=True)
class CapabilityAuthorityIdentity:
    authority_id: str
    _private_key: Ed25519PrivateKey

    @classmethod
    def generate(cls, authority_id: str) -> "CapabilityAuthorityIdentity":
        return cls(authority_id=authority_id, _private_key=Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, authority_id: str, raw: bytes) -> "CapabilityAuthorityIdentity":
        return cls(authority_id=authority_id, _private_key=_private_from_bytes(raw))

    def private_key_bytes(self) -> bytes:
        return _raw_private(self._private_key)

    def public_key_bytes(self) -> bytes:
        return _raw_public(self._private_key.public_key())

    def sign(self, payload: bytes) -> bytes:
        return self._private_key.sign(payload)
