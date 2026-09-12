from capt_runtime.soma.benchmark import run_strategy


class FakeTrajectory:
    def token_count(self):
        return 10

    def utility_score(self):
        return 0.8


def identity(value):
    return value


def test_benchmark_density():
    result = run_strategy("identity", FakeTrajectory(), identity)
    assert result.strategy == "identity"
    assert result.density > 0
