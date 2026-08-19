"""Canonical construction path for the CAPT runtime.

This module owns component lifecycle only.  It does not add a runtime, daemon,
or authority path: RuntimeService remains the sole command surface, and
RuntimeCommandService remains the authenticated operator relay.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from .driver_host import DriverHost
from .drivers.openharness import DESCRIPTOR, OpenHarnessDriver
from .drivers.registry import DriverRegistry
from .memory.engine import MemoryTriggerEngine
from .memory.store import MemoryStore
from .services import RuntimeService
from .store import EventStore
from .task_resolver import TaskResolver
from .tool_broker import ToolBroker
from .tools.adapters import (
    CodeExecutionAdapter, DockerTerminalToolAdapter, FileToolAdapter,
    SSHTerminalToolAdapter, TerminalToolAdapter,
)
from .tools.backends.docker import DockerProcessBackend, DockerProfile, DockerProfileRegistry
from .tools.backends.ssh import SSHProcessBackend, SSHProfile, SSHProfileRegistry
from .tools.builtins import (
    CODE_EXECUTION_DESCRIPTOR, FILE_OPERATIONS_DESCRIPTOR,
    TERMINAL_DOCKER_DESCRIPTOR, TERMINAL_LOCAL_DESCRIPTOR, TERMINAL_SSH_DESCRIPTOR,
)
from .tools.registry import ToolRegistry


@dataclass
class RuntimeComposition:
    """One owned set of runtime dependencies for an operator process."""

    store: EventStore
    service: RuntimeService
    registry: DriverRegistry
    memory_store: MemoryStore
    memory_engine: MemoryTriggerEngine
    tool_registry: ToolRegistry
    tool_broker: ToolBroker
    ssh_profile_registry: SSHProfileRegistry
    docker_profile_registry: DockerProfileRegistry

    def command_service(self, operator_id: str, session_id: str):
        # Import lazily to avoid a desktop-to-runtime import cycle at module load.
        from desktop.m1_command_service import RuntimeCommandService

        return RuntimeCommandService(
            self.store,
            operator_id,
            session_id,
            memory_engine=self.memory_engine,
            runtime_service=self.service,
            tool_broker=self.tool_broker,
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
        enforce_memory: bool = True, dispatch_prompt: str = "",
    ) -> DriverHost:
        from .drivers.hermes import DESCRIPTOR as HERMES_DESCRIPTOR, HermesDriver
        if not self.registry.is_registered(HERMES_DESCRIPTOR["driverId"]):
            self.registry.register(HERMES_DESCRIPTOR)
        host = DriverHost(self.registry, staging_root, target_repo,
                          memory_engine=self.memory_engine if enforce_memory else None)
        host.select_driver(HermesDriver(
            staging_root, executable=executable, task_resolver=self.task_resolver(),
            dispatch_prompt=dispatch_prompt,
        ))
        return host

    def provider_host(
        self, *, target_repo: str, staging_root: str, provider_id: str, model: str,
        base_url: str, api_key: str = "", dispatch_prompt: str = "",
    ) -> DriverHost:
        from .drivers.provider import DESCRIPTOR as PROVIDER_DESCRIPTOR, ProviderDriver
        if not self.registry.is_registered(PROVIDER_DESCRIPTOR["driverId"]):
            self.registry.register(PROVIDER_DESCRIPTOR)
        host = DriverHost(self.registry, staging_root, target_repo)
        host.select_driver(ProviderDriver(
            staging_root, provider_id=provider_id, model=model, base_url=base_url,
            api_key=api_key, task_resolver=self.task_resolver(),
            dispatch_prompt=dispatch_prompt,
        ))
        return host

    def task_resolver(self) -> TaskResolver:
        """Return CAPT's authoritative task-reference resolver."""
        return TaskResolver(self.store)

    def reconcile_stranded_tools(self) -> list[dict[str, Any]]:
        """Reconcile durable ToolExecutions without redispatching adapters."""
        return self.tool_broker.reconcile_stranded()

    def close(self) -> None:
        self.memory_store.close()
        self.store.close()


def create_runtime(
    ledger_path: str,
    *,
    memory_path: Optional[str] = None,
    model_safe_limit_steps: int = 8,
    ssh_profiles: Iterable[SSHProfile] = (),
    docker_profiles: Iterable[DockerProfile] = (),
) -> RuntimeComposition:
    """Construct every operator-owned runtime dependency exactly once."""
    ledger = str(Path(ledger_path))
    store = EventStore(ledger)
    service = RuntimeService(store)
    memory_store = MemoryStore(memory_path or (ledger + ".memory"))
    memory_engine = MemoryTriggerEngine(
        memory_store,
        model_safe_limit_steps=model_safe_limit_steps,
        ledger_db=ledger + ".memory-policy",
    )
    tool_registry = ToolRegistry()

    def readiness_probe(tool_id: str, probe: Callable[[], dict[str, object]]):
        def checked() -> dict[str, object]:
            state = dict(probe())
            return {
                "schemaVersion": "1.0.0",
                "toolId": tool_id,
                "status": state["status"],
                "reason": state["reason"],
                "checkedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        return checked

    terminal = TerminalToolAdapter()
    files = FileToolAdapter()
    code = CodeExecutionAdapter()
    ssh_profile_registry = SSHProfileRegistry(ssh_profiles)
    ssh_terminal = SSHTerminalToolAdapter(SSHProcessBackend(ssh_profile_registry))
    docker_profile_registry = DockerProfileRegistry(docker_profiles)
    docker_terminal = DockerTerminalToolAdapter(DockerProcessBackend(docker_profile_registry))
    for descriptor, adapter in (
        (TERMINAL_LOCAL_DESCRIPTOR, terminal),
        (TERMINAL_SSH_DESCRIPTOR, ssh_terminal),
        (TERMINAL_DOCKER_DESCRIPTOR, docker_terminal),
        (FILE_OPERATIONS_DESCRIPTOR, files),
        (CODE_EXECUTION_DESCRIPTOR, code),
    ):
        tool_registry.register(
            descriptor,
            adapter,
            readiness_probe=readiness_probe(descriptor["toolId"], adapter.readiness),
        )
    now = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tool_broker = ToolBroker(service, tool_registry, now=now)
    return RuntimeComposition(
        store=store,
        service=service,
        registry=DriverRegistry(),
        memory_store=memory_store,
        memory_engine=memory_engine,
        tool_registry=tool_registry,
        tool_broker=tool_broker,
        ssh_profile_registry=ssh_profile_registry,
        docker_profile_registry=docker_profile_registry,
    )
