"""Persistent store for verification records (JSONL, local-only)."""
from __future__ import annotations

import json
import os
import uuid
from typing import Dict, List, Optional

from .identity import VerifiedStateIdentity, vsi_equivalent
from .record import VerificationRecord


class VerificationStore:
    """Append-only JSONL store of verification records.

    Records are never mutated in place; a superseded record gets
    `invalidated_by` set and a new record is appended.
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or os.path.join(
            os.getcwd(), ".capt_verify", "records.jsonl")
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    def add(self, record: VerificationRecord) -> None:
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), default=str) + "\n")

    def all(self) -> List[Dict]:
        if not os.path.exists(self._path):
            return []
        out = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def latest(self) -> Optional[Dict]:
        recs = self.all()
        return recs[-1] if recs else None

    def latest_for_scope(self, scope: str) -> Optional[Dict]:
        """Most recent non-superseded record for a given verification scope."""
        best = None
        for rec in self.all():
            if rec.get("invalidated_by"):
                continue
            if rec.get("vsi", {}).get("verification_scope") == scope:
                best = rec
        return best

    def find_compatible(self, vsi: VerifiedStateIdentity) -> Optional[Dict]:
        """Return the most recent record whose VSI is equivalent to `vsi` and
        not superseded/invalidated."""
        best = None
        for rec in self.all():
            if rec.get("invalidated_by"):
                continue
            rvsi = rec.get("vsi", {})
            cand = VerifiedStateIdentity(
                repository=rvsi.get("repository", ""),
                project_id=rvsi.get("project_id", ""),
                active_branch=rvsi.get("active_branch", ""),
                head_commit=rvsi.get("head_commit", ""),
                working_tree_status=rvsi.get("working_tree_status", ""),
                scope_file_hashes=rvsi.get("scope_file_hashes", {}),
                dependency_state=rvsi.get("dependency_state", ""),
                runtime_identity=rvsi.get("runtime_identity", ""),
                operating_environment=rvsi.get("operating_environment", ""),
                verification_command=rvsi.get("verification_command", ""),
                verification_scope=rvsi.get("verification_scope", ""),
            )
            if vsi_equivalent(cand, vsi):
                best = rec
        return best

    def mark_superseded(self, old_record_id: str, by_record_id: str) -> None:
        recs = self.all()
        rewritten = []
        for rec in recs:
            if rec.get("record_id") == old_record_id:
                rec["invalidated_by"] = by_record_id
            rewritten.append(rec)
        with open(self._path, "w", encoding="utf-8") as f:
            for rec in rewritten:
                f.write(json.dumps(rec, default=str) + "\n")
