# CAPT Solo v0.4 — Plugin Guide

The Hermes plugin (`capt_solo/plugin/__init__.py`) exposes CAPT Solo as stable,
public-only tools for Hermes Agent. It is the integration boundary: it calls
domain methods and never exposes raw SQL or internal state.

## Tool count: 46

### Memory (v0.1–v0.3, 36 tools)
`capt_store_memory, capt_search_memory, capt_get_memory, capt_begin_transaction,
capt_commit_transaction, capt_abort_transaction, capt_send_message, capt_health,
capt_export_project, capt_import_project, capt_build_context, capt_explain_context,
capt_add_memory_relation, capt_detect_memory_conflicts, capt_review_memory_conflicts,
capt_compress_memory, capt_memory_pipeline_status, capt_session_begin,
capt_session_checkpoint, capt_session_resume, capt_session_status,
capt_session_consolidate, capt_session_close, capt_promote_memory, capt_archive_memory,
capt_pin_memory, capt_explain_memory_lifecycle, capt_create_procedure,
capt_get_procedure, capt_record_procedure_run, capt_find_procedures,
capt_add_prospective_memory, capt_list_pending_intents, capt_resolve_intent,
capt_record_retrieval_feedback, capt_get_restart_context`

### Foundry (v0.4, 10 tools)
- `capt_generate_skill(procedure_id, name=, ...)` — create a skill candidate.
- `capt_validate_skill(skill_id)` — run 12-stage harness.
- `capt_publish_skill(skill_id, reviewer=, ...)` — approve + publish.
- `capt_query_capability(identifier)` — show capability (incl. degradations).
- `capt_verify_claim(claim_text, capability_id=)` — ClaimGuard validation.
- `capt_build_bubble(name, skills=, procedures=, proof=, ...)` — build manifest.
- `capt_validate_bubble(bubble)` — 12-step validation.
- `capt_install_bubble(bubble, approver=)` — quarantine->approve->install.
- `capt_export_bubble(skills=, procedures=, include_private=)` — selective export.
- `capt_inspect_proof(scope)` — list proof evidence for a scope.

## Implemented

- 46 stable public tools (36 legacy + 10 v0.4 foundry).
- ClaimGuard integration (`capt_verify_claim`).
- Bubble build/validate/install/export.
- Capability query with degradation surfacing.

## Experimental

- Workflow proof via plugin (planned; use CLI/API directly for now).

## Future

- `capt_compose_workflow` and `capt_verify_workflow` plugin tools.
- Signed bubble install via plugin.

## Limitations

- Plugin is local-first; no remote execution.
- `capt_publish_skill` requires a reviewer name (no anonymous publish).

## Security Boundaries

- Plugin exposes only `public_only` tools; no raw SQL, no internal state.
- ClaimGuard never reports verified without satisfied proof.
- Bubble install is quarantine-default; explicit approval required.
- Secret patterns are screened before any claim or bubble is accepted.

## Verification

- `tests/test_v04_plugin.py` (12 tests: skill gen/validate/publish, capability
  query, claim verify, bubble build/install/export, proof inspect).
- `tests/test_v04_boundary.py` (plugin tool count is 46).
- `doctor.sh` (plugin tool count is 46, plugin installed).
