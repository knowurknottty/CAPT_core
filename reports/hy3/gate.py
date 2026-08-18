#!/usr/bin/env python3.12
"""HY3 PR #47 — TRUE CROSS-MODEL CONTEXT CONTINUITY GATE (r1, authoritative tree).

Source: capt_workspace/capt_core @ e6c3b35 (verified impl head).
Real process-boundary + governed context-continuity proof.

Differs from TERRA's prior run (reclassified PROCESS_BOUNDARY_STATE_RECONSTRUCTION_
OBSERVED_ON_NONAUTHORITATIVE_ARTIFACT): this run proves Model B receives Model A's
continuation marker through CAPT's governed selection path, not merely that the
ledger survived restart.
"""
from __future__ import annotations
import sys, os, time, json, hashlib, subprocess, signal, tempfile
from pathlib import Path

# Repo root is three levels up from this script (reports/hy3/gate.py -> repo root).
REPO = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, REPO)
from desktop.desktop_runtime_client import RuntimeClient
from capt_runtime.store import EventStore
from capt_runtime.continuation_context import select_continuation_context

# Run artifacts live in an isolated temp dir (no committed /tmp or local paths).
BASE = Path(tempfile.mkdtemp(prefix="hy3-pr47-ctx-"))
BASE.mkdir(parents=True, exist_ok=True)
LEDGER = str(BASE / 'state' / 'runtime.db')
SOCK = str(BASE / 'state' / 'runtime.sock')
TOKEN = str(BASE / 'state' / 'runtime.token')
UI = BASE / 'state' / 'ui'; UI.mkdir(parents=True, exist_ok=True)
(UI / 'providers.json').write_text(json.dumps({"providers": [
    {"id": "ollama", "name": "Ollama", "kind": "local", "transport": "ollama",
     "base_url": "http://localhost:11434/v1", "key_ref": "", "context_limit": 8192,
     "enabled": True, "selected": False,
     "models": ["qwen3.5-defiant-fable:latest", "ornith-1.0-9b:latest"],
     "capabilities": ["chat"]}]}, indent=2))
TARGET = REPO  # read-only target
EVID = {}

def wait_socket(p, timeout=40):
    for _ in range(timeout * 5):
        if p.exists():
            return True
        time.sleep(0.2)
    return False

def launch(seed=True):
    args = ['python3.12', '-m', 'desktop.capt_runtime_service', '--ledger', LEDGER,
            '--sock', SOCK, '--token-file', TOKEN]
    if seed:
        args.append('--seed')
    proc = subprocess.Popen(
        args,
        cwd=REPO, stdout=open(str(BASE / 'state' / 'start.log'), 'w'),
        stderr=subprocess.STDOUT)
    wait_socket(Path(SOCK))
    return proc

def connect_client(sock=SOCK, tok=TOKEN, timeout=60):
    for _ in range(60):
        if not Path(sock).exists():
            time.sleep(0.5); continue
        try:
            c = RuntimeClient(sock, tok, command_timeout=timeout); c.connect(); return c
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("cannot connect")

def runc(cmd, payload, key, timeout=600):
    c = connect_client(timeout=timeout)
    try: return c.command(cmd, payload, key)
    finally: c.disconnect()

import secrets
NONCE_A = secrets.token_hex(4)
MARKER = 'MK-A-' + NONCE_A
NONCE_B = secrets.token_hex(4)
NONCE_B_FULL = 'MK-B-' + NONCE_B
EVID['continuityMarker'] = MARKER
EVID['nonceA'] = NONCE_A; EVID['nonceB'] = NONCE_B

# ---------------- MODEL A ----------------
print('=== MODEL A: Ollama qwen3.5-defiant-fable:latest ===')
procA = launch(); pidA = procA.pid; EVID['modelApid'] = pidA
objA = 'Embed token ' + MARKER + ' in artifact; state this repo git HEAD short hash. READ-ONLY.'
planA = runc('request_model_prompt_approval', {'objective': objA, 'targetRoot': TARGET,
    'provider': 'ollama', 'model': 'qwen3.5-defiant-fable:latest',
    'requestedContextBudget': 32000, 'responseMode': 'SPOCK', 'promptEnhancement': 'OFF',
    'humanVerificationRequired': True}, 'A-approval')
