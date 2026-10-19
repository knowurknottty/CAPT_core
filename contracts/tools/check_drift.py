#!/usr/bin/env python3
"""Fail if committed bindings differ from a fresh generation (ADR-0102).

Regenerates into a temporary directory and compares file-by-file against
contracts/generated/. Exit 0 = in sync, exit 1 = drift.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
CONTRACTS_DIR = TOOLS_DIR.parent
COMMITTED = CONTRACTS_DIR / "generated"


def tree_digests(root: Path):
    """Digest every generated SOURCE file under root.

    TypeScript dist and node_modules are build outputs, not generator source.
    Local compiler installation must not affect contract drift validation.
    """
    result = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("typescript/dist/", "typescript/node_modules/")) or "__pycache__" in rel:
            continue
        result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="capt-contract-drift-"))
    try:
        proc = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "generate.py"), "--out", str(tmp)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            sys.stderr.write(proc.stdout + proc.stderr)
            print("DRIFT CHECK: FAILED (generator error)")
            return 1

        fresh = tree_digests(tmp)
        committed = tree_digests(COMMITTED)

        missing = sorted(set(fresh) - set(committed))
        extra = sorted(set(committed) - set(fresh))
        modified = sorted(
            name for name in set(fresh) & set(committed) if fresh[name] != committed[name]
        )

        if not (missing or extra or modified):
            print("DRIFT CHECK: OK (%d generated files match the schema source)" % len(fresh))
            return 0

        for name in missing:
            print("MISSING (generated but not committed): " + name)
        for name in extra:
            print("STALE (committed but no longer generated): " + name)
        for name in modified:
            print("MODIFIED (committed content differs from generated): " + name)
        print("")
        print("DRIFT CHECK: FAILED")
        print("Run: python3 contracts/tools/generate.py && git add contracts/generated")
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
