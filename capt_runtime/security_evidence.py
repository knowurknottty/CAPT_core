"""Build ephemeral exact-head evidence bundles for the CAPT security gate.

Evidence belongs to the execution that produced it, not to a committed file in
the source tree. CI therefore generates this JSON after checks execute and feeds
it directly to ``capt_runtime.security_gate``. This avoids the impossible
self-reference of a committed evidence file trying to attest its own commit SHA.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .security_gate import CONTROL_BY_ID


def _parse_attestation(value: str) -> Tuple[str, str]:
    control_id, sep, ref = value.partition("=")
    control_id = control_id.strip()
    ref = ref.strip()
    if not sep or not control_id or not ref:
        raise ValueError("SECURITY_ATTESTATION_FORMAT: expected CONTROL_ID=REFERENCE")
    if control_id not in CONTROL_BY_ID:
        raise ValueError("SECURITY_ATTESTATION_UNKNOWN_CONTROL:%s" % control_id)
    return control_id, ref


def build_bundle(
    *,
    source_sha: str,
    passed: Sequence[str] = (),
    failed: Sequence[str] = (),
    verifier: str = "ci",
) -> Dict[str, object]:
    source_sha = source_sha.strip()
    verifier = verifier.strip()
    if not source_sha:
        raise ValueError("SECURITY_SOURCE_SHA_REQUIRED")
    if not verifier:
        raise ValueError("SECURITY_VERIFIER_REQUIRED")

    rows: Dict[str, Dict[str, object]] = {}
    for status, values in (("pass", passed), ("fail", failed)):
        for raw in values:
            control_id, ref = _parse_attestation(raw)
            if control_id in rows:
                raise ValueError("SECURITY_ATTESTATION_DUPLICATE:%s" % control_id)
            rows[control_id] = {
                "controlId": control_id,
                "status": status,
                "sourceSha": source_sha,
                "refs": [ref],
                "verifier": verifier,
                "detail": "ephemeral exact-head %s attestation" % status,
            }
    return {
        "schemaVersion": "1.0.0",
        "sourceSha": source_sha,
        "ephemeral": True,
        "evidence": [rows[k] for k in sorted(rows)],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m capt_runtime.security_evidence")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--verifier", default="ci")
    parser.add_argument("--pass", dest="passed", action="append", default=[])
    parser.add_argument("--fail", dest="failed", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    bundle = build_bundle(
        source_sha=args.source_sha,
        passed=args.passed,
        failed=args.failed,
        verifier=args.verifier,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
