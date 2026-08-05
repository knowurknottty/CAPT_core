#!/usr/bin/env python3
"""Adversarial authority-matrix battery against the INSTALLED CAPT harness."""
import socket, json, pathlib, time, hashlib, uuid

SOCK = "/tmp/capt-release-state/rt.sock"  # REDACTED
TOKEN = pathlib.Path("/tmp/capt-release-state/token").read_text().strip()  # REDACTED

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(60)
s.connect(SOCK)

def send(p):
    s.sendall(len(json.dumps(p).encode()).to_bytes(4, "big") + json.dumps(p).encode())

def recv():
    h = s.recv(4)
    if not h:
        return {"_closed": True}
    n = int.from_bytes(h, "big")
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            return {"_closed": True}
        b += c
    return json.loads(b)

send({"token": TOKEN})
auth = recv()
print("AUTH_OK operator=%s session=%s" % (auth["operatorId"], auth["sessionId"]))
BOUND_OP = auth["operatorId"]
BOUND_SESS = auth["sessionId"]

def head():
    send({"op": "identity"})
    r = recv()
    if not isinstance(r, dict) or "result" not in r:
        raise RuntimeError("identity query failed: %r" % (r,))
    return r["result"]["headSequence"]

def env(op_, payload_, key_, **over):
    e = {
        "commandId": "cmd-" + hashlib.sha256((op_ + json.dumps(payload_, sort_keys=True) + key_).encode()).hexdigest()[:16],
        "operatorId": BOUND_OP, "sessionId": BOUND_SESS, "schemaVersion": "1.0.0",
        "correlationId": "corr-" + uuid.uuid4().hex, "idempotencyKey": key_,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "op": op_, "payload": payload_,
    }
    e.update(over)
    return e

def probe(label, cmd):
    before = head()
    send({"op": "command", "command": cmd})
    r = recv()
    after = head()
    if not isinstance(r, dict):
        print("CASE %-28s RAW=%r head %d->%d" % (label, r, before, after))
        return r, before, after
    status = r.get("status")
    cls = r.get("classification")
    det = (r.get("detail") or (r.get("error") or {}).get("code", "") or "")[:70]
    print("CASE %-28s status=%-12s class=%-22s head %d->%d  %s" % (label, status, cls, before, after, det))
    return r, before, after

probe("forged_operator", env("checkpoint_runtime", {}, "adv-op", operatorId="operator-evil"))
probe("forged_session", env("checkpoint_runtime", {}, "adv-sess", sessionId="sess-deadbeefcafe"))
probe("unsupported_schema", env("checkpoint_runtime", {}, "adv-schema", schemaVersion="9.9.9"))
probe("unsupported_op", env("run_unknown_operation", {}, "adv-op2"))
probe("missing_field", {"operatorId": BOUND_OP, "sessionId": BOUND_SESS, "schemaVersion": "1.0.0", "op": "checkpoint_runtime", "payload": {}, "idempotencyKey": "adv-missing"})
probe("forged_shutdown", env("shutdown", {}, "adv-shutdown", sessionId="sess-deadbeefcafe"))
probe("forged_resume", env("resume_runtime", {}, "adv-resume", sessionId="sess-deadbeefcafe"))
p1 = {"schemaVersion": "1.0.0", "missionId": "m-adv-1", "objective": "alpha",
      "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False},
      "requiresApproval": False, "constraints": [], "successCriteria": [],
      "terminationCriteria": [], "requestedCapability": "cap.fs.read",
      "resource": "/tmp", "operation": "ModelOperatorInspection",
      "riskClassification": "low", "taskId": "m-adv-1-task-1"}
probe("idempotent_first_ok", env("create_mission", p1, "adv-idem-1"))
p2 = dict(p1); p2["objective"] = "beta"
probe("conflicting_payload", env("create_mission", p2, "adv-idem-1"))
send({"op": "identity"})
ident = recv()["result"]
print("HEALTHY_AFTER_ADVERSARIAL head=%d integrity=%s" % (ident["headSequence"], ident["integrity"]))
s.close()
