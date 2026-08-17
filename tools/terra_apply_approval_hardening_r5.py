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


runpy.run_path("tools/terra_apply_approval_hardening_r4.py", run_name="__main__")

# The command-service decision stamps actual wall-clock time.  Keep this legacy
# routing test deterministic by explicitly requesting a future expiry rather
# than relying on a fixed historical command timestamp.
replace_once(
    "tests/capt_runtime/test_model_operator.py",
    '''    request = svc.execute(
        _envelope("request_model_prompt_approval", payload, key=key + "-request")
    )
''',
    '''    request_payload = {**payload, "expiresAt": "2030-01-01T00:00:00Z"}
    request = svc.execute(
        _envelope(
            "request_model_prompt_approval",
            request_payload,
            key=key + "-request",
        )
    )
''',
)

# The real Operator facade already accepts an optional approval idempotency key.
# Keep the TUI dogfood fake behaviorally compatible so the test exercises the
# TUI contract rather than failing on Python method arity.
replace_once(
    "tests/test_tui_dogfood.py",
    '''    def request_prompt_approval(self, payload):
        self.approval_requests.append(dict(payload))
''',
    '''    def request_prompt_approval(self, payload, idempotency_key=None):
        self.approval_requests.append(dict(payload))
''',
)

print("TERRA_APPROVAL_HARDENING_R5_APPLIED")
