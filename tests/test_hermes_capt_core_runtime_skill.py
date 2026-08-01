"""Verification suite for the capt-core-runtime Hermes skill.

Every assertion depends on an observed result: a real subprocess exit code, real
CLI JSON, real file contents. No fixture fakes a "green" outcome.

Isolation contract: any test that reaches CAPTRuntime.load() sets CAPT_SOLO_HOME
to a temp dir. The owner's ~/.capt-solo is never written by this suite.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "hermes" / "capt-core-runtime"
SCRIPTS = SKILL / "scripts"
INSTALLER = REPO / "skills" / "hermes" / "install-capt-core-runtime.sh"


def _canonical_repo() -> Path | None:
    """The checkout the installed capt-solo distribution actually resolves to.

    REPO may be a git worktree that does not own the venv; running CAPT commands
    from there is a genuine WRONG_CHECKOUT (see the adversarial test below).

    "Editable project location" wins over "Location": for an editable install the
    latter is site-packages, which holds no capt_cli.py.
    """
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pip", "show", "capt-solo"],
            capture_output=True, text=True, timeout=60,
        ).stdout
    except Exception:
        return None
    editable = location = None
    for line in out.splitlines():
        if line.startswith("Editable project location:"):
            editable = Path(line.split(":", 1)[1].strip())
        elif line.startswith("Location:"):
            location = Path(line.split(":", 1)[1].strip())
    for cand in (editable, location):
        if cand and (cand / "capt_cli.py").exists():
            return cand
    for cand in (editable, location):
        if cand and cand.exists():
            return cand
    return None


CANONICAL_REPO = _canonical_repo()


def _capt_bin() -> str | None:
    if CANONICAL_REPO and (CANONICAL_REPO / ".venv" / "bin" / "capt").exists():
        return str(CANONICAL_REPO / ".venv" / "bin" / "capt")
    return shutil.which("capt")


CAPT_BIN = _capt_bin()

RUNTIME_CONSTRUCTORS = [
    "CAPTRuntime(", "CAPTRuntime.load", "MemoryEngine(", "MemoryUseGate(",
    "CTPRuntime(", "KHSB(", "LifecycleManager(", "ProofEngine(",
    "CapabilityRegistry(", "ClaimGuard(", "ContextPackBuilder(", "ArtifactStore(",
]


def run(cmd, env=None, cwd=None, timeout=180):
    e = dict(os.environ)
    # Ensure the canonical CAPT venv (capt console script + python) is on PATH.
    # Correctness must not depend on an ambient shell activation; the skill's
    # scripts select the interpreter deterministically, but `capt` itself is a
    # console script that must be resolvable.
    if CANONICAL_REPO is not None:
        vbin = str(CANONICAL_REPO / ".venv" / "bin")
        if os.path.isdir(vbin):
            e["PATH"] = vbin + os.pathsep + e.get("PATH", "")
            e.setdefault("CAPT_ACCEPT_PY", str(CANONICAL_REPO / ".venv" / "bin" / "python"))
    if env:
        e.update(env)
    return subprocess.run(
        cmd, capture_output=True, text=True, env=e, cwd=cwd, timeout=timeout
    )


def capt_available() -> bool:
    return CAPT_BIN is not None


needs_capt = pytest.mark.skipif(not capt_available(), reason="capt CLI not resolvable")

def make_isolated_workspace(tmp_path: Path, name: str) -> tuple[Path, dict]:
    """Build a fully isolated CAPT workspace.

    Observed capt-solo 0.5.0 behaviour: `capt mission checkpoint` derives the
    checkpoint-store root from the location of capt_cli.py, NOT from the CWD and
    NOT from CAPT_SOLO_HOME. Running it via the installed console script
    therefore writes into the owner's repository. Copying capt_cli.py into the
    temp workspace redirects the store to that workspace. CAPT_SOLO_HOME still
    isolates the memory db / CTP journal / KHSB log.
    """
    ws = tmp_path / name
    ws.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(ws)], check=True)
    subprocess.run(
        ["git", "-C", str(ws), "commit", "-q", "--allow-empty", "-m", "init"],
        check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )
    shutil.copy2(CANONICAL_REPO / "capt_cli.py", ws / "capt_cli.py")
    env = {"CAPT_SOLO_HOME": str(tmp_path / "home")}
    return ws, env


def capt_cli(ws: Path, *args: str):
    """Invoke the canonical CLI through the workspace-local capt_cli.py."""
    py = str(CANONICAL_REPO / ".venv" / "bin" / "python")
    return [py, str(ws / "capt_cli.py"), *args]




# ---------------------------------------------------------------- structure --

def test_skill_package_exists():
    assert (SKILL / "SKILL.md").is_file()
    for d in ("references", "scripts", "schemas"):
        assert (SKILL / d).is_dir(), f"missing {d}/"


def test_skill_frontmatter_matches_hermes_loader_contract():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    assert m, "SKILL.md must open with a --- delimited YAML frontmatter block"
    fm, body = m.group(1), m.group(2)

    data = {}
    for line in fm.splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip()

    assert data.get("name") == "capt-core-runtime"
    desc = data.get("description", "")
    assert desc, "description is required"
    # Hermes: MAX_DESCRIPTION_LENGTH=1024, SKILL_PROMPT_DESC_LIMIT=60 for new skills
    assert len(desc) <= 1024
    assert len(desc) <= 60, f"description {len(desc)}ch exceeds new-skill cap 60"
    assert body.strip(), "body must be non-empty"
    assert len(text) <= 100_000, "exceeds MAX_SKILL_CONTENT_CHARS"


def test_referenced_files_all_resolve():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    refs = set(re.findall(r"`?((?:references|scripts|schemas)/[A-Za-z0-9._-]+)`?", text))
    assert refs, "SKILL.md should reference its support files"
    missing = [r for r in sorted(refs) if not (SKILL / r).exists()]
    assert not missing, f"dangling references in SKILL.md: {missing}"


def test_no_parallel_runtime_construction_in_scripts():
    """The non-negotiable architectural rule, enforced mechanically."""
    offenders = []
    for path in SCRIPTS.glob("*.sh"):
        src = path.read_text(encoding="utf-8")
        # strip comment lines and the doctor's deliberate import-probe/guard text
        code = "\n".join(
            ln for ln in src.splitlines() if not ln.lstrip().startswith("#")
        )
        for token in RUNTIME_CONSTRUCTORS:
            if token in code:
                offenders.append(f"{path.name}: {token}")
    assert not offenders, f"skill scripts must not construct CAPT components: {offenders}"


def test_scripts_are_executable_and_syntactically_valid():
    scripts = sorted(SCRIPTS.glob("*.sh"))
    assert scripts, "no scripts found"
    for s in scripts:
        assert os.access(s, os.X_OK), f"{s.name} not executable"
        r = run(["bash", "-n", str(s)])
        assert r.returncode == 0, f"{s.name} syntax error: {r.stderr}"


def test_boot_report_schema_is_valid_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SKILL / "schemas" / "boot-report.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_rejects_governed_without_gate_pass():
    """A report claiming GOVERNED while the gate did not PASS must not validate."""
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SKILL / "schemas" / "boot-report.schema.json").read_text())
    bad = {
        "report": "capt-boot-report",
        "schema": "capt-core-runtime/boot-report/v1",
        "generated_at": "2026-08-01T00:00:00Z",
        "workspace_root": "/tmp/ws", "branch": "main", "head": "", "dirty": False,
        "python": {"version": "3.12.0", "executable": "/usr/bin/python"},
        "capt": {"module_file": "x", "version": "0.5.0", "home": "/tmp/home"},
        "mission_id": "m", "session_id": "s", "checkpoint_id": "c",
        "active_directive_ids": [], "superseded_directive_ids": "UNPROVEN",
        "selected_memory_ids": "UNPROVEN", "rejected_memory_ids": "UNPROVEN",
        "missing_memory_ids": "UNPROVEN", "conflict_ids": "UNPROVEN",
        "contextpack_digest": "", "memory_use_decision_id": "UNPROVEN",
        "gate_result": "BLOCKED",
        "capt_execution_mode": "GOVERNED",
        "hermes_session_mode": "BOOTSTRAP_DEGRADED",
        "next_justified_action": "x",
    }
    errs = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errs, "schema must reject GOVERNED with a non-PASS gate"


def test_installer_validates_and_refuses_runtime_construction(tmp_path):
    r = run(["bash", str(INSTALLER), "--dry-run"])
    assert r.returncode == 0, r.stderr
    assert "frontmatter OK" in r.stdout
    assert "boundary OK" in r.stdout
    assert "dry-run: nothing written" in r.stdout


def test_installer_copies_full_tree_with_provenance(tmp_path):
    dest = tmp_path / "skills" / "capt" / "capt-core-runtime"
    r = run(["bash", str(INSTALLER), "--dest", str(dest)],
            env={"HERMES_CONFIG_DIR": str(tmp_path)})
    assert r.returncode == 0, r.stderr
    assert (dest / "SKILL.md").is_file()
    assert (dest / "references" / "diagnostics.md").is_file()
    assert (dest / "scripts" / "capt-doctor.sh").is_file()
    assert (dest / "schemas" / "boot-report.schema.json").is_file()
    assert os.access(dest / "scripts" / "capt-doctor.sh", os.X_OK)

    prov = json.loads((dest / ".install-provenance.json").read_text())
    assert prov["skill"] == "capt-core-runtime"
    assert prov["install_method"] == "copy"
    assert re.fullmatch(r"[0-9a-f]{64}", prov["content_digest"])
    assert prov["file_count"] >= 10
    assert not (dest / ".install-provenance.json").is_symlink()


def test_hermes_loader_would_discover_installed_skill(tmp_path):
    """Mirror the loader: rglob SKILL.md under the skills root, excluding support dirs."""
    dest = tmp_path / "skills" / "capt" / "capt-core-runtime"
    r = run(["bash", str(INSTALLER), "--dest", str(dest)],
            env={"HERMES_CONFIG_DIR": str(tmp_path)})
    assert r.returncode == 0, r.stderr

    support = {"references", "templates", "assets", "scripts"}
    found = []
    for p in (tmp_path / "skills").rglob("SKILL.md"):
        if support & set(p.relative_to(tmp_path / "skills").parts):
            continue
        found.append(p)
    assert len(found) == 1, f"expected exactly one discoverable skill, got {found}"
    assert found[0].parent.name == "capt-core-runtime"
    assert found[0].parent.parent.name == "capt", "category namespace must be capt/"


# ----------------------------------------------------------------- behaviour --

@needs_capt
def test_environment_report_resolves_source_and_hides_secrets(tmp_path):
    r = run(["bash", str(SCRIPTS / "capt-environment-report.sh"), str(CANONICAL_REPO)],
            env={"CAPT_SOLO_HOME": str(tmp_path / "home"),
                 "LM_STUDIO_API_KEY": "sk-should-never-appear-xyz123"})
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["capt"]["checkout_verdict"] == "PASS"
    assert data["capt"]["source_resolved_via"].startswith("installed-distribution")
    assert data["capt"]["module_version"]
    # secret discipline: presence only, value never emitted anywhere
    assert data["credentials"]["LM_STUDIO_API_KEY"] == "present (env)"
    assert "sk-should-never-appear-xyz123" not in r.stdout
    assert "sk-should-never-appear-xyz123" not in r.stderr


@needs_capt
def test_environment_report_rejects_foreign_checkout(tmp_path):
    """Adversarial: a genuinely foreign checkout must be refused (WRONG_CHECKOUT).

    The skill worktree legitimately shares the canonical editable install
    (capt-solo), so it is a VALID checkout — not a wrong one. A real foreign
    checkout is a separate repo whose capt_solo import resolves outside the
    resolved source root.
    """
    # 1. The skill worktree shares the canonical editable install → valid (PASS).
    if CANONICAL_REPO is None or REPO.resolve() == CANONICAL_REPO.resolve():
        pytest.skip("test suite is running inside the canonical checkout")
    r = run([str(SCRIPTS / "capt-environment-report.sh"), str(REPO)])
    assert r.returncode == 0, f"worktree sharing canonical install should PASS, got {r.returncode}: {r.stderr}"
    data = json.loads(r.stdout)
    assert data["capt"]["checkout_verdict"] == "PASS", data["capt"]["checkout_verdict"]

    # 2. A genuine foreign checkout (own fake capt_solo) is refused.
    foreign = tmp_path / "foreign-repo"
    (foreign / "capt_solo").mkdir(parents=True)
    (foreign / "capt_solo" / "__init__.py").write_text('__version__ = "9.9.9-FOREIGN"\n')
    rf = run([str(SCRIPTS / "capt-environment-report.sh"), str(foreign)])
    # Either the script refuses (exit 3) or reports FAIL:WRONG_CHECKOUT — both
    # are acceptable "refused" outcomes; a silent PASS is the failure mode.
    assert rf.returncode != 0 or "FAIL:WRONG_CHECKOUT" in rf.stdout, \
        f"foreign checkout must be refused, got rc={rf.returncode}: {rf.stdout[:500]}"


@needs_capt
def test_environment_report_rejects_nonexistent_workspace():
    r = run(["bash", str(SCRIPTS / "capt-environment-report.sh"), "/nonexistent/xyz"])
    assert r.returncode == 2
    assert "workspace not found" in r.stdout


@needs_capt
def test_fresh_boot_requires_explicit_mission():
    """--mission is mandatory: auto-discovery raises on legacy checkpoints."""
    r = run(["bash", str(SCRIPTS / "capt-fresh-boot.sh"), str(CANONICAL_REPO)])
    assert r.returncode == 2
    assert "mission" in (r.stderr + r.stdout).lower()


@needs_capt
def test_resume_check_requires_explicit_mission():
    r = run(["bash", str(SCRIPTS / "capt-resume-check.sh"), str(CANONICAL_REPO)])
    assert r.returncode == 2


@needs_capt
def test_doctor_reports_no_source_as_failure(tmp_path):
    """A workspace with no CAPT store must FAIL, not silently pass."""
    ws = tmp_path / "empty-ws"
    ws.mkdir()
    r = run(["bash", str(SCRIPTS / "capt-doctor.sh"), str(ws)],
            env={"CAPT_SOLO_HOME": str(tmp_path / "home")})
    assert r.returncode == 1, "doctor must exit 1 when a mandatory check FAILs"
    assert "FAIL" in r.stdout
    assert "MISSION_MISSING" in r.stdout


@needs_capt
def test_doctor_never_collapses_available_into_operational(tmp_path):
    r = run(["bash", str(SCRIPTS / "capt-doctor.sh"), str(CANONICAL_REPO)],
            env={"CAPT_SOLO_HOME": str(tmp_path / "home")})
    out = r.stdout
    assert "NOT_PROVEN" in out, "doctor must use NOT_PROVEN for unprobed capability"
    # ClaimGuard importable must never be reported as PASS
    cg = [ln for ln in out.splitlines() if "claimguard" in ln]
    assert cg and cg[0].startswith("NOT_PROVEN"), f"claimguard row: {cg}"
    # the honest tool-authorization line must always be present
    assert "OBSERVATIONAL" in out
    assert "hermes_session_mode: BOOTSTRAP_DEGRADED" in out


@needs_capt
def test_doctor_flags_legacy_checkpoint_schema(tmp_path):
    """Adversarial: a legacy checkpoint (no project_id/objective) must be flagged."""
    ws = tmp_path / "ws"
    (ws / ".capt" / "checkpoints").mkdir(parents=True)
    (ws / ".capt" / "checkpoints" / "legacy-mission.json").write_text(
        json.dumps({"mission_id": "legacy-mission", "current_phase": "p"})
    )
    r = run(["bash", str(SCRIPTS / "capt-doctor.sh"), str(ws)],
            env={"CAPT_SOLO_HOME": str(tmp_path / "home")})
    assert "LEGACY_CHECKPOINT_SCHEMA" in r.stdout
    assert "legacy-mission" in r.stdout


@needs_capt
def test_doctor_flags_placeholder_checkpoint_digest(tmp_path):
    """Adversarial: a 64-zero event_digest must be reported before it BLOCKs a boot."""
    ws = tmp_path / "ws"
    (ws / ".capt" / "checkpoints").mkdir(parents=True)
    (ws / ".capt" / "checkpoints" / "m.json").write_text(json.dumps({
        "mission_id": "m", "project_id": "ws", "objective": "o",
        "event_digest": "sha256:" + "0" * 64,
    }))
    r = run(["bash", str(SCRIPTS / "capt-doctor.sh"), str(ws)],
            env={"CAPT_SOLO_HOME": str(tmp_path / "home")})
    assert "placeholder digest" in r.stdout
    assert "CHECKPOINT_INTEGRITY" in r.stdout


@needs_capt
def test_boot_report_conforms_to_schema_on_isolated_mission(tmp_path):
    """End-to-end: create an isolated mission, boot it, validate the report."""
    jsonschema = pytest.importorskip("jsonschema")
    ws, env = make_isolated_workspace(tmp_path, "acceptance-ws")
    mission = "mission-skill-acceptance"

    mk = run(capt_cli(ws, "mission", "checkpoint", "--mission-id", mission,
                      "--project-id", ws.name, "--objective", "verify skill boot path",
                      "--phase", "PHASE_TEST", "--next", "validate report"),
             env=env, cwd=str(ws))
    assert mk.returncode == 0, mk.stderr + mk.stdout
    # isolation proof: the checkpoint landed inside the temp workspace
    assert (ws / ".capt" / "checkpoints" / f"{mission}.json").is_file()

    boot = run(["bash", str(SCRIPTS / "capt-fresh-boot.sh"), str(ws), mission], env=env)
    assert boot.returncode in (0, 3), f"rc={boot.returncode} {boot.stderr}"
    report = json.loads(boot.stdout)

    schema = json.loads((SKILL / "schemas" / "boot-report.schema.json").read_text())
    errs = list(jsonschema.Draft202012Validator(schema).iter_errors(report))
    assert not errs, f"boot report violates schema: {[e.message for e in errs][:5]}"

    assert report["mission_id"] == mission
    assert report["contextpack_digest"].startswith("sha256:")
    assert report["gate_result"] in ("PASS", "DEGRADED")
    # the honesty contract: never inherit GOVERNED for the Hermes session
    assert report["hermes_session_mode"] == "BOOTSTRAP_DEGRADED"


@needs_capt
def test_checkpoint_and_fresh_process_resume(tmp_path):
    """Continuity: checkpoint, then recover in a genuinely separate process."""
    ws, env = make_isolated_workspace(tmp_path, "resume-ws")
    mission = "mission-skill-continuity"

    mk = run(capt_cli(ws, "mission", "checkpoint", "--mission-id", mission,
                      "--project-id", ws.name, "--objective", "verify continuity",
                      "--phase", "PHASE_TEST", "--next", "resume"),
             env=env, cwd=str(ws))
    assert mk.returncode == 0, mk.stderr + mk.stdout
    assert (ws / ".capt" / "checkpoints" / f"{mission}.json").is_file()

    receipt = tmp_path / "checkpoint-receipt.json"
    cp = run(["bash", str(SCRIPTS / "capt-checkpoint.sh"), str(ws), mission,
              "--receipt-out", str(receipt)], env=env)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    cpr = json.loads(receipt.read_text())
    assert cpr["reload_verified"] is True
    cp_id = cpr["checkpoint_id"]
    assert cp_id

    rec = tmp_path / "recovery-receipt.json"
    rs = run(["bash", str(SCRIPTS / "capt-resume-check.sh"), str(ws), mission,
              "--receipt-out", str(rec), "--expect-checkpoint", cp_id], env=env)
    assert rs.returncode == 0, rs.stdout + rs.stderr
    rr = json.loads(rec.read_text())

    assert rr["continuity_verdict"] == "PROVEN"
    assert rr["reconstructed_in"] == "fresh-process"
    assert rr["transcript_inheritance"] == "none"
    assert rr["mission_id"] == mission
    assert rr["checkpoint_id"] == cp_id
    assert rr["post_resume"]["gate_result"] == "PASS"
    assert rr["post_resume"]["contextpack_digest"].startswith("sha256:")
    assert all(c["verdict"] == "PASS" for c in rr["checks"]), rr["checks"]
    assert rr["hermes_session_mode"] == "BOOTSTRAP_DEGRADED"


@needs_capt
def test_resume_of_unknown_mission_is_not_proven(tmp_path):
    """Adversarial: a mission that does not exist must not report continuity."""
    home = tmp_path / "home"
    ws = tmp_path / "ws"
    ws.mkdir()
    r = run(["bash", str(SCRIPTS / "capt-resume-check.sh"), str(ws), "mission-does-not-exist"],
            env={"CAPT_SOLO_HOME": str(home)})
    assert r.returncode in (4, 5), f"rc={r.returncode}"
    assert "PROVEN" not in r.stdout or "NOT_PROVEN" in r.stdout


@needs_capt
def test_owner_capt_home_untouched_by_suite():
    """The isolation contract itself: the suite must not write the owner's home."""
    owner = Path.home() / ".capt-solo"
    if not owner.exists():
        pytest.skip("no owner CAPT home on this machine")
    for name in ("mission-skill-acceptance", "mission-skill-continuity"):
        hits = list(owner.rglob(f"*{name}*"))
        assert not hits, f"test mission leaked into owner home: {hits}"


