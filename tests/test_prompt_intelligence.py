from capt_ui.operator.prompt_intelligence import CONTEXT_BUDGETS, PromptPreferences, inspect_prompt


def test_auto_routes_implementation_prompt_to_forge():
    proposal = inspect_prompt("Implement a tested fix for the provider run failure.")
    assert proposal.engine == "FORGE"
    assert "acceptance tests" in proposal.optimized_prompt
    assert not proposal.questions


def test_underspecified_prompt_requires_clarification_without_inventing_intent():
    proposal = inspect_prompt("help", "AUTO")
    assert proposal.engine == "OMNI"
    assert proposal.optimized_prompt == "help"
    assert proposal.questions


def test_explicit_off_preserves_prompt():
    proposal = inspect_prompt("Write a report", "OFF")
    assert proposal.engine == "OFF"
    assert proposal.optimized_prompt == "Write a report"


def test_preferences_reject_invalid_persisted_values(tmp_path):
    (tmp_path / "prompt-preferences.json").write_text('{"responseMode":"NO","contextBudget":1,"humanVerificationRequired":false}')
    prefs = PromptPreferences(tmp_path)
    assert prefs.response_mode == "SPOCK"
    assert prefs.context_budget == CONTEXT_BUDGETS[0]
    assert prefs.human_verification_required is False
