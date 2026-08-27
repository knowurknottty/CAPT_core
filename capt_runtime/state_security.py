"""Local-state hardening primitives for CAPT authoritative persistence."""
from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_ENCRYPTED_PREFIX = "enc:v1:"
_KEY_ENV = "CAPT_STATE_KEY_B64"
_KEYCHAIN_SERVICE = "capt-runtime-state"
_KEYCHAIN_ACCOUNT = "state-v1"
_KEY_CACHE: Optional[bytes] = None
MAX_PERSISTED_JSON_BYTES = 4 * 1024 * 1024
MAX_MEMORY_CONTENT_BYTES = 1024 * 1024


class AtRestProtectionError(ValueError):
    pass


def validate_persisted_text(value: str, *, field: str, max_bytes: int) -> None:
    if not isinstance(value, str):
        raise ValueError("%s_TYPE" % field)
    if "\x00" in value:
        raise ValueError("%s_NUL" % field)
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("%s_UTF8" % field) from exc
    if len(encoded) > max_bytes:
        raise ValueError("%s_TOO_LARGE" % field)


def harden_sqlite_path(path: str) -> None:
    if path == ":memory:":
        return
    db = Path(path)
    parent_preexisted = db.parent.exists()
    db.parent.mkdir(parents=True, exist_ok=True)
    if not parent_preexisted:
        try:
            os.chmod(db.parent, 0o700)
        except OSError:
            pass
    for target in (db, db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")):
        if target.exists():
            try:
                os.chmod(target, 0o600)
            except OSError:
                pass


def _decode_key(text: str) -> bytes:
    try:
        key = base64.b64decode(text.strip(), validate=True)
    except Exception as exc:
        raise AtRestProtectionError("STATE_KEY_INVALID_BASE64") from exc
    if len(key) != 32:
        raise AtRestProtectionError("STATE_KEY_INVALID_LENGTH")
    return key


def _keychain_key() -> Optional[bytes]:
    if sys.platform != "darwin" or not shutil.which("security"):
        return None
    find = subprocess.run(
        ["security", "find-generic-password", "-s", _KEYCHAIN_SERVICE,
         "-a", _KEYCHAIN_ACCOUNT, "-w"],
        capture_output=True, text=True, timeout=5, check=False,
    )
    if find.returncode == 0 and find.stdout.strip():
        return _decode_key(find.stdout.strip())
    key = os.urandom(32)
    encoded = base64.b64encode(key).decode("ascii")
    add = subprocess.run(
        ["security", "add-generic-password", "-U", "-s", _KEYCHAIN_SERVICE,
         "-a", _KEYCHAIN_ACCOUNT, "-w", encoded],
        capture_output=True, text=True, timeout=5, check=False,
    )
    return key if add.returncode == 0 else None


def _file_key() -> bytes:
    root = Path.home() / ".capt" / "keys"
    root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    path = root / "runtime-state-v1.key"
    if path.exists():
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return _decode_key(path.read_text(encoding="ascii"))
    key = os.urandom(32)
    encoded = (base64.b64encode(key).decode("ascii") + "\n").encode("ascii")
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return _decode_key(path.read_text(encoding="ascii"))
    with os.fdopen(fd, "wb") as handle:
        handle.write(encoded)
    return key


def state_key() -> bytes:
    global _KEY_CACHE
    env = os.environ.get(_KEY_ENV, "").strip()
    if env:
        return _decode_key(env)
    if _KEY_CACHE is None:
        _KEY_CACHE = _keychain_key() or _file_key()
    return _KEY_CACHE


class AtRestProtector:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._aes = AESGCM(state_key()) if enabled else None

    @classmethod
    def for_path(cls, path: str) -> "AtRestProtector":
        return cls(enabled=path != ":memory:")

    @staticmethod
    def is_sealed(value: str) -> bool:
        return isinstance(value, str) and value.startswith(_ENCRYPTED_PREFIX)

    def seal_text(self, plaintext: str, *, context: str) -> str:
        if not self.enabled:
            return plaintext
        validate_persisted_text(
            plaintext, field="PERSISTED_JSON", max_bytes=MAX_PERSISTED_JSON_BYTES
        )
        nonce = os.urandom(12)
        ciphertext = self._aes.encrypt(
            nonce, plaintext.encode("utf-8"), context.encode("utf-8")
        )
        return _ENCRYPTED_PREFIX + base64.b64encode(nonce + ciphertext).decode("ascii")

    def open_text(self, stored: str, *, context: str) -> str:
        if not self.enabled:
            return stored
        if not self.is_sealed(stored):
            raise AtRestProtectionError("STATE_PLAINTEXT_UNEXPECTED")
        try:
            blob = base64.b64decode(stored[len(_ENCRYPTED_PREFIX):], validate=True)
            if len(blob) < 13:
                raise ValueError("short ciphertext")
            clear = self._aes.decrypt(
                blob[:12], blob[12:], context.encode("utf-8")
            )
            return clear.decode("utf-8")
        except Exception as exc:
            raise AtRestProtectionError("STATE_CIPHERTEXT_INVALID") from exc
