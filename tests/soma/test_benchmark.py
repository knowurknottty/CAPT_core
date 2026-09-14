from capt_runtime.soma import ContextReducer, CodingTrajectory, TrajectoryEvent
from capt_runtime.soma.benchmark import run_strategy


def test_benchmark_density_uses_real_reducer_result():
    trajectory = CodingTrajectory([
        TrajectoryEvent(kind="error", content="failure", importance=1.0),
        TrajectoryEvent(kind="note", content="noise", importance=0.1),
    ])
    reducer = ContextReducer()

    result = run_strategy(
        "context",
        trajectory,
        lambda value: reducer.compress(value, budget_events=1),
    )

    assert result.strategy == "context"
    assert result.tokens_retained > 0
    assert result.utility_retained == 1.0
    assert result.density > 0