# ------------------------------------------------- interpreter determinism --

SELECT_LIB = SCRIPTS / "capt-select-python.sh"


def _source_and_report(tmp_path, env_extra=None, ws=None):
    """Source capt-select-python.sh in a clean shell and emit its variables as JSON."""
    import shlex
    script = tmp_path / "probe.sh"
    ws_arg = shlex.quote(str(ws)) if ws else ""
    # The inner heredoc must run under the SELECTED interpreter ($CAPT_PY), not
    # ambient python3, or it cannot import capt_solo. We echo $CAPT_PY first.
    script.write_text(
        f'source {shlex.quote(str(SELECT_LIB))} {ws_arg} || exit $?\n'
        'echo "SELECTED=$CAPT_PY"\n'
        '"$CAPT_PY" - <<PY\n'
        'import json, os\n'
        'keys = ["CAPT_PY","CAPT_PY_SOURCE","CAPT_PY_VERSION","CAPT_PY_PREFIX",\n'
        '        "CAPT_PKG_FILE","CAPT_PKG_VERSION","CAPT_PKG_EDITABLE","CAPT_PY_DISAGREES"]\n'
        'print(json.dumps({k: os.environ.get(k,"") for k in keys}))\n'
        'PY\n'
    )
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    env.pop("VIRTUAL_ENV", None)
    r = run(["bash", str(script)], env=env, cwd=str(tmp_path))
    return r


