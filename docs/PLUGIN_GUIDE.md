# CAPT Solo Plugin Guide

**Use CAPT from Hermes through stable, public-only tools.**

The Hermes plugin is the integration boundary between Hermes and CAPT Solo. It calls supported domain APIs and does not expose raw SQL or internal state.

## Start here

In Hermes, ask for a CAPT action in plain language, for example:

```text
Store this release decision in the project namespace with high confidence.
```

or:

```text
Begin a CAPT transaction for publishing this skill, validate the prerequisites, and commit only if they pass.
```

The plugin maps those requests to named `capt_*` tools.

## What the plugin provides

The public tool surface is grouped into four practical areas:

### Memory and continuity

Store, search, retrieve, organize, export, and restore durable local memory.

Common tools:

- `capt_store_memory`
- `capt_search_memory`
- `capt_get_memory`
- `capt_export_project`
- `capt_import_project`
- `capt_get_restart_context`

### Transactions and recovery

Wrap state-changing work in append-only transactions with receipts and recovery state.

Common tools:

- `capt_begin_transaction`
- `capt_commit_transaction`
- `capt_abort_transaction`
- `capt_session_checkpoint`
- `capt_session_resume`
- `capt_session_close`

### Skills and governed packages

Generate, validate, review, publish, inspect, and install proof-governed skills and Knowledge Bubbles.

Common tools:

- `capt_generate_skill`
- `capt_validate_skill`
- `capt_publish_skill`
- `capt_build_bubble`
- `capt_validate_bubble`
- `capt_install_bubble`
- `capt_export_bubble`

### Claims and proof

Inspect evidence and prevent unsupported completion claims.

Common tools:

- `capt_query_capability`
- `capt_verify_claim`
- `capt_inspect_proof`

## Safety boundaries

The plugin is intentionally narrow:

- public CAPT tools only
- no raw SQL access
- no direct internal-state mutation
- no anonymous publication
- no automatic trust for imported packages
- no verified claim without sufficient proof
- no required remote execution

Knowledge Bubbles enter quarantine before approval. Secret patterns and unsafe permissions can block validation.

## Full public tool inventory

### Memory, context, sessions, and procedures

```text
capt_store_memory
capt_search_memory
capt_get_memory
capt_begin_transaction
capt_commit_transaction
capt_abort_transaction
capt_send_message
capt_health
capt_export_project
capt_import_project
capt_build_context
capt_explain_context
capt_add_memory_relation
capt_detect_memory_conflicts
capt_review_memory_conflicts
capt_compress_memory
capt_memory_pipeline_status
capt_session_begin
capt_session_checkpoint
capt_session_resume
capt_session_status
capt_session_consolidate
capt_session_close
capt_promote_memory
capt_archive_memory
capt_pin_memory
capt_explain_memory_lifecycle
capt_create_procedure
capt_get_procedure
capt_record_procedure_run
capt_find_procedures
capt_add_prospective_memory
capt_list_pending_intents
capt_resolve_intent
capt_record_retrieval_feedback
capt_get_restart_context
```

### Foundry and proof

```text
capt_generate_skill
capt_validate_skill
capt_publish_skill
capt_query_capability
capt_verify_claim
capt_build_bubble
capt_validate_bubble
capt_install_bubble
capt_export_bubble
capt_inspect_proof
```

The repository may add new additive tools over time. Treat the runtime and boundary tests as authoritative for the exact current count.

## Typical workflows

### Save a reusable decision

```text
Use CAPT to store this architecture decision in the project namespace, tag it "ADR", and record me as the provenance.
```

### Publish a skill safely

```text
Generate a CAPT skill from procedure proc-123, validate it, submit it for review, and do not publish unless the proof requirements are satisfied.
```

### Verify a claim

```text
Use ClaimGuard to verify the claim "the release is ready" against the release-verification capability.
```

### Import a governed package

```text
Import this Knowledge Bubble into quarantine, validate its manifest before payload approval, and report any blocked permissions or secret patterns.
```

## Implemented and reserved surfaces

### Implemented

- stable public memory, transaction, context, session, and procedure tools
- ClaimGuard integration
- capability and proof inspection
- skill generation, validation, and publication
- Knowledge Bubble build, validation, installation, and export

### Reserved or experimental

- plugin-level workflow composition and verification
- signed Knowledge Bubble installation
- remote execution

A reserved seam is not an implementation claim.

## Verification

Use the repository verification commands before relying on a local installation:

```bash
./verify.sh
./doctor.sh
python verify_runtime.py
```

Boundary and plugin tests verify the exported tool surface and major Foundry flows.

## Related documentation

- [Quickstart](../README.md)
- [API Reference](API.md)
- [Skill Guide](SKILL_GUIDE.md)
- [Security Boundaries](SECURITY.md)
