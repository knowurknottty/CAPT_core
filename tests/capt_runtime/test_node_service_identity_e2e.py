"""CAPT Node service identity (R0.4), end to end, with real Unix users.

Three identities: the Node service account, the human operator (holds the human
credential and the signing keys) and an agent account. Linux: create them with
``scripts/setup_capt_node_e2e_linux.sh``. macOS: ``deploy/macos/capt-node/staging-e2e.sh``
maps them to the real accounts through CAPT_NODE_E2E_* variables. Run as root.
Skipped, never faked, when prerequisites are missing.

Nothing here touches a live runtime: every path lives under a fresh, marked base directory.
"""
from __future__ import annotations

import grp
import json
import os
import pwd
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

SVC = os.environ.get("CAPT_NODE_E2E_SVC", "cnode-svc")
HUMAN = os.environ.get("CAPT_NODE_E2E_HUMAN", "cnode-human")
AGENT = os.environ.get("CAPT_NODE_E2E_AGENT", "cnode-agent")
CLIENTS = os.environ.get("CAPT_NODE_E2E_CLIENTS", "cnode-clients")
PY = os.environ.get("CAPT_NODE_E2E_PYTHON", "/opt/capt-venv/bin/python")
REPO = Path(__file__).resolve().parents[2]
BASE = Path(os.environ.get("CAPT_NODE_E2E_BASE") or (
    ("/srv" if sys.platform == "linux" else "/Users/Shared") + f"/capt-node-e2e-{os.getpid()}"))
MARKER = "CAPT Node service-identity E2E fixture v1\n"
CTL = "e2e-controller"


def _missing() -> str | None:
    if sys.platform not in ("linux", "darwin"):
        return "Linux and macOS only"
    if os.geteuid() != 0:
        return "needs root to act as several real users"
    for user in (SVC, HUMAN, AGENT):
        try:
            pwd.getpwnam(user)
        except KeyError:
            return f"user {user} missing"
    try:
        members = set(grp.getgrnam(CLIENTS).gr_mem)
    except KeyError:
        return f"group {CLIENTS} missing"
    if AGENT in members:
        return f"{AGENT} must not be in {CLIENTS}"
    if not Path(PY).is_file():
        return "interpreter missing"
    return None


_REASON = _missing()
if _REASON and os.environ.get("CAPT_NODE_E2E_REQUIRED") == "1":
    raise RuntimeError(f"CAPT_NODE_E2E_REQUIRED=1 but prerequisites are missing: {_REASON}")
pytestmark = pytest.mark.skipif(_REASON is not None, reason=_REASON or "")


def _uid(name: str) -> int:
    return pwd.getpwnam(name).pw_uid


def _gid(name: str) -> int:
    return grp.getgrnam(name).gr_gid


def _as(user: str) -> list[str]:
    return ["runuser", "-u", user, "--"] if sys.platform == "linux" else ["sudo", "-n", "-u", user, "--"]


def _own(path: Path, user: str | int, group: str | int | None, mode: int) -> None:
    uid = user if isinstance(user, int) else _uid(user)
    gid = (pwd.getpwuid(uid).pw_gid if group is None else group if isinstance(group, int) else _gid(group))
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def _env(home: Path) -> list[str]:
    return ["env", "-i", f"PATH=/usr/bin:/bin", f"HOME={home}", f"PYTHONPATH={BASE / 'app'}"]