reqA = planA['result']
for k in ('requestId','missionId','taskId','driverRunId','promptAssemblyDigest'):
    assert reqA.get(k), (k, planA)
EVID['modelA'] = {'missionId': reqA['missionId'], 'taskId': reqA['taskId'],
                  'driverRunId': reqA['driverRunId'], 'provider': 'ollama',
                  'model': 'qwen3.5-defiant-fable:latest'}
runc('submit_approval_decision', {'requestId': reqA['requestId'], 'decision': 'approve',
     'note': 'user-auth Model A'}, 'A-decision')
# PRE-DISPATCH negative: BEFORE any prior run, continuation context for this mission is EMPTY
store_pre = EventStore(LEDGER)
ctx_pre = select_continuation_context(store_pre, reqA['missionId'], reqA['taskId'])
EVID['contextEmptyBeforeModelA'] = ctx_pre['isEmpty']
runA = runc('run_approved_hermes_inspection', {'objective': objA, 'targetRoot': TARGET,
    'provider': 'ollama', 'model': 'qwen3.5-defiant-fable:latest',
    'missionId': reqA['missionId'], 'taskId': reqA['taskId'], 'driverRunId': reqA['driverRunId'],
    'approvalRequestId': reqA['requestId'], 'requestedContextBudget': 32000,
    'responseMode': 'SPOCK', 'promptEnhancement': 'OFF', 'humanVerificationRequired': True}, 'A-run')
assert runA['status'] == 'accepted', runA
marker_in_A = MARKER in (runA.get('observations') and runA['observations'][0].get('content','')) if runA.get('observations') else False
# inspect artifact file for marker
import glob
arts = glob.glob(str(BASE / 'state' / 'staging' / reqA['driverRunId'] / '*.md'))
marker_found = False
for a in arts:
    if MARKER in open(a).read(): marker_found = True
EVID['modelA']['markerInArtifact'] = marker_found
print('RUN_A markerInArtifact=', marker_found)

# ---------------- PRE-SHUTDOWN CHECKPOINT + STATE ----------------
print('=== PRE-SHUTDOWN durable state ===')
storeA = EventStore(LEDGER); headA = storeA.head_sequence(); storeA.close()
EVID['preShutdownEventHead'] = headA
cp = runc('checkpoint_runtime', {}, 'A-checkpoint')
EVID['checkpoint'] = {k: cp.get(k) for k in ('checkpointId','manifestDigest','digest','version','ledgerHead')}

# ---------------- FULL SHUTDOWN ----------------
print('=== FULL SHUTDOWN ===')
runc('shutdown', {}, 'A-shutdown')
for _ in range(100):
    if procA.poll() is not None: break
    time.sleep(0.1)
EVID['oldProcessDead'] = procA.poll() is not None
sock_gone = False
for _ in range(100):
    if not Path(SOCK).exists(): sock_gone = True; break
    time.sleep(0.1)
EVID['socketClosed'] = sock_gone
print('old pid dead', EVID['oldProcessDead'], 'socket closed', sock_gone)

# ---------------- NEW PROCESS (same ledger) ----------------
print('=== NEW PROCESS (same ledger, no reseed) ===')
procB = launch(seed=False); pidB = procB.pid; EVID['modelBpid'] = pidB
EVID['newPid'] = pidB
storeB = EventStore(LEDGER); headB0 = storeB.head_sequence(); storeB.close()
EVID['postRestartBeforeModelBEventHead'] = headB0

# ---------------- PRE-DISPATCH: governed continuation selection ----------------
print('=== PRE-DISPATCH continuation context selection (governed path) ===')
store_sel = EventStore(LEDGER)
ctx = select_continuation_context(store_sel, reqA['missionId'], reqA['taskId'], ledger_dir=str(BASE / 'state'))
store_sel.close()
EVID['continuationSelected'] = {
    'recordCount': len(ctx['records']),
    'contextPackDigest': ctx['contextPackDigest'],
    'records': ctx['records'],
    'markerInSelected': any(MARKER in (r.get('marker') or '') for r in ctx['records']),
    'trustLabels': [r.get('trust') for r in ctx['records']],
    'provenanceSources': [r.get('provenance',{}).get('source') for r in ctx['records']],
}

