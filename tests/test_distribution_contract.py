"""Build and installed-artifact gates for the v0.5 public distribution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
REQUIRED_PACKAGES = {
    "capt_solo",
    "capt_solo.components",
    "capt_solo.contextpack",
    "capt_solo.continuity",
    "capt_solo.core",
    "capt_solo.ctp",
    "capt_solo.engines",
    "capt_solo.evidence",
    "capt_solo.execution",
    "capt_solo.foundry",
    "capt_solo.khsb",
    "capt_solo.knowledge",
    "capt_solo.learning",
    "capt_solo.lifecycle",
    "capt_solo.memory",
    "capt_solo.ontology",
    "capt_solo.plugin",
    "capt_solo.research",
    "capt_solo.verification",
}
UNSAFE_SEGMENTS = {
    ".capt",
    ".capt_state",
    ".capt_verify",
    ".git",
    "__pycache__",
    "backups",
    "checkpoints",
    "credentials",
    "data",
    "private",
    "secrets",
    "tests",
}
UNSAFE_SUFFIXES = (
    ".db",
    ".db-journal",
    ".db-shm",
    ".db-wal",
    ".env",
    ".key",
    ".pem",
    ".pyc",
)


def _run(command, *, cwd=REPO, env=None):
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode:
        pytest.fail(
            f"command failed ({result.returncode}): {' '.join(map(str, command))}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


@pytest.fixture(scope="session")
def built_artifacts(tmp_path_factory):
    dist = tmp_path_factory.mktemp("capt-dist")
    _run([sys.executable, "-m", "build", "--outdir", str(dist)])
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1
    return {"wheel": wheels[0], "sdist": sdists[0]}


def _names(kind: str, path: Path):
    if kind == "wheel":
        return zipfile.ZipFile(path).namelist()
    return tarfile.open(path).getnames()


def _relative(kind: str, name: str):
    parts = Path(name).parts
    if kind == "sdist" and parts and parts[0].startswith("capt_solo-"):
        parts = parts[1:]
    return parts


def _packages(kind: str, names):
    result = set()
    for name in names:
        parts = _relative(kind, name)
        if parts and parts[-1] == "__init__.py" and parts[0] == "capt_solo":
            result.add(".".join(parts[:-1]))
    return result


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_artifact_contains_every_source_package(built_artifacts, kind):
    names = _names(kind, built_artifacts[kind])
    assert _packages(kind, names) == REQUIRED_PACKAGES


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_artifact_contains_required_runtime_data(built_artifacts, kind):
    names = ["/".join(_relative(kind, name)) for name in _names(kind, built_artifacts[kind])]
    assert "capt_solo/plugin/plugin.json" in names
    skills = [name for name in names if name.startswith("capt_solo/skills/") and name.endswith("/SKILL.md")]
    assert len(skills) == 8
    assert "capt_cli.py" in names


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_artifact_excludes_state_secrets_and_development_files(built_artifacts, kind):
    offenders = []
    for name in _names(kind, built_artifacts[kind]):
        parts = _relative(kind, name)
        lowered = tuple(part.lower() for part in parts)
        if any(part in UNSAFE_SEGMENTS for part in lowered):
            offenders.append(name)
            continue
        if lowered and lowered[-1].endswith(UNSAFE_SUFFIXES):
            offenders.append(name)
    assert offenders == []


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_installed_artifact_profiles_and_cli(built_artifacts, kind, tmp_path):
    venv = tmp_path / f"{kind}-venv"
    _run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)])
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    capt = venv / ("Scripts/capt.exe" if os.name == "nt" else "bin/capt")
    install = [str(python), "-m", "pip", "install", "--no-deps"]
    if kind == "sdist":
        install.append("--no-build-isolation")
    install.append(str(built_artifacts[kind]))
    _run(install, cwd=tmp_path)

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["CAPT_SOLO_HOME"] = str(tmp_path / "runtime-home")
    smoke = _run(
        [
            str(python),
            str(REPO / "tools/profile_smoke.py"),
            "--state-root",
            str(tmp_path / "profile-state"),
            "--json",
        ],
        cwd=tmp_path,
        env=env,
    )
    payload = json.loads(smoke.stdout)
    assert payload["ok"] is True
    assert payload["network"] == "blocked and unused"
    for origin in payload["module_origins"].values():
        assert str(REPO) not in origin

    help_result = _run([str(capt), "--help"], cwd=tmp_path, env=env)
    assert "CAPT Solo local-first verification" in help_result.stdout
    doctor = _run([str(capt), "--json", "doctor"], cwd=tmp_path, env=env)
    doctor_result = json.loads(doctor.stdout)
    assert doctor_result["ok"] is True
    assert not (tmp_path / "runtime-home").exists()

    tutorial_output = tmp_path / f"{kind}-tutorial-output"
    tutorial = _run(
        [
            str(python),
            str(REPO / "examples/verification_first/run.py"),
            "--output",
            str(tutorial_output),
        ],
        cwd=tmp_path,
        env=env,
    )
    tutorial_result = json.loads(tutorial.stdout)
    assert tutorial_result["ok"] is True
    assert tutorial_result["before"] == "PASS"
    assert tutorial_result["after_mutation"] == "FAIL"
    assert tutorial_result["prior_evidence_applicable_after_mutation"] is False
    assert tutorial_result["next_decision"] == "RUN_TARGETED_VERIFICATION"
    for origin in tutorial_result["module_origins"].values():
        assert str(REPO) not in origin
