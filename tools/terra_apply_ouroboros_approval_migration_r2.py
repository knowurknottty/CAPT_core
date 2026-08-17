from __future__ import annotations

import runpy
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}: {old[:180]!r}")
    p.write_text(text.replace(old, new, 1))


# Start from the previously exercised lifecycle migration. It also removes the
# unnecessary global RuntimeClient correlation change and restores command
# idempotency precedence before approval consumption.
runpy.run_path("tools/terra_apply_ouroboros_approval_migration.py", run_name="__main__")

# Human approval is now authoritative durable runtime state. New checkpoints
# must account for its stream version instead of rejecting the aggregate as an
# unknown kind. Keep the schema field optional so existing v1 manifests remain
# verifiable; all newly created manifests emit it.
replace_once(
    "capt_runtime/checkpoint.py",
    '''    "claim": "claimVersions",
}
''',
    '''    "claim": "claimVersions",
    "human_approval": "humanApprovalVersions",
}
''',
)
replace_once(
    "capt_runtime/checkpoint.py",
    '''        "claimVersions": sorted(versions["claimVersions"], key=lambda e: e["streamId"]),
        "activeLeaseIds": sorted(active_lease_ids),
''',
    '''        "claimVersions": sorted(versions["claimVersions"], key=lambda e: e["streamId"]),
        "humanApprovalVersions": sorted(
            versions["humanApprovalVersions"], key=lambda e: e["streamId"]
        ),
        "activeLeaseIds": sorted(active_lease_ids),
''',
)
replace_once(
    "contracts/schema/checkpoint.schema.json",
    '''        "claimVersions": { "type": "array", "maxItems": 4096, "items": { "$ref": "checkpoint.schema.json#/$defs/StreamVersionEntry" } },
        "activeLeaseIds": { "type": "array", "maxItems": 4096, "items": { "$ref": "common.schema.json#/$defs/Identifier" } },
''',
    '''        "claimVersions": { "type": "array", "maxItems": 4096, "items": { "$ref": "checkpoint.schema.json#/$defs/StreamVersionEntry" } },
        "humanApprovalVersions": { "type": "array", "maxItems": 4096, "items": { "$ref": "checkpoint.schema.json#/$defs/StreamVersionEntry" } },
        "activeLeaseIds": { "type": "array", "maxItems": 4096, "items": { "$ref": "common.schema.json#/$defs/Identifier" } },
''',
)

# Regression: a ledger containing HumanApprovalRequest is checkpointable and
# the manifest explicitly records that authoritative aggregate version.
replace_once(
    "tests/capt_runtime/test_prompt_approval_security.py",
    '''from capt_runtime import commands
from capt_runtime.errors import AuthorityViolation
''',
    '''from capt_runtime import commands
from capt_runtime.checkpoint import create_checkpoint
from capt_runtime.errors import AuthorityViolation
''',
)
insert_before = '''def test_approved_request_is_rejected_after_expiry_at_use_time(tmp_path):
'''
checkpoint_test = '''def test_checkpoint_accounts_for_durable_human_approval_stream(tmp_path):
    store = EventStore(str(tmp_path / "checkpoint-approval.db"))
    try:
        svc = RuntimeService(store)
        result = request_model_prompt_approval(
            svc,
            approval_intent(requestId="approval-checkpoint"),
            meta("cmd-checkpoint-request", "human", "idem-checkpoint-request"),
        )
        manifest = create_checkpoint(
            store,
            "cp-approval-security",
            "2026-08-17T00:00:00Z",
            "sha256:" + "c" * 64,
        )
        assert manifest["humanApprovalVersions"] == [
            {"streamId": "human_approval-" + result["requestId"], "version": 1}
        ]
    finally:
        store.close()


'''
replace_once(
    "tests/capt_runtime/test_prompt_approval_security.py",
    insert_before,
    checkpoint_test + insert_before,
)

print("TERRA_OUROBOROS_APPROVAL_MIGRATION_R2_APPLIED")
