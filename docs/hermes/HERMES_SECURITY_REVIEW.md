# Hermes Security Review

Scope: `capt_runtime/drivers/hermes.py` and the CAPT-side handling of its output.

## Threat model

Hermes is a large, network-capable, model-driven agent whose behaviour is not
deterministic and whose prompt may be influenced by content in the target
repository. It is treated as hostile-by-default.

## Findings and mitigations

| # | Threat | Mitigation | Test |
|---|---|---|---|
| 1 | Command injection via the prompt | `shell=False`, explicit argv list; the prompt is a single argv element and is never interpolated into a shell | code review + `argvShape` recorded in diagnostics |
| 2 | Credential exfiltration through the environment | `minimal_env()` allow-list; names containing TOKEN/SECRET/PASSWORD/APIKEY/API_KEY/PRIVATE_KEY/CREDENTIAL/SESSION_KEY/AUTH dropped; explicit credential-shaped extras raise | `test_minimal_env_excludes_credentials`, `test_minimal_env_refuses_credential_shaped_extra` |
| 3 | Context over-disclosure | prompt derived from the ContextSlice alone; 8 governance tokens asserted absent | `test_prompt_derives_only_from_context_slice` |
| 4 | Forged authoritative CAPT state | `reject_forged_authority()` pre-observation + `capt_runtime.ingestion` structural rejection | `test_forged_authoritative_output_rejected` (6 cases) |
| 5 | Driver identity spoofing | descriptor digest bound at registration; `observedBy` must equal the registered driver id | `test_registry_rejects_hermes_identity_spoofing`, frozen `test_driver_impersonation_rejected` |
| 6 | Path traversal / symlink escape | artifact path resolved with `os.path.realpath` and required to be inside the staging root | frozen `test_symlink_traversal_rejected`, `test_artifact_writing_allowed_only_in_staging` |
| 7 | Artifact substitution | CAPT recomputes the SHA-256 and compares to the claimed digest | frozen `test_artifact_substitution_rejected` |
| 8 | Repository mutation | `writesAllowed: false`; write-capable slice refused; tree digest compared before/after | `test_write_capable_slice_refused`, `test_real_hermes_read_only_governed_run` |
| 9 | Capability escalation | `verify_lease` re-run immediately before dispatch; write ops rejected structurally first | `test_write_operation_rejected_before_hermes_is_contacted`, expired/revoked/wrong-driver tests |
| 10 | Runaway process / resource exhaustion | wall-clock budget from the ContextSlice; `start_new_session=True` then SIGKILL of the whole process group | `test_timeout_budget_fails_closed` |
| 11 | Duplicate execution | `driverRunId` single-use at the driver; replay of a terminal run refused | `test_duplicate_run_id_rejected_at_driver`, frozen replay tests |
| 12 | Network egress | `networkPolicy.egressAllowed: false`; toolset limited to `terminal` — web/browser/delegation toolsets not loaded | ContextSlice assertion in the e2e trace |
| 13 | User-config influence on a governed run | `--safe-mode` (sets `ignore_rules` and `ignore_user_config`) | invocation recorded in diagnostics |
| 14 | Silent failure reported as success | every failure path raises; no fallback, no synthesised observation | `test_missing_hermes_executable_raises_not_fabricates`, `test_reconcile_unknown_run_reports_unknown_not_success` |
| 15 | Secrets in source | ruff `S105/S106/S107/S608` clean; no credential literal in the module | command 9 in the conformance report |

## Residual risk (accepted, documented)

* **Per-tool-call activity inside the Hermes loop is not intercepted.** Hermes
  runs with the `terminal` tool available and could, in principle, execute a read
  command outside the ContextSlice's declared paths, because the OS-level cwd pin
  and the prompt constraint are not a kernel-enforced sandbox. What CAPT does
  guarantee is detection of any *effect* on the target repository (digest
  comparison) and refusal of any artifact outside staging. A hard guarantee would
  require an OS sandbox (seatbelt/namespaces) or Mode B interception; neither is
  in scope here and neither is claimed.
* **Prompt injection from repository content** could steer the Hermes analysis.
  The blast radius is bounded to the observation text, which is untrusted, is
  never promoted without CAPT verification, and cannot create authoritative
  state. Forged-authority scanning is the specific mitigation.
* The `~/.hermes/plugins/capt-solo/` plugin is broken against the authoritative
  repository and registers no tools. It is unused by this integration but remains
  installed and enabled in the user's Hermes profile.
