from __future__ import annotations

from capt_runtime.cohort_contract import normalize_cohort_spec
from capt_ui.operator.council_workflow import CohortWorkflow, CouncilWorkflow


def test_image_modality_is_bound_into_approval_cohort_spec(tmp_path):
    workflow = CouncilWorkflow(
        council_id="image-council",
        mission_id="image-mission",
        target_root=str(tmp_path),
        cohorts=(
            CohortWorkflow(
                cohort_id="ming-design",
                provider="openrouter",
                model="inclusionai/ming-image-0.1-design",
                objective="Render one final campaign board.",
                vessels_per_cohort=11,
                configuration_id="design-r1",
                output_modality="image",
                output_format="png",
            ),
        ),
    ).validate()
    payload = workflow.approval_payloads()[0]
    spec = normalize_cohort_spec(payload["cohortSpec"])
    assert spec == {
        "cohortId": "ming-design",
        "vesselsPerCohort": 11,
        "configurationId": "design-r1",
        "outputModality": "image",
        "outputFormat": "png",
    }
    restored = CouncilWorkflow.from_mapping(workflow.to_record()).validate()
    assert restored.cohorts[0].output_modality == "image"
    assert restored.cohorts[0].output_format == "png"


def test_image_cohort_contract_is_visual_not_textual():
    from capt_runtime.cohort_contract import compile_cohort_objective

    text = compile_cohort_objective(
        "Render the final campaign board.",
        provider="openrouter",
        model="inclusionai/ming-image-0.1-design",
        cohort_spec={
            "cohortId": "ming-design",
            "vesselsPerCohort": 11,
            "configurationId": "design-r1",
            "outputModality": "image",
            "outputFormat": "png",
        },
    )
    assert "11 logical vessels as distinct visual design lenses" in text
    assert "ONE final visual artifact" in text
    assert "do not emit a textual cohort report" in text
    assert "end with a cohort synthesis" not in text
