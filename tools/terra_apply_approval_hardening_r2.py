from __future__ import annotations

import runpy
from pathlib import Path

path = Path("capt_runtime/drivers/hermes.py")
text = path.read_text()
actual = '        prompt = build_prompt(ctx, work_order.get("operations", []), objective=resolved.objective if resolved else None)\n'
normalized = '''        prompt = build_prompt(
            ctx, work_order["operations"], objective=resolved.objective if resolved else None
        )
'''
if text.count(actual) != 1:
    raise SystemExit(
        "capt_runtime/drivers/hermes.py: expected one canonical one-line build_prompt call"
    )
path.write_text(text.replace(actual, normalized, 1))
runpy.run_path("tools/terra_apply_approval_hardening.py", run_name="__main__")
