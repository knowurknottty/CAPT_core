from capt_runtime.soma import ContextReducer, CodingTrajectory


def test_reducer_preserves_high_value_events():
    result = ContextReducer().compress(
        CodingTrajectory([
            {"type": "chat", "content": "hello"},
            {"type": "error", "content": "test failure in API schema"},
            {"type": "chat", "content": "noise"},
        ]),
        budget_events=1,
    )
    assert result.output_events == 1
    assert result.retained[0]["type"] == "error"
    assert result.digest.startswith("sha256:")