def _parse_selection(stdout):
    """Extract the JSON object from the probe's mixed stdout."""
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            import json as _json
            return _json.loads(line)
    raise AssertionError(f"no JSON in probe output: {stdout!r}")


def test_interpreter_explicit_override_wins_over_system_python(tmp_path):
    """A system python first on PATH must NOT override an explicit CAPT_ACCEPT_PY."""
    system_py = shutil.which("python3") or shutil.which("python")
    if system_py is None:
        pytest.skip("no system python to shadow with")
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    (fakebin / "python3").write_text('#!/bin/sh\necho "Python 3.9.6 (fake)"; exit 0\n')
    (fakebin / "python3").chmod(0o755)
    real_py = str(CANONICAL_REPO / ".venv" / "bin" / "python")
    r = _source_and_report(
        tmp_path,
        env_extra={"CAPT_ACCEPT_PY": real_py, "PATH": f"{fakebin}:{os.environ['PATH']}"},
    )
    assert r.returncode == 0, r.stderr + r.stdout
    data = _parse_selection(r.stdout)
    assert data["CAPT_PY_SOURCE"] == "explicit:CAPT_ACCEPT_PY"
    assert data["CAPT_PY"] == real_py
    assert data["CAPT_PKG_VERSION"] == "0.5.0", data
    assert "3.9" not in data["CAPT_PY_VERSION"]


