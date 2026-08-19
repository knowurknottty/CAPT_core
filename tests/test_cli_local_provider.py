from pathlib import Path

from capt_cli import main


def test_capt_run_parser_accepts_registered_provider_id(tmp_path: Path, capsys) -> None:
    result = main([
        "run",
        "--provider", "mtplx",
        "--model", "qwen3.8-27b-mtplx",
        "--prompt", "probe",
        "--state-dir", str(tmp_path),
    ])
    assert result == 1
    assert "CAPT runtime is not running" in capsys.readouterr().err
