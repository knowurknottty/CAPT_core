from __future__ import annotations

import runpy
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}: {old[:160]!r}")
    p.write_text(text.replace(old, new, 1))


runpy.run_path("tools/terra_apply_approval_hardening_r5.py", run_name="__main__")

replace_once(
    "tests/capt_runtime/test_model_operator.py",
    '''    assert decision["status"] == "accepted"
    assert decision["result"]["state"] == "approved"
    return {
''',
    '''    assert decision["status"] == "accepted"
    authoritative = svc.store.require_state(
        "human_approval-" + planned["requestId"]
    )
    assert authoritative["state"] == "approved"
    return {
''',
)

print("TERRA_APPROVAL_HARDENING_R6_APPLIED")