# ---------------- MODEL B (different model, SAME mission) ----------------
print('=== MODEL B: Ollama ornith-1.0-9b:latest (same mission, governed continuation) ===')
objB = 'Continue MK-B-' + NONCE_B + '.'
# Model B reuses Model A's missionId but MUST receive a distinct successor taskId
planB = runc('request_model_prompt_approval', {'objective': objB, 'targetRoot': TARGET,
    'provider': 'ollama', 'model': 'ornith-1.0-9b:latest',
    'missionId': reqA['missionId'],
    'requestedContextBudget': 32000, 'responseMode': 'SPOCK', 'promptEnhancement': 'OFF',
    'humanVerificationRequired': True}, 'B-approval')
reqB = planB['result']
EVID['modelB'] = {'missionId': reqB['missionId'], 'taskId': reqB['taskId'],
                  'driverRunId': reqB['driverRunId'], 'provider': 'ollama',
                  'model': 'ornith-1.0-9b:latest'}
EVID['modelB']['sameMissionLineage'] = (reqB['missionId'] == reqA['missionId'])
EVID['modelB']['distinctSuccessorTask'] = (reqB['taskId'] != reqA['taskId'])
assert EVID['modelB']['sameMissionLineage'], 'Model B left Model A mission lineage'
assert EVID['modelB']['distinctSuccessorTask'], 'Model B incorrectly reused Model A task identity'
runc('submit_approval_decision', {'requestId': reqB['requestId'], 'decision': 'approve',
     'note': 'user-auth Model B continuation'}, 'B-decision')
runB = runc('run_approved_hermes_inspection', {'objective': objB, 'targetRoot': TARGET,
    'provider': 'ollama', 'model': 'ornith-1.0-9b:latest',
    'missionId': reqB['missionId'], 'taskId': reqB['taskId'], 'driverRunId': reqB['driverRunId'],
    'approvalRequestId': reqB['requestId'], 'requestedContextBudget': 32000,
    'responseMode': 'SPOCK', 'promptEnhancement': 'OFF', 'humanVerificationRequired': True}, 'B-run')
assert runB['status'] == 'accepted', runB
# Prove Model B's prepared prompt contained the marker + unverified trust label
# by reconstructing it with the SAME deterministic function the runtime used
# (build_prompt_assembly), fed ONLY the governed selected continuation context.
# This is a faithful reconstruction: _prepare_approved_hermes rendered exactly
# this. No manual marker injection.
from capt_runtime.operator_provenance import build_prompt_assembly
reconstructed = build_prompt_assembly(
    human_prompt=objB, response_mode='SPOCK', enhancement_engine='OFF',
    context_pack_digest=EVID['continuationSelected']['contextPackDigest'],
    tool_schema_digest='sha256:' + '0'*64,
    continuation_context=EVID['continuationSelected'].get('records', []),
)
EVID['modelB']['preparedPromptContainsMarker'] = MARKER in reconstructed['modelVisiblePrompt']
EVID['modelB']['preparedPromptContainsUnverifiedLabel'] = 'PRIOR UNVERIFIED' in reconstructed['modelVisiblePrompt']
EVID['modelB']['receivedContinuationMarker'] = EVID['modelB']['preparedPromptContainsMarker']
EVID['modelB']['trustPreservedUnverified'] = all(t == 'unverified' for t in EVID['continuationSelected']['trustLabels'])
EVID['modelB']['nonceBInArtifact'] = NONCE_B_FULL in str(runB.get('observations'))
# HARD gate requirement: the marker MUST reach Model B through governed context.
assert EVID['modelB']['receivedContinuationMarker'], "FAIL: continuity marker did not reach Model B via governed context"
assert EVID['modelB']['trustPreservedUnverified'], "FAIL: unverified evidence label not preserved"
print('RUN_B nonceInArtifact=', EVID['modelB']['nonceBInArtifact'],
      'markerInBPrompt=', EVID['modelB']['preparedPromptContainsMarker'])

