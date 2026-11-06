from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path


def scoped_path(roots: tuple[str, ...], candidate: str) -> Path:
    path = Path(candidate).expanduser().resolve(strict=False)
    for raw_root in roots:
        root = Path(raw_root).expanduser().resolve(strict=False)
        try:
            path.relative_to(root)
            return path
        except ValueError:
            continue
    raise PermissionError("filesystem_scope_violation")


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def system_telemetry() -> dict[str, object]:
    return {
        "kind": "system_telemetry",
        "platform": platform.system().lower(),
        "architecture": platform.machine(),
        "pid": os.getpid(),
        "uid": os.getuid() if hasattr(os, "getuid") else None,
    }
