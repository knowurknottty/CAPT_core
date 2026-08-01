"""Deterministic directory tree digest (path + content), stdlib only."""
from __future__ import annotations

import hashlib
import json
import os
import sys


def tree_digest(root: str) -> dict:
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            with open(path, "rb") as fh:
                blob = fh.read()
            files.append(
                {
                    "path": rel,
                    "sha256": hashlib.sha256(blob).hexdigest(),
                    "bytes": len(blob),
                }
            )
    files.sort(key=lambda e: e["path"])
    h = hashlib.sha256()
    for entry in files:
        h.update(entry["path"].encode("utf-8"))
        h.update(bytes.fromhex(entry["sha256"]))
    return {
        "root": os.path.abspath(root),
        "file_count": len(files),
        "tree_digest": "sha256:" + h.hexdigest(),
        "files": files,
    }


if __name__ == "__main__":
    print(json.dumps(tree_digest(sys.argv[1]), indent=2, sort_keys=True))
