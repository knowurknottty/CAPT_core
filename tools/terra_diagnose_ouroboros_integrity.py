from __future__ import annotations

import runpy
from pathlib import Path

runpy.run_path("tools/terra_apply_ouroboros_approval_migration.py", run_name="__main__")

path = Path("tests/capt_runtime/test_ouroboros_lifecycle.py")
text = path.read_text()
old = '''        receipt = client.command("run_approved_hermes_inspection", payload, "idem-ouro-happy")
        assert receipt["status"] == "accepted", receipt
'''
new = '''        receipt = client.command("run_approved_hermes_inspection", payload, "idem-ouro-happy")
        print("TERRA_HAPPY_RECEIPT=" + json.dumps(receipt, indent=2, sort_keys=True))
        assert receipt["status"] == "accepted", receipt
'''
if text.count(old) != 1:
    raise SystemExit("expected one happy-path receipt assertion")
path.write_text(text.replace(old, new, 1))
