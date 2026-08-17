from pathlib import Path

source = Path("/tmp/terra_apply_d09_living_docs.py").read_text()
old = "- [ ] independently verify the operator-supplied `{HERMES_BRANCH}` / `{HERMES_HEAD}` metadata and the reported 98/0/0, 174/0/2, skip, npm, and no-blocker claims before promoting them back to evidence;"
new = "- [ ] independently verify the **currently unverified** operator-supplied `{HERMES_BRANCH}` / `{HERMES_HEAD}` metadata and the reported 98/0/0, 174/0/2, skip, npm, and no-blocker claims before promoting them back to evidence;"
if source.count(old) != 1:
    raise SystemExit(f"expected one roadmap source phrase, found {source.count(old)}")
source = source.replace(old, new, 1)
exec(compile(source, "/tmp/terra_apply_d09_living_docs.py", "exec"), {"__name__": "__main__"})
