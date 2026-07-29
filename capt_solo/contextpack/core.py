"""Immutable ContextPack v1 construction and validation.

No network, model call, implicit write, or semantic reconciliation occurs here.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "capt.contextpack.v1"
CANONICALIZATION_VERSION = "capt-json-v1"
DIGEST_ALGORITHM = "sha256"
_FACT_PATTERNS = (
    ("negation", re.compile(r"\b(not|never|no|cannot|can't|won't|false)\b", re.I)),
    ("uncertainty", re.compile(r"\b(maybe|unknown|uncertain|likely|possibly)\b", re.I)),
    ("version", re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b")),
    ("path", re.compile(r"(?:/[\w.\-]+)+|\b[\w.\-]+\.[a-z]{2,4}\b")),
    ("number", re.compile(r"\b\d+(?:\.\d+)?\b")),
    ("error", re.compile(r"\b(?:error|failed|failure|traceback|exception)\b", re.I)),
)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict): return tuple((str(k), _freeze(value[k])) for k in sorted(value))
    if isinstance(value, (list, tuple)): return tuple(_freeze(v) for v in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, tuple) and all(isinstance(x, tuple) and len(x) == 2 and isinstance(x[0], str) for x in value):
        return {k: _thaw(v) for k, v in value}
    if isinstance(value, tuple): return [_thaw(v) for v in value]
    return value


def _clock(value: str) -> str:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("evaluation_clock must be ISO-8601") from exc
    if stamp.tzinfo is None: raise ValueError("evaluation_clock must include timezone")
    return stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RecordRef:
    record_id: str
    record_digest: str
    origin: str
    embedded: Any = field(default_factory=tuple)
    def __post_init__(self): object.__setattr__(self, "embedded", _freeze(self.embedded))
    def to_dict(self): return {"record_id": self.record_id, "record_digest": self.record_digest, "origin": self.origin, "embedded": _thaw(self.embedded)}


@dataclass(frozen=True)
class Mission:
    mission_id: str
    objective: str
    success_criteria: Tuple[str, ...] = ()
    def __post_init__(self): object.__setattr__(self, "success_criteria", tuple(self.success_criteria))
    def to_dict(self): return {"mission_id": self.mission_id, "objective": self.objective, "success_criteria": list(self.success_criteria)}


@dataclass(frozen=True)
class MissionIntent:
    purpose: str
    priority: str
    tradeoffs: Tuple[str, ...]
    success_definition: str
    safety_constraints: Tuple[str, ...]
    def __post_init__(self):
        object.__setattr__(self, "tradeoffs", tuple(self.tradeoffs)); object.__setattr__(self, "safety_constraints", tuple(self.safety_constraints))
    def to_dict(self): return {"purpose": self.purpose, "priority": self.priority, "tradeoffs": list(self.tradeoffs), "success_definition": self.success_definition, "safety_constraints": list(self.safety_constraints)}


@dataclass(frozen=True)
class Assumption:
    ref: RecordRef
    statement: str
    status: str
    supporting_evidence: Tuple[str, ...] = ()
    missing_evidence: Tuple[str, ...] = ()
    validation_required: str = ""
    def __post_init__(self):
        object.__setattr__(self, "supporting_evidence", tuple(self.supporting_evidence)); object.__setattr__(self, "missing_evidence", tuple(self.missing_evidence))
    def to_dict(self): return {"ref": self.ref.to_dict(), "statement": self.statement, "status": self.status, "supporting_evidence": list(self.supporting_evidence), "missing_evidence": list(self.missing_evidence), "validation_required": self.validation_required}


@dataclass(frozen=True)
class ProtectedFact:
    fact_id: str
    fact_type: str
    canonical_value: str
    source_refs: Tuple[str, ...]
    source_location: str
    required: bool = True
    rendered_occurrences: Tuple[str, ...] = ()
    validation_status: str = "unknown"
    def __post_init__(self):
        object.__setattr__(self, "source_refs", tuple(self.source_refs)); object.__setattr__(self, "rendered_occurrences", tuple(self.rendered_occurrences))
    def to_dict(self): return {"fact_id": self.fact_id, "fact_type": self.fact_type, "canonical_value": self.canonical_value, "source_refs": list(self.source_refs), "source_location": self.source_location, "required": self.required, "rendered_occurrences": list(self.rendered_occurrences), "validation_status": self.validation_status}


@dataclass(frozen=True)
class TokenBudget:
    maximum_input_tokens: int
    reserved_output_tokens: int
    available_input_tokens: int
    estimated_input_tokens: int
    remaining_tokens: int
    tokenizer_id: str
    estimation_method: str
    measurement_status: str
    def to_dict(self): return self.__dict__.copy()


@dataclass(frozen=True)
class Handoff:
    mission_id: str
    objective: str
    established_facts: Tuple[str, ...]
    unresolved_unknowns: Tuple[str, ...]
    active_assumptions: Tuple[str, ...]
    blockers: Tuple[str, ...]
    prior_failed_attempts: Tuple[str, ...]
    next_justified_action: str
    required_approvals: Tuple[str, ...]
    pack_digest: str = ""
    def __post_init__(self):
        for name in ("established_facts", "unresolved_unknowns", "active_assumptions", "blockers", "prior_failed_attempts", "required_approvals"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
    def to_dict(self): return {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()}


@dataclass(frozen=True)
class ContextPackBlock:
    category: str
    code: str
    explanation: str
    affected_fields: Tuple[str, ...]
    source_refs: Tuple[str, ...]
    remediation: str
    reconstructable: bool
    def __post_init__(self): object.__setattr__(self, "affected_fields", tuple(self.affected_fields)); object.__setattr__(self, "source_refs", tuple(self.source_refs))
    def to_dict(self): return {"category": self.category, "code": self.code, "explanation": self.explanation, "affected_fields": list(self.affected_fields), "source_refs": list(self.source_refs), "remediation": self.remediation, "reconstructable": self.reconstructable}


@dataclass(frozen=True)
class ContextPack:
    mission: Mission
    intent: MissionIntent
    invariants: Tuple[RecordRef, ...]
    evidence: Tuple[RecordRef, ...]
    memory: Tuple[RecordRef, ...]
    assumptions: Tuple[Assumption, ...]
    assumption_review_status: str
    protected_facts: Tuple[ProtectedFact, ...]
    protected_fact_review_status: str
    receipts: Tuple[RecordRef, ...]
    rendered_context: str
    token_budget: TokenBudget
    handoff: Handoff
    confidence: float
    evaluation_clock: str
    schema_version: str = SCHEMA_VERSION
    canonicalization_version: str = CANONICALIZATION_VERSION
    digest_algorithm: str = DIGEST_ALGORITHM
    digest: str = ""
    def __post_init__(self):
        for name in ("invariants", "evidence", "memory", "assumptions", "protected_facts", "receipts"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(self, "evaluation_clock", _clock(self.evaluation_clock))
        if not 0 <= self.confidence <= 1: raise ValueError("confidence must be in [0,1]")
        expected = _digest(self.semantic_dict())
        if self.digest and self.digest != expected: raise ValueError("pack digest mismatch")
        object.__setattr__(self, "digest", expected)
    def semantic_dict(self):
        return {"schema_version": self.schema_version, "canonicalization_version": self.canonicalization_version, "digest_algorithm": self.digest_algorithm, "mission": self.mission.to_dict(), "intent": self.intent.to_dict(), "invariants": [x.to_dict() for x in sorted(self.invariants, key=lambda x: x.record_id)], "evidence": [x.to_dict() for x in sorted(self.evidence, key=lambda x: x.record_id)], "memory": [x.to_dict() for x in sorted(self.memory, key=lambda x: x.record_id)], "assumptions": [x.to_dict() for x in sorted(self.assumptions, key=lambda x: x.ref.record_id)], "assumption_review_status": self.assumption_review_status, "protected_facts": [x.to_dict() for x in sorted(self.protected_facts, key=lambda x: x.fact_id)], "protected_fact_review_status": self.protected_fact_review_status, "receipts": [x.to_dict() for x in sorted(self.receipts, key=lambda x: x.record_id)], "rendered_context": self.rendered_context, "token_budget": self.token_budget.to_dict(), "handoff": self.handoff.to_dict(), "confidence": self.confidence, "evaluation_clock": self.evaluation_clock}
    def to_dict(self):
        data = self.semantic_dict(); data["digest"] = self.digest; return data
    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, compatibility_inspection: bool = False):
        known = set(cls.__dataclass_fields__)
        unknown = {k: data[k] for k in data if k not in known}
        if unknown and not compatibility_inspection:
            raise ValueError("unknown ContextPack semantic fields: " + ", ".join(sorted(unknown)))
        def ref(x): return RecordRef(x["record_id"], x["record_digest"], x["origin"], x.get("embedded", {}))
        def assumption(x):
            return Assumption(ref(x["ref"]), x["statement"], x["status"], tuple(x.get("supporting_evidence", ())), tuple(x.get("missing_evidence", ())), x.get("validation_required", ""))
        def fact(x):
            return ProtectedFact(x["fact_id"], x["fact_type"], x["canonical_value"], tuple(x["source_refs"]), x["source_location"], bool(x.get("required", True)), tuple(x.get("rendered_occurrences", ())), x.get("validation_status", "unknown"))
        handoff = Handoff(**{k: tuple(v) if isinstance(v, list) else v for k, v in data["handoff"].items()})
        budget = TokenBudget(**data["token_budget"])
        pack = cls(Mission(data["mission"]["mission_id"], data["mission"]["objective"], tuple(data["mission"].get("success_criteria", ()))), MissionIntent(data["intent"]["purpose"], data["intent"]["priority"], tuple(data["intent"].get("tradeoffs", ())), data["intent"]["success_definition"], tuple(data["intent"].get("safety_constraints", ()))), tuple(ref(x) for x in data["invariants"]), tuple(ref(x) for x in data["evidence"]), tuple(ref(x) for x in data["memory"]), tuple(assumption(x) for x in data["assumptions"]), data["assumption_review_status"], tuple(fact(x) for x in data["protected_facts"]), data["protected_fact_review_status"], tuple(ref(x) for x in data["receipts"]), data["rendered_context"], budget, handoff, data["confidence"], data["evaluation_clock"], data.get("schema_version", SCHEMA_VERSION), data.get("canonicalization_version", CANONICALIZATION_VERSION), data.get("digest_algorithm", DIGEST_ALGORITHM), data.get("digest", ""))
        return (pack, _freeze(unknown)) if compatibility_inspection else pack


@dataclass(frozen=True)
class ContextPackValidation:
    pack_digest: str
    status: str
    blocks: Tuple[ContextPackBlock, ...] = ()
    warnings: Tuple[str, ...] = ()
    missing_facts: Tuple[str, ...] = ()
    altered_facts: Tuple[str, ...] = ()
    token_accounting: Any = field(default_factory=tuple)
    def __post_init__(self):
        object.__setattr__(self, "blocks", tuple(self.blocks)); object.__setattr__(self, "warnings", tuple(self.warnings)); object.__setattr__(self, "missing_facts", tuple(self.missing_facts)); object.__setattr__(self, "altered_facts", tuple(self.altered_facts)); object.__setattr__(self, "token_accounting", _freeze(self.token_accounting))
    def to_dict(self): return {"pack_digest": self.pack_digest, "status": self.status, "blocks": [x.to_dict() for x in self.blocks], "warnings": list(self.warnings), "missing_facts": list(self.missing_facts), "altered_facts": list(self.altered_facts), "token_accounting": _thaw(self.token_accounting)}


def derive_protected_facts(sources: Iterable[RecordRef], rendered_context: str) -> Tuple[ProtectedFact, ...]:
    facts = []
    for source in sources:
        text = canonical_json(_thaw(source.embedded))
        for kind, pattern in _FACT_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(0)
                key = kind + "|" + value.lower() + "|" + source.record_id
                occurrence = (value,) if value.lower() in rendered_context.lower() else ()
                facts.append(ProtectedFact("pf-" + hashlib.sha256(key.encode()).hexdigest()[:16], kind, value, (source.record_id,), "embedded", True, occurrence, "preserved" if occurrence else "missing"))
    return tuple(sorted(facts, key=lambda item: item.fact_id))


def _derive_handoff(mission: Mission, assumptions: Sequence[Assumption], facts: Sequence[ProtectedFact], evidence: Sequence[RecordRef]) -> Handoff:
    unknowns = tuple(sorted(a.statement for a in assumptions if a.status in {"unknown", "hypothesized"}))
    blockers = tuple(sorted(f.canonical_value for f in facts if f.required and f.validation_status != "preserved"))
    established = tuple(sorted(f.canonical_value for f in facts if f.validation_status == "preserved"))
    action = "Validate missing protected facts" if blockers else "Proceed with the mission success criteria"
    return Handoff(mission.mission_id, mission.objective, established, unknowns, tuple(sorted(a.ref.record_id for a in assumptions if a.status != "resolved")), blockers, (), action, (), "")


def build_context_pack(mission: Mission, intent: MissionIntent, assumptions: Sequence[Assumption], *, invariants: Sequence[RecordRef], evidence: Sequence[RecordRef], memory: Sequence[RecordRef], receipts: Sequence[RecordRef], rendered_context: str, token_budget: TokenBudget, evaluation_clock: str, confidence: float, assumption_review_status: str, protected_fact_review_status: str) -> ContextPack:
    sources = tuple(evidence) + tuple(memory) + tuple(invariants)
    facts = derive_protected_facts(sources, rendered_context)
    return ContextPack(mission, intent, tuple(invariants), tuple(evidence), tuple(memory), tuple(assumptions), assumption_review_status, facts, protected_fact_review_status, tuple(receipts), rendered_context, token_budget, _derive_handoff(mission, assumptions, facts, evidence), confidence, evaluation_clock)


def build_from_context_result(mission: Mission, intent: MissionIntent, context_result: Any, **kwargs: Any) -> ContextPack:
    """Adapt existing ContextBuildResult without consuming its random trace id."""
    items = getattr(context_result, "items", ())
    memory = []
    for item in items:
        embedded = {"memory_id": item.memory_id, "antitoken": item.antitoken.to_dict() if item.antitoken else None}
        memory.append(RecordRef("memory:" + item.memory_id, _digest(embedded), "context-builder", embedded))
    return build_context_pack(mission, intent, kwargs.pop("assumptions", ()), memory=tuple(memory), rendered_context=context_result.rendered, **kwargs)


def validate_context_pack(pack: ContextPack) -> ContextPackValidation:
    blocks: List[ContextPackBlock] = []
    if pack.schema_version != SCHEMA_VERSION or pack.canonicalization_version != CANONICALIZATION_VERSION or pack.digest_algorithm != DIGEST_ALGORITHM:
        blocks.append(ContextPackBlock("SCHEMA_BLOCK", "unsupported_contract", "Unsupported ContextPack contract metadata", ("schema_version",), (), "Construct a v1 pack", False))
    if pack.assumption_review_status == "not_reviewed" or pack.protected_fact_review_status == "not_reviewed":
        blocks.append(ContextPackBlock("PROVENANCE_BLOCK", "review_incomplete", "Required source review was not completed", ("assumptions", "protected_facts"), (), "Complete explicit source review", True))
    refs = tuple(pack.invariants) + tuple(pack.evidence) + tuple(pack.memory) + tuple(pack.receipts)
    bad_refs = tuple(ref.record_id for ref in refs if not ref.record_id or not ref.record_digest or not ref.origin)
    if bad_refs:
        blocks.append(ContextPackBlock("PROVENANCE_BLOCK", "unstable_reference", "Referenced records require stable id, digest, and origin", ("invariants", "evidence", "memory", "receipts"), bad_refs, "Supply stable record references", True))
    missing = tuple(f.fact_id for f in pack.protected_facts if f.required and f.validation_status != "preserved")
    if missing:
        refs = tuple(ref for f in pack.protected_facts if f.fact_id in missing for ref in f.source_refs)
        blocks.append(ContextPackBlock("FIDELITY_BLOCK", "protected_fact_missing", "Required source facts are absent from rendered context", ("rendered_context", "protected_facts"), refs, "Preserve each listed fact in rendered context", True))
    if pack.token_budget.remaining_tokens < 0 or pack.token_budget.estimated_input_tokens > pack.token_budget.available_input_tokens:
        blocks.append(ContextPackBlock("BUDGET_BLOCK", "budget_exceeded", "Context exceeds declared input budget", ("token_budget",), (), "Reduce selected context or increase declared budget", True))
    return ContextPackValidation(pack.digest, "PASS" if not blocks else "BLOCK", tuple(blocks), (), missing, (), pack.token_budget.to_dict())


def render_handoff(pack: ContextPack) -> Handoff:
    return Handoff(**{**pack.handoff.__dict__, "pack_digest": pack.digest})
