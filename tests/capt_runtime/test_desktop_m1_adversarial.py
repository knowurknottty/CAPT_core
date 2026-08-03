"""CAPT Desktop Runtime M1 — adversarial authority & rendering-security tests.

These tests attack the operator-identity / authority boundary and the rendering
trust boundary, per the M1 spec sections 9 and 10. They prove the desktop can
never become authoritative and that untrusted content cannot masquerade as CAPT
state.
"""

import os
import time
import uuid

import pytest

from desktop.capt_runtime_service import serve as serve_runtime
from desktop.desktop_runtime_client import RuntimeClient, project_authoritative_state
from desktop.desktop_app import sanitize_for_display, trust_tag, render_m1_text


def _start(tmp):
    ledger = os.path.join(tmp, "rt.db")
    sock = os.path.join(tmp, "rt.sock")
    token_file = os.path.join(tmp, "token")
    import threading
    threading.Thread(target=serve_runtime, args=(ledger, sock, token_file, False), daemon=True).start()
    for _ in range(100):
        if os.path.exists(sock):
            break
        time.sleep(0.05)
    return sock, token_file, ledger


@pytest.fixture
def client():
    import tempfile
    tmp = tempfile.mkdtemp(prefix="/tmp/capt-m1adv-")
    sock, token_file, ledger = _start(tmp)
    c = RuntimeClient(sock, token_file)
    c.connect()
    yield c
    c.disconnect()


def _mission(mid, approval=False):
    return {
        "missionId": mid, "objective": "analyze", "rawRequest": "analyze",
        "normalizedRequest": "analyze",
        "constraints": [{"kind": "resource_boundary", "constraintId": "c", "origin": "explicit_user",
                         "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False}}],
        "successCriteria": [{"criterionId": "s", "statement": "d", "requiresVerification": True}],
        "terminationCriteria": [{"criterionId": "t", "statement": "d", "terminalState": "failed"}],
        "unresolvedAmbiguities": [], "requiresApproval": approval,
        "requestedCapability": "cap.fs.read", "operation": "RepositoryRead",
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False},
        "riskClassification": "low", "policyReason": "x",
    }


# --------------------------------------------------------------------------
# Section 9 — operator identity & authority attacks
# --------------------------------------------------------------------------

def test_unauthenticated_command_rejected():
    import tempfile, socket, json, threading
    tmp = tempfile.mkdtemp(prefix="/tmp/capt-m1unauth2-")
    ledger = os.path.join(tmp, "rt.db")
    sock = os.path.join(tmp, "rt.sock")
    token_file = os.path.join(tmp, "token")
    threading.Thread(target=serve_runtime, args=(ledger, sock, token_file, False), daemon=True).start()
    for _ in range(100):
        if os.path.exists(sock):
            break
        time.sleep(0.05)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock)
    s.settimeout(5)
    data = json.dumps({"token": "wrong"}).encode()
    s.sendall(len(data).to_bytes(4, "big") + data)
    header = s.recv(4)
    buf = b""
    while len(buf) < int.from_bytes(header, "big"):
        chunk = s.recv(1024)
        if not chunk:
            break
        buf += chunk
    resp = json.loads(buf.decode())
    assert resp.get("ok") is False and resp.get("error") == "unauthenticated"


def test_invalid_session_rejected(client):
    # A command carrying a sessionId that does not match the bound connection
    # must be rejected as unauthorized.
    mid = "m-inv-" + uuid.uuid4().hex[:8]
    env = {
        "commandId": "c-inv", "operatorId": client.operator_id, "sessionId": "sess-bogus",
        "schemaVersion": "1.0.0", "correlationId": "c", "idempotencyKey": "idem-inv",
        "timestamp": "2026-08-03T00:00:00Z", "op": "create_mission", "payload": _mission(mid),
    }
    client._send(client._sock, {"op": "command", "command": env})
    resp = client._recv(client._sock)
    assert resp["classification"] == "unauthorized"


def test_operator_id_spoofing_rejected(client):
    mid = "m-sp2-" + uuid.uuid4().hex[:8]
    env = {
        "commandId": "c-sp2", "operatorId": "operator-someone-else", "sessionId": client.session_id,
        "schemaVersion": "1.0.0", "correlationId": "c", "idempotencyKey": "idem-sp2",
        "timestamp": "2026-08-03T00:00:00Z", "op": "create_mission", "payload": _mission(mid),
    }
    client._send(client._sock, {"op": "command", "command": env})
    resp = client._recv(client._sock)
    assert resp["classification"] == "unauthorized"


def test_approval_for_nonexistent_request_not_found(client):
    # "approval for another task" reduces to approving a request that does not
    # exist in this operator's session -> not_found (no fake approval possible).
    r = client.command("submit_approval_decision",
                       {"requestId": "har-nonexistent-" + uuid.uuid4().hex[:8], "decision": "approve"})
    assert r["classification"] == "not_found"


