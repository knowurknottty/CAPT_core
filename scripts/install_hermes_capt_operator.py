#!/usr/bin/env python3
"""Install the source-controlled CAPT Operator Hermes plugin into the user profile."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "integrations" / "hermes" / "capt-operator"
FILES = ("__init__.py", "plugin.yaml", "README.md")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.home() / ".hermes" / "plugins" / "capt-operator",
    )
    args = parser.parse_args()
    target = args.target.expanduser()
    target.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src = SOURCE / name
        if not src.is_file():
            raise SystemExit(f"missing canonical plugin file: {src}")
        tmp = target / (name + ".tmp")
        shutil.copy2(src, tmp)
        tmp.replace(target / name)
    print(f"installed CAPT Operator from {SOURCE} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
