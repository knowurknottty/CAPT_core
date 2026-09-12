import capt_runtime.soma as soma
from capt_runtime.soma.trajectory import CodingTrajectory, TrajectoryEvent


def test_public_api_exports_canonical_trajectory_types():
    assert soma.CodingTrajectory is CodingTrajectory
    assert soma.TrajectoryEvent is TrajectoryEvent


def test_context_reducer_accepts_canonical_trajectory():
    trajectory = CodingTrajectory([
        TrajectoryEvent(kind="chat", content="hello", importance=0.1),
        TrajectoryEvent(kind="error", content="api schema failure", importance=0.95),
    ])

    result = soma.ContextReducer().compress(trajectory, budget_events=1)

    assert result.retained == [trajectory.events[1]]


def test_compressed_context_satisfies_explicit_reducer_result_contract():
    assert hasattr(soma, "ReducerResult")
    trajectory = CodingTrajectory([
        TrajectoryEvent(kind="error", content="boom", importance=1.0),
    ])
    result = soma.ContextReducer().compress(trajectory, budget_events=1)

    assert isinstance(result, soma.ReducerResult)
    assert list(result.events) == result.retained
    assert result.input_events == 1
    assert result.output_events == 1


def test_benchmark_runs_real_context_reducer_result():
    from capt_runtime.soma.benchmark import run_strategy

    trajectory = CodingTrajectory([
        TrajectoryEvent(kind="failure", content="service failed", importance=1.0),
        TrajectoryEvent(kind="note", content="minor note", importance=0.1),
    ])
    reducer = soma.ContextReducer()

    result = run_strategy(
        "context",
        trajectory,
        lambda value: reducer.compress(value, budget_events=1),
    )

    assert result.tokens_retained > 0
    assert result.utility_retained == 1.0
    assert result.density > 0


def test_real_soma_pipeline_composes_end_to_end():
    from capt_runtime.soma.arena import ArenaEntry, evaluate
    from capt_runtime.soma.benchmark import run_strategy
    from capt_runtime.soma.evidence import from_evidence_records
    from capt_runtime.soma.reconstruction import evaluate_reconstruction

    trajectory = from_evidence_records([
        {"kind": "failure", "content": "service failed", "source": "test"},
        {"kind": "decision", "content": "use bounded retry", "source": "test"},
        {"kind": "note", "content": "incidental chatter", "source": "test"},
    ])
    reducer = soma.ContextReducer()
    reduce_to_two = lambda value: reducer.compress(value, budget_events=2)

    compressed = reduce_to_two(trajectory)
    arena_score = evaluate(trajectory, [ArenaEntry("context", reduce_to_two)])[0]
    reconstruction = evaluate_reconstruction(trajectory, compressed)
    benchmark = run_strategy("context", trajectory, reduce_to_two)

    assert arena_score.critical_preservation == 1.0
    assert arena_score.utility_density > 0
    assert reconstruction.preserved_events == 2
    assert reconstruction.total_critical_events == 2
    assert reconstruction.preservation_ratio == 1.0
    assert benchmark.utility_retained == 1.85
    assert benchmark.density > 0


