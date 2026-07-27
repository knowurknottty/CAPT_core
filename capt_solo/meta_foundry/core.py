"""CAPT Meta Foundry deterministic domain-compilation core.

This module implements a dependency-free vertical slice of the Meta Foundry:
registered domains, typed creation intents, deterministic compiler execution,
constraint evaluation, provenance, artifact hashing, and quarantine-aware
compiler lifecycles. It intentionally does not execute external renderers.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from capt_solo.core.errors import CaptSoloError


_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
_ALLOWED_COMPILER_STATES = {
    "candidate", "generated", "quarantined", "validated", "approved", "registered", "revoked"
}


class MetaFoundryError(CaptSoloError):
    """Base error for Meta Foundry operations."""


class DomainNotFoundError(MetaFoundryError):
    """Raised when a requested domain is not registered."""


class CompilerNotExecutableError(MetaFoundryError):
    """Raised when a compiler has not reached the registered lifecycle state."""


class ConstraintViolationError(MetaFoundryError):
    """Raised when one or more error-severity constraints fail."""

    def __init__(self, violations: Sequence["ConstraintResult"]) -> None:
        self.violations = tuple(violations)
        summary = "; ".join(v.message for v in self.violations)
        super().__init__(summary or "Constraint evaluation failed")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def _validate_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise MetaFoundryError(
            f"{label} must match {_IDENTIFIER.pattern!r}; received {value!r}"
        )


def _read_path(document: Mapping[str, Any], path: str) -> Any:
    if not path.startswith("$."):
        raise MetaFoundryError(f"Constraint path must begin with '$.': {path!r}")
    current: Any = document
    for segment in path[2:].split("."):
        if not isinstance(current, Mapping) or segment not in current:
            raise KeyError(path)
        current = current[segment]
    return current


@dataclass(frozen=True)
class ProvenanceRecord:
    source_type: str
    source_id: Optional[str]
    transformation: str
    compiler_id: Optional[str] = None
    compiler_version: Optional[str] = None
    confidence: float = 1.0
    canonical: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise MetaFoundryError("Provenance confidence must be between 0 and 1")


@dataclass(frozen=True)
class Constraint:
    constraint_id: str
    path: str
    operator: str
    value: Any = None
    severity: str = "error"
    rationale: str = ""

    def __post_init__(self) -> None:
        _validate_identifier(self.constraint_id, "constraint_id")
        if self.operator not in {"exists", "equals", "not_equals", "in", "not_in", "range"}:
            raise MetaFoundryError(f"Unsupported constraint operator: {self.operator}")
        if self.severity not in {"info", "warning", "error"}:
            raise MetaFoundryError(f"Unsupported constraint severity: {self.severity}")


@dataclass(frozen=True)
class ConstraintResult:
    constraint_id: str
    passed: bool
    severity: str
    path: str
    actual: Any
    expected: Any
    message: str


@dataclass(frozen=True)
class DomainDefinition:
    domain_id: str
    name: str
    version: str
    description: str
    compiler_ids: Tuple[str, ...]
    constraints: Tuple[Constraint, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.domain_id, "domain_id")
        if not self.name.strip() or not self.version.strip():
            raise MetaFoundryError("Domain name and version are required")
        if not self.compiler_ids:
            raise MetaFoundryError("A domain must declare at least one compiler")


@dataclass(frozen=True)
class CreationIntent:
    intent_id: str
    domain_id: str
    objective: str
    audience: Mapping[str, Any]
    constraints: Mapping[str, Any]
    preferences: Mapping[str, Any]
    source_refs: Tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class DomainSpecification:
    specification_id: str
    intent_id: str
    domain_id: str
    schema_version: str
    canonical_data: Mapping[str, Any]
    assumptions: Tuple[str, ...]
    unresolved_questions: Tuple[str, ...]
    provenance: Tuple[ProvenanceRecord, ...]
    content_hash: str


@dataclass(frozen=True)
class CompilerDefinition:
    compiler_id: str
    version: str
    domain_id: str
    input_type: str
    output_type: str
    deterministic: bool
    lifecycle_state: str = "quarantined"

    def __post_init__(self) -> None:
        _validate_identifier(self.compiler_id, "compiler_id")
        _validate_identifier(self.domain_id, "domain_id")
        if self.lifecycle_state not in _ALLOWED_COMPILER_STATES:
            raise MetaFoundryError(f"Invalid compiler lifecycle state: {self.lifecycle_state}")


@dataclass(frozen=True)
class CompiledArtifact:
    artifact_id: str
    artifact_type: str
    domain_id: str
    compiler_id: str
    compiler_version: str
    source_ids: Tuple[str, ...]
    payload: Mapping[str, Any]
    provenance: Tuple[ProvenanceRecord, ...]
    constraint_results: Tuple[ConstraintResult, ...]
    validation_state: str
    content_hash: str
    created_at: str


CompilerFunction = Callable[[DomainSpecification], Mapping[str, Any]]


@dataclass
class _CompilerRegistration:
    definition: CompilerDefinition
    function: CompilerFunction


class DomainRegistry:
    """In-memory registry with explicit duplicate rejection."""

    def __init__(self) -> None:
        self._domains: Dict[str, DomainDefinition] = {}
        self._compilers: Dict[str, _CompilerRegistration] = {}

    def register_domain(self, domain: DomainDefinition) -> None:
        if domain.domain_id in self._domains:
            raise MetaFoundryError(f"Domain already registered: {domain.domain_id}")
        self._domains[domain.domain_id] = domain

    def register_compiler(
        self,
        definition: CompilerDefinition,
        function: CompilerFunction,
    ) -> None:
        if definition.compiler_id in self._compilers:
            raise MetaFoundryError(f"Compiler already registered: {definition.compiler_id}")
        if definition.domain_id not in self._domains:
            raise DomainNotFoundError(definition.domain_id)
        if not callable(function):
            raise MetaFoundryError("Compiler function must be callable")
        self._compilers[definition.compiler_id] = _CompilerRegistration(definition, function)

    def domain(self, domain_id: str) -> DomainDefinition:
        try:
            return self._domains[domain_id]
        except KeyError as exc:
            raise DomainNotFoundError(domain_id) from exc

    def compiler(self, compiler_id: str) -> _CompilerRegistration:
        try:
            return self._compilers[compiler_id]
        except KeyError as exc:
            raise MetaFoundryError(f"Compiler not registered: {compiler_id}") from exc

    def list_domains(self) -> Tuple[DomainDefinition, ...]:
        return tuple(self._domains[key] for key in sorted(self._domains))


class MetaFoundry:
    """Deterministic, local-first domain compiler orchestrator."""

    def __init__(self, registry: Optional[DomainRegistry] = None) -> None:
        self.registry = registry or DomainRegistry()
        self._intents: Dict[str, CreationIntent] = {}
        self._specifications: Dict[str, DomainSpecification] = {}
        self._artifacts: Dict[str, CompiledArtifact] = {}

    def create_intent(
        self,
        domain_id: str,
        objective: str,
        audience: Optional[Mapping[str, Any]] = None,
        constraints: Optional[Mapping[str, Any]] = None,
        preferences: Optional[Mapping[str, Any]] = None,
        source_refs: Iterable[str] = (),
    ) -> CreationIntent:
        self.registry.domain(domain_id)
        if not objective.strip():
            raise MetaFoundryError("Creation intent objective is required")
        intent = CreationIntent(
            intent_id=_new_id("intent"),
            domain_id=domain_id,
            objective=objective.strip(),
            audience=dict(audience or {}),
            constraints=dict(constraints or {}),
            preferences=dict(preferences or {}),
            source_refs=tuple(source_refs),
            created_at=_utc_now(),
        )
        self._intents[intent.intent_id] = intent
        return intent

    def specify(
        self,
        intent_id: str,
        assumptions: Iterable[str] = (),
        unresolved_questions: Iterable[str] = (),
    ) -> DomainSpecification:
        try:
            intent = self._intents[intent_id]
        except KeyError as exc:
            raise MetaFoundryError(f"Unknown intent: {intent_id}") from exc
        canonical_data = {
            "objective": intent.objective,
            "audience": dict(intent.audience),
            "constraints": dict(intent.constraints),
            "preferences": dict(intent.preferences),
            "source_refs": list(intent.source_refs),
        }
        provenance = (
            ProvenanceRecord(
                source_type="creator_intent",
                source_id=intent.intent_id,
                transformation="normalized",
                confidence=1.0,
                canonical=True,
            ),
        )
        hash_input = {
            "domain_id": intent.domain_id,
            "schema_version": "1.0",
            "canonical_data": canonical_data,
            "assumptions": list(assumptions),
            "unresolved_questions": list(unresolved_questions),
        }
        specification = DomainSpecification(
            specification_id=_new_id("spec"),
            intent_id=intent.intent_id,
            domain_id=intent.domain_id,
            schema_version="1.0",
            canonical_data=canonical_data,
            assumptions=tuple(assumptions),
            unresolved_questions=tuple(unresolved_questions),
            provenance=provenance,
            content_hash=_sha256(hash_input),
        )
        self._specifications[specification.specification_id] = specification
        return specification

    @staticmethod
    def evaluate_constraints(
        payload: Mapping[str, Any], constraints: Sequence[Constraint]
    ) -> Tuple[ConstraintResult, ...]:
        results = []
        for constraint in constraints:
            missing = False
            try:
                actual = _read_path(payload, constraint.path)
            except KeyError:
                actual = None
                missing = True

            if constraint.operator == "exists":
                passed = not missing
            elif missing:
                passed = False
            elif constraint.operator == "equals":
                passed = actual == constraint.value
            elif constraint.operator == "not_equals":
                passed = actual != constraint.value
            elif constraint.operator == "in":
                passed = actual in constraint.value
            elif constraint.operator == "not_in":
                passed = actual not in constraint.value
            else:  # range
                if not isinstance(constraint.value, Sequence) or len(constraint.value) != 2:
                    raise MetaFoundryError(
                        f"Range constraint {constraint.constraint_id} requires [minimum, maximum]"
                    )
                minimum, maximum = constraint.value
                passed = minimum <= actual <= maximum

            message = (
                f"{constraint.constraint_id} passed"
                if passed
                else f"{constraint.constraint_id} failed at {constraint.path}: "
                     f"expected {constraint.operator} {constraint.value!r}, got {actual!r}"
            )
            results.append(
                ConstraintResult(
                    constraint_id=constraint.constraint_id,
                    passed=passed,
                    severity=constraint.severity,
                    path=constraint.path,
                    actual=actual,
                    expected=constraint.value,
                    message=message,
                )
            )
        return tuple(results)

    def compile(self, specification_id: str, compiler_id: str) -> CompiledArtifact:
        try:
            specification = self._specifications[specification_id]
        except KeyError as exc:
            raise MetaFoundryError(f"Unknown specification: {specification_id}") from exc
        registration = self.registry.compiler(compiler_id)
        definition = registration.definition
        if definition.lifecycle_state != "registered":
            raise CompilerNotExecutableError(
                f"Compiler {compiler_id} is {definition.lifecycle_state}, not registered"
            )
        if definition.domain_id != specification.domain_id:
            raise MetaFoundryError(
                f"Compiler domain {definition.domain_id} does not match "
                f"specification domain {specification.domain_id}"
            )

        payload = dict(registration.function(specification))
        domain = self.registry.domain(specification.domain_id)
        results = self.evaluate_constraints(payload, domain.constraints)
        blocking = [r for r in results if not r.passed and r.severity == "error"]
        if blocking:
            raise ConstraintViolationError(blocking)

        provenance = specification.provenance + (
            ProvenanceRecord(
                source_type="compiled_artifact",
                source_id=specification.specification_id,
                transformation="domain_compile",
                compiler_id=definition.compiler_id,
                compiler_version=definition.version,
                confidence=1.0,
                canonical=True,
            ),
        )
        hash_input = {
            "artifact_type": definition.output_type,
            "domain_id": definition.domain_id,
            "compiler_id": definition.compiler_id,
            "compiler_version": definition.version,
            "source_hash": specification.content_hash,
            "payload": payload,
        }
        artifact = CompiledArtifact(
            artifact_id=_new_id("artifact"),
            artifact_type=definition.output_type,
            domain_id=definition.domain_id,
            compiler_id=definition.compiler_id,
            compiler_version=definition.version,
            source_ids=(specification.specification_id,),
            payload=payload,
            provenance=provenance,
            constraint_results=results,
            validation_state="structurally_valid",
            content_hash=_sha256(hash_input),
            created_at=_utc_now(),
        )
        self._artifacts[artifact.artifact_id] = artifact
        return artifact

    def artifact(self, artifact_id: str) -> CompiledArtifact:
        try:
            return self._artifacts[artifact_id]
        except KeyError as exc:
            raise MetaFoundryError(f"Unknown artifact: {artifact_id}") from exc

    @staticmethod
    def export_artifact(artifact: CompiledArtifact) -> str:
        """Return a canonical, human-readable JSON export."""
        return json.dumps(asdict(artifact), sort_keys=True, indent=2, ensure_ascii=False)
