"""Unit tests for the action-loop detector (upgrade: Antidoom-inspired #7)."""
from capt_runtime.loop_detector import ActionStep, StopLoopDetected, detect_action_loop


def _s(tool, a, st):
    return ActionStep(tool, a, st)


def test_empty_stream_is_not_a_loop():
    assert detect_action_loop([]) is None


def test_no_loop_on_varied_stream():
    steps = [_s("read", "a", "s1"), _s("edit", "b", "s2"), _s("test", "c", "s3")]
    assert detect_action_loop(steps) is None


def test_detects_period_one_stuck():
    steps = [_s("edit", "x", "s")] * 3
    assert detect_action_loop(steps) == StopLoopDetected(period=1, repeats=3, first_index=0)


def test_detects_period_two():
    steps = [_s("edit", "x", "s1"), _s("test", "y", "s2")] * 3
    r = detect_action_loop(steps)
    assert r is not None and r.period == 2 and r.repeats == 3 and r.first_index == 0


def test_progress_is_not_a_loop():
    steps = [_s("edit", "x", f"s{i}") for i in range(4)]
    assert detect_action_loop(steps) is None


def test_prefers_shortest_period():
    steps = [_s("edit", "x", "s")] * 6
    r = detect_action_loop(steps)
    assert r is not None and r.period == 1 and r.repeats == 6


def test_extends_repeat_count_backwards():
    steps = [_s("read", "q", "sq")] + [_s("edit", "x", "s")] * 4
    r = detect_action_loop(steps)
    assert r is not None and r.period == 1 and r.repeats == 4 and r.first_index == 1
