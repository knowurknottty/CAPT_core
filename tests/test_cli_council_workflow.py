from __future__ import annotations

import json
from pathlib import Path

import capt_cli


def test_capt_council_headless_uses_human_workflow_surface(tmp_path, capsys):
    rc = capt_cli.main([
        "council",
        "--headless",
        "--template",
        "donor-convergence",
        "--target-root",
        str(tmp_path),
    ])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["logicalVessels"] == 33
    assert payload["maxConcurrentCohorts"] == 1
    assert [row["vesselsPerCohort"] for row in payload["cohorts"]] == [11, 11, 11]
    assert [row["model"] for row in payload["cohorts"]] == [
        "qwen/qwen3.8-flash",
        "xiaomi/mimo-v2.6-flash",
        "z-ai/glm-5.3-flash",
    ]


def test_capt_cli_source_root_is_the_repository_root():
    assert Path(capt_cli._SRC) == Path(capt_cli.__file__).resolve().parent