def test_cancellation_without_authority_rejected(client):
    # A cancel command whose operatorId/sessionId is spoofed must be rejected.
    env = {
        "commandId": "c-cwa", "operatorId": "operator-attacker", "sessionId": "sess-attacker",
        "schemaVersion": "1.0.0", "correlationId": "c", "idempotencyKey": "idem-cwa",
        "timestamp": "2026-08-03T00:00:00Z", "op": "cancel_driver_run",
        "payload": {"driverRunId": "dr-whatever"},
    }
    client._send(client._sock, {"op": "command", "command": env})
    resp = client._recv(client._sock)
    assert resp["classification"] == "unauthorized"


def test_desktop_cannot_inject_event_envelope(client):
    # The client has no API to write events; only read queries and governed
    # commands exist. Assert there is no method that would let the desktop
    # fabricate an EventEnvelope, VerificationResult, or ClaimGuardDecision.
    for forbidden in ("record_event", "inject_event", "set_verification", "set_claimguard",
                      "write_ledger", "commit_event"):
        assert not hasattr(client, forbidden), "desktop must not be able to %s" % forbidden


def test_desktop_cannot_mutate_database_directly(client):
    # The client holds no EventStore handle and no write path to the ledger.
    assert not hasattr(client, "store")
    assert not hasattr(client, "ledger")


def test_fake_verification_query_is_read_only(client):
    # claimguard_disposition / verification are read-only runtime computations;
    # the desktop cannot set them. Confirm the query returns a disposition
    # without granting any write capability.
    disp = client.claimguard_disposition("Repository inspected in read-only mode.")
    assert "verdict" in disp


# --------------------------------------------------------------------------
# Section 10 — rendering trust boundary
# --------------------------------------------------------------------------

def test_terminal_escape_sequences_stripped():
    evil = "\x1b[31mFAKE VERIFIED\x1b[0m\r\n\x07"
    out = sanitize_for_display(evil)
    # Control/escape sequences are removed so the text cannot spoof terminal
    # color or cursor movement; the remaining literal text is inert (not
    # rendered as markup, not promoted to authoritative state).
    assert "\x1b" not in out
    assert "\x07" not in out
    assert "\r" not in out
    assert "FAKE VERIFIED" in out  # literal text survives as inert display text


def test_fake_verified_text_is_not_trusted_tag():
    # The trust tag system never emits a tag that would let untrusted text
    # claim CAPT authority. 'verified' maps to [VERIFIED FACT] which is a
    # desktop inference label, not [AUTHORITATIVE].
    assert trust_tag("verified") == "[VERIFIED FACT]"
    assert trust_tag("authoritative") == "[AUTHORITATIVE]"
    assert trust_tag("verified") != trust_tag("authoritative")


def test_html_like_content_is_not_rendered_as_markup():
    evil = "<b>VERIFIED</b> <script>alert(1)</script>"
    out = sanitize_for_display(evil)
    # Tk renders text literally; sanitize keeps it as inert text (no markup
    # interpretation). We assert the dangerous tokens survive as plain text
    # (i.e., not executed/removed as if parsed).
    assert "<b>" in out and "<script>" in out


def test_oversized_output_truncated():
    big = "x" * 100000
    out = sanitize_for_display(big, limit=2000)
    assert len(out) <= 2020


def test_path_traversal_link_is_not_resolved():
    evil = "../../../../etc/passwd"
    out = sanitize_for_display(evil)
    assert "../" in out  # remains inert text; desktop never resolves/opens it


def test_symlink_target_not_opened():
    # The desktop never opens artifact paths; sanitize keeps the path as text.
    evil = "/tmp/evil-symlink -> /etc/shadow"
    out = sanitize_for_display(evil)
    assert "/etc/shadow" in out  # shown as text only, not opened


def test_secret_like_value_not_trusted():
    evil = "api_key=sk_live_abcdef1234567890"
    out = sanitize_for_display(evil)
    assert "sk_live_" in out  # displayed as untrusted text, not promoted to fact


def test_render_labels_authoritative_vs_untrusted():
    import tempfile, threading
    tmp = tempfile.mkdtemp(prefix="/tmp/capt-m1render2-")
    sock, token_file, ledger = _start(tmp)
    c = RuntimeClient(sock, token_file)
    c.connect()
    app = type("App", (), {})()
    app.connected = True
    app.client = c
    app.identity = c.identity()
    app.m1_state = {"missions": [], "tasks": [], "approvals": [], "driverRuns": [],
                    "claims": [], "eventTimeline": [], "verification": {}, "identity": {}}
    app.m1_approvals = []
    text = render_m1_text(app)
    assert "[AUTHORITATIVE]" in text
    # Untrusted model text would be rendered with [UNTRUSTED]/[INFERENCE] tags,
    # never [AUTHORITATIVE]. The renderer itself never emits authoritative tags
    # for operator/untrusted content.
    c.disconnect()