def run_as(user: str, action: str, args: dict | None = None, *, home: Path | None = None) -> dict:
    argv = [*_as(user), *_env(home or BASE), PY, str(BASE / "app/tests/capt_runtime/node_e2e_actions.py"),
            action, json.dumps(args or {})]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=60, cwd="/")
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def node_cli(user: str, *cli: str, home: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([*_as(user), *_env(home or BASE), PY, "-m", "capt_runtime.node.cli", *cli],
                          capture_output=True, text=True, timeout=60, cwd="/")


def _reset_base() -> None:
    if BASE.parent not in (Path("/srv"), Path("/Users/Shared")) or not BASE.name.startswith("capt-node-e2e-"):
        raise RuntimeError("CAPT_NODE_E2E_BASE must be a dedicated capt-node-e2e-* directory")
    if BASE.is_symlink():
        raise RuntimeError("refusing symlinked base")
    if BASE.exists():
        marker = BASE / ".marker"
        if BASE.stat().st_uid != 0 or marker.is_symlink() or not marker.is_file() or marker.read_text() != MARKER:
            raise RuntimeError("refusing to reset unmarked base")
        shutil.rmtree(BASE)
    BASE.mkdir(parents=True)
    os.chmod(BASE, 0o755)
    (BASE / ".marker").write_text(MARKER)
    os.chmod(BASE / ".marker", 0o600)


@pytest.fixture(scope="module")
def node():
    _reset_base()
    private = ("*.key", "*.token", ".env", ".env.*", "*.pem")
    shutil.copytree(REPO, BASE / "app", ignore=shutil.ignore_patterns(
        ".git", "node_modules", "__pycache__", ".pytest_cache", ".venv", "venv", *private))
    subprocess.run(["chmod", "-R", "a+rX,go-w", str(BASE / "app")], check=True)  # root-owned, read-only

    human_home = BASE / "human"
    operator = human_home / "operator"
    for d in (BASE / "etc", BASE / "trust", BASE / "state", BASE / "run", BASE / "ws", human_home, BASE / "agent"):
        d.mkdir()
    _own(human_home, HUMAN, None, 0o700)
    _own(BASE / "agent", AGENT, None, 0o700)
    operator.mkdir()
    _own(operator, HUMAN, None, 0o700)
    token = human_home / "runtime.token"
    token.write_text(secrets.token_hex(32))
    _own(token, HUMAN, None, 0o600)

    # Operator (human) generates the Node, authority and controller identities and pairs.
    op_cfg = operator / "node.json"
    assert node_cli(HUMAN, "init", "--config", str(op_cfg), "--workspace", str(BASE / "ws"), home=human_home).returncode == 0
    raw = json.loads(op_cfg.read_text())
    raw["endpoint"] = f"unix://{BASE / 'run/capt-node.sock'}"
    op_cfg.write_text(json.dumps(raw, indent=2))
    _own(op_cfg, HUMAN, None, 0o600)
    pend = json.loads(node_cli(HUMAN, "pair", "--config", str(op_cfg), "--controller-id", CTL, home=human_home).stdout)
    act = node_cli(HUMAN, "pair", "--config", str(op_cfg), "--controller-id", CTL,
                   "--approve-code", pend["verificationCode"], home=human_home)
    assert json.loads(act.stdout)["state"] == "active", act.stderr

    # Install: node identity to the service; trust anchors root-owned and read-only.
    op_state = operator / ".capt-node-state"
    shutil.copy2(op_state / "node.key", BASE / "state" / "node.key")
    (op_state / "node.key").unlink()  # the Node's identity is the service's, not the operator's
    for name in ("authority.pub", "pairings.json"):
        shutil.copy2(op_state / name, BASE / "trust" / name)
        _own(BASE / "trust" / name, 0, 0, 0o644)
    _own(BASE / "trust", 0, 0, 0o755)
    # setgid: files the Node creates (journal, denials) inherit the client group so the
    # human can audit them; node.key stays 0600 owner-only.
    _own(BASE / "state", SVC, CLIENTS, 0o2750)
    _own(BASE / "state" / "node.key", SVC, None, 0o600)
    _own(BASE / "run", SVC, CLIENTS, 0o750)
    _own(BASE / "ws", SVC, CLIENTS, 0o2770)
    svc_cfg = BASE / "etc" / "node.json"
    svc_raw = {k: raw[k] for k in ("endpoint", "workspaceRoots", "nodeId", "authorityId", "deviceName")}
    svc_raw["emergencyStopHotkey"] = None
    svc_raw["serviceIdentity"] = {
        "trustDir": str(BASE / "trust"), "stateDir": str(BASE / "state"),
        "allowedPeerUids": [_uid(HUMAN)], "forbiddenUids": [_uid(HUMAN), _uid(AGENT)],
        "forbiddenReadablePaths": [str(token), str(op_state / "authority.key"),
                                   str(op_state / f"controller-{CTL}.key")],
        "socketGroup": CLIENTS,
    }
    svc_cfg.write_text(json.dumps(svc_raw, indent=2))
    _own(svc_cfg, 0, 0, 0o644)
    _own(BASE / "etc", 0, 0, 0o755)

    def start() -> tuple[subprocess.Popen, dict]:
        proc = subprocess.Popen([*_as(SVC), *_env(BASE / "state"), PY, "-m", "capt_runtime.node.cli",
                                 "serve", "--config", str(svc_cfg)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd="/")
        first = proc.stdout.readline()
        assert first, "node exited before reporting"
        return proc, json.loads(first)

    def stop(proc: subprocess.Popen) -> None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    proc, report = start()
    ctx = {"proc": proc, "report": report, "start": start, "stop": stop, "op_cfg": str(op_cfg),
           "svc_cfg": svc_cfg, "token": token, "human_home": human_home, "op_state": op_state}
    yield ctx
    stop(ctx["proc"])
    if not os.environ.get("CAPT_NODE_E2E_KEEP"):
        shutil.rmtree(BASE)


def human_exec(node, op: str, argv: list[str], **kw) -> dict:
    args = {"config": node["op_cfg"], "controller": CTL, "op": op, "argv": argv, "cwd": str(BASE / "ws"), **kw}
    return run_as(HUMAN, "exec", args, home=node["human_home"])


# ---------------------------------------------------------------- R1.5 basic isolation

def test_node_runs_as_the_service_uid(node) -> None:
    rep = node["report"]
    assert rep["state"] == "serving" and rep["service"]["mode"] == "service_identity"
    assert rep["service"]["serviceUid"] == _uid(SVC) != _uid(HUMAN)
    out = human_exec(node, "r1-id", ["/usr/bin/id", "-u"])
    assert out["state"] == "closed" and out["stdout"].strip() == str(_uid(SVC))


def test_shell_exec_cannot_read_human_token_or_home(node) -> None:
    for i, argv in enumerate((["/bin/cat", str(node["token"])], ["/bin/ls", str(node["human_home"])],
                              ["/bin/cat", str(node["op_state"] / "authority.key")])):
        out = human_exec(node, f"r1-deny-{i}", argv)
        assert out["state"] == "failed" and out["exitCode"] != 0, out
        assert "ermission denied" in (out["stderr"] or ""), out


def test_shell_exec_cannot_rewrite_trust_anchors_config_or_code(node) -> None:
    targets = [BASE / "trust/authority.pub", BASE / "trust/pairings.json", node["svc_cfg"],
               BASE / "app/capt_runtime/node/server.py"]
    for i, target in enumerate(targets):
        out = human_exec(node, f"r1-tamper-{i}", ["/bin/sh", "-c", f"echo x >> '{target}'"])
        assert out["exitCode"] != 0, (target, out)
        mv = human_exec(node, f"r1-mv-{i}", ["/bin/mv", str(target), str(BASE / "ws" / f"stolen{i}")])
        assert mv["exitCode"] != 0, (target, mv)
    assert json.loads((BASE / "trust/pairings.json").read_text())  # unchanged and parseable


def test_permitted_work_executes_and_human_reads_result(node) -> None:
    out = human_exec(node, "r1-write", ["/bin/sh", "-c", "printf governed > result.txt && cat result.txt"])
    assert out["state"] == "closed" and out["stdout"] == "governed"
    assert run_as(HUMAN, "read", {"path": str(BASE / "ws/result.txt")}, home=node["human_home"])["readable"]
    assert "error" in run_as(AGENT, "read", {"path": str(BASE / "ws/result.txt")}, home=BASE / "agent")


def test_scope_violations_fail_closed(node) -> None:
    outside = human_exec(node, "r1-cwd-out", ["/bin/pwd"], cwd=str(BASE / "trust"))
    assert outside.get("code") == "filesystem_scope_violation", outside
    widened = human_exec(node, "r1-wide", ["/bin/pwd"], roots=[str(BASE)])
    assert widened.get("code") == "NODE_CAPABILITY_ROOT_OUTSIDE_SERVICE_SCOPE", widened


def test_only_the_human_peer_reaches_the_socket(node) -> None:
    sock = str(BASE / "run/capt-node.sock")
    agent = run_as(AGENT, "raw_connect", {"socket": sock}, home=BASE / "agent")
    assert agent.get("error") in ("PermissionError",) or agent.get("errno") in (13,), agent
    # The service uid itself can open the socket (group member) but the peer gate refuses it:
    # a shell.exec process cannot drive its own Node.
    out = human_exec(node, "r1-loop", [PY, str(BASE / "app/tests/capt_runtime/node_e2e_actions.py"),
                                       "raw_connect", json.dumps({"socket": sock})])
    assert json.loads(out["stdout"])["response"]["code"] == "NODE_PEER_UID_DENIED", out


def test_receipts_and_denials_are_durable_and_readable_by_the_human(node) -> None:
    assert run_as(HUMAN, "status", {"config": node["op_cfg"], "controller": CTL, "op": "r1-write"},
                  home=node["human_home"])["state"] == "closed"
    denials = [json.loads(x) for x in (BASE / "state/denials.jsonl").read_text().splitlines()]
    codes = {d["code"] for d in denials}
    assert {"NODE_PEER_UID_DENIED", "NODE_CAPABILITY_ROOT_OUTSIDE_SERVICE_SCOPE"} <= codes
    assert run_as(HUMAN, "read", {"path": str(BASE / "state/denials.jsonl")}, home=node["human_home"])["readable"]
    assert "error" in run_as(AGENT, "read", {"path": str(BASE / "state/denials.jsonl")}, home=BASE / "agent")
    assert "error" in run_as(HUMAN, "read", {"path": str(BASE / "state/node.key")}, home=node["human_home"])


def test_service_has_no_sudo(node) -> None:
    out = human_exec(node, "r1-sudo", ["/bin/sh", "-c", "sudo -n true"])
    assert out["exitCode"] != 0, out


def test_restart_keeps_identity_and_replays_not_redispatches(node) -> None:
    node["stop"](node["proc"])
    node["proc"], node["report"] = node["start"]()
    assert node["report"]["service"]["serviceUid"] == _uid(SVC)
    # The journal survived the restart: the receipt is still there ...
    assert run_as(HUMAN, "status", {"config": node["op_cfg"], "controller": CTL, "op": "r1-write"},
                  home=node["human_home"])["state"] == "closed"
    # ... and reusing the operation id for different work is refused, never redispatched.
    again = human_exec(node, "r1-write", ["/bin/sh", "-c", "printf DIFFERENT > result.txt"])
    assert again.get("code") == "operation_digest_mismatch", again
    assert (BASE / "ws/result.txt").read_text() == "governed"


# ---------------------------------------------------------------- R2 adversarial (service running)

def test_symlinks_do_not_launder_reach(node) -> None:
    link = human_exec(node, "r2-link", ["/bin/sh", "-c", f"ln -s '{node['token']}' tok && cat tok"])
    assert link["exitCode"] != 0 and "ermission denied" in (link["stderr"] or ""), link
    made = human_exec(node, "r2-link2", ["/bin/ln", "-s", str(BASE / "trust"), "out"])
    assert made["state"] == "closed", made
    escaped = human_exec(node, "r2-cwd-link", ["/bin/pwd"], cwd=str(BASE / "ws/out"))
    assert escaped.get("code") == "filesystem_scope_violation", escaped


def test_concurrent_reuse_of_one_operation_id_dispatches_once(node) -> None:
    from concurrent.futures import ThreadPoolExecutor
    argv = ["/bin/sh", "-c", "echo once >> race.txt"]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: human_exec(node, "r2-race", argv), range(6)))
    closed = [r for r in results if r.get("state") == "closed"]
    refused = [r for r in results if r.get("code") == "operation_digest_mismatch"]
    assert len(closed) + len(refused) == 6, results
    assert (BASE / "ws/race.txt").read_text() == "once\n"


