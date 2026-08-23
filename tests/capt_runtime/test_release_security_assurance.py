import json
import subprocess
import sys
from pathlib import Path

from capt_runtime.memory.store import MemoryRecord, MemoryStore


def _record(record_id: str, memory_class: str, content: str) -> MemoryRecord:
    return MemoryRecord(
        record_id=record_id,
        memory_class=memory_class,
        owner="operator",
        source="test",
        provenance="test",
        trust="verified",
        verification_status="verified",
        sensitivity="user",
        consent="private",
        content=content,
    )


def test_memory_query_parameterizes_attacker_controlled_filters(tmp_path: Path):
    store = MemoryStore(str(tmp_path / "memory.db"))
    try:
        attacker_class = "x') OR 1=1 --"
        store.store(_record("safe", "normal", "safe-content"))
        store.store(_record("attacker", attacker_class, "attacker-content"))
        rows = store.query(classes=[attacker_class], bypass_governance=True)
        assert [row.record_id for row in rows] == ["attacker"]
        assert set(store.all_record_ids()) == {"safe", "attacker"}
    finally:
        store.close()


def test_client_safe_memory_projection_excludes_raw_content():
    secret = "private-memory-payload-never-cross-client-boundary"
    projected = _record("r1", "working", secret).to_record_dict()
    assert "content" not in projected
    assert secret not in json.dumps(projected, sort_keys=True)


def test_release_security_python_manifest_is_machine_checked():
    manifest = Path("security/profiles/capt-core-python-evidence.json")
    assert manifest.exists(), "release-security proof manifest must exist"
    raw = json.loads(manifest.read_text())
    controls = raw.get("controls", [])
    assert len(controls) == 18
    ids = [row["controlId"] for row in controls]
    assert len(ids) == len(set(ids))
    assert all(str(row.get("ref", "")).startswith("pytest:") for row in controls)


