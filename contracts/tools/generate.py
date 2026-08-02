#!/usr/bin/env python3
"""CAPT contract binding generator (ADR-0102).

Reproducible: sorted traversal, no timestamps, no paths, no hostnames in
output. Two runs on different machines produce byte-identical trees.

Usage:
    python3 contracts/tools/generate.py            # write bindings
    python3 contracts/tools/generate.py --out DIR  # write to an alternate root
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_spec  # noqa: E402
import emit_python  # noqa: E402
import emit_typescript  # noqa: E402
from schema_model import SchemaModel, canonical_json  # noqa: E402

CONTRACTS_DIR = TOOLS_DIR.parent
TEMPLATES = TOOLS_DIR / "templates"

REGEN = "python3 contracts/tools/generate.py"


def header(model: SchemaModel, comment: str) -> str:
    lines = [
        "DO NOT EDIT. This file is GENERATED from contracts/schema/.",
        "",
        "generator:      contracts/tools/generate.py",
        "regenerate:     " + REGEN,
        "drift check:    python3 contracts/tools/check_drift.py",
        "schema version: " + model.contract_schema_version,
        "source digest:  " + model.source_digest,
        "",
        "The JSON Schema source is normative (ADR-0101). Edits made here are",
        "erased on the next generation and will fail the CI drift check.",
    ]
    return "\n".join(comment + " " + line if line else comment for line in lines) + "\n"


def write(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    if previous == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def generate(out_root: Path) -> int:
    model = SchemaModel()
    spec = build_spec.build_spec(model)
    spec_json = canonical_json(spec)

    py_header = header(model, "#")
    ts_header = header(model, "//")

    py_dir = out_root / "python" / "capt_contracts"
    ts_dir = out_root / "typescript" / "src"

    changed = 0

    changed += write(
        py_dir / "__init__.py",
        py_header
        + "\n"
        + '"""Generated CAPT contract bindings (Python)."""\n\n'
        + "from .types import *  # noqa: F401,F403\n"
        + "from .types import CONTRACT_SCHEMA_VERSION, RUNTIME_VERSION  # noqa: F401\n"
        + "from .validate import (  # noqa: F401\n"
        + "    ValidationFailure,\n"
        + "    is_valid,\n"
        + "    known_types,\n"
        + "    require_valid,\n"
        + "    validate,\n"
        + ")\n"
        + "from .spec import SPEC, SPEC_JSON  # noqa: F401\n",
    )
    changed += write(py_dir / "types.py", py_header + "\n" + emit_python.emit_types(model))
    changed += write(
        py_dir / "spec.py",
        py_header + "\n" + emit_python.emit_spec(model, spec_json).replace(
            "SPEC: Dict[str, Any] = json.loads(SPEC_JSON)",
            "SPEC: Dict[str, Any] = json.loads(SPEC_JSON)",
        ),
    )
    changed += write(
        py_dir / "validate.py",
        py_header + "\n" + (TEMPLATES / "validator_py.txt").read_text(encoding="utf-8"),
    )

    changed += write(ts_dir / "types.ts", ts_header + "\n" + emit_typescript.emit_types(model))
    changed += write(
        ts_dir / "spec.ts", ts_header + "\n" + emit_typescript.emit_spec(model, spec_json)
    )
    changed += write(
        ts_dir / "validate.ts",
        ts_header + "\n" + (TEMPLATES / "validator_ts.txt").read_text(encoding="utf-8"),
    )
    changed += write(
        ts_dir / "index.ts",
        ts_header
        + "\nexport * from \"./types.js\";\nexport * from \"./validate.js\";\nexport { SPEC, SPEC_JSON } from \"./spec.js\";\n",
    )
    changed += write(
        out_root / "typescript" / "tsconfig.json",
        json.dumps(
            {
                "compilerOptions": {
                    "target": "ES2022",
                    "module": "ES2022",
                    "moduleResolution": "bundler",
                    "strict": True,
                    "declaration": True,
                    "noEmitOnError": True,
                    "outDir": "dist",
                    "rootDir": "src",
                    "resolveJsonModule": True,
                    "esModuleInterop": True,
                    "forceConsistentCasingInFileNames": True,
                },
                "include": ["src/**/*.ts"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    changed += write(
        out_root / "typescript" / "package.json",
        json.dumps(
            {
                "name": "@capt/contracts",
                "version": model.contract_schema_version,
                "description": "GENERATED CAPT runtime contract bindings. Do not edit.",
                "type": "module",
                "main": "dist/index.js",
                "types": "dist/index.d.ts",
                "private": True,
                "scripts": {"build": "tsc -p tsconfig.json", "check": "tsc -p tsconfig.json --noEmit"},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )

    print("contract schema version: " + model.contract_schema_version)
    print("source digest:           " + model.source_digest)
    print("types generated:         %d" % len(model.types))
    print("files written/changed:   %d" % changed)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CAPT contract bindings.")
    parser.add_argument(
        "--out",
        default=str(CONTRACTS_DIR / "generated"),
        help="output root (default: contracts/generated)",
    )
    args = parser.parse_args()
    return generate(Path(args.out))


if __name__ == "__main__":
    raise SystemExit(main())
