"""Session lifecycle management for CAPT Runtime.

Provides session registration, lifecycle signaling via KHSB, and CTP
continuation binding. This module wires existing primitives together;
it does not own memory, transport, or continuity contracts.

Responsibilities:
- Session registration with KHSB topic convention
- CTP transaction binding for session continuity
- Lifecycle event publishing via KHSB
- Session state tracking (registered, active, checkpointed, closed)

Does NOT:
- Own memory storage (delegates to MemoryStore)
- Own transport (uses KHSB)
- Own continuity contracts (uses CTP)
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from capt_solo.khsb.bus import KHSB
from capt_solo.ctp.journal import CTPRuntime


class SessionLifecycleError(Exception):
    """Raised when session lifecycle operations fail."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SessionLifecycle:
    """Manages session lifecycle via KHSB + CTP integration."""

    def __init__(
        self,
        bus: KHSB,
        ctp: CTPRuntime,
        *,
        operator_id: Optional[str] = None,
    ) -> None:
        self._bus = bus
        self._ctp = ctp
        self._operator_id = operator_id or "operator"
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._sub_id = self._bus.subscribe("session.lifecycle", self._on_session_event)
        self._restore_from_ctp()

    def _restore_from_ctp(self) -> None:
        """Rebuild a reference-only session projection from CTP receipts."""
        for receipt in self._ctp.receipts():
            if receipt.status != "committed":
                continue
            meta = receipt.meta
            action = meta.get("lifecycleAction")
            session_id = meta.get("sessionId")
            if not action or not session_id:
                continue
            if action == "register":
                self._sessions[session_id] = {
                    "sessionId": session_id,
                    "missionId": meta.get("missionId"),
                    "operatorId": meta.get("operatorId", self._operator_id),
                    "state": "active",
                    "ctpTxId": receipt.tx_id,
                    "createdAt": receipt.created_at,
                }
            elif session_id in self._sessions and action == "checkpoint":
                self._sessions[session_id].update(
                    {
                        "state": "checkpointed",
                        "ctpTxId": receipt.tx_id,
                        "exactNextAction": meta.get("exactNextAction"),
                        "offloadId": meta.get("offloadId"),
                    }
                )
            elif session_id in self._sessions and action == "resume":
                self._sessions[session_id].update(
                    {"state": "active", "ctpTxId": receipt.tx_id}
                )
            elif session_id in self._sessions and action == "close":
                self._sessions[session_id].update(
                    {
                        "state": "closed",
                        "ctpTxId": receipt.tx_id,
                        "closeReason": meta.get("reason"),
                    }
                )

    def _on_session_event(self, message: Any) -> None:
        """Internal handler for session lifecycle events."""
        payload = message.payload
        session_id = payload.get("sessionId")
        action = payload.get("action")
        if session_id and action == "register":
            self._sessions[session_id] = {
                "sessionId": session_id,
                "missionId": payload.get("missionId"),
                "operatorId": payload.get("operatorId", self._operator_id),
                "state": "registered",
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "ctpTxId": None,
            }

    def register_session(
        self,
        session_id: str,
        mission_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a new session with lifecycle tracking.

        Args:
            session_id: Unique session identifier
            mission_id: Associated mission identifier
            operator_id: Operator initiating the session

        Returns:
            Registration result with session_id, mission_id, ctp_tx_id
        """
        operator_id = operator_id or self._operator_id
        existing = self._sessions.get(session_id)
        if existing is not None:
            if existing.get("missionId") != mission_id:
                raise SessionLifecycleError(
                    "SESSION_MISSION_MISMATCH",
                    f"session {session_id} is already bound to another mission",
                )
            return {
                "sessionId": session_id,
                "missionId": mission_id,
                "ctpTxId": existing.get("ctpTxId"),
                "state": existing.get("state"),
            }

        # Begin CTP transaction for session continuity
        ctp_tx_id = self._ctp.begin(
            correlation_id=session_id,
            idempotency_key=f"session-register:{session_id}",
            meta={
                "lifecycleAction": "register",
                "sessionId": session_id,
                "missionId": mission_id,
                "operatorId": operator_id,
            },
        )

        # Publish registration event via KHSB
        self._bus.publish(
            topic="session.lifecycle",
            payload={
                "sessionId": session_id,
                "missionId": mission_id,
                "operatorId": operator_id,
                "action": "register",
                "ctpTxId": ctp_tx_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            correlation_id=session_id,
        )

        # Track session state
        self._sessions[session_id] = {
            "sessionId": session_id,
            "missionId": mission_id,
            "operatorId": operator_id,
            "state": "active",
            "ctpTxId": ctp_tx_id,
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._ctp.commit(ctp_tx_id)

        return {
            "sessionId": session_id,
            "missionId": mission_id,
            "ctpTxId": ctp_tx_id,
            "state": "active",
        }

    def checkpoint_session(
        self,
        session_id: str,
        mission_id: str,
        exact_next_action: str,
        offload_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Checkpoint session state with CTP continuation.

        Args:
            session_id: Session to checkpoint
            mission_id: Associated mission
            exact_next_action: The precise next action on resume
            offload_id: CAPTMem offload record identifier

        Returns:
            Checkpoint result with ctp_tx_id and session state
        """
        if session_id not in self._sessions:
            raise SessionLifecycleError(
                "SESSION_NOT_REGISTERED",
                f"session {session_id} not registered",
            )

        # Begin CTP continuation transaction
        ctp_tx_id = self._ctp.begin(
            correlation_id=session_id,
            idempotency_key=f"session-checkpoint:{session_id}:{offload_id or 'unknown'}",
            meta={
                "lifecycleAction": "checkpoint",
                "sessionId": session_id,
                "missionId": mission_id,
                "exactNextAction": exact_next_action,
                "offloadId": offload_id,
            },
        )

        # Publish checkpoint event
        self._bus.publish(
            topic="session.lifecycle",
            payload={
                "sessionId": session_id,
                "missionId": mission_id,
                "action": "checkpoint",
                "exactNextAction": exact_next_action,
                "offloadId": offload_id,
                "ctpTxId": ctp_tx_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            correlation_id=session_id,
        )

        # Update session state
        self._sessions[session_id]["state"] = "checkpointed"
        self._sessions[session_id]["ctpTxId"] = ctp_tx_id
        self._sessions[session_id]["exactNextAction"] = exact_next_action
        self._sessions[session_id]["offloadId"] = offload_id
        self._ctp.commit(ctp_tx_id)

        return {
            "sessionId": session_id,
            "ctpTxId": ctp_tx_id,
            "exactNextAction": exact_next_action,
            "offloadId": offload_id,
        }

    def resume_session(
        self,
        session_id: str,
        ctp_receipt_tx_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resume a checkpointed session.

        Args:
            session_id: Session to resume
            ctp_receipt_tx_id: CTP transaction ID for receipt validation

        Returns:
            Resume result with session state and exact_next_action
        """
        if session_id not in self._sessions:
            raise SessionLifecycleError(
                "SESSION_NOT_REGISTERED",
                f"session {session_id} not registered",
            )

        session = self._sessions[session_id]

        # Validate CTP receipt if provided
        if ctp_receipt_tx_id:
            try:
                receipt = self._ctp.get_receipt(ctp_receipt_tx_id)
                if receipt.status != "committed":
                    raise SessionLifecycleError(
                        "CTP_RECEIPT_INVALID",
                        f"CTP receipt for {ctp_receipt_tx_id} not committed",
                    )
            except Exception as e:
                raise SessionLifecycleError("CTP_RECEIPT_INVALID", str(e))

        resume_tx_id = self._ctp.begin(
            correlation_id=session_id,
            idempotency_key=f"session-resume:{session_id}:{session.get('ctpTxId')}",
            meta={
                "lifecycleAction": "resume",
                "sessionId": session_id,
                "missionId": session.get("missionId"),
                "exactNextAction": session.get("exactNextAction"),
                "offloadId": session.get("offloadId"),
            },
        )

        # Publish resume event
        self._bus.publish(
            topic="session.lifecycle",
            payload={
                "sessionId": session_id,
                "missionId": session.get("missionId"),
                "action": "resume",
                "exactNextAction": session.get("exactNextAction"),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            correlation_id=session_id,
        )

        # Update session state
        session["state"] = "active"
        session["ctpTxId"] = resume_tx_id
        self._ctp.commit(resume_tx_id)

        return {
            "sessionId": session_id,
            "missionId": session.get("missionId"),
            "exactNextAction": session.get("exactNextAction"),
            "offloadId": session.get("offloadId"),
        }

    def close_session(
        self,
        session_id: str,
        reason: str = "completed",
    ) -> Dict[str, Any]:
        """Close a session.

        Args:
            session_id: Session to close
            reason: Closure reason

        Returns:
            Closure result
        """
        if session_id not in self._sessions:
            raise SessionLifecycleError(
                "SESSION_NOT_REGISTERED",
                f"session {session_id} not registered",
            )

        session = self._sessions[session_id]
        close_tx_id = self._ctp.begin(
            correlation_id=session_id,
            idempotency_key=f"session-close:{session_id}:{session.get('ctpTxId')}",
            meta={
                "lifecycleAction": "close",
                "sessionId": session_id,
                "missionId": session.get("missionId"),
                "reason": reason,
            },
        )

        # Publish close event
        self._bus.publish(
            topic="session.lifecycle",
            payload={
                "sessionId": session_id,
                "missionId": session.get("missionId"),
                "action": "close",
                "reason": reason,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            correlation_id=session_id,
        )

        # Update session state
        session["state"] = "closed"
        session["closedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        session["closeReason"] = reason
        session["ctpTxId"] = close_tx_id
        self._ctp.commit(close_tx_id)

        return {
            "sessionId": session_id,
            "state": "closed",
            "reason": reason,
        }

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current session state."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """List all registered sessions."""
        return dict(self._sessions)
