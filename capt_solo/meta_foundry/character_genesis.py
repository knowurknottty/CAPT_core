"""Character Genesis reference subsystem for CAPT Meta Foundry.

This module defines a reusable, renderer-independent character package. The
children's video pipeline is the first consumer, but the package is designed to
support animation, illustration, games, books, voice systems, and future CAPT
agent embodiments without changing the canonical character model.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from .core import (
    CompilerDefinition,
    Constraint,
    DomainDefinition,
    DomainRegistry,
    DomainSpecification,
    MetaFoundryError,
)


DOMAIN_ID = "org.inversionlabs.character-genesis"
COMPILER_ID = "character-genesis.package"
FORMAT_VERSION = "0.1.0"


_REQUIRED_GENOMES = (
    "identity",
    "physical",
    "visual",
    "motion",
    "voice",
    "mind",
    "emotion",
    "relationships",
    "memory",
    "constitution",
)


def domain_definition() -> DomainDefinition:
    return DomainDefinition(
        domain_id=DOMAIN_ID,
        name="CAPT Character Genesis",
        version=FORMAT_VERSION,
        description=(
            "Canonical compiler for persistent character identity, behavior, "
            "memory, continuity, safety, and renderer-adapter packages."
        ),
        compiler_ids=(COMPILER_ID,),
        constraints=(
            Constraint(
                constraint_id="character.name.exists",
                path="$.character.identity.name",
                operator="exists",
                rationale="Every character requires a canonical name.",
            ),
            Constraint(
                constraint_id="character.role.exists",
                path="$.character.identity.role",
                operator="exists",
                rationale="A character must have a declared narrative role.",
            ),
            Constraint(
                constraint_id="character.render-state.compiled",
                path="$.render_state",
                operator="equals",
                value="compiled_not_rendered",
                rationale="Character compilation must not be reported as rendering.",
            ),
            Constraint(
                constraint_id="character.creator-control.required",
                path="$.character.constitution.creator_control",
                operator="equals",
                value=True,
                rationale="The creator retains authority over canonical changes.",
            ),
            Constraint(
                constraint_id="character.child-safety.required",
                path="$.character.constitution.child_safety",
                operator="equals",
                value=True,
                rationale="The first reference implementation is for children's media.",
            ),
        ),
    )


def compiler_definition() -> CompilerDefinition:
    return CompilerDefinition(
        compiler_id=COMPILER_ID,
        version=FORMAT_VERSION,
        domain_id=DOMAIN_ID,
        input_type="domain-specification",
        output_type="capt-character-package",
        deterministic=True,
        lifecycle_state="registered",
    )


def _mapping(value: Any, label: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise MetaFoundryError(f"{label} must be a mapping")
    return dict(value)


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise MetaFoundryError(f"{label} must be a sequence")
    return tuple(value)


def _normalized_emotion_model(source: Mapping[str, Any]) -> Dict[str, float]:
    dimensions = (
        "joy",
        "curiosity",
        "trust",
        "fear",
        "calm",
        "energy",
        "empathy",
        "confidence",
        "wonder",
        "playfulness",
    )
    result: Dict[str, float] = {}
    for dimension in dimensions:
        raw = source.get(dimension, 0.5)
        if not isinstance(raw, (int, float)):
            raise MetaFoundryError(f"emotion.{dimension} must be numeric")
        value = float(raw)
        if value < 0.0 or value > 1.0:
            raise MetaFoundryError(f"emotion.{dimension} must be between 0 and 1")
        result[dimension] = value
    return result


def compile_character_package(specification: DomainSpecification) -> Mapping[str, Any]:
    data = specification.canonical_data
    preferences = _mapping(data.get("preferences"), "preferences")
    creator_constraints = _mapping(data.get("constraints"), "constraints")
    character_input = _mapping(preferences.get("character"), "preferences.character")

    identity = _mapping(character_input.get("identity"), "character.identity")
    if not identity.get("name"):
        identity["name"] = preferences.get("character_name") or "Unnamed Character"
    if not identity.get("role"):
        identity["role"] = preferences.get("character_role") or "supporting"

    physical = _mapping(character_input.get("physical"), "character.physical")
    visual = _mapping(character_input.get("visual"), "character.visual")
    motion = _mapping(character_input.get("motion"), "character.motion")
    voice = _mapping(character_input.get("voice"), "character.voice")
    mind = _mapping(character_input.get("mind"), "character.mind")
    relationships = _mapping(character_input.get("relationships"), "character.relationships")
    memory = _mapping(character_input.get("memory"), "character.memory")
    constitution_input = _mapping(
        character_input.get("constitution"), "character.constitution"
    )
    emotion = _normalized_emotion_model(
        _mapping(character_input.get("emotion"), "character.emotion")
    )

    immutable_traits = list(
        _sequence(character_input.get("immutable_traits"), "character.immutable_traits")
    )
    required_assets = list(
        _sequence(character_input.get("required_assets"), "character.required_assets")
    )

    constitution = {
        "creator_control": True,
        "child_safety": True,
        "human_approval_required_for_canon_changes": True,
        "human_approval_required_before_publication": True,
        "no_deceptive_completion_claims": True,
        "no_unapproved_identity_drift": True,
        "rules": list(_sequence(constitution_input.get("rules"), "constitution.rules")),
    }

    character = {
        "identity": identity,
        "physical": physical,
        "visual": visual,
        "motion": motion,
        "voice": voice,
        "mind": mind,
        "emotion": emotion,
        "relationships": relationships,
        "memory": {
            "persistent": True,
            "episodic": list(_sequence(memory.get("episodic"), "memory.episodic")),
            "semantic": list(_sequence(memory.get("semantic"), "memory.semantic")),
            "retrieval_policy": memory.get("retrieval_policy", "canon_relevant_first"),
        },
        "constitution": constitution,
        "continuity": {
            "immutable_traits": immutable_traits,
            "versioned_traits": {},
            "drift_policy": "reject_unapproved",
            "regression_tests_required": True,
        },
        "evolution": {
            "state": "baseline",
            "changes": [],
            "change_policy": "explicit_versioned_event",
        },
    }

    missing = [name for name in _REQUIRED_GENOMES if name not in character]
    if missing:
        raise MetaFoundryError(f"Character package missing genomes: {missing}")

    renderer_targets = list(
        _sequence(preferences.get("renderer_targets"), "preferences.renderer_targets")
    ) or [preferences.get("renderer", "unselected")]

    return {
        "format": "capt-character-package",
        "format_version": FORMAT_VERSION,
        "render_state": "compiled_not_rendered",
        "objective": data["objective"],
        "source_specification_id": specification.specification_id,
        "character": character,
        "asset_manifest": {
            "required": required_assets,
            "references": [],
            "rights_state": "unverified",
            "generated_assets": [],
        },
        "behavior_tests": {
            "state": "specified_not_run",
            "cases": list(
                _sequence(character_input.get("behavior_tests"), "character.behavior_tests")
            ),
        },
        "renderer_adapters": {
            "targets": renderer_targets,
            "execution": "external",
            "required_exports": [
                "identity.json",
                "visual.json",
                "motion.json",
                "voice.json",
                "continuity.json",
                "references.json",
                "prompt.txt",
                "negative_prompt.txt",
            ],
            "visual_validation": {
                "state": "not_run",
                "reason": "No rendered media exists at character compilation time",
            },
        },
        "creator_constraints": creator_constraints,
        "assumptions": list(specification.assumptions),
        "unresolved_questions": list(specification.unresolved_questions),
    }


def register(registry: DomainRegistry) -> None:
    """Register the reusable Character Genesis domain and compiler."""
    registry.register_domain(domain_definition())
    registry.register_compiler(compiler_definition(), compile_character_package)
