"""Append-only, digest-linked local continuity receipt chain."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

from .runtime import ContinuityError, canonical_json, digest


class ReceiptChain:
    _lock = threading.RLock()

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.is_symlink():
            raise ContinuityError("receipt chain path must not be a symlink")

    def entries(self) -> List[Dict[str, Any]]:
        if not self._path.exists(): return []
        entries = []
        for number, line in enumerate(self._path.read_text(encoding="utf-8").splitlines(), 1):
            try: entries.append(json.loads(line))
            except ValueError as exc: raise ContinuityError("invalid receipt chain line " + str(number)) from exc
        return entries

    def append(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            previous = self.entries()
            item = dict(receipt)
            item["previous_receipt_digest"] = digest(previous[-1]) if previous else ""
            item["chain_digest"] = digest(item)
            encoded = canonical_json(item) + "\n"
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
            return item

    def verify(self) -> Dict[str, Any]:
        previous_digest = ""
        for index, item in enumerate(self.entries()):
            expected_previous = previous_digest
            content = dict(item); observed = content.pop("chain_digest", "")
            if content.get("previous_receipt_digest", "") != expected_previous:
                return {"valid": False, "index": index, "reason": "previous receipt digest mismatch"}
            if observed != digest(content):
                return {"valid": False, "index": index, "reason": "receipt chain digest mismatch"}
            previous_digest = digest(item)
        return {"valid": True, "entries": len(self.entries())}
