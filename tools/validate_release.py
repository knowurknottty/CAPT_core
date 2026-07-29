#!/usr/bin/env python3
"""Read-only entry point for CAPT Solo release semantic validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capt_solo.release_validation import result_document, validate_release


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dist-dir", type=Path)
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--candidate-sha")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    document = result_document(validate_release(
        args.root,
        dist_dir=args.dist_dir,
        final=args.final,
        candidate_sha=args.candidate_sha,
    ))
    if args.json:
        print(json.dumps(document, indent=2))
    else:
        for check in document["checks"]:
            print(
                f"{check['status'].upper():4} "
                f"{check['check_id']}: {check['evidence']}"
            )
        print(
            "release semantic validation: "
            f"{document['summary']['passed']} pass / "
            f"{document['summary']['failed']} fail"
        )
    return 0 if document["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
