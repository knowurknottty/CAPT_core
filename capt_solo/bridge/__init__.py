"""CAPT Bootstrap Bridge — runtime handoff from Hermes to the CAPT Agent Runner.

The bridge is a **launcher and authority gate**. It deliberately contains no
memory retrieval, ContextPack construction, MemoryUseGate, CTP, KHSB, checkpoint,
or provider logic — all of that stays inside canonical CAPT.
"""

from capt_solo.bridge.contracts import (
    BOOT_STATE_FULL,
    BOOT_STATE_PARTIAL,
    BOOT_STATE_SKILL_ONLY,
    BOOT_STATE_UNAVAILABLE,
    BOOT_STATES,
    OWNER_CAPT_AFTER_READY,
    OWNER_HERMES_BEFORE_BRIDGE,
    OWNER_NONE_WHEN_BLOCKED,
    PROVIDER_OWNERS,
    BridgeReadyEvent,
    BridgeResult,
    ProviderOwnership,
    ProviderOwnershipViolation,
    blocked,
)

__all__ = [
    "BOOT_STATE_FULL",
    "BOOT_STATE_PARTIAL",
    "BOOT_STATE_SKILL_ONLY",
    "BOOT_STATE_UNAVAILABLE",
    "BOOT_STATES",
    "OWNER_CAPT_AFTER_READY",
    "OWNER_HERMES_BEFORE_BRIDGE",
    "OWNER_NONE_WHEN_BLOCKED",
    "PROVIDER_OWNERS",
    "BridgeReadyEvent",
    "BridgeResult",
    "ProviderOwnership",
    "ProviderOwnershipViolation",
    "blocked",
]
