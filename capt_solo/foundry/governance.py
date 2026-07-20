"""CAPT Solo v0.4 — Governance Layer.

Nothing may rewrite trust, evidence, lifecycle, proofs, publish skills, or
install bubbles without explicit transaction boundaries.

Every governance action generates:
    - a CTP receipt (transaction id + status)
    - an audit trail entry (actor, reason, timestamp, rollback info)
    - a rollback reference

This module provides a single Governance facade that wraps the foundry
subsystems (SkillFoundry, CapabilityRegistry, KnowledgeBubbleRuntime) so that
every consequential mutation is CTP-bounded and audited.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.ctp.journal import CTPRuntime
from capt_solo.foundry.skill_foundry import SkillFoundry
from capt_solo.foundry.registry import CapabilityRegistry
from capt_solo.foundry.bubble import KnowledgeBubbleRuntime


@dataclass
class GovernanceReceipt:
    action: str
    actor: str
    ctp_tx_id: Optional[str]
    status: str
    timestamp: float
    target: str
    reason: str
    rollback_ref: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action, "actor": self.actor,
            "ctp_tx_id": self.ctp_tx_id, "status": self.status,
            "timestamp": self.timestamp, "target": self.target,
            "reason": self.reason, "rollback_ref": self.rollback_ref,
        }


class Governance:
    """Wraps foundry mutations in CTP transactions + audit trail."""

    def __init__(self, conn, ctp: CTPRuntime,
                 foundry: Optional[SkillFoundry] = None,
                 registry: Optional[CapabilityRegistry] = None,
                 bubbles: Optional[KnowledgeBubbleRuntime] = None) -> None:
        self._conn = conn
        self._ctp = ctp
        self._sf = foundry
        self._reg = registry
        self._bubbles = bubbles

    # ----- governed wrappers -------------------------------------------
    def _act(self, action: str, actor: str, target: str, reason: str,
             fn) -> GovernanceReceipt:
        """Run `fn` inside a CTP transaction; record audit + receipt."""
        if not actor:
            raise MemoryError_("governance action requires a named actor")
        tx_id = self._ctp.begin(
            correlation_id=f"gov:{action}:{target}",
            meta={"action": action, "actor": actor, "target": target})
        try:
            result = fn(tx_id)
            rcpt = self._ctp.commit(tx_id)
            status = "committed"
        except Exception as e:
            try:
                self._ctp.abort(tx_id)
            except Exception:
                pass
            self._record(action, actor, target, reason, "aborted", None, None)
            raise
        self._record(action, actor, target, reason, status, rcpt.tx_id, None)
        return GovernanceReceipt(
            action=action, actor=actor, ctp_tx_id=rcpt.tx_id,
            status=status, timestamp=time.time(), target=target,
            reason=reason)

    def _record(self, action, actor, target, reason, status, ctp_tx_id, rollback_ref):
        self._conn.execute(
            """INSERT INTO governance_audit
               (audit_id, action, actor, ctp_tx_id, target, reason, status, timestamp, rollback_ref)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (uuid.uuid4().hex, action, actor, ctp_tx_id, target, reason,
             status, time.time(), rollback_ref))
        self._conn.commit()

    # ----- governed wrappers -------------------------------------------
    def publish_skill(self, skill_id: str, actor: str, reason: str = "",
                      ctp_tx_id: Optional[str] = None) -> GovernanceReceipt:
        if self._sf is None:
            raise MemoryError_("skill foundry not attached")
        return self._act("publish_skill", actor, skill_id, reason,
                         lambda tx: self._sf.publish(skill_id, ctp_tx_id=tx))

    def approve_capability(self, identifier: str, actor: str, reason: str = "",
                           ctp_tx_id: Optional[str] = None) -> GovernanceReceipt:
        if self._reg is None:
            raise MemoryError_("registry not attached")
        return self._act("approve_capability", actor, identifier, reason,
                         lambda tx: self._reg.govern_approve(
                             identifier, actor, ctp_tx_id=tx))

    def install_bubble(self, bubble_id: str, actor: str, reason: str = "",
                       ctp_tx_id: Optional[str] = None) -> GovernanceReceipt:
        if self._bubbles is None:
            raise MemoryError_("bubble runtime not attached")
        return self._act("install_bubble", actor, bubble_id, reason,
                         lambda tx: self._bubbles.install_bubble(
                             bubble_id, ctp_tx_id=tx))

    def audit_trail(self, *, target: Optional[str] = None,
                    action: Optional[str] = None) -> List[Dict[str, Any]]:
        q = "SELECT * FROM governance_audit"
        args: List[Any] = []
        where = []
        if target:
            where.append("target=?")
            args.append(target)
        if action:
            where.append("action=?")
            args.append(action)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY timestamp DESC"
        rows = self._conn.execute(q, args).fetchall()
        return [dict(r) for r in rows]
