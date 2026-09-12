from capt_runtime.soma.trajectory import extract_events


def test_extract_events_preserves_order():
    trajectory = extract_events(
        [
            {"kind": "error", "content": "failure"},
            {"kind": "fix", "content": "patch"},
        ]
    )

    assert [e.kind for e in trajectory.events] == ["error", "fix"]
    assert trajectory.events[0].content == "failure"