def test_trajectory_event_rejects_non_finite_and_out_of_range_importance():
    import math
    import pytest

    for bad in (-0.1, 1.1, math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            TrajectoryEvent(kind="event", content="x", importance=bad)


def test_reducer_rejects_invalid_budget_domain():
    import pytest

    trajectory = CodingTrajectory([
        TrajectoryEvent(kind="error", content="boom", importance=1.0),
    ])
    reducer = soma.ContextReducer()

    with pytest.raises(ValueError):
        reducer.compress(trajectory, budget_events=-1)
    with pytest.raises(ValueError):
        reducer.compress(trajectory, budget_events=2)
    with pytest.raises(TypeError):
        reducer.compress(trajectory, budget_events=1.0)
    with pytest.raises(TypeError):
        reducer.compress(trajectory, budget_events=True)


def test_reducer_rejects_invalid_budget_domain():
    import pytest

    trajectory = CodingTrajectory([
        TrajectoryEvent(kind="note", content="x", importance=0.1),
    ])
    reducer = soma.ContextReducer()

    for bad in (-1, 2):
        with pytest.raises(ValueError):
            reducer.compress(trajectory, budget_events=bad)
    for bad in (True, 1.0, "1"):
        with pytest.raises(TypeError):
            reducer.compress(trajectory, budget_events=bad)


def test_compression_receipt_binds_input_budget_policy_and_removed_set():
    first = CodingTrajectory([
        TrajectoryEvent(kind="failure", content="boom", importance=1.0),
        TrajectoryEvent(kind="note", content="tail-a", importance=0.1),
    ])
    second = CodingTrajectory([
        TrajectoryEvent(kind="failure", content="boom", importance=1.0),
        TrajectoryEvent(kind="note", content="tail-b", importance=0.1),
    ])
    reducer = soma.ContextReducer()

    a = reducer.compress(first, budget_events=1)
    b = reducer.compress(second, budget_events=1)

    assert a.retained == b.retained
    assert a.digest != b.digest
    assert a.receipt.policy_version
    assert a.receipt.budget_events == 1
    assert a.receipt.input_digest != b.receipt.input_digest
    assert a.receipt.removed_digest != b.receipt.removed_digest
    assert a.receipt.retained_digest == b.receipt.retained_digest


def test_preservation_metrics_count_duplicate_critical_events():
    from capt_runtime.soma.arena import ArenaEntry, evaluate
    from capt_runtime.soma.reconstruction import evaluate_reconstruction

    duplicate = TrajectoryEvent(kind="failure", content="same failure", importance=1.0)
    original = CodingTrajectory([duplicate, duplicate])
    reducer = soma.ContextReducer()
    reduce_to_one = lambda value: reducer.compress(value, budget_events=1)
    compressed = reduce_to_one(original)

    arena_score = evaluate(original, [ArenaEntry("context", reduce_to_one)])[0]
    reconstruction = evaluate_reconstruction(original, compressed)

    assert arena_score.critical_preservation == 0.5
    assert reconstruction.preserved_events == 1
    assert reconstruction.total_critical_events == 2
    assert reconstruction.preservation_ratio == 0.5


def test_empty_critical_set_is_explicitly_vacuous():
    from capt_runtime.soma.arena import ArenaEntry, evaluate
    from capt_runtime.soma.reconstruction import evaluate_reconstruction

    original = CodingTrajectory([
        TrajectoryEvent(kind="note", content="noncritical", importance=0.1),
    ])
    reducer = soma.ContextReducer()
    keep_one = lambda value: reducer.compress(value, budget_events=1)
    compressed = keep_one(original)

    arena_score = evaluate(original, [ArenaEntry("context", keep_one)])[0]
    reconstruction = evaluate_reconstruction(original, compressed)

    assert arena_score.critical_preservation is None
    assert reconstruction.total_critical_events == 0
    assert reconstruction.preservation_ratio is None


def test_corpus_uses_evidence_normalization_defaults_and_tolerates_source():
    from capt_runtime.soma.corpus import build_case

    case = build_case(
        "normalized",
        [
            {"kind": "failure", "content": "boom", "source": "capt"},
            {"kind": "note", "content": "minor", "source": "capt"},
        ],
    )

    assert case.trajectory.events[0].importance == 1.0
    assert case.trajectory.events[0].metadata["source"] == "capt"
    assert case.expected_critical_events == ["failure"]


def test_reducer_importance_dominates_keyword_stuffed_noise():
    trajectory = CodingTrajectory([
        TrajectoryEvent(
            kind="note",
            content="rapid latest api schema interface diff commit test",
            importance=0.01,
        ),
        TrajectoryEvent(kind="failure", content="boom", importance=1.0),
    ])

    result = soma.ContextReducer().compress(trajectory, budget_events=1)

    assert result.retained == [trajectory.events[1]]
