"""Independent source-fidelity regression fixtures. No external model calls."""
import json
import pytest

from capt_runtime.source_fidelity import (
    frozen_source_manifest,
    source_coverage_contract,
    validate_source_coverage,
)


def _fixture():
    ids = [f"CAPT-UPG-{n:03}" for n in range(25, 69)]  # 44 synthetic IDs
    ids = ids[:37] + [f"CAPT-UPG-{n:03}" for n in range(69, 75)]
    assert len(ids) == 43
    paths = [f"corpus/file-{i}.md" for i in range(1, 6)]
    paths.append("corpus/capt_upg_025_backlog.json")
    objective = "Give an explicit disposition for every one of the 43 backlog controls.\n"
    for path in paths:
        body = json.dumps([{"id": v, "evidence": "synthetic"} for v in ids]) if path.endswith(".json") else "synthetic file\n"
        objective += f"=== BEGIN {path} ===\n{body}\n=== END {path} ===\n"
    return objective, paths, ids


def _report(paths, ids):
    return (
        "".join(f"CAPT_SOURCE_FILE {p} | PRESENT\n" for p in paths)
        + "".join(f"CAPT_SOURCE_ITEM {i} | DISPOSITION=reviewed with evidence\n" for i in ids)
    )


def test_manifest_is_six_files_and_43_exact_ids():
    objective, paths, ids = _fixture()
    manifest = frozen_source_manifest(objective)
    assert manifest is not None
    assert manifest["requiresDisposition"] is True
    assert len(manifest["files"]) == len(paths) == 6
    assert len(manifest["backlogIds"]) == len(ids) == 43
    assert "CAPT_SOURCE_ITEM" in source_coverage_contract(objective)


def test_43_of_43_and_six_files_is_covered_but_unverified():
    objective, paths, ids = _fixture()
    result = validate_source_coverage(objective, _report(paths, ids))
    assert result["required"] and result["valid"]
    assert result["status"] == "covered_unverified"


def test_structural_charter_cannot_mask_37_of_43_and_five_of_six():
    objective, paths, ids = _fixture()
    report = "CAPT_CHARTER_AUDIT | generated=66 | selected=22\n" + _report(paths[:5], ids[:37])
    result = validate_source_coverage(objective, report)
    assert result["required"] and not result["valid"]
    assert len(result["missingBacklogIds"]) == 6
    assert result["missingFiles"] == [paths[5]]


def test_missing_or_repeated_rows_are_rejected():
    objective, paths, ids = _fixture()
    result = validate_source_coverage(objective, _report(paths, ids) + f"CAPT_SOURCE_ITEM {ids[0]} | DISPOSITION=duplicate\n")
    assert not result["valid"]
    assert result["duplicateBacklogIds"] == [ids[0]]
    report = _report(paths, ids).replace(
        f"CAPT_SOURCE_ITEM {ids[0]} | DISPOSITION=reviewed with evidence",
        f"CAPT_SOURCE_ITEM {ids[0]} | DISPOSITION=unavailable",
    )
    assert ids[0] in validate_source_coverage(objective, report)["invalidDispositionIds"]


def test_missing_end_marker_fails_before_approval():
    objective, _, _ = _fixture()
    with pytest.raises(ValueError, match="UNBALANCED"):
        frozen_source_manifest(objective.rsplit("=== END", 1)[0])


def test_no_frozen_corpus_does_not_impose_specialized_gate():
    result = validate_source_coverage("ordinary review", "ordinary result")
    assert result == {"required": False, "valid": True, "status": "not_required"}


def test_future_strict_approval_compilation_binds_source_rows():
    from capt_runtime.cohort_contract import compile_cohort_objective
    objective, paths, ids = _fixture()
    spec = {
        "cohortId": "source-fidelity-fixture",
        "configurationId": "fixture",
        "vesselsPerCohort": 22,
        "vesselCharterPolicy": {"schemaVersion": "2.0.0"},
    }
    compiled = compile_cohort_objective(
        objective, provider="openrouter", model="offline-fixture",
        cohort_spec=spec,
    )
    assert "CAPT FROZEN SOURCE FIDELITY CONTRACT" in compiled
    assert "6 enclosed files" in compiled
    assert "43 authoritative backlog IDs" in compiled
    assert compiled.index("CAPT STRICT OUTPUT ORDER") < compiled.index("CAPT FROZEN SOURCE FIDELITY CONTRACT")


def test_malformed_corpus_rejected_during_strict_prompt_compilation():
    from capt_runtime.cohort_contract import compile_cohort_objective
    objective, _, _ = _fixture()
    truncated = objective.rsplit("=== END", 1)[0]
    with pytest.raises(ValueError, match="FROZEN_SOURCE_BLOCKS_UNBALANCED"):
        compile_cohort_objective(
            truncated, provider="openrouter", model="offline-fixture",
            cohort_spec={
                "cohortId": "source-fidelity-fixture",
                "configurationId": "fixture",
                "vesselsPerCohort": 22,
                "vesselCharterPolicy": {"schemaVersion": "2.0.0"},
            },
        )
