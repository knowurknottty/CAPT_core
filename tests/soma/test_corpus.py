from capt_runtime.soma.corpus import build_case


def test_build_case_extracts_critical_events():
    case = build_case(
        "bug_fix",
        [
            {"kind": "note", "content": "minor", "importance": 0.2},
            {"kind": "failure", "content": "api broke", "importance": 1.0},
        ],
    )

    assert case.name == "bug_fix"
    assert case.expected_critical_events == ["failure"]
