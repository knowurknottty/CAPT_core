from __future__ import annotations

import json

import pytest

from capt_solo.api import (
    CompilerDefinition,
    CompilerNotExecutableError,
    ConstraintViolationError,
    DomainRegistry,
    MetaFoundry,
    register_childrens_studio,
)
from capt_solo.meta_foundry.childrens_studio import COMPILER_ID, DOMAIN_ID


def _foundry() -> MetaFoundry:
    registry = DomainRegistry()
    register_childrens_studio(registry)
    return MetaFoundry(registry)


def _specification(foundry: MetaFoundry):
    intent = foundry.create_intent(
        domain_id=DOMAIN_ID,
        objective="Create a nature-adventure cartoon channel for ages 5-8",
        audience={"age_min": 5, "age_max": 8},
        constraints={"episode_minutes": 6, "violence": "none"},
        preferences={"renderer": "seedance", "aspect_ratio": "16:9"},
    )
    return foundry.specify(
        intent.intent_id,
        assumptions=("Initial release language is English.",),
        unresolved_questions=("Final channel name is not selected.",),
    )


def test_reference_domain_compiles_renderer_independent_package():
    foundry = _foundry()
    specification = _specification(foundry)

    artifact = foundry.compile(specification.specification_id, COMPILER_ID)

    assert artifact.validation_state == "structurally_valid"
    assert artifact.payload["render_state"] == "compiled_not_rendered"
    assert artifact.payload["production"]["renderer"] == "seedance"
    assert artifact.payload["production"]["renderer_execution"] == "external"
    assert artifact.payload["renderer_package_contract"]["visual_validation"]["state"] == "not_run"
    assert artifact.payload["constitution"]["human_approval_required_before_publication"] is True


def test_same_specification_compiles_to_same_content_hash():
    foundry = _foundry()
    specification = _specification(foundry)

    first = foundry.compile(specification.specification_id, COMPILER_ID)
    second = foundry.compile(specification.specification_id, COMPILER_ID)

    assert first.artifact_id != second.artifact_id
    assert first.content_hash == second.content_hash
    assert first.payload == second.payload


def test_export_is_valid_human_readable_json():
    foundry = _foundry()
    specification = _specification(foundry)
    artifact = foundry.compile(specification.specification_id, COMPILER_ID)

    exported = foundry.export_artifact(artifact)
    decoded = json.loads(exported)

    assert decoded["content_hash"] == artifact.content_hash
    assert decoded["payload"]["format"] == "capt-childrens-studio"
    assert "\n  " in exported


def test_duplicate_domain_registration_is_rejected():
    registry = DomainRegistry()
    register_childrens_studio(registry)

    with pytest.raises(Exception, match="Domain already registered"):
        register_childrens_studio(registry)


def test_quarantined_compiler_cannot_execute():
    foundry = _foundry()
    specification = _specification(foundry)

    definition = CompilerDefinition(
        compiler_id="childrens-studio.quarantined-test",
        version="0.1.0",
        domain_id=DOMAIN_ID,
        input_type="domain-specification",
        output_type="test-output",
        deterministic=True,
        lifecycle_state="quarantined",
    )
    foundry.registry.register_compiler(definition, lambda spec: {"ok": True})

    with pytest.raises(CompilerNotExecutableError):
        foundry.compile(specification.specification_id, definition.compiler_id)


def test_constraint_failure_blocks_artifact_creation():
    foundry = _foundry()
    specification = _specification(foundry)
    registration = foundry.registry.compiler(COMPILER_ID)

    original = registration.function
    registration.function = lambda spec: {
        **dict(original(spec)),
        "render_state": "rendered",
    }
    try:
        with pytest.raises(ConstraintViolationError) as exc:
            foundry.compile(specification.specification_id, COMPILER_ID)
    finally:
        registration.function = original

    assert any(
        result.constraint_id == "studio.render-state.compiled"
        for result in exc.value.violations
    )


def test_creator_statements_and_compiler_transformation_are_provenanced():
    foundry = _foundry()
    specification = _specification(foundry)
    artifact = foundry.compile(specification.specification_id, COMPILER_ID)

    assert artifact.provenance[0].source_type == "creator_intent"
    assert artifact.provenance[0].canonical is True
    assert artifact.provenance[-1].compiler_id == COMPILER_ID
    assert artifact.provenance[-1].transformation == "domain_compile"