# ---------------------------------------------------------------- preflight refuses unsafe deployments

def _start_refused(user: str, cfg: Path) -> dict:
    proc = node_cli(user, "serve", "--config", str(cfg), home=BASE / "state")
    assert proc.returncode == 3, (proc.stdout, proc.stderr[-800:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_preflight_refuses_human_and_agent_uids(node) -> None:
    assert _start_refused(HUMAN, node["svc_cfg"])["code"] == "NODE_RUNNING_AS_FORBIDDEN_UID"
    assert _start_refused(AGENT, node["svc_cfg"])["code"] == "NODE_RUNNING_AS_FORBIDDEN_UID"


def test_preflight_refuses_reachable_human_credential(node) -> None:
    os.chmod(node["human_home"], 0o711)
    os.chmod(node["token"], 0o644)
    try:
        refused = _start_refused(SVC, node["svc_cfg"])
        assert refused["code"] == "NODE_HUMAN_CREDENTIAL_REACHABLE" and refused["detail"] == str(node["token"])
    finally:
        os.chmod(node["token"], 0o600)
        os.chmod(node["human_home"], 0o700)


def test_preflight_refuses_service_owned_trust_and_writable_code(node) -> None:
    os.chown(BASE / "trust", _uid(SVC), -1)
    try:
        assert _start_refused(SVC, node["svc_cfg"])["code"] == "NODE_TRUST_ANCHOR_OWNED_BY_SERVICE"
    finally:
        os.chown(BASE / "trust", 0, -1)
    node_dir = BASE / "app/capt_runtime/node"
    os.chown(node_dir, _uid(SVC), -1)
    try:
        assert _start_refused(SVC, node["svc_cfg"])["code"] == "NODE_CODE_OR_CONFIG_WRITABLE"
    finally:
        os.chown(node_dir, 0, -1)


# ---------------------------------------------------------------- cancel vs emergency revocation (R2)

def _svc_processes(marker: str) -> list[str]:
    out = subprocess.run(["pgrep", "-u", SVC, "-f", marker], capture_output=True, text=True)
    return out.stdout.split()


def test_operation_close_is_not_revocation_but_service_revocation_is(node) -> None:
    """A capability holder can leave a detached process behind (double fork + setsid).
    Closing or cancelling the operation does not reach it; the emergency revocation
    procedure (stop the service, kill every process of the service uid) does. It runs
    last: it leaves the Node stopped."""
    marker = f"capt-r2-detached-{os.getpid()}"
    script = ("import os,sys,time\nif os.fork(): sys.exit(0)\nos.setsid()\n"
              "if os.fork(): sys.exit(0)\nos.closerange(0, 256)\ntime.sleep(300)\n")
    out = human_exec(node, "r2-detach", [PY, "-c", script, marker])
    assert out["state"] == "closed", out
    time.sleep(0.5)
    survivors = _svc_processes(marker)
    assert survivors, "expected the detached child to outlive its operation (documents the cancel gap)"
    # Emergency revocation, as the owner would run it (root): stop the Node, kill the uid.
    node["stop"](node["proc"])
    subprocess.run(["pkill", "-KILL", "-u", SVC], check=False)
    deadline = time.time() + 10
    while time.time() < deadline:
        left = subprocess.run(["pgrep", "-u", SVC], capture_output=True, text=True).stdout.split()
        if not left:
            break
        subprocess.run(["pkill", "-KILL", "-u", SVC], check=False)
        time.sleep(0.2)
    assert not _svc_processes(marker)
    left = subprocess.run(["ps", "-o", "pid=,stat=,command=", "-U", SVC], capture_output=True, text=True).stdout
    assert not left.strip(), left  # nothing of the service uid survives revocation
