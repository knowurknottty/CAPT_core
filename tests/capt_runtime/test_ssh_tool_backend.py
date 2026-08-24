from __future__ import annotations

import getpass
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

from capt_runtime import commands, contracts
from capt_runtime.composition import create_runtime
from capt_runtime.errors import AuthorityViolation
from capt_runtime.tool_broker import tool_request_fingerprint
from capt_runtime.tools.backends.ssh import (
    SSHNetworkPolicy,
    SSHProcessBackend,
    SSHProcessRequest,
    SSHProfile,
    SSHProfileRegistry,
    openssh_sha256_fingerprint,
)


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _require_openssh() -> tuple[str, str, str]:
    ssh = shutil.which("ssh")
    ssh_keygen = shutil.which("ssh-keygen")
    sshd = shutil.which("sshd") or ("/usr/sbin/sshd" if Path("/usr/sbin/sshd").exists() else None)
    if not ssh or not ssh_keygen or not sshd:
        pytest.skip("real OpenSSH client/server fixture unavailable")
    return ssh, ssh_keygen, sshd


def _run(argv: list[str]) -> None:
    subprocess.run(argv, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


class OpenSSHFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.port = _free_loopback_port()
        self.proc: subprocess.Popen[str] | None = None
        self.ssh, self.ssh_keygen, self.sshd = _require_openssh()
        self.host_key = root / "host_key"
        self.client_key = root / "client_key"
        self.authorized_keys = root / "authorized_keys"
        self.config = root / "sshd_config"

    def start(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        _run([self.ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-f", str(self.host_key)])
        _run([self.ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-f", str(self.client_key)])
        self.authorized_keys.write_text(self.client_key.with_suffix(".pub").read_text())
        os.chmod(self.authorized_keys, 0o600)
        os.chmod(self.client_key, 0o600)
        os.chmod(self.host_key, 0o600)
        self.config.write_text(
            "\n".join(
                [
                    f"Port {self.port}",
                    "ListenAddress 127.0.0.1",
                    f"HostKey {self.host_key}",
                    f"PidFile {self.root / 'sshd.pid'}",
                    f"AuthorizedKeysFile {self.authorized_keys}",
                    "PubkeyAuthentication yes",
                    "PasswordAuthentication no",
                    "KbdInteractiveAuthentication no",
                    "ChallengeResponseAuthentication no",
                    "UsePAM no",
                    "PermitRootLogin no",
                    f"AllowUsers {getpass.getuser()}",
                    "StrictModes no",
                    "LogLevel ERROR",
                    "",
                ]
            )
        )
        _run([self.sshd, "-t", "-f", str(self.config)])
        self.proc = subprocess.Popen(
            [self.sshd, "-D", "-e", "-f", str(self.config)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError(f"sshd exited: {self.proc.stderr.read() if self.proc.stderr else ''}")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.1)
                if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                    return
            time.sleep(0.02)
        raise AssertionError("sshd did not accept loopback connections")

    def stop(self) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=3)


def _profile(fixture: OpenSSHFixture, remote_root: Path, *, allow_loopback: bool = True) -> SSHProfile:
    profile_id = "ssh-loopback-test"
    public = fixture.host_key.with_suffix(".pub").read_text().strip().split()
    known_hosts = fixture.root / "known_hosts"
    known_hosts.write_text(f"{profile_id} {public[0]} {public[1]}\n")
    return SSHProfile(
        profile_id=profile_id,
        hostname="127.0.0.1",
        port=fixture.port,
        username=getpass.getuser(),
        known_hosts_policy="strict_profile_alias",
        known_hosts_file=known_hosts,
        credential_ref=f"identity-file:{fixture.client_key}",
        allowed_remote_roots=(str(remote_root),),
        network_policy=SSHNetworkPolicy(
            allowed_destination_classes=("loopback",) if allow_loopback else ("public",)
        ),
        remote_python="/usr/bin/python3",
    )


def test_network_policy_denies_loopback_unless_profile_explicitly_allows_it(tmp_path: Path) -> None:
    fixture = OpenSSHFixture(tmp_path / "ssh")
    fixture.start()
    try:
        profile = _profile(fixture, tmp_path, allow_loopback=False)
        registry = SSHProfileRegistry([profile])
        backend = SSHProcessBackend(registry)
        with pytest.raises(AuthorityViolation, match="network policy"):
            backend.preflight(
                SSHProcessRequest(
                    profile_id=profile.profile_id,
                    argv=("/bin/echo", "no"),
                    cwd=str(tmp_path),
                    filesystem_root=str(tmp_path),
                )
            )
    finally:
        fixture.stop()


def test_credential_reference_never_accepts_inline_private_key_material(tmp_path: Path) -> None:
    fixture = OpenSSHFixture(tmp_path / "ssh")
    fixture.start()
    try:
        profile = _profile(fixture, tmp_path)
        bad = SSHProfile(
            **{**profile.__dict__, "credential_ref": "-----BEGIN OPENSSH PRIVATE KEY-----"}
        )
        backend = SSHProcessBackend(SSHProfileRegistry([bad]))
        with pytest.raises(AuthorityViolation, match="credentialRef"):
            backend.preflight(
                SSHProcessRequest(
                    profile_id=bad.profile_id,
                    argv=("/bin/echo", "no"),
                    cwd=str(tmp_path),
                    filesystem_root=str(tmp_path),
                )
            )
    finally:
        fixture.stop()


def test_real_openssh_exec_preserves_argv_and_reports_pinned_host_fingerprint(tmp_path: Path) -> None:
    fixture = OpenSSHFixture(tmp_path / "ssh")
    remote_root = tmp_path / "remote"
    remote_root.mkdir()
    fixture.start()
    try:
        profile = _profile(fixture, remote_root)
        backend = SSHProcessBackend(SSHProfileRegistry([profile]))
        marker = remote_root / "shell-interpolation-must-not-run"
        literal = f"$(touch {marker})"
        result = backend.execute(
            SSHProcessRequest(
                profile_id=profile.profile_id,
                argv=("/bin/echo", literal),
                cwd=str(remote_root),
                filesystem_root=str(remote_root),
            )
        )
        public_blob = fixture.host_key.with_suffix(".pub").read_text().split()[1]
        assert result.exit_code == 0
        assert result.stdout.strip() == literal
        assert result.stderr == ""
        assert not marker.exists()
        assert result.profile_id == profile.profile_id
        assert result.remote_cwd == str(remote_root.resolve())
        assert result.host_fingerprint == openssh_sha256_fingerprint(public_blob)
        assert result.remote_pid > 0
        assert result.remote_process_group_id > 0
    finally:
        fixture.stop()


def test_real_openssh_remote_timeout_kills_remote_process_group(tmp_path: Path) -> None:
    fixture = OpenSSHFixture(tmp_path / "ssh")
    remote_root = tmp_path / "remote"
    remote_root.mkdir()
    fixture.start()
    try:
        profile = _profile(fixture, remote_root)
        backend = SSHProcessBackend(SSHProfileRegistry([profile]))
        result = backend.execute(
            SSHProcessRequest(
                profile_id=profile.profile_id,
                argv=("/usr/bin/python3", "-c", "import time; time.sleep(30)"),
                cwd=str(remote_root),
                filesystem_root=str(remote_root),
                timeout_seconds=0.15,
            )
        )
        assert result.timed_out is True
        assert result.exit_code is not None
    finally:
        fixture.stop()


def test_remote_symlink_escape_is_denied_before_user_argv_executes(tmp_path: Path) -> None:
    fixture = OpenSSHFixture(tmp_path / "ssh")
    remote_root = tmp_path / "remote"
    outside = tmp_path / "outside"
    remote_root.mkdir()
    outside.mkdir()
    (remote_root / "escape").symlink_to(outside, target_is_directory=True)
    fixture.start()
    try:
        profile = _profile(fixture, remote_root)
        backend = SSHProcessBackend(SSHProfileRegistry([profile]))
        marker = outside / "must-not-exist"
        result = backend.execute(
            SSHProcessRequest(
                profile_id=profile.profile_id,
                argv=("/usr/bin/python3", "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('bad')"),
                cwd=str(remote_root / "escape"),
                filesystem_root=str(remote_root),
            )
        )
        assert result.denied is True
        assert "remote cwd escapes" in result.denial_reason
        assert not marker.exists()
    finally:
        fixture.stop()


def _tool_request(profile: SSHProfile, remote_root: Path, argv: list[str], **extra) -> dict:
    arguments = [
        {"kind": "string", "name": "argv", "value": __import__("json").dumps(argv)},
        {"kind": "path", "name": "cwd", "value": str(extra.pop("cwd", remote_root))},
    ]
    for name, value in extra.items():
        arguments.append({"kind": "integer", "name": name, "value": value})
    return {
        "toolRequestId": "ssh-tool-request",
        "toolId": "terminal.ssh",
        "operation": "terminal.exec",
        "arguments": arguments,
        "filesystemScope": str(remote_root),
        "targetIdentity": profile.profile_id,
        "backendId": "ssh",
    }


def _output_value(result: dict, name: str):
    return next(item["value"] for item in result["output"] if item["name"] == name)


def test_ssh_terminal_adapter_returns_remote_provenance_and_durable_effect_identity(tmp_path: Path) -> None:
    from capt_runtime.tools.adapters.ssh_terminal import SSHTerminalToolAdapter

    fixture = OpenSSHFixture(tmp_path / "ssh")
    remote_root = tmp_path / "remote"
    remote_root.mkdir()
    fixture.start()
    try:
        profile = _profile(fixture, remote_root)
        adapter = SSHTerminalToolAdapter(SSHProcessBackend(SSHProfileRegistry([profile])))
        request = _tool_request(profile, remote_root, ["/bin/echo", "SSH_ADAPTER_OK"])
        prepared = adapter.preflight(request)
        result = adapter.execute(request)
        identity = __import__("json").loads(result["sideEffectIdentity"])

        assert prepared.profile.profile_id == profile.profile_id
        assert result["status"] == "succeeded"
        assert result["exitCode"] == 0
        assert _output_value(result, "stdout").strip() == "SSH_ADAPTER_OK"
        assert _output_value(result, "profileId") == profile.profile_id
        assert _output_value(result, "hostFingerprint").startswith("SHA256:")
        assert _output_value(result, "remoteCwd") == str(remote_root.resolve())
        assert identity["profileId"] == profile.profile_id
        assert identity["hostFingerprint"] == _output_value(result, "hostFingerprint")
        assert identity["remoteCwd"] == str(remote_root.resolve())
        assert identity["remotePid"] > 0
    finally:
        fixture.stop()


def test_ssh_terminal_adapter_timeout_is_indeterminate(tmp_path: Path) -> None:
    from capt_runtime.tools.adapters.ssh_terminal import SSHTerminalToolAdapter

    fixture = OpenSSHFixture(tmp_path / "ssh")
    remote_root = tmp_path / "remote"
    remote_root.mkdir()
    fixture.start()
    try:
        profile = _profile(fixture, remote_root)
        adapter = SSHTerminalToolAdapter(SSHProcessBackend(SSHProfileRegistry([profile])))
        result = adapter.execute(
            _tool_request(
                profile,
                remote_root,
                ["/usr/bin/python3", "-c", "import time; time.sleep(30)"],
                timeout_ms=100,
            )
        )
        assert result["status"] == "indeterminate"
        assert _output_value(result, "timedOut") is True
    finally:
        fixture.stop()


RUNTIME_NOW = "2026-08-19T16:00:00Z"


def _runtime_meta(step: str, kind: str, actor: str) -> dict:
    return commands.command(
        command_id=f"cmd-ssh-{step}",
        idempotency_key=f"idem-ssh-{step}",
        operation_fingerprint=commands.fingerprint("ssh-" + step, {"step": step}),
        correlation_id="corr-ssh-runtime",
        actor_id=actor,
        actor_kind=kind,
        issued_at=RUNTIME_NOW,
        replay_policy="never",
    )


def _seed_ssh_authority(runtime, remote_root: Path, *, suffix: str, max_uses: int = 1) -> tuple[str, str]:
    mission = f"m-ssh-{suffix}"
    task = f"t-ssh-{suffix}"
    policy = f"pd-ssh-{suffix}"
    grant = f"g-ssh-{suffix}"
    lease = f"l-ssh-{suffix}"
    scope = {"kind": "filesystem", "rootPath": str(remote_root), "recursive": True}
    policy_digest = contracts.digest({"policy": "ssh-runtime", "suffix": suffix})
    runtime.service.create_mission(
        {
            "schemaVersion": "1.0.0",
            "missionId": mission,
            "rawRequest": "governed SSH acceptance",
            "normalizedRequest": "governed SSH acceptance",
            "objectives": [{"objectiveId": "obj-ssh", "statement": "run governed SSH", "priority": 1}],
            "constraints": [{
                "kind": "resource_boundary",
                "constraintId": "con-ssh",
                "origin": "explicit_user",
                "scope": scope,
            }],
            "successCriteria": [{
                "criterionId": "sc-ssh", "statement": "remote result recorded", "requiresVerification": True
            }],
            "terminationCriteria": [{
                "criterionId": "tc-ssh", "statement": "authority failure", "terminalState": "failed"
            }],
            "unresolvedAmbiguities": [],
            "taskGraphId": None,
            "createdAt": RUNTIME_NOW,
        },
        _runtime_meta("mission-" + suffix, "human", "operator-ssh"),
    )
    runtime.service.evaluate_policy(
        {
            "schemaVersion": "1.0.0",
            "policyDecisionId": policy,
            "policyBundleDigest": policy_digest,
            "effect": "allow",
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "missionId": mission,
            "taskId": task,
            "requestedOperations": ["terminal.exec"],
            "requestedScope": scope,
            "conditions": [],
            "rationale": "bounded named-profile SSH acceptance",
            "decidedBy": {"actorId": "gk-ssh", "kind": "governance_kernel"},
            "decidedAt": RUNTIME_NOW,
        },
        _runtime_meta("policy-" + suffix, "governance_kernel", "gk-ssh"),
    )
    runtime.service.issue_grant(
        {
            "schemaVersion": "1.0.0",
            "grantId": grant,
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "capabilityId": "cap.terminal.exec.ssh",
            "operations": ["terminal.exec"],
            "scope": scope,
            "policyDecisionId": policy,
            "policyBundleDigest": policy_digest,
            "conditions": [],
            "maxUses": max_uses,
            "validFrom": "2026-08-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "issuedBy": {"actorId": "gk-ssh", "kind": "governance_kernel"},
            "issuedAt": RUNTIME_NOW,
        },
        _runtime_meta("grant-" + suffix, "governance_kernel", "gk-ssh"),
    )
    runtime.service.activate_lease(
        {
            "schemaVersion": "1.0.0",
            "leaseId": lease,
            "grantId": grant,
            "missionId": mission,
            "taskId": task,
            "executionContextId": "ec-ssh-" + suffix,
            "operations": ["terminal.exec"],
            "scope": scope,
            "maxUses": max_uses,
            "validFrom": "2026-08-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "activatedAt": RUNTIME_NOW,
        },
        _runtime_meta("lease-" + suffix, "governance_kernel", "gk-ssh"),
    )
    return grant, lease


def _governed_ssh_request(
    profile: SSHProfile,
    remote_root: Path,
    argv: list[str],
    grant: str,
    lease: str,
    *,
    idem: str,
) -> dict:
    request = {
        "schemaVersion": "1.0.0",
        "toolRequestId": "req-" + idem,
        "toolId": "terminal.ssh",
        "operation": "terminal.exec",
        "arguments": [
            {"kind": "string", "name": "argv", "value": json.dumps(argv)},
            {"kind": "path", "name": "cwd", "value": str(remote_root)},
        ],
        "consequential": True,
        "grantId": grant,
        "leaseId": lease,
        "reservationId": None,
        "backendId": "ssh",
        "targetIdentity": profile.profile_id,
        "filesystemScope": str(remote_root),
        "idempotencyKey": idem,
        "operationFingerprint": "sha256:" + "0" * 64,
        "replayPolicy": "never",
        "requestedAt": RUNTIME_NOW,
    }
    request["operationFingerprint"] = tool_request_fingerprint(request)
    return request


def _ssh_envelope(request: dict, *, session: str = "sess-ssh", command_id: str = "cmd-run-ssh") -> dict:
    return {
        "commandId": command_id,
        "operatorId": "operator-ssh",
        "sessionId": session,
        "schemaVersion": "1.0.0",
        "correlationId": "corr-run-ssh",
        "idempotencyKey": request["idempotencyKey"],
        "timestamp": RUNTIME_NOW,
        "op": "run_tool",
        "payload": request,
    }


def test_authenticated_runtime_executes_real_ssh_and_replays_without_second_remote_effect(tmp_path: Path) -> None:
    fixture = OpenSSHFixture(tmp_path / "ssh")
    remote_root = tmp_path / "remote"
    remote_root.mkdir()
    fixture.start()
    profile = _profile(fixture, remote_root)
    runtime = create_runtime(str(tmp_path / "runtime.db"), ssh_profiles=[profile])
    try:
        assert runtime.tool_registry.readiness("terminal.ssh")["status"] == "available"
        grant, lease = _seed_ssh_authority(runtime, remote_root, suffix="exec", max_uses=1)
        marker = remote_root / "remote-count.txt"
        code = (
            "from pathlib import Path; p=Path('remote-count.txt'); "
            "p.write_text(p.read_text()+'x' if p.exists() else 'x')"
        )
        request = _governed_ssh_request(
            profile,
            remote_root,
            ["/usr/bin/python3", "-c", code],
            grant,
            lease,
            idem="ssh-runtime-exec",
        )
        relay = runtime.command_service("operator-ssh", "sess-ssh")
        first = relay.execute(_ssh_envelope(request, command_id="cmd-ssh-first"))
        second = relay.execute(_ssh_envelope(request, command_id="cmd-ssh-first"))

        assert first["status"] == "accepted"
        assert first["result"]["status"] == "succeeded"
        assert second["status"] == "idempotent"
        assert second["result"]["replayed"] is True
        assert marker.read_text() == "x"
        output = first["result"]["result"]["output"]
        assert next(x["value"] for x in output if x["name"] == "profileId") == profile.profile_id
        assert next(x["value"] for x in output if x["name"] == "hostFingerprint").startswith("SHA256:")
        execution = runtime.store.require_state("tool_execution-" + first["result"]["toolExecutionId"])
        assert execution["effectClass"] == "durable_remote"
        assert execution["operatorId"] == "operator-ssh"
        assert execution["sessionId"] == "sess-ssh"
        capability = runtime.store.require_state("capability-" + grant)
        assert capability["usesConsumed"] == 1
        assert len(capability["consumptions"]) == 1
    finally:
        runtime.close()
        fixture.stop()


def test_runtime_ssh_network_preflight_denial_consumes_no_capability_use(tmp_path: Path) -> None:
    fixture = OpenSSHFixture(tmp_path / "ssh")
    remote_root = tmp_path / "remote"
    remote_root.mkdir()
    fixture.start()
    profile = _profile(fixture, remote_root, allow_loopback=False)
    runtime = create_runtime(str(tmp_path / "runtime.db"), ssh_profiles=[profile])
    try:
        grant, lease = _seed_ssh_authority(runtime, remote_root, suffix="deny", max_uses=1)
        request = _governed_ssh_request(
            profile,
            remote_root,
            ["/bin/echo", "must-not-run"],
            grant,
            lease,
            idem="ssh-runtime-deny",
        )
        receipt = runtime.command_service("operator-ssh", "sess-ssh").execute(_ssh_envelope(request))
        assert receipt["status"] == "accepted"
        assert receipt["result"]["status"] == "denied"
        execution = runtime.store.require_state("tool_execution-" + receipt["result"]["toolExecutionId"])
        assert execution["state"] == "failed"
        assert execution["dispatchBoundary"] == "not_started"
        assert execution["reservationId"] is None
        capability = runtime.store.require_state("capability-" + grant)
        assert capability["usesConsumed"] == 0
        assert capability["reservations"] == []
        assert capability["consumptions"] == []
    finally:
        runtime.close()
        fixture.stop()
