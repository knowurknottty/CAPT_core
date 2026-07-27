"""Children's Studio reference domain for CAPT Meta Foundry.

The reference compiler creates a canonical, renderer-independent studio package.
It does not call Seedance, YouTube, or any external service.
"""

from __future__ import annotations

from typing import Any, Mapping

from .core import (
    CompilerDefinition,
    Constraint,
    DomainDefinition,
    DomainRegistry,
    DomainSpecification,
)


DOMAIN_ID = "org.inversionlabs.childrens-studio"
COMPILER_ID = "childrens-studio.package"


def domain_definition() -> DomainDefinition:
    return DomainDefinition(
        domain_id=DOMAIN_ID,
        name="Children's Studio",
        version="0.1.0",
        description=(
            "Renderer-independent compiler for children's animation studio canon, "
            "production constraints, and model-export packages."
        ),
        compiler_ids=(COMPILER_ID,),
        constraints=(
            Constraint(
                constraint_id="studio.objective.exists",
                path="$.studio.objective",
                operator="exists",
                rationale="Every studio requires an explicit creative objective.",
            ),
            Constraint(
                constraint_id="studio.audience.exists",
                path="$.audience",
                operator="exists",
                rationale="Children's media must declare its intended audience.",
            ),
            Constraint(
                constraint_id="studio.render-state.compiled",
                path="$.render_state",
                operator="equals",
                value="compiled_not_rendered",
                rationale="Prompt compilation must never be reported as media rendering.",
            ),
            Constraint(
                constraint_id="studio.safety.constitution",
                path="$.constitution.child_safety",
                operator="equals",
                value=True,
                rationale="The reference domain requires an explicit child-safety constitution.",
            ),
        ),
    )


def compiler_definition() -> CompilerDefinition:
    return CompilerDefinition(
        compiler_id=COMPILER_ID,
        version="0.1.0",
        domain_id=DOMAIN_ID,
        input_type="domain-specification",
        output_type="childrens-studio-package",
        deterministic=True,
        lifecycle_state="registered",
    )


def _age_band(audience: Mapping[str, Any]) -> str:
    minimum = audience.get("age_min")
    maximum = audience.get("age_max")
    if isinstance(minimum, int) and isinstance(maximum, int):
        return f"{minimum}-{maximum}"
    return "unspecified"


def compile_studio_package(specification: DomainSpecification) -> Mapping[str, Any]:
    data = specification.canonical_data
    audience = dict(data.get("audience", {}))
    creator_constraints = dict(data.get("constraints", {}))
    preferences = dict(data.get("preferences", {}))

    return {
        "format": "capt-childrens-studio",
        "format_version": "0.1.0",
        "render_state": "compiled_not_rendered",
        "studio": {
            "objective": data["objective"],
            "domain_id": specification.domain_id,
            "age_band": _age_band(audience),
            "source_specification_id": specification.specification_id,
        },
        "audience": audience,
        "constitution": {
            "child_safety": True,
            "creator_control": True,
            "no_deceptive_completion_claims": True,
            "trust_over_maximum_screen_time": True,
            "human_approval_required_before_publication": True,
        },
        "canon": {
            "characters": {},
            "worlds": {},
            "relationships": {},
            "props": {},
            "episodes": {},
            "immutable_rules": [],
            "continuity_events": [],
        },
        "production": {
            "episode_length_minutes": creator_constraints.get("episode_minutes"),
            "aspect_ratio": preferences.get("aspect_ratio", "16:9"),
            "language": preferences.get("language", "en-US"),
            "renderer": preferences.get("renderer", "unselected"),
            "renderer_execution": "external",
            "required_stages": [
                "specify",
                "compile_canon",
                "compile_episode",
                "compile_scenes",
                "compile_shots",
                "export_renderer_package",
                "render_external",
                "validate_output",
                "human_review",
                "publish",
            ],
        },
        "renderer_package_contract": {
            "required_files": [
                "shot_spec.json",
                "references.json",
                "prompt.txt",
                "negative_prompt.txt",
                "continuity_checklist.json",
                "rights_manifest.json",
            ],
            "visual_validation": {
                "state": "not_run",
                "reason": "No rendered media exists at studio-package compilation time",
            },
        },
        "creator_constraints": creator_constraints,
        "preferences": preferences,
        "assumptions": list(specification.assumptions),
        "unresolved_questions": list(specification.unresolved_questions),
    }


def register(registry: DomainRegistry) -> None:
    """Register the reference domain and its executable compiler."""
    registry.register_domain(domain_definition())
    registry.register_compiler(compiler_definition(), compile_studio_package)