def test_security_evidence_cli_accepts_pass_manifest(tmp_path: Path):
    manifest = tmp_path / "passes.json"
    manifest.write_text(json.dumps({
        "schemaVersion": "1.0.0",
        "controls": [
            {"controlId": "VIBE2-09", "ref": "pytest:test-injection"},
            {"controlId": "VIBE2-10", "ref": "pytest:test-budget"},
        ],
    }))
    output = tmp_path / "evidence.json"
    proc = subprocess.run([
        sys.executable, "-m", "capt_runtime.security_evidence",
        "--source-sha", "abc123",
        "--verifier", "release-security-ci",
        "--pass-manifest", str(manifest),
        "--output", str(output),
    ], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    rows = json.loads(output.read_text())["evidence"]
    assert [row["controlId"] for row in rows] == ["VIBE2-09", "VIBE2-10"]


def test_manifest_refs_resolve_to_real_test_nodes():
    raw = json.loads(Path("security/profiles/capt-core-python-evidence.json").read_text())
    for row in raw["controls"]:
        ref = row["ref"]
        assert ref.startswith("pytest:")
        node = ref[len("pytest:"):]
        path_text, sep, test_name = node.partition("::")
        assert sep == "::", node
        path = Path(path_text)
        assert path.exists(), node
        assert ("def %s(" % test_name) in path.read_text(), node


def test_release_security_workflow_consumes_python_manifest_only_after_python_success():
    text = Path(".github/workflows/release-security.yml").read_text()
    assert 'if [ "$PYTHON_JOB" = "success" ]; then' in text
    assert 'args+=(--pass-manifest security/profiles/capt-core-python-evidence.json)' in text


def _state_key() -> str:
    import base64
    return base64.b64encode(b"K" * 32).decode("ascii")


def test_event_store_encrypts_authoritative_json_at_rest_and_reopens(tmp_path: Path, monkeypatch):
    from capt_runtime import commands
    from capt_runtime.services import RuntimeService
    from capt_runtime.store import EventStore

    monkeypatch.setenv("CAPT_STATE_KEY_B64", _state_key())
    db = tmp_path / "ledger" / "runtime.db"
    secret = "super-secret-objective-should-not-be-plaintext"
    store = EventStore(str(db))
    svc = RuntimeService(store)
    spec = {
        "schemaVersion": "1.0.0", "missionId": "m-secret",
        "rawRequest": secret, "normalizedRequest": secret,
        "objectives": [{"objectiveId": "o1", "statement": secret, "priority": 1}],
        "constraints": [],
        "successCriteria": [{"criterionId": "s1", "statement": "done", "requiresVerification": True}],
        "terminationCriteria": [{"criterionId": "t1", "statement": "stop", "terminalState": "failed"}],
        "unresolvedAmbiguities": [], "taskGraphId": None,
        "createdAt": "2026-08-22T00:00:00Z",
    }
    cmd = commands.command(
        command_id="cmd-secret", idempotency_key="idem-secret",
        operation_fingerprint=commands.fingerprint("create_mission", {"missionId": "m-secret"}),
        correlation_id="c", actor_id="captain", actor_kind="human",
        issued_at="2026-08-22T00:00:00Z",
    )
    svc.create_mission(spec, cmd)
    store.close()
    assert secret.encode() not in db.read_bytes()

    reopened = EventStore(str(db))
    try:
        state = reopened.load_state("mission-m-secret")
        assert state is not None
        assert state["missionId"] == "m-secret"
        assert state["state"] == "draft"
        assert any(secret in json.dumps(e) for e in reopened.read_events())
    finally:
        reopened.close()


def test_memory_store_encrypts_content_at_rest_and_reopens(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CAPT_STATE_KEY_B64", _state_key())
    db = tmp_path / "memory" / "records.db"
    secret = "memory-secret-that-must-not-be-plaintext"
    store = MemoryStore(str(db))
    store.store(_record("r-secret", "project", secret))
    store.close()
    assert secret.encode() not in db.read_bytes()
    reopened = MemoryStore(str(db))
    try:
        assert reopened.get("r-secret").content == secret
    finally:
        reopened.close()


def test_memory_store_rejects_unsafe_persistence_shapes_but_preserves_untrusted_text(tmp_path: Path):
    store = MemoryStore(str(tmp_path / "memory.db"))
    try:
        with __import__("pytest").raises(ValueError, match="MEMORY_CONTENT_NUL"):
            store.store(_record("nul", "project", "bad\x00content"))
        with __import__("pytest").raises(ValueError, match="MEMORY_CONTENT_TOO_LARGE"):
            store.store(_record("huge", "project", "x" * (1024 * 1024 + 1)))
        hostile = '<script>alert("untrusted-data")</script>'
        store.store(_record("hostile", "project", hostile))
        assert store.get("hostile").content == hostile
    finally:
        store.close()


def test_all_authoritative_runtime_sqlite_files_are_private_and_repaired(tmp_path: Path):
    import os
    import stat
    from capt_runtime.memory.engine import MemoryTriggerEngine
    from capt_runtime.store import EventStore

    ledger_db = tmp_path / "state" / "runtime.db"
    event_store = EventStore(str(ledger_db))
    event_store.close()
    db = tmp_path / "state" / "memory.db"
    store = MemoryStore(str(db))
    policy_db = tmp_path / "state" / "memory-policy.db"
    engine = MemoryTriggerEngine(store, ledger_db=str(policy_db))
    engine._ledger.close()
    store.close()
    assert stat.S_IMODE(os.stat(db.parent).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(ledger_db).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(db).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(policy_db).st_mode) == 0o600

    os.chmod(ledger_db, 0o644)
    os.chmod(db, 0o644)
    os.chmod(policy_db, 0o644)
    repaired_event_store = EventStore(str(ledger_db))
    repaired_event_store.close()
    repaired_store = MemoryStore(str(db))
    repaired_engine = MemoryTriggerEngine(repaired_store, ledger_db=str(policy_db))
    try:
        assert stat.S_IMODE(os.stat(ledger_db).st_mode) == 0o600
        assert stat.S_IMODE(os.stat(db).st_mode) == 0o600
        assert stat.S_IMODE(os.stat(policy_db).st_mode) == 0o600
    finally:
        repaired_engine._ledger.close()
        repaired_store.close()


def test_authoritative_runtime_and_memory_state_encryption_release_proof(tmp_path: Path, monkeypatch):
    from capt_runtime.store import EventStore

    monkeypatch.setenv("CAPT_STATE_KEY_B64", _state_key())
    ledger = tmp_path / "runtime.db"
    memory = tmp_path / "memory.db"
    event_secret = "event-store-sensitive-rejection-detail"
    memory_secret = "memory-store-sensitive-content"

    store = EventStore(str(ledger))
    store.record_security_rejection("r1", "test", {"secret": event_secret})
    store.close()
    mem = MemoryStore(str(memory))
    mem.store(_record("m1", "project", memory_secret))
    mem.close()

    assert event_secret.encode() not in ledger.read_bytes()
    assert memory_secret.encode() not in memory.read_bytes()
    reopened_store = EventStore(str(ledger))
    reopened_mem = MemoryStore(str(memory))
    try:
        assert reopened_store.list_security_rejections()[0]["details"]["secret"] == event_secret
        assert reopened_mem.get("m1").content == memory_secret
    finally:
        reopened_store.close()
        reopened_mem.close()


def test_event_store_ciphertext_tamper_fails_closed(tmp_path: Path, monkeypatch):
    import sqlite3
    from capt_runtime import commands
    from capt_runtime.services import RuntimeService
    from capt_runtime.state_security import AtRestProtectionError
    from capt_runtime.store import EventStore

    monkeypatch.setenv("CAPT_STATE_KEY_B64", _state_key())
    db = tmp_path / "ledger.db"
    store = EventStore(str(db))
    svc = RuntimeService(store)
    spec = {
        "schemaVersion": "1.0.0", "missionId": "tamper",
        "rawRequest": "sensitive", "normalizedRequest": "sensitive",
        "objectives": [{"objectiveId": "o1", "statement": "sensitive", "priority": 1}],
        "constraints": [],
        "successCriteria": [{"criterionId": "s1", "statement": "done", "requiresVerification": True}],
        "terminationCriteria": [{"criterionId": "t1", "statement": "stop", "terminalState": "failed"}],
        "unresolvedAmbiguities": [], "taskGraphId": None,
        "createdAt": "2026-08-22T00:00:00Z",
    }
    cmd = commands.command(
        command_id="cmd-tamper", idempotency_key="idem-tamper",
        operation_fingerprint=commands.fingerprint("create_mission", {"missionId": "tamper"}),
        correlation_id="c", actor_id="captain", actor_kind="human",
        issued_at="2026-08-22T00:00:00Z",
    )
    svc.create_mission(spec, cmd)
    store.close()
    conn = sqlite3.connect(str(db))
    row = conn.execute("SELECT state_json FROM aggregates WHERE stream_id = ?", ("mission-tamper",)).fetchone()
    stored = row[0]
    replacement = stored[:-1] + ("A" if stored[-1] != "A" else "B")
    conn.execute("UPDATE aggregates SET state_json = ? WHERE stream_id = ?", (replacement, "mission-tamper"))
    conn.commit()
    conn.close()

    with __import__("pytest").raises(AtRestProtectionError, match="STATE_CIPHERTEXT_INVALID"):
        EventStore(str(db))


def test_legacy_plaintext_memory_rows_migrate_without_data_loss(tmp_path: Path, monkeypatch):
    import sqlite3
    monkeypatch.setenv("CAPT_STATE_KEY_B64", _state_key())
    db = tmp_path / "legacy-memory.db"
    seed = MemoryStore(str(db))
    seed.close()
    secret = "legacy-plaintext-memory-secret"
    conn = sqlite3.connect(str(db))
    rec = _record("legacy", "project", secret)
    conn.execute(
        """INSERT OR REPLACE INTO memory_records
        (record_id,memory_class,owner,source,provenance,trust,verification_status,
         sensitivity,consent,content,created_at,last_verified_at,expires_at,stale,
         conflict_state,downstream_use_restriction,digest)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (rec.record_id, rec.memory_class, rec.owner, rec.source, rec.provenance,
         rec.trust, rec.verification_status, rec.sensitivity, rec.consent, secret,
         rec.created_at, rec.last_verified_at, rec.expires_at, 0, None, None, rec.digest),
    )
    conn.commit()
    conn.close()
    assert secret.encode() in db.read_bytes()

    migrated = MemoryStore(str(db))
    try:
        assert migrated.get("legacy").content == secret
    finally:
        migrated.close()
    assert secret.encode() not in db.read_bytes()


def test_runtime_provider_governor_emits_durable_data_minimized_spend_alert(tmp_path, monkeypatch):
    from capt_runtime.store import EventStore
    from desktop.capt_runtime_service import _build_provider_governor

    monkeypatch.setenv("CAPT_PROVIDER_SESSION_COST_CAP_USD", "10")
    monkeypatch.setenv("CAPT_PROVIDER_SPEND_ALERT_USD", "8")
    store = EventStore(str(tmp_path / "runtime.db"))
    try:
        governor = _build_provider_governor(store)
        receipt = governor.record_usage(prompt_tokens=100, completion_tokens=50, cost_usd=8.25)
        assert receipt["costAlert"]["kind"] == "spend_threshold_crossed"
        rows = store.list_security_rejections()
        alert = next(r for r in rows if r["rejectionKind"] == "provider_spend_threshold_alert")
        assert alert["details"] == {
            "kind": "spend_threshold_crossed",
            "thresholdUsd": 8.0,
            "consumedCostUsd": 8.25,
            "maxCostUsd": 10.0,
            "consumedRequests": 1,
        }
        assert "prompt" not in json.dumps(alert).lower()
        assert "response" not in json.dumps(alert).lower()
        assert "token" not in json.dumps(alert).lower()
    finally:
        store.close()


def test_runtime_provider_governor_rejects_invalid_cost_policy(tmp_path, monkeypatch):
    from capt_runtime.store import EventStore
    from desktop.capt_runtime_service import _build_provider_governor

    monkeypatch.setenv("CAPT_PROVIDER_SESSION_COST_CAP_USD", "10")
    monkeypatch.setenv("CAPT_PROVIDER_SPEND_ALERT_USD", "10")
    store = EventStore(str(tmp_path / "runtime.db"))
    try:
        with __import__("pytest").raises(ValueError, match="COST_ALERT_THRESHOLD_INVALID"):
            _build_provider_governor(store)
    finally:
        store.close()


def test_openrouter_billing_assurance_requires_real_non_admin_hard_cap(tmp_path):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from capt_runtime.billing_assurance import verify_openrouter_key_limit

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            assert self.headers.get("Authorization") == "Bearer test-inference-key"
            body = json.dumps({"data": {
                "limit": 25.0, "limit_remaining": 19.5,
                "is_management_key": False, "is_provisioning_key": False,
            }}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, format, *args):  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        receipt = verify_openrouter_key_limit(
            "test-inference-key", source_sha="abc123",
            endpoint=f"http://127.0.0.1:{server.server_port}/api/v1/key",
        )
        assert receipt == {
            "schemaVersion": "1.0.0", "provider": "openrouter",
            "sourceSha": "abc123", "hardCapUsd": 25.0,
            "limitRemainingUsd": 19.5, "managementCredential": False,
            "provisioningCredential": False,
        }
        assert "test-inference-key" not in json.dumps(receipt)
    finally:
        server.shutdown(); server.server_close()


def test_openrouter_billing_assurance_rejects_missing_cap_and_management_key():
    from capt_runtime.billing_assurance import BillingAssuranceError, validate_openrouter_key_policy

    with __import__("pytest").raises(BillingAssuranceError, match="PROVIDER_HARD_CAP_MISSING"):
        validate_openrouter_key_policy({"limit": None, "is_management_key": False}, source_sha="abc")
    with __import__("pytest").raises(BillingAssuranceError, match="ADMIN_CREDENTIAL_NOT_ALLOWED"):
        validate_openrouter_key_policy({"limit": 10, "is_management_key": True}, source_sha="abc")


def test_release_security_attests_billing_control_only_after_live_cap_job_success():
    text = Path(".github/workflows/release-security.yml").read_text()
    assert "billing-assurance:" in text
    assert "OPENROUTER_RELEASE_KEY: ${{ secrets.OPENROUTER_RELEASE_KEY }}" in text
    assert "OPENROUTER_MANAGEMENT_KEY" not in text
    assert "needs: [python, secrets, billing-assurance]" in text
    assert 'BILLING_JOB: ${{ needs.billing-assurance.result }}' in text
    assert 'if [ "$PYTHON_JOB" = "success" ] && [ "$BILLING_JOB" = "success" ]; then' in text
    assert 'CAPT-SUP-07=openrouter:hard-key-cap+pytest:tests/capt_runtime/test_release_security_assurance.py::test_runtime_provider_governor_emits_durable_data_minimized_spend_alert' in text
    assert 'name: capt-billing-assurance' in text
    assert 'billing-assurance/' in text


def test_memory_store_never_chmods_a_preexisting_caller_owned_parent(tmp_path):
    import os
    import stat
    parent = tmp_path / "shared-project"
    parent.mkdir(mode=0o755)
    os.chmod(parent, 0o755)
    store = MemoryStore(str(parent / "memory.db"))
    store.close()
    assert stat.S_IMODE(os.stat(parent).st_mode) == 0o755
    assert stat.S_IMODE(os.stat(parent / "memory.db").st_mode) == 0o600


def test_file_backed_store_rejects_plaintext_injected_after_migration(tmp_path, monkeypatch):
    import sqlite3
    from capt_runtime.state_security import AtRestProtectionError

    monkeypatch.setenv("CAPT_STATE_KEY_B64", _state_key())
    db = tmp_path / "memory.db"
    store = MemoryStore(str(db))
    store.store(_record("sealed", "project", "original"))
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE memory_records SET content = ? WHERE record_id = ?", ("injected-plaintext", "sealed"))
    conn.commit(); conn.close()
    try:
        with __import__("pytest").raises(AtRestProtectionError, match="STATE_PLAINTEXT_UNEXPECTED"):
            store.get("sealed")
    finally:
        store.close()


def test_file_backed_store_rejects_wrong_key_during_open(tmp_path, monkeypatch):
    import base64
    from capt_runtime.state_security import AtRestProtectionError

    key1 = base64.b64encode(b"1" * 32).decode("ascii")
    key2 = base64.b64encode(b"2" * 32).decode("ascii")
    db = tmp_path / "memory.db"
    monkeypatch.setenv("CAPT_STATE_KEY_B64", key1)
    store = MemoryStore(str(db))
    store.store(_record("sealed", "project", "sensitive"))
    store.close()
    monkeypatch.setenv("CAPT_STATE_KEY_B64", key2)
    with __import__("pytest").raises(AtRestProtectionError, match="STATE_CIPHERTEXT_INVALID"):
        MemoryStore(str(db))


def test_memory_query_returns_decrypted_content_after_at_rest_sealing(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_STATE_KEY_B64", _state_key())
    db = tmp_path / "memory-query.db"
    secret = "query-visible-plaintext-content"
    store = MemoryStore(str(db))
    try:
        store.store(_record("query-record", "project", secret))
        rows = store.query(classes=["project"], limit=10)
        assert len(rows) == 1
        assert rows[0].record_id == "query-record"
        assert rows[0].content == secret
        assert not rows[0].content.startswith("enc:v1:")
    finally:
        store.close()


def test_python38_crypto_dependency_is_bounded_to_last_supported_major():
    text = Path("pyproject.toml").read_text()
    assert "cryptography>=47.0.0,<48.0.0; python_version < '3.9'" in text
    assert "cryptography>=47.0.0; python_version >= '3.9'" in text
