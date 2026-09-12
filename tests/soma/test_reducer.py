from capt_runtime.soma import ContextReducer, CodingTrajectory, TrajectoryEvent


def test_reducer_preserves_high_value_events():
    trajectory = CodingTrajectory([
        TrajectoryEvent(kind="chat", content="hello", importance=0.1),
        TrajectoryEvent(kind="error", content="test failure in API schema", importance=0.95),
        TrajectoryEvent(kind="chat", content="noise", importance=0.1),
    ])

    result = ContextReducer().compress(trajectory, budget_events=1)

    assert result.output_events == 1
    assert result.retained[0].kind == "error"
    assert result.digest.startswith("sha256:")
