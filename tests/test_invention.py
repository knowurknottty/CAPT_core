"""Tests for the CAPT Invention Engine.

Covers: structured 17-step workflow, feasibility scoring (explainable),
constraint tracking, contradiction detection, safety gates, integration with
math/physics results, revision history, report export, and negative tests for
unsafe/unsupported claims. No patentability claims are made.
"""
import pytest

from capt_solo.engines.mathematics import Number, Quantity, parse_unit
from capt_solo.engines.physics import PhysicsEngine, PhysicsResult
from capt_solo.engines.invention import (
    InventionEngine, InventionRecord, ArtifactStage, SafetyGate,
    FeasibilityComponent, Revision,
)


def _q(v, unit):
    return Quantity(Number.from_float(v), parse_unit(unit))


def test_structured_workflow():
    eng = InventionEngine()
    rec = eng.new_record("Low-power water-level sensor for a rain barrel")
    rec.constraints = ["battery powered", "cost < $5", "outdoor rated"]
    rec.functional_decomposition = ["sense level", "transmit", "power manage"]
    rec.candidate_principles = ["capacitive sensing", "ultrasonic ranging"]
    rec.candidate_mechanisms = ["RC oscillator frequency shift"]
    rec.candidate_architectures = ["MCU + capacitive probe"]
    # integrate a physics result directly
    phys = PhysicsEngine()
    fr = phys.mechanics.force(_q(0.05, "kg"), _q(9.8, "m/s^2"))
    eng.add_calculation(rec, "probe_weight_force", fr, source="physics.mechanics.force")
    rec.physical_feasibility = ["force within probe mount rating"]
    rec.tradeoffs = ["capacitive cheaper but less robust than ultrasonic"]
    rec.safety_analysis = ["low voltage, no hazard"]
    rec.validation_criteria = ["±2mm accuracy over 0-1m range"]
    rec.evidence = ["physics F=ma within mount limit"]
    rec.uncertainty = ["capacitive reading drifts with temperature"]
    # feasibility components
    comps = [
        FeasibilityComponent("technical", 0.8, 0.4, "known sensing principle"),
        FeasibilityComponent("cost", 0.7, 0.3, "MCU + probe < $5 BOM est."),
        FeasibilityComponent("safety", 0.95, 0.3, "low voltage, passive probe"),
    ]
    score = eng.assess_feasibility(rec, comps)
    assert 0.7 < score < 0.9
    eng.finalize(rec)
    assert rec.safety_gate == SafetyGate.PASS
    assert rec.detect_contradictions() == []  # all consistent for IDEA stage


def test_stage_promotion_requires_data():
    eng = InventionEngine()
    rec = eng.new_record("Example")
    rec.add_revision(Revision("r1", "2026-07-27", "promote", ArtifactStage.IDEA,
                              ArtifactStage.CALCULATED_DESIGN))
    assert rec.stage == ArtifactStage.CALCULATED_DESIGN
    # contradiction: calculated stage but no calculations
    found = rec.detect_contradictions()
    assert any("calculations" in f for f in found)


def test_safety_block():
    eng = InventionEngine()
    rec = eng.new_record("Example")
    rec.safety_analysis = ["contains explosive charge"]
    gate = eng.finalize(rec).safety_gate
    assert gate == SafetyGate.BLOCK


def test_safety_review_when_open():
    eng = InventionEngine()
    rec = eng.new_record("Example")
    # no safety_analysis -> REVIEW
    assert eng.finalize(rec).safety_gate == SafetyGate.REVIEW


def test_no_auto_promotion_by_detail():
    eng = InventionEngine()
    rec = eng.new_record("Very detailed but unvalidated concept")
    rec.constraints = ["a", "b"]
    rec.candidate_mechanisms = ["x", "y", "z"]
    rec.candidate_architectures = ["p", "q"]
    rec.prototype_plan = ["build it"]
    rec.validation_criteria = ["test it"]
    # Despite lots of detail, stage stays IDEA until explicitly revised.
    assert rec.stage == ArtifactStage.IDEA


def test_report_export_no_patent_claim():
    eng = InventionEngine()
    rec = eng.new_record("Solar water heater")
    rec.constraints = ["passive"]
    report = eng.finalize(rec).export_report()
    assert "patent" not in report.lower() or "no patentability claim" in report.lower()
    assert "Stage:" in report


def test_feasibility_component_bounds():
    with pytest.raises(ValueError):
        FeasibilityComponent("bad", 1.5, 1.0, "out of range")


def test_integration_with_physics_result():
    eng = InventionEngine()
    rec = eng.new_record("Lifting aid")
    phys = PhysicsEngine()
    fr = phys.mechanics.force(_q(10.0, "kg"), _q(2.0, "m/s^2"))
    eng.add_calculation(rec, "lift_force", fr)
    assert rec.calculations[0]["relation"] == "F = m*a"
    assert abs(rec.calculations[0]["value"] - 20.0) < 1e-9
