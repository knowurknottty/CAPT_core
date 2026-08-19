"""Canonical construction path for the CAPT runtime.

This module owns component lifecycle only.  It does not add a runtime, daemon,
or authority path: RuntimeService remains the sole command surface, and
RuntimeCommandService remains the authenticated operator relay.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .driver_host import DriverHost
from .drivers.openharness import DESCRIPTOR, OpenHarnessDriver
from .drivers.registry import DriverRegistry
from .memory.engine import MemoryTriggerEngine
from .memory.store import MemoryStore
from .services import RuntimeService
from .store import EventStore
from .task_resolver import TaskResolver


@dataclass
class RuntimeComposition:
    """One owned set of runtime dependencies for an operator process."""

    store: EventStore
    service: RuntimeService
    registry: DriverRegistry
    memory_store: MemoryStore
    memory_engine: MemoryTriggerEngine

    def command_service(self, operator_id: str, session_id: str):
        # Import lazily to avoid a desktop-to-runtime import cycle at module load.
        from desktop.m1_command_service import RuntimeCommandService

        return RuntimeCommandService(
            self.store,
            operator_id,
            session_id,
            memory_engine=self.memory_engine,
            runtime_service=self.service,
        )

    def openharness_host(
        self, *, target_repo: str, staging_root: str, enforce_memory: bool = True
    ) -> DriverHost:
        if not self.registry.is_registered(DESCRIPTOR["driverId"]):
            self.registry.register(DESCRIPTOR)
        host = DriverHost(
            self.registry,
            staging_root,
            target_repo,
            memory_engine=self.memory_engine if enforce_memory else None,
        )
        host.select_driver(OpenHarnessDriver(staging_root))
        return host

    def hermes_host(
        self, *, target_repo: str, staging_root: str, executable: Optional[str] = None,
        enforce_memory: bool = True, authored_skill_pack_root: Optional[str] = None,
        authored_skill_pack_lock: Optional[dict] = None,
    ) -> DriverHost:
        from .drivers.hermes import DESCRIPTOR as HERMES_DESCRIPTOR, HermesDriver
        if not self.registry.is_registered(HERMES_DESCRIPTOR["driverId"]):
            self.registry.register(HERMES_DESCRIPTOR)
        host = DriverHost(
            self.registry, staging_root, target_repo,
            memory_engine=self.memory_engine if enforce_memory else None,
            authored_skill_pack_root=authored_skill_pack_root,
            authored_skill_pack_lock=authored_skill_pack_lock,
        )
        host.select_driver(HermesDriver(staging_root, executable=executable,
                                        task_resolver=self.task_resolver()))
        return host

    def task_resolver(self) -> TaskResolver:
        """Return CAPT's authoritative task-reference resolver."""
        return TaskResolver(self.store)

    def close(self) -> None:
        self.memory_store.close()
        self.store.close()


def create_runtime(
    ledger_path: str,
    *,
    memory_path: Optional[str] = None,
    model_safe_limit_steps: int = 8,
) -> RuntimeComposition:
    """Construct every operator-owned runtime dependency exactly once."""
    ledger = str(Path(ledger_path))
    store = EventStore(ledger)
    memory_store = MemoryStore(memory_path or (ledger + ".memory"))
    memory_engine = MemoryTriggerEngine(
        memory_store,
        model_safe_limit_steps=model_safe_limit_steps,
        ledger_db=ledger + ".memory-policy",
    )
    return RuntimeComposition(
        store=store,
        service=RuntimeService(store),
        registry=DriverRegistry(),
        memory_store=memory_store,
        memory_engine=memory_engine,
    )
