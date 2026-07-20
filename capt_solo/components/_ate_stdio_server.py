#!/usr/bin/env python3
"""Bundled local stdio server for the Anti-Token-Extraction component.

This is the vendored local runtime that the component spawns as a child
process over stdio (JSON-RPC 2.0, one JSON object per line). It is fully
offline: no network, no credentials, cache mode off, sensitive-input refusal
on. The pinned upstream (https://github.com/knowurknottty/anti-token-extraction
@ b68adac...) is the canonical source; this server mirrors its contract.

Protocol:
  request  {"jsonrpc":"2.0","id":<str>,"method":<m>,"params":<obj>}
  response {"jsonrpc":"2.0","id":<str>,"result":<obj>}
           {"jsonrpc":"2.0","id":<str>,"error":<obj>}

Methods: initialize, health, extract, shutdown.
"""

import argparse
import json
import re
import sys

# Token shapes we extract (high-precision, offline regexes).
_TOKEN_PATTERNS = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "stripe_key": re.compile(r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}"),
    "google_api": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "bearer_token": re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}"),
    "api_key_assign": re.compile(r"(?i)(api[_-]?key|apikey|secret[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    "password_assign": re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\\s'\"]{6,}"),
}

# Sensitive-input refusal: refuse CREDENTIAL ASSIGNMENTS (something submitted
# as a secret), NOT bare tokens that are extraction targets (AKIA…, ghp_…).
_SENSITIVE_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|apikey|secret[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\\s'\"]{6,}"),
    re.compile(r"(?i)(session|auth|access)[_\-]?token\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{20,}"),
    re.compile(r"(?i)recovery[_-]?code\s*[:=]\s*['\"]?[A-Za-z0-9]{8,}"),
    re.compile(r"(?i)(seed\s*phrase|mnemonic|recovery\s*phrase)\b"),
]


def _refuses(text: str) -> bool:
    return any(p.search(text) for p in _SENSITIVE_PATTERNS)


def _extract(text: str) -> list:
    found = []
    for name, pat in _TOKEN_PATTERNS.items():
        for m in pat.finditer(text):
            found.append({"type": name, "match": m.group(0)})
    return found


def _handle(method: str, params: dict) -> dict:
    if method == "initialize":
        return {"capabilities": {"cache": "off", "refusal": "on",
                                 "transport": "stdio"}}
    if method == "health":
        return {"ok": True, "detail": "stdio server operational"}
    if method == "extract":
        text = params.get("text", "")
        if _refuses(text):
            raise ValueError("sensitive input refused by policy")
        return {"tokens": _extract(text)}
    if method == "shutdown":
        return {"ok": True}
    raise ValueError(f"unknown method: {method}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-mode", default="off")
    parser.add_argument("--refusal", default="on")
    args = parser.parse_args()
    if args.cache_mode != "off":
        sys.stderr.write("fatal: cache-mode must be off\n")
        return 2
    if args.refusal != "on":
        sys.stderr.write("fatal: refusal must be on\n")
        return 2

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {}) or {}
        try:
            result = _handle(method, params)
            out = {"jsonrpc": "2.0", "id": rid, "result": result}
        except Exception as e:
            out = {"jsonrpc": "2.0", "id": rid,
                   "error": {"code": -32000, "message": str(e)}}
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()
        if method == "shutdown":
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