def test_interpreter_missing_override_fails_precisely(tmp_path):
    """A missing/non-executable override must fail, not fall back to PATH."""
    r = _source_and_report(
        tmp_path, env_extra={"CAPT_ACCEPT_PY": "/nonexistent/python"}
    )
    assert r.returncode == 2, f"expected exit 2, got {r.returncode}: {r.stderr}"
    assert "CAPT_ACCEPT_PY" in r.stderr
    assert "CAPT_PY_SELECTION_FAILED" in r.stderr


def test_interpreter_explicit_valid_produces_canonical_identity(tmp_path):
    """An explicit valid interpreter yields the canonical CAPT identity."""
    real_py = str(CANONICAL_REPO / ".venv" / "bin" / "python")
    r = _source_and_report(tmp_path, env_extra={"CAPT_ACCEPT_PY": real_py})
    assert r.returncode == 0, r.stderr
    data = _parse_selection(r.stdout)
    assert data["CAPT_PY_SOURCE"] == "explicit:CAPT_ACCEPT_PY"
    assert data["CAPT_PKG_VERSION"] == "0.5.0"
    assert data["CAPT_PKG_FILE"].endswith("capt_solo/__init__.py")


def test_interpreter_cwd_shadow_detected_without_switching(tmp_path):
    """CWD shadowing is detected while the selected interpreter stays fixed."""
    real_py = str(CANONICAL_REPO / ".venv" / "bin" / "python")
    (tmp_path / "capt_solo").mkdir()
    (tmp_path / "capt_solo" / "__init__.py").write_text('__version__ = "0.0.0-FAKE"\n')
    r = _source_and_report(tmp_path, env_extra={"CAPT_ACCEPT_PY": real_py})
    assert r.returncode == 0, r.stderr
    data = _parse_selection(r.stdout)
    assert data["CAPT_PY"] == real_py
    assert data["CAPT_PKG_VERSION"] == "0.5.0"
    assert "capt_solo" in data["CAPT_PKG_FILE"]
    assert "0.0.0-FAKE" not in data["CAPT_PKG_VERSION"]


def test_interpreter_fresh_shell_reproducible(tmp_path):
    """Two independent fresh shells select the same deterministic identity."""
    real_py = str(CANONICAL_REPO / ".venv" / "bin" / "python")
    r1 = _source_and_report(tmp_path, env_extra={"CAPT_ACCEPT_PY": real_py})
    r2 = _source_and_report(tmp_path, env_extra={"CAPT_ACCEPT_PY": real_py})
    assert r1.returncode == 0 and r2.returncode == 0
    d1, d2 = _parse_selection(r1.stdout), _parse_selection(r2.stdout)
    assert d1["CAPT_PY"] == d2["CAPT_PY"]
    assert d1["CAPT_PKG_VERSION"] == d2["CAPT_PKG_VERSION"] == "0.5.0"
    assert d1["CAPT_PKG_FILE"] == d2["CAPT_PKG_FILE"]
