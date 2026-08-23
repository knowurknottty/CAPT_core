"""Live, non-secret verification of provider-side billing enforcement."""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


class BillingAssuranceError(RuntimeError):
    pass


def validate_openrouter_key_policy(data: Dict[str, Any], *, source_sha: str) -> Dict[str, Any]:
    if not source_sha:
        raise BillingAssuranceError("SOURCE_SHA_REQUIRED")
    if bool(data.get("is_management_key")) or bool(data.get("is_provisioning_key")):
        raise BillingAssuranceError("ADMIN_CREDENTIAL_NOT_ALLOWED")
    limit = data.get("limit")
    if not isinstance(limit, (int, float)) or isinstance(limit, bool) or float(limit) <= 0:
        raise BillingAssuranceError("PROVIDER_HARD_CAP_MISSING")
    remaining = data.get("limit_remaining")
    if remaining is not None and (not isinstance(remaining, (int, float)) or isinstance(remaining, bool)):
        raise BillingAssuranceError("PROVIDER_LIMIT_REMAINING_INVALID")
    return {
        "schemaVersion": "1.0.0",
        "provider": "openrouter",
        "sourceSha": source_sha,
        "hardCapUsd": float(limit),
        "limitRemainingUsd": None if remaining is None else float(remaining),
        "managementCredential": False,
        "provisioningCredential": False,
    }


def verify_openrouter_key_limit(
    api_key: str, *, source_sha: str,
    endpoint: str = "https://openrouter.ai/api/v1/key",
    timeout: float = 15.0,
) -> Dict[str, Any]:
    if not api_key:
        raise BillingAssuranceError("OPENROUTER_RELEASE_KEY_REQUIRED")
    req = urllib.request.Request(
        endpoint,
        headers={"Authorization": "Bearer " + api_key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise BillingAssuranceError("OPENROUTER_POLICY_QUERY_FAILED:%s" % type(exc).__name__) from exc
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise BillingAssuranceError("OPENROUTER_POLICY_RESPONSE_INVALID")
    return validate_openrouter_key_policy(data, source_sha=source_sha)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m capt_runtime.billing_assurance")
    parser.add_argument("--provider", choices=("openrouter",), required=True)
    parser.add_argument("--key-env", default="OPENROUTER_RELEASE_KEY")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = verify_openrouter_key_limit(
        os.environ.get(args.key_env, ""), source_sha=args.source_sha
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
