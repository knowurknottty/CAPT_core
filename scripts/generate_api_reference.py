#!/usr/bin/env python3
"""Generate docs/API.md by introspecting the live capt_solo public surface.

Reads the actual installed/source `capt_solo.api` and `capt_solo.foundry`,
emits a signature-accurate markdown reference, and overwrites docs/API.md.

Run:
    python3 scripts/generate_api_reference.py [OUT_PATH]
    python3 scripts/generate_api_reference.py --check   # assert docs/API.md is current, no write

Exit codes:
    0  success (or --check current)
    1  failure (or --check drifted)
"""
from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "docs" / "API.md"


def _sig_safe(m) -> str:
    try:
        return str(inspect.signature(m))
    except (TypeError, ValueError):
        return "(signature unavailable)"


def _api_public_names(module) -> list:
    return sorted(n for n in dir(module) if not n.startswith("_"))


def render() -> str:
    import capt_solo.api as api
    from capt_solo import foundry

    md = [
        "# CAPT Public Integration Reference",
        "",
        "> Generated from the installed v0.5 wheel by introspecting the public surface.",
        "> Signatures below are **real signatures read from source** — not hand-maintained copies.",
        "> Regenerate with `scripts/generate_api_reference.py` and validate with",
        "> `python3 -m pytest tests/test_api_reference.py -q`. Do not edit by hand.",
        "> Source of truth: the installed `capt_solo` package at the referenced commit.",
        "",
        "CAPT Core exposes two supported public surfaces:",
        "",
        "1. `capt_solo.api` for in-process CAPT Solo integrations (memory, CTP, KHSB, proof-governed services).",
        "2. The installed `capt harness` CLI for governed runtime lifecycle and bounded execution.",
        "",
        "They serve different purposes and are not interchangeable.",
        "",
        "---",
        "",
        "## 1. `capt_solo.api` public surface",
        "",
        "```text",
        ", ".join(_api_public_names(api)),
        "```",
        "",
        "---",
        "",
        "## 2. Core class method signatures (read from source)",
        "",
    ]

    for clsname, doc in [
        ("MemoryEngine", "Local-first memory store backed by SQLite."),
        ("CTPRuntime", "Small append-only local transaction journal."),
        ("KHSB", "In-process publish/subscribe/request-reply bus."),
    ]:
        cls = getattr(api, clsname)
        first = (inspect.getdoc(cls) or "").split("\n")[0] or doc
        md.append(f"### `{clsname}`")
        md.append("")
        md.append(first)
        md.append("")
        md.append("| Method | Signature |")
        md.append("|---|---|")
        for mn in _api_public_names(cls):
            obj = getattr(cls, mn)
            if not callable(obj):
                continue
            sig = _sig_safe(obj)
            # strip leading "self" (or "self,") for readability
            import re as _re
            sig = _re.sub(r"^\(\s*self\s*(,\s*)?", "(", sig)
            md.append(f"| `{mn}` | `{sig}` |")
        md.append("")

    md += [
        "---",
        "",
        "## 3. Foundry public surface (import from `capt_solo.foundry`)",
        "",
        "These proof-governed classes are NOT re-exported on `capt_solo.api` at top level.",
        "Import them from `capt_solo.foundry`.",
        "",
        "| Class | Public methods |",
        "|---|---|",
    ]
    for n in _api_public_names(foundry):
        obj = getattr(foundry, n)
        if isinstance(obj, type):
            count = sum(
                1 for m in dir(obj)
                if not m.startswith("_") and callable(getattr(obj, m))
            )
            md.append(f"| `{n}` | {count} |")

    md += [
        "",
        "---",
        "",
        "## 4. Validation",
        "",
        "This reference is generated from the installed wheel at the referenced commit. To reproduce:",
        "",
        "```",
        "python3 scripts/generate_api_reference.py",
        "python3 -m pytest tests/test_api_reference.py -q",
        "```",
        "",
        "The generator introspects `capt_solo.api` and `capt_solo.foundry` and overwrites `docs/API.md`.",
        "The validator asserts the committed `docs/API.md` equals the freshly generated output, so a",
        "drift between code and documentation fails CI rather than silently going stale.",
        "",
    ]
    return "\n".join(md) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate docs/API.md from live source")
    ap.add_argument("out", nargs="?", default=None, help="output path (default docs/API.md)")
    ap.add_argument("--check", action="store_true", help="assert current, do not write")
    args = ap.parse_args(argv)

    text = render()
    out = Path(args.out) if args.out else DEFAULT_OUT

    if args.check:
        if out.exists() and out.read_text() == text:
            print("API reference is current.")
            return 0
        print("API reference is STALE. Run scripts/generate_api_reference.py and commit.", file=sys.stderr)
        return 1

    out.write_text(text)
    print(f"wrote {out.resolve()} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
