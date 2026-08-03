# Hermes Model-Turn Ownership Trace

Run: `dr-hermes-1` · Evidence: `artifacts/hermes-integration/e2e_proof_run.json`
Reproduce: `python3 tests/capt_runtime/hermes_e2e_proof.py`

## 1. Who owns what

This is the precise ownership statement. It is deliberately narrower than
"CAPT intercepts every model call", because that is not what Mode A does.

| Concern | Owner | Enforced by |
|---|---|---|
| Whether a Hermes process runs at all | **CAPT** | `DriverHost.dispatch` after `verify_lease` |
| Which capability the run holds | **CAPT** | capability lease, revalidated pre-dispatch |
| Which paths are readable | **CAPT** | `ContextSlice.filesystemPolicy`, cwd pinned |
| Whether writes are possible | **CAPT** | `writesAllowed: false`; write-capable slice refused |
| Network egress | **CAPT** | `networkPolicy.egressAllowed: false` |
| Wall-clock budget | **CAPT** | `budgets.maxSeconds` → subprocess timeout, SIGKILL on overrun |
| Which env vars the process sees | **CAPT** | `minimal_env()` allow-list, credential-shaped names dropped |
| The model call inside the Hermes turn | **Hermes** | Hermes' own provider path |
| Whether Hermes output becomes authoritative | **CAPT** | `ingestion` → `verification` → `ClaimGuard` |
| The staging artifact | **CAPT** | written by the adapter, never by Hermes |
| Terminal run state | **CAPT** | `DriverRunAggregate`, `reconcile` |

Hermes performs its own model turn internally. CAPT does not intercept individual
tokens or individual tool calls inside that turn. **No such claim is made.**
CAPT's authority is over the bounded delegation and over the trust promotion of
everything that comes back.

Duplicate model calls are impossible at the boundary: a `driverRunId` is
single-use in `HermesDriver.submit` (`test_duplicate_run_id_rejected_at_driver`).

Fallback cannot bypass CAPT: there is no fallback path. If the executable is
missing, `HermesDriverUnavailable` is raised. If it exits non-zero, times out, or
returns empty output, `HermesDriverFailure` is raised. The adapter never
synthesises an observation.

## 2. Recorded trace (real run)

```
HermesRuntimeIdentified       executable=/Users/knowurknot/.local/bin/hermes
                              version=Hermes Agent v0.19.1 (2026.7.30) · upstream dae5df22
                              exitCode=0
MissionAndCapabilityPathExecuted
                              eventTypes=[MissionCreated, PolicyEvaluated,
                                          CapabilityGranted, CapabilityLeaseActivated,
                                          TaskCreated, TaskTransitioned ×3]
                              headSequence=8  checkpointId=cp-m0a-001
DriverRegistered              driverId=hermes  registered=true
TargetHashedBefore            sha256:048716dd6a66e0860189ad66f55e4dfb4c8210d54a25fcaca98352ddaf389c90
CapabilityLeaseIssued         leaseId=l-hermes-1
                              operations=[RepositoryRead, FilesystemRead,
                                          ArtifactCreate, AnalysisOnly]
ContextSliceBuilt             writesAllowed=false  egressAllowed=false
DriverWorkOrderCreated        driverRunId=dr-hermes-1
DriverRunTransitioned         state=running
CapabilityRevalidatedBeforeDispatch  ok=true
DriverInvoked                 externalRunId=hermes-pid-51294  externalPid=51294
                              exitCode=0  elapsedSeconds=11.8
                              envKeys=[CAPT_DRIVER_RUN_ID, HOME, LANG, LC_ALL,
                                       PATH, SHELL, TMPDIR, USER]
UntrustedObservationIngested  observations=1  artifacts=1  trust=untrusted
VerificationCompleted         status=verified  trust=capt_authoritative
                              checks={repositoryUnchanged: true,
                                      noGitMutation: true, artifactPresent: true}
ClaimGuardDecision            accepted=true
                              statement="Repository inspected in read-only mode."
ClaimGuardOverclaimRejected   error=ClaimRejected   ("The issue was fixed.")
TargetHashedAfter             sha256:048716…389c90  unchanged=true
Reconciled                    result=reconciled_completed
CheckpointCreated             checkpointId=cp-hermes  replayEquivalent=true
SeparateProcessRestartReplay  exitCode=0  equivalent=true
                              full_digest == replay_digest
                              sha256:b82feb61ce120acf71d420e7074d7f657b6d7a57b0b73e290f12dd5b90e5c3e1
SwapProofCompleted            bothVerified=true  bothRepoUnchanged=true
                              bothSameBoundedClaim=true
                              bothReconciledCompleted=true  artifactsDistinct=true
```

## 3. Untrusted observation actually returned by the real Hermes process

> Runtime architecture: single Python package "fixture" v0.0.1; one module
> `src/app.py` exposing a pure function `handler(event)` returning `{'ok': True}`;
> no deps, no entrypoint, no server, no build config; README only states it is a
> tiny fixture repo.
>
> OBSERVATION: The project declares no dependencies and […]

Ingested with `trust: untrusted`. Promoted to authoritative only after CAPT's own
independent verification (tree digest comparison, artifact existence + digest
match, staging-path containment).

## 4. What was proven and what was not

Proven:

* A real Hermes OS process ran (PID recorded, exit code 0, elapsed time measured).
* CAPT decided whether it ran, with what lease, over what paths, for how long.
* CAPT rejected an over-broad claim from the same path that accepted a bounded one.
* The target repository digest was byte-identical before and after.
* Restart in a separate OS process replayed to an identical digest.

Not proven, and not claimed:

* Per-model-turn interception inside the Hermes loop (that is Mode B).
* Per-tool-action capability revalidation inside the Hermes loop.
