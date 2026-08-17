from __future__ import annotations

import runpy
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


# Normalize the exact Hermes source shape expected by the fail-closed r1 applicator.
replace_once(
    "capt_runtime/drivers/hermes.py",
    '        prompt = build_prompt(ctx, work_order.get("operations", []), objective=resolved.objective if resolved else None)\n',
    '''        prompt = build_prompt(
            ctx, work_order["operations"], objective=resolved.objective if resolved else None
        )
''',
)

# Apply the full production hardening transform from the pristine PR head.
runpy.run_path("tools/terra_apply_approval_hardening.py", run_name="__main__")

# An approval attempt is keyed by the outer idempotency identity.  Its inner
# fingerprint must bind the semantic approval, not transport-variant
# correlation/timestamp fields in the request envelope.  The exact approved
# execution digest already binds all execution-relevant intent.
replace_once(
    "capt_runtime/prompt_approval.py",
    '        operation_fingerprint=commands.fingerprint("request_human_approval", request),\n',
    '''        operation_fingerprint=commands.fingerprint(
            "request_human_approval",
            {
                "requestId": request_id,
                "promptAssemblyDigest": assembly["promptAssemblyDigest"],
                "approvalAttemptId": suffix,
            },
        ),
''',
)

# r1 makes RuntimeClient correlation deterministic from op+idempotency key;
# ensure the new hashlib use is explicitly imported.
replace_once(
    "desktop/desktop_runtime_client.py",
    "import json\nimport socket\n",
    "import hashlib\nimport json\nimport socket\n",
)

print("TERRA_APPROVAL_HARDENING_R3_APPLIED")
