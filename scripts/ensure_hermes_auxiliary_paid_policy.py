#!/usr/bin/env python3
"""CAPT-managed Hermes auxiliary paid-model policy.

When the operator explicitly authorizes paid auxiliary models, CAPT enforces
auxiliary.free_only=false after Hermes updates. This avoids per-task source
patches for MoA references/aggregators and applies consistently to all auxiliary
lanes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def config_allows_paid_auxiliary(text: str) -> bool:
    lines = text.splitlines()
    in_aux = False
    aux_indent = None
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped == "auxiliary:":
            in_aux = True
            aux_indent = indent
            continue
        if in_aux and stripped and indent <= int(aux_indent or 0):
            in_aux = False
        if in_aux and stripped.lower() == "free_only: false":
            return True
    return False

def patch_config(text: str) -> str:
    if config_allows_paid_auxiliary(text):
        return text

    lines = text.splitlines()
    in_aux = False
    aux_indent = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped == "auxiliary:":
            in_aux = True
            aux_indent = indent
            continue
        if in_aux and stripped and indent <= int(aux_indent or 0):
            break
        if in_aux and stripped.lower().startswith("free_only:"):
            prefix = line[: len(line) - len(line.lstrip())]
            lines[index] = f"{prefix}free_only: false"
            result = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
            if not config_allows_paid_auxiliary(result):
                raise RuntimeError("failed to enable paid auxiliary policy")
            return result

    raise RuntimeError("auxiliary.free_only setting not found in Hermes config")

def inspect(config_path: Path) -> dict[str, object]:
    data = config_path.read_bytes()
    text = data.decode()
    enabled = config_allows_paid_auxiliary(text)
    return {
        "config": str(config_path),
        "configSha256": sha256_bytes(data),
        "paidAuxiliaryEnabled": enabled,
        "policy": "auxiliary.free_only=false",
        "conformant": enabled,
    }


def apply(config_path: Path, backup_root: Path) -> dict[str, object]:
    before = config_path.read_bytes()
    patched = patch_config(before.decode()).encode()

    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / f"config.{sha256_bytes(before)[:16]}.bak"
    if not backup.exists():
        shutil.copy2(config_path, backup)

    config_path.write_bytes(patched)
    result = inspect(config_path)
    result["configBeforeSha256"] = sha256_bytes(before)
    result["configAfterSha256"] = sha256_bytes(patched)
    result["backupRoot"] = str(backup_root)
    return result

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".hermes" / "config.yaml",
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        default=Path.home() / ".capt" / "hermes-compat" / "backups",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    state = (
        apply(args.config, args.backup_root)
        if args.apply
        else inspect(args.config)
    )
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0 if state["conformant"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

