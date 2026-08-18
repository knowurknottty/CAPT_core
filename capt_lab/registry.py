"""Deterministic registry for bounded Inversion Labs specialist engines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from .contracts import LabEngineRequest, LabEngineResult
from .provenance import donor_for


class LabRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class LabOperationDescriptor:
    name: str
    epistemic_class: str
    description: str

    def to_mapping(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "epistemicClass": self.epistemic_class,
            "description": self.description,
        }


@dataclass(frozen=True)
class LabEngineDescriptor:
    engine_id: str
    engine_version: str
    display_name: str
    description: str
    operations: Tuple[LabOperationDescriptor, ...]
    provenance: Mapping[str, Any]
    requires_filesystem: bool = False
    requires_network: bool = False

    def operation(self, name: str) -> Optional[LabOperationDescriptor]:
        return next((item for item in self.operations if item.name == name), None)


EngineCallable = Callable[[LabEngineRequest, Mapping[str, Any]], LabEngineResult]


class LabEngineRegistry:
    def __init__(self) -> None:
        self._items: Dict[str, Tuple[LabEngineDescriptor, Optional[EngineCallable]]] = {}

    def register(self, descriptor: LabEngineDescriptor, engine: Optional[EngineCallable] = None) -> None:
        if descriptor.engine_id in self._items:
            raise LabRegistryError("engine %s already registered" % descriptor.engine_id)
        if not descriptor.operations:
            raise LabRegistryError("engine must expose at least one operation")
        self._items[descriptor.engine_id] = (descriptor, engine)

    def describe(self) -> list:
        output = []
        for engine_id in sorted(self._items):
            descriptor, engine = self._items[engine_id]
            output.append({
                "engineId": descriptor.engine_id,
                "engineVersion": descriptor.engine_version,
                "displayName": descriptor.display_name,
                "description": descriptor.description,
                "operations": [item.to_mapping() for item in descriptor.operations],
                "requiresFilesystem": descriptor.requires_filesystem,
                "requiresNetwork": descriptor.requires_network,
                "available": engine is not None,
                "provenance": dict(descriptor.provenance),
            })
        return output

    def execute(self, request: LabEngineRequest, context: Mapping[str, Any]) -> LabEngineResult:
        item = self._items.get(request.engine_id)
        if item is None:
            raise LabRegistryError("unknown engine %s" % request.engine_id)
        descriptor, engine = item
        if descriptor.operation(request.operation) is None:
            raise LabRegistryError("unknown operation %s for %s" % (request.operation, request.engine_id))
        if engine is None:
            raise LabRegistryError("engine %s is unavailable" % request.engine_id)
        return engine(request, context)


def _descriptor(engine_id: str, name: str, description: str,
                operations: Tuple[LabOperationDescriptor, ...],
                requires_filesystem: bool = False) -> LabEngineDescriptor:
    return LabEngineDescriptor(
        engine_id=engine_id,
        engine_version="0.1.0",
        display_name=name,
        description=description,
        operations=operations,
        provenance=donor_for(engine_id),
        requires_filesystem=requires_filesystem,
        requires_network=False,
    )


def build_default_registry() -> LabEngineRegistry:
    from .engines.math_engine import execute_math

    registry = LabEngineRegistry()
    registry.register(_descriptor(
        "lab.math", "CAPTLang Math", "Bounded deterministic and heuristic mathematical instruments.",
        (
            LabOperationDescriptor("cyclotomic_summary", "calculation", "Summarize a bounded cyclotomic field."),
            LabOperationDescriptor("mcmillan_tc", "calculation", "Evaluate the McMillan transition-temperature equation."),
        ),
    ), execute_math)
    registry.register(_descriptor(
        "lab.analogy", "Structural Analogy", "Deterministic VSA/SME-inspired structural comparison.",
        (
            LabOperationDescriptor("structural_map", "heuristic", "Score and map supplied structures."),
            LabOperationDescriptor("schema_abstract", "advisory", "Abstract a schema from supplied structures."),
        ),
    ))
    registry.register(_descriptor(
        "lab.consensus", "QIPC Consensus", "Bounded consensus and uncertainty diagnostics.",
        (LabOperationDescriptor("aggregate_beliefs", "advisory", "Aggregate supplied belief probabilities."),),
    ))
    registry.register(_descriptor(
        "lab.forge", "Forge", "Read-only repository archaeology, gap synthesis, and implementation briefs.",
        (
            LabOperationDescriptor("repository_archaeology", "advisory", "Inspect bounded repository structure."),
            LabOperationDescriptor("gap_analysis", "advisory", "Synthesize bounded implementation gaps."),
            LabOperationDescriptor("sigma_brief", "advisory", "Generate a bounded SIGMA implementation brief."),
            LabOperationDescriptor("forgeproof_score", "advisory", "Apply the ForgeProof evaluation rubric."),
        ),
        requires_filesystem=True,
    ))
    return registry