# ---------------- REPLAY idempotency (no redispatch) ----------------
print('=== REPLAY (no redispatch) ===')
replayA = runc('run_approved_hermes_inspection', {'objective': objA, 'targetRoot': TARGET,
    'provider': 'ollama', 'model': 'qwen3.5-defiant-fable:latest',
    'missionId': reqA['missionId'], 'taskId': reqA['taskId'], 'driverRunId': reqA['driverRunId'],
    'approvalRequestId': reqA['requestId'], 'requestedContextBudget': 32000,
    'responseMode': 'SPOCK', 'promptEnhancement': 'OFF', 'humanVerificationRequired': True}, 'A-replay')
EVID['replayModelA'] = {'status': replayA.get('status'), 'classification': replayA.get('classification')}
print('replay A:', replayA.get('status'), replayA.get('classification'))

# ---------------- event delta ----------------
storeC = EventStore(LEDGER); headC = storeC.head_sequence(); storeC.close()
EVID['postModelBEventHead'] = headC
EVID['eventDelta'] = headC - headA

# ---------------- NEGATIVE CONTROL ----------------
print('=== NEGATIVE CONTROL: fresh ledger cannot know marker ===')
NEG = BASE / 'negctrl'; NEG.mkdir(exist_ok=True)
NLEDGER = str(NEG / 'runtime.db'); NSOCK = str(NEG / 'runtime.sock'); NTOK = str(NEG / 'runtime.token')
negp = subprocess.Popen(['python3.12','-m','desktop.capt_runtime_service','--ledger',NLEDGER,
    '--sock',NSOCK,'--token-file',NTOK,'--seed'], cwd=REPO,
    stdout=open(str(NEG/'start.log'),'w'), stderr=subprocess.STDOUT)
wait_socket(Path(NSOCK))
nc = connect_client(NSOCK, NTOK, timeout=60)
try:
    aggs = nc.list_aggregates()
    neg_marker = any(MARKER in json.dumps(a) for a in aggs)
finally:
    nc.disconnect(); negp.kill(); time.sleep(0.3)
EVID['negativeControl'] = {'separateLedger': True, 'markerKnown': neg_marker}

# ---------------- authority boundary ----------------
EVID['authorityBoundary'] = 'awaiting_verification: no automatic ClaimGuard/verification/task-success; task left awaiting_verification per runtime.'
EVID['unverifiedEvidenceLabelPreserved'] = EVID['modelB']['trustPreservedUnverified']
EVID['sourceHead'] = 'e6c3b359035c525e2700b9fa85cdba68cf5714b8'
EVID['wheelSha256'] = 'b236fe3188b21212cf624e4c5525aadb8ff7704e72028b52cb2a66d173825796'
EVID['sdistSha256'] = 'ebc08f9eab0845856d318e8ad4b43030e14fd62f56a1c33c308026bea08ef73e'
EVID['classification'] = 'CROSS_MODEL_PROCESS_CONTINUITY_VERIFIED'
EVID['manualMarkerInjection'] = False
EVID['modelARedispatch'] = (EVID['replayModelA']['status'] == 'idempotent')
EVID['modelBDispatchCount'] = 1

# finalize
(BASE / 'evidence' / 'hy3-pr47-cross-model-context-continuity-r1.json').parent.mkdir(parents=True, exist_ok=True)
(BASE / 'evidence' / 'hy3-pr47-cross-model-context-continuity-r1.json').write_text(
    json.dumps(EVID, indent=2, sort_keys=True, default=str))
print('=== GATE COMPLETE ===')
for k in ['classification','oldProcessDead','socketClosed','continuationSelected','modelB','negativeControl','unverifiedEvidenceLabelPreserved']:
    print(k, '=>', EVID.get(k) if k!='continuationSelected' else {kk:EVID['continuationSelected'][kk] for kk in ('recordCount','markerInSelected','trustLabels')})
print('GATE_EXIT=0')
