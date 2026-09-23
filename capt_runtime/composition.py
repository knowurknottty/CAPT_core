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

from .aggregates import SandboxLeaseAggregate
from .cloudflare_resource_adoption import CloudflareResourceBindingRegistry
from .driver_host import DriverHost
from .drivers.openharness import DESCRIPTOR, OpenHarnessDriver
from .drivers.registry import DriverRegistry
from .mcp import MCPManager
from .memory.engine import MemoryTriggerEngine
from .memory.store import MemoryStore
from .sandbox_reconciliation import SandboxLeaseReconciler
from .services import RuntimeService
from .steered_service import SteeredRuntimeService
from .store import EventStore
from .task_resolver import TaskResolver
from .tool_broker import ToolBroker
from .tools.adapters import (
    CloudflareTerminalToolAdapter,
    CodeExecutionAdapter,
    DockerTerminalToolAdapter,
    FileToolAdapter,
    InversionSandboxLifecycleToolAdapter,
    InversionSandboxTerminalToolAdapter,
    SSHTerminalToolAdapter,
    TerminalToolAdapter,
)
from .tools.backends.cloudflare import (
    CloudflareSandboxBackend,
    CloudflareSandboxProfile,
    CloudflareSandboxProfileRegistry,
)
from .tools.backends.cloudflare_artifacts import CloudflareBinaryArtifactSpool
from .tools.backends.cloudflare_free_planner import CloudflareFreeExecutionPlanner
from .tools.backends.cloudflare_free_router import CloudflareFreeTierRouter
from .tools.backends.cloudflare_native import (
    CloudflareBrowserRunner,
    CloudflareD1StateStore,
    CloudflareNativeSurfaces,
    CloudflareQueueDelegator,
    CloudflareWorkersAIInferencer,
    CloudflareWorkersCoordinator,
    CloudflareWorkflowOrchestrator,
)
from .tools.backends.cloudflare_native_api import (
    CloudflareNativeAPIBridge,
    CloudflareNativeAPIProfile,
)
from .tools.backends.cloudflare_usage import CloudflareUsageLedger
from .tools.backends.docker import (
    DockerProcessBackend,
    DockerProfile,
    DockerProfileRegistry,
)
from .tools.backends.inversion_sandbox import (
    InversionSandboxProcessBackend,
    InversionSandboxProfile,
    InversionSandboxProfileRegistry,
)
from .tools.backends.ssh import SSHProcessBackend, SSHProfile, SSHProfileRegistry
from .tools.builtins import (
    CODE_EXECUTION_DESCRIPTOR,
    FILE_OPERATIONS_DESCRIPTOR,
    SANDBOX_INVERSION_DESCRIPTOR,
    TERMINAL_CLOUDFLARE_DESCRIPTOR,
    TERMINAL_DOCKER_DESCRIPTOR,
    TERMINAL_INVERSION_SANDBOX_DESCRIPTOR,
    TERMINAL_LOCAL_DESCRIPTOR,
    TERMINAL_SSH_DESCRIPTOR,
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
    sandbox_reconciler: SandboxLeaseReconciler
    sandbox_reconciliation_report: list[dict[str, Any]]
    ssh_profile_registry: SSHProfileRegistry
    docker_profile_registry: DockerProfileRegistry
    inversion_sandbox_profile_registry: InversionSandboxProfileRegistry
    cloudflare_profile_registry: CloudflareSandboxProfileRegistry
    cloudflare_usage_ledger: CloudflareUsageLedger
    cloudflare_free_planner: CloudflareFreeExecutionPlanner
    cloudflare_artifact_spool: CloudflareBinaryArtifactSpool | None
    cloudflare_native: CloudflareNativeSurfaces | None
    mcp_manager: MCPManager | None

    def command_service(self, operator_id: str, session_id: str, *, prompt_compiler=None, operator_control=None):
        # Import lazily to avoid a desktop-to-runtime import cycle at module load.
        from desktop.replay_command_service import ReplayRuntimeCommandService

        return ReplayRuntimeCommandService(
            self.store,
            operator_id,
            session_id,
            memory_engine=self.memory_engine,
            runtime_service=self.service,
            tool_broker=self.tool_broker,
            prompt_compiler=prompt_compiler,
            operator_control=operator_control,
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
        authored_skill_pack_root: Optional[str] = None,
        authored_skill_pack_lock: Optional[dict] = None,
    ) -> DriverHost:
        from .drivers.hermes import DESCRIPTOR as HERMES_DESCRIPTOR
        from .drivers.hermes import HermesDriver
        if not self.registry.is_registered(HERMES_DESCRIPTOR["driverId"]):
            self.registry.register(HERMES_DESCRIPTOR)
        host = DriverHost(
            self.registry, staging_root, target_repo,
            memory_engine=self.memory_engine if enforce_memory else None,
            authored_skill_pack_root=authored_skill_pack_root,
            authored_skill_pack_lock=authored_skill_pack_lock,
        )
        host.select_driver(HermesDriver(
            staging_root, executable=executable, task_resolver=self.task_resolver(),
            dispatch_prompt=dispatch_prompt,
        ))
        return host

    def provider_host(
        self, *, target_repo: str, staging_root: str, provider_id: str, model: str,
        base_url: str, api_key: str = "", dispatch_prompt: str = "",
        reasoning_effort: str = "", governor=None, tool_bridge=None,
    ) -> DriverHost:
        from .drivers.provider import DESCRIPTOR as PROVIDER_DESCRIPTOR
        from .drivers.provider import ProviderDriver
        if not self.registry.is_registered(PROVIDER_DESCRIPTOR["driverId"]):
            self.registry.register(PROVIDER_DESCRIPTOR)
        host = DriverHost(self.registry, staging_root, target_repo)
        host.select_driver(ProviderDriver(
            staging_root, provider_id=provider_id, model=model, base_url=base_url,
            api_key=api_key, task_resolver=self.task_resolver(),
            dispatch_prompt=dispatch_prompt, reasoning_effort=reasoning_effort,
            governor=governor, tool_bridge=tool_bridge,
        ))
        return host

    def task_resolver(self) -> TaskResolver:
        """Return CAPT's authoritative task-reference resolver."""
        return TaskResolver(self.store)

    def reconcile_stranded_tools(self) -> list[dict[str, Any]]:
        """Reconcile durable ToolExecutions without redispatching adapters."""
        return self.tool_broker.reconcile_stranded()

    def reconcile_sandbox_leases(self) -> list[dict[str, Any]]:
        """Reconcile persistent sandbox leases without creating/adopting resources."""
        self.sandbox_reconciliation_report = self.sandbox_reconciler.reconcile_all()
        return list(self.sandbox_reconciliation_report)

    def close(self) -> None:
        if self.mcp_manager is not None:
            self.mcp_manager.close()
        self.cloudflare_usage_ledger.close()
        self.memory_engine.close()
        self.memory_store.close()
        self.store.close()


def create_runtime(
    ledger_path: str,
    *,
    memory_path: Optional[str] = None,
    model_safe_limit_steps: int = 8,
    ssh_profiles: Iterable[SSHProfile] = (),
    docker_profiles: Iterable[DockerProfile] = (),
    inversion_sandbox_profiles: Iterable[InversionSandboxProfile] = (),
    cloudflare_profiles: Iterable[CloudflareSandboxProfile] = (),
    cloudflare_native_profile: CloudflareNativeAPIProfile | None = None,
    enable_mcp: bool = False,
    mcp_timeout: float = 3.0,
) -> RuntimeComposition:
    """Construct every operator-owned runtime dependency exactly once."""
    ledger = str(Path(ledger_path))
    store = EventStore(ledger)
    service = SteeredRuntimeService(store)
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
    inversion_sandbox_profile_registry = InversionSandboxProfileRegistry(inversion_sandbox_profiles)
    inversion_sandbox_backend = InversionSandboxProcessBackend(inversion_sandbox_profile_registry)
    inversion_sandbox_lifecycle = InversionSandboxLifecycleToolAdapter(
        inversion_sandbox_backend, store
    )
    inversion_sandbox_terminal = InversionSandboxTerminalToolAdapter(
        inversion_sandbox_backend,
        lease_resolver=lambda lease_id: store.load_state(
            SandboxLeaseAggregate.stream_id(lease_id)
        ),
    )
    cloudflare_profile_registry = CloudflareSandboxProfileRegistry(cloudflare_profiles)
    cloudflare_free_router = CloudflareFreeTierRouter.default()
    cloudflare_usage_ledger = CloudflareUsageLedger(
        ledger + ".cloudflare-usage", router=cloudflare_free_router
    )
    cloudflare_free_planner = CloudflareFreeExecutionPlanner(
        cloudflare_usage_ledger, cloudflare_free_router
    )
    cloudflare_artifact_spool = None
    cloudflare_native = None
    if cloudflare_native_profile is not None:
        cloudflare_artifact_spool = CloudflareBinaryArtifactSpool(
            ledger + ".cloudflare-artifacts"
        )
        native_bridge = CloudflareNativeAPIBridge(
            cloudflare_native_profile,
            binding_registry=CloudflareResourceBindingRegistry(store),
            artifact_spool=cloudflare_artifact_spool,
        )
        cloudflare_native = CloudflareNativeSurfaces(
            workers=CloudflareWorkersCoordinator(cloudflare_free_planner, native_bridge),
            queues=CloudflareQueueDelegator(cloudflare_free_planner, native_bridge),
            d1=CloudflareD1StateStore(cloudflare_free_planner, native_bridge),
            browser=CloudflareBrowserRunner(cloudflare_free_planner, native_bridge),
            ai=CloudflareWorkersAIInferencer(cloudflare_free_planner, native_bridge),
            workflows=CloudflareWorkflowOrchestrator(cloudflare_free_planner, native_bridge),
        )
    cloudflare_terminal = CloudflareTerminalToolAdapter(
        CloudflareSandboxBackend(cloudflare_profile_registry)
    )
    for descriptor, adapter in (
        (TERMINAL_LOCAL_DESCRIPTOR, terminal),
        (TERMINAL_SSH_DESCRIPTOR, ssh_terminal),
        (TERMINAL_DOCKER_DESCRIPTOR, docker_terminal),
        (SANDBOX_INVERSION_DESCRIPTOR, inversion_sandbox_lifecycle),
        (TERMINAL_INVERSION_SANDBOX_DESCRIPTOR, inversion_sandbox_terminal),
        (TERMINAL_CLOUDFLARE_DESCRIPTOR, cloudflare_terminal),
        (FILE_OPERATIONS_DESCRIPTOR, files),
        (CODE_EXECUTION_DESCRIPTOR, code),
    ):
        tool_registry.register(
            descriptor,
            adapter,
            readiness_probe=readiness_probe(descriptor["toolId"], adapter.readiness),
        )
    mcp_manager = None
    if enable_mcp:
        mcp_manager = MCPManager(Path(ledger).parent, timeout=mcp_timeout)
        mcp_manager.refresh_all()
        for descriptor, adapter in mcp_manager.tool_bindings():
            tool_registry.register(
                descriptor,
                adapter,
                readiness_probe=readiness_probe(descriptor["toolId"], adapter.readiness),
            )
    now = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tool_broker = ToolBroker(service, tool_registry, now=now)
    sandbox_reconciler = SandboxLeaseReconciler(service, inversion_sandbox_backend, now=now)
    try:
        sandbox_reconciliation_report = sandbox_reconciler.reconcile_all()
    except Exception as exc:  # noqa: BLE001 - startup reconciliation is non-fatal and fail-closed
        sandbox_reconciliation_report = [{
            "status": "unproven",
            "reason": f"startup sandbox reconciliation failed: {type(exc).__name__}: {exc}"[:1024],
        }]
    return RuntimeComposition(
        store=store,
        service=service,
        registry=DriverRegistry(),
        memory_store=memory_store,
        memory_engine=memory_engine,
        tool_registry=tool_registry,
        tool_broker=tool_broker,
        sandbox_reconciler=sandbox_reconciler,
        sandbox_reconciliation_report=sandbox_reconciliation_report,
        ssh_profile_registry=ssh_profile_registry,
        docker_profile_registry=docker_profile_registry,
        inversion_sandbox_profile_registry=inversion_sandbox_profile_registry,
        cloudflare_profile_registry=cloudflare_profile_registry,
        cloudflare_usage_ledger=cloudflare_usage_ledger,
        cloudflare_free_planner=cloudflare_free_planner,
        cloudflare_artifact_spool=cloudflare_artifact_spool,
        cloudflare_native=cloudflare_native,
        mcp_manager=mcp_manager,
    )
