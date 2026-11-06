"""The R0.4 enforcement status is computed from evidence, never asserted."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("r04_report", ROOT / "scripts/r04_enforcement_report.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

ALL = sorted({t for tests in report.DECLARED_EFFECTS.values() for t in tests})


def _junit(path: Path, *, fail: str | None = None, skip: str | None = None, drop: str | None = None) -> Path:
    cases = []
    for name in ALL:
        if name == drop:
            continue
        body = "<failure message='x'/>" if name == fail else "<skipped/>" if name == skip else ""
        cases.append(f"<testcase classname='tests.capt_runtime.test_node_service_identity_e2e' name='{name}'>{body}</testcase>")
    path.write_text("<testsuites><testsuite>" + "".join(cases) + "</testsuite></testsuites>")
    return path


def test_every_declared_test_exists_in_the_e2e_module() -> None:
    source = (ROOT / "tests/capt_runtime/test_node_service_identity_e2e.py").read_text()
    for name in ALL:
        assert f"def {name}(" in source, name


def test_all_passed_on_both_platforms_is_enforced(tmp_path: Path) -> None:
    r = report.compute({"linux": _junit(tmp_path / "l.xml"), "macos": _junit(tmp_path / "m.xml")})
    assert r["status"] == "ENFORCED_FOR_DECLARED_EFFECT_SET"


def test_missing_platform_or_test_or_skip_is_partial(tmp_path: Path) -> None:
    assert report.compute({"linux": _junit(tmp_path / "l.xml")})["status"] == "PARTIAL"
    for kw in ({"drop": ALL[0]}, {"skip": ALL[1]}):
        r = report.compute({"linux": _junit(tmp_path / "l.xml"), "macos": _junit(tmp_path / "m.xml", **kw)})
        assert r["status"] == "PARTIAL", kw


def test_any_failure_is_not_enforced(tmp_path: Path) -> None:
    r = report.compute({"linux": _junit(tmp_path / "l.xml"), "macos": _junit(tmp_path / "m.xml", fail=ALL[2])})
    assert r["status"] == "NOT_ENFORCED"
