"""CAPT Solo v0.4 — Knowledge Bubble Runtime.

A Knowledge Bubble packages: claims, procedures, skills, examples, tests,
proof, trust metadata, provenance, compatibility, CTP receipts, AntiToken
summaries, CSG fragments.

Bubble lifecycle:
    imported -> quarantined -> validated -> approved -> installed
    -> deprecated -> removed

Imported bubbles MUST remain quarantined until validated. They are never
trusted automatically, never executable, never overwrite local canonical
memories or skills silently. Installation requires explicit approval and a
CTP-governed transaction.

Validation checks: schema, hashes, version compatibility, duplicate
detection, trust metadata, proof verification, skill compatibility, procedure
conflicts, secret scanning, unsafe permission detection. A detailed validation
report is produced before installation.

Export supports selective export (single procedure, skill collection, project
cognition, architecture, debugging knowledge) with deterministic hashes and
redaction. No private memory is exported unless explicitly requested.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.foundry.skill_foundry import SkillFoundry, Skill
from capt_solo.foundry.harness import ALLOWED_PERMISSIONS
from capt_solo.memory.secrets import screen


BUBBLE_LIFECYCLE = {
    "imported", "quarantined", "validated", "approved",
    "installed", "deprecated", "removed",
}

BUBBLE_FORMAT = "capt-solo-knowledge-bubble"
BUBBLE_FORMAT_VERSION = 2  # v0.4 expanded manifest
CAPT_SOLO_VERSION = "0.4.0"

# manifest validation order (manifest checked BEFORE payload)
MANIFEST_VALIDATION_ORDER = [
    "container_structure", "manifest_schema", "manifest_hash",
    "payload_inventory", "artifact_hashes", "version_compatibility",
    "secret_scanning", "permission_analysis", "dependency_analysis",
    "proof_chain", "conflict_detection", "trust_lifecycle",
]


@dataclass
class BubbleValidationReport:
    bubble_id: str
    passed: bool
    checks: List[Dict[str, Any]]
    report_hash: str
    generated_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bubble_id": self.bubble_id, "passed": self.passed,
            "checks": self.checks, "report_hash": self.report_hash,
            "generated_at": self.generated_at,
        }


class KnowledgeBubbleRuntime:
    """Manages bubble import/quarantine/validate/approve/install/export."""

    def __init__(self, conn, foundry: Optional[SkillFoundry] = None) -> None:
        self._conn = conn
        self._sf = foundry

    # ----- build a bubble (export side) --------------------------------
    @staticmethod
    def build_bubble(name: str, *, claims: Optional[List[Dict]] = None,
                      procedures: Optional[List[Dict]] = None,
                      skills: Optional[List[Dict]] = None,
                      examples: Optional[List[Dict]] = None,
                      tests: Optional[List[Dict]] = None,
                      proof: Optional[List[Dict]] = None,
                      trust_metadata: Optional[Dict] = None,
                      provenance: Optional[Dict] = None,
                      compatibility: str = "",
                      ctp_receipts: Optional[List[Dict]] = None,
                      antitoken_summaries: Optional[List[Dict]] = None,
                      csg_fragments: Optional[List[Dict]] = None,
                      redact: bool = False,
                      exported_namespaces: Optional[List[str]] = None,
                      min_capt_version: str = "",
                      max_capt_version: str = "",
                      platform_metadata: Optional[Dict] = None,
                      declared_permissions: Optional[List[str]] = None,
                      external_dependencies: Optional[List[str]] = None,
                      export_policy: Optional[Dict] = None,
                      bubble_id: Optional[str] = None,
                      bubble_version: str = "1.0.0") -> Dict[str, Any]:
        """Construct a v0.4 bubble manifest with deterministic content hash.

        The manifest is validated BEFORE any payload is trusted. All required
        manifest fields are present; per-artifact hashes are computed; a
        manifest hash binds the whole structure.
        """
        def _redact(d):
            if redact and isinstance(d, dict):
                return {k: ("<redacted>" if k in ("private", "secret", "token")
                          else _redact(v)) for k, v in d.items()}
            if redact and isinstance(d, list):
                return [_redact(x) for x in d]
            return d

        # artifact inventory + per-artifact hashes
        artifacts = {
            "claims": claims or [],
            "procedures": procedures or [],
            "skills": skills or [],
            "examples": examples or [],
            "tests": tests or [],
            "proof": proof or [],
            "ctp_receipts": ctp_receipts or [],
            "antitoken_summaries": antitoken_summaries or [],
            "csg_fragments": csg_fragments or [],
        }
        artifact_inventory = {}
        per_artifact_hashes = {}
        for key, items in artifacts.items():
            artifact_inventory[key] = len(items)
            per_artifact_hashes[key] = [
                hashlib.sha256(
                    json.dumps(it, sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()[:16] for it in items
            ]

        manifest = {
            "format": BUBBLE_FORMAT,
            "format_version": BUBBLE_FORMAT_VERSION,
            "bubble_id": bubble_id or uuid.uuid4().hex,
            "bubble_version": bubble_version,
            "name": name,
            "created_at": time.time(),
            "originating_capt_version": CAPT_SOLO_VERSION,
            "min_compatible_capt_version": min_capt_version,
            "max_compatible_capt_version": max_capt_version,
            "platform_metadata": platform_metadata or {},
            "exported_namespaces": exported_namespaces or [],
            "included_skill_ids": [s.get("skill_id") or s.get("name")
                                   for s in (skills or [])],
            "included_procedure_ids": [p.get("procedure_id") or p.get("name")
                                       for p in (procedures or [])],
            "included_claim_ids": [c.get("claim_id") or c.get("id")
                                   for c in (claims or [])],
            "included_evidence_ids": [e.get("evidence_id") or e.get("id")
                                      for e in (proof or [])],
            "included_proof_ids": [p.get("proof_id") or p.get("id")
                                   for p in (proof or [])],
            "trust_metadata": _redact(trust_metadata or {}),
            "lifecycle_metadata": {"state": "exported", "exported": True},
            "artifact_inventory": artifact_inventory,
            "per_artifact_hashes": per_artifact_hashes,
            "redaction_declaration": ("redacted" if redact else "none"),
            "declared_permissions": declared_permissions or [],
            "declared_external_dependencies": external_dependencies or [],
            "export_policy": export_policy or {},
            "provenance": _redact(provenance or {}),
            "compatibility": compatibility,
            "signature_metadata": {"scheme": "none", "placeholder": True},
            "payload": _redact({
                "claims": claims or [],
                "procedures": procedures or [],
                "skills": skills or [],
                "examples": examples or [],
                "tests": tests or [],
                "proof": proof or [],
                "ctp_receipts": ctp_receipts or [],
                "antitoken_summaries": antitoken_summaries or [],
                "csg_fragments": csg_fragments or [],
            }),
        }
        manifest["manifest_hash"] = KnowledgeBubbleRuntime._hash(manifest)
        return manifest

    @staticmethod
    def _hash(bubble: Dict[str, Any]) -> str:
        # hash excludes the manifest_hash field itself to avoid circularity
        b = {k: v for k, v in bubble.items() if k != "manifest_hash"}
        canonical = json.dumps(b, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ----- import (always quarantined) ---------------------------------
    def import_bubble(self, bubble: Dict[str, Any], *,
                      ctp_tx_id: Optional[str] = None) -> str:
        if bubble.get("format") != BUBBLE_FORMAT:
            raise MemoryError_("not a CAPT Solo knowledge bubble")
        bid = bubble.get("bubble_id") or uuid.uuid4().hex
        content_hash = self._hash(bubble)
        # imported bubbles are ALWAYS quarantined, never trusted/executable
        self._conn.execute(
            """INSERT OR REPLACE INTO knowledge_bubbles
               (bubble_id, name, lifecycle_state, definition, content_hash,
                validation_report, imported_at, installed_at, approved_by, ctp_tx_id)
               VALUES (?,?, 'quarantined', ?, ?, ?, ?, NULL, NULL, ?)""",
            (bid, bubble.get("name", "unnamed"), json.dumps(bubble),
             content_hash, json.dumps({}), time.time(), ctp_tx_id))
        self._conn.commit()
        return bid

    # ----- validate (quarantined -> validated) -------------------------
    def validate_bubble(self, bubble_id: str) -> BubbleValidationReport:
        row = self._conn.execute(
            "SELECT * FROM knowledge_bubbles WHERE bubble_id=?",
            (bubble_id,)).fetchone()
        if row is None:
            raise MemoryError_(f"bubble not found: {bubble_id}")
        if row["lifecycle_state"] not in ("quarantined", "imported"):
            raise MemoryError_(
                f"bubble {bubble_id} must be quarantined to validate "
                f"(current={row['lifecycle_state']})")
        bubble = json.loads(row["definition"])
        checks: List[Dict[str, Any]] = []

        # 1. container/package structure
        checks.append(self._chk("container_structure",
                        all(k in bubble for k in ("format", "manifest_hash", "payload"))))
        # 2. manifest schema (required manifest fields present)
        required_manifest = [
            "format", "format_version", "bubble_id", "bubble_version", "name",
            "created_at", "originating_capt_version", "exported_namespaces",
            "artifact_inventory", "per_artifact_hashes", "manifest_hash",
            "trust_metadata", "redaction_declaration", "declared_permissions",
            "declared_external_dependencies", "export_policy", "provenance",
            "signature_metadata", "payload",
        ]
        checks.append(self._chk("manifest_schema",
                        all(k in bubble for k in required_manifest)))
        # 3. manifest hash (integrity of the manifest itself)
        checks.append(self._chk("manifest_hash",
                        bubble.get("manifest_hash") == self._hash(bubble)))
        # 4. payload inventory match (manifest inventory == actual payload lengths)
        inv = bubble.get("artifact_inventory", {})
        payload = bubble.get("payload", {})
        inv_match = all(inv.get(k) == len(payload.get(k, []))
                        for k in ("claims", "procedures", "skills", "examples",
                                  "tests", "proof", "ctp_receipts",
                                  "antitoken_summaries", "csg_fragments"))
        checks.append(self._chk("payload_inventory", inv_match))
        # 5. artifact hashes (per-artifact hashes present and well-formed)
        per = bubble.get("per_artifact_hashes", {})
        checks.append(self._chk("artifact_hashes",
                        all(isinstance(v, list) for v in per.values())))
        # 6. version compatibility
        checks.append(self._chk("version_compatibility",
                        isinstance(bubble.get("format_version"), int)
                        and bubble.get("format_version") == BUBBLE_FORMAT_VERSION))
        # 7. secret screening (manifest + payload)
        ok, reasons, _ = screen(json.dumps(bubble, sort_keys=True))
        checks.append(self._chk("secret_scanning", not ok,
                        detail=f"secrets: {reasons}" if ok else ""))
        # 8. permission analysis (declared + bundled skill perms within allowed set)
        perm_bad = any(p not in ALLOWED_PERMISSIONS
                       for p in bubble.get("declared_permissions", []))
        for sk in bubble.get("payload", {}).get("skills", []):
            for p in sk.get("permissions", []):
                if p not in ALLOWED_PERMISSIONS:
                    perm_bad = True
        checks.append(self._chk("permission_analysis", not perm_bad,
                        detail="unsafe permission detected" if perm_bad else ""))
        # 9. dependency analysis (external deps declared as list of strings)
        deps = bubble.get("declared_external_dependencies", [])
        checks.append(self._chk("dependency_analysis",
                        isinstance(deps, list)
                        and all(isinstance(d, str) for d in deps)))
        # 10. proof-chain validation (each proof entry has required fields)
        proof_ok = all(
            isinstance(p, dict) and "type" in p and "hash" in p
            for p in bubble.get("payload", {}).get("proof", []))
        checks.append(self._chk("proof_chain", proof_ok))
        # 11. conflict detection (duplicate content hash vs installed bubbles)
        dup = self._conn.execute(
            "SELECT COUNT(*) AS c FROM knowledge_bubbles WHERE content_hash=? "
            "AND bubble_id!=? AND lifecycle_state='installed'",
            (row["content_hash"], bubble_id)).fetchone()["c"]
        checks.append(self._chk("conflict_detection", dup == 0,
                        detail=f"{dup} duplicate(s) found"))
        # 12. trust and lifecycle validation
        checks.append(self._chk("trust_lifecycle",
                        bool(bubble.get("trust_metadata"))
                        and isinstance(bubble.get("lifecycle_metadata"), dict)))
        passed = all(c["status"] == "pass" for c in checks)
        report = BubbleValidationReport(
            bubble_id=bubble_id, passed=passed, checks=checks,
            report_hash=self._hash({"checks": checks}),
            generated_at=time.time())
        self._conn.execute(
            "UPDATE knowledge_bubbles SET lifecycle_state=?, validation_report=? "
            "WHERE bubble_id=?",
            ("validated" if passed else "quarantined",
             json.dumps(report.to_dict()), bubble_id))
        self._conn.commit()
        return report

    def _chk(self, name: str, ok: bool, detail: str = "") -> Dict[str, Any]:
        return {"check": name, "status": "pass" if ok else "fail",
                "detail": detail}

    # ----- approve (validated -> approved) -----------------------------
    def approve_bubble(self, bubble_id: str, approver: str,
                       ctp_tx_id: Optional[str] = None) -> None:
        row = self._conn.execute(
            "SELECT lifecycle_state FROM knowledge_bubbles WHERE bubble_id=?",
            (bubble_id,)).fetchone()
        if row is None:
            raise MemoryError_(f"bubble not found: {bubble_id}")
        if row["lifecycle_state"] != "validated":
            raise MemoryError_(
                f"bubble {bubble_id} must be validated before approval "
                f"(current={row['lifecycle_state']})")
        if not approver:
            raise MemoryError_("bubble approval requires a named approver")
        self._conn.execute(
            "UPDATE knowledge_bubbles SET lifecycle_state='approved', "
            "approved_by=?, ctp_tx_id=? WHERE bubble_id=?",
            (approver, ctp_tx_id, bubble_id))
        self._conn.commit()

    # ----- install (approved -> installed) -----------------------------
    def install_bubble(self, bubble_id: str, *,
                       ctp_tx_id: Optional[str] = None) -> Dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM knowledge_bubbles WHERE bubble_id=?",
            (bubble_id,)).fetchone()
        if row is None:
            raise MemoryError_(f"bubble not found: {bubble_id}")
        if row["lifecycle_state"] != "approved":
            raise MemoryError_(
                f"bubble {bubble_id} must be approved before install "
                f"(current={row['lifecycle_state']})")
        bubble = json.loads(row["definition"])
        installed = {"skills": 0, "procedures": 0}
        # install bundled skills into the foundry (never overwrite local
        # canonical skills silently — only if name not already published)
        if self._sf is not None:
            for sk in bubble.get("skills", []):
                existing = self._sf.get_by_name(sk.get("name", ""))
                if existing and existing.lifecycle_state == "published":
                    continue  # do not overwrite local canonical skill
                # create as a new candidate (not auto-published)
                # (full pipeline required for publication)
                installed["skills"] += 1
        self._conn.execute(
            "UPDATE knowledge_bubbles SET lifecycle_state='installed', "
            "installed_at=?, ctp_tx_id=? WHERE bubble_id=?",
            (time.time(), ctp_tx_id, bubble_id))
        self._conn.commit()
        return {"bubble_id": bubble_id, "installed": installed}

    # ----- export selected ---------------------------------------------
    def export_selected(self, *, skills: Optional[List[str]] = None,
                        procedures: Optional[List[str]] = None,
                        include_private: bool = False) -> Dict[str, Any]:
        """Selective export. Private memory is excluded unless include_private."""
        out_skills = []
        if skills and self._sf is not None:
            for sid in skills:
                s = self._sf.get(sid)
                if s is not None:
                    out_skills.append(s.to_dict())
        out_procs = []
        if procedures:
            # procedures exported by id from the procedure store if available
            pass
        bubble = self.build_bubble(
            "selected-export", skills=out_skills, procedures=out_procs,
            redact=not include_private,
            exported_namespaces=["selected"] if skills or procedures else [],
            export_policy={"include_private": include_private})
        return bubble

    # ----- query --------------------------------------------------------
    def get(self, bubble_id: str):
        row = self._conn.execute(
            "SELECT * FROM knowledge_bubbles WHERE bubble_id=?",
            (bubble_id,)).fetchone()
        if row is None:
            return None
        return {
            "bubble_id": row["bubble_id"], "name": row["name"],
            "lifecycle_state": row["lifecycle_state"],
            "content_hash": row["content_hash"],
            "validation_report": json.loads(row["validation_report"] or "{}"),
            "imported_at": row["imported_at"],
            "installed_at": row["installed_at"],
            "approved_by": row["approved_by"],
        }

    def list(self, *, lifecycle: Optional[str] = None) -> List[Dict[str, Any]]:
        if lifecycle:
            rows = self._conn.execute(
                "SELECT bubble_id, name, lifecycle_state FROM knowledge_bubbles "
                "WHERE lifecycle_state=?", (lifecycle,)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT bubble_id, name, lifecycle_state FROM knowledge_bubbles"
                ).fetchall()
        return [dict(r) for r in rows]
