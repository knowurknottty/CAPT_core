#!/usr/bin/env python3
"""Local stdio adapter for the pinned Anti-Token-Extraction package.

This adapter never implements credential extraction. It imports the installed
upstream package and exposes only stateless tool-output compression and type
detection over a bounded newline-delimited JSON-RPC channel.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

MAX_REQUEST_BYTES = 1_048_576


def _load_upstream():
    try:
        from anti_token_extraction._core import rtk_compress, rtk_detect
        from anti_token_extraction.security import process_sensitive_input
    except Exception as exc:  # pragma: no cover - reported to parent process
        raise RuntimeError(f"pinned anti-token-extraction package unavailable: {exc}") from exc
    return rtk_compress, rtk_detect, process_sensitive_input


def _secure_text(text: str, process_sensitive_input) -> str:
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if len(text.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("request exceeds 1 MiB limit")
    return process_sensitive_input(text, policy="refuse").text


def _handle(method: str, params: dict[str, Any]) -> dict[str, Any]:
    rtk_compress, rtk_detect, process_sensitive_input = _load_upstream()
    if method == "initialize":
        return {
            "capabilities": {
                "compression": True,
                "detection": True,
                "cache": "off",
                "sensitive_input_policy": "refuse",
                "transport": "stdio",
            }
        }
    if method == "health":
        return {"ok": True, "detail": "pinned upstream runtime operational"}
    if method == "compress":
        text = _secure_text(params.get("text", ""), process_sensitive_input)
        filter_name = params.get("filter_name", "auto")
        if not isinstance(filter_name, str):
            raise ValueError("filter_name must be a string")
        output = rtk_compress(text, filter_name, 0, 0)
        return {
            "output": output,
            "bytes_in": len(text.encode("utf-8")),
            "bytes_out": len(output.encode("utf-8")),
        }
    if method == "detect":
        text = _secure_text(params.get("text", ""), process_sensitive_input)
        return {"detection": rtk_detect(text)}
    if method == "shutdown":
        return {"ok": True}
    raise ValueError(f"unknown method: {method}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-mode", default="off")
    parser.add_argument("--refusal", default="on")
    args = parser.parse_args()
    if args.cache_mode != "off" or args.refusal != "on":
        sys.stderr.write("fatal: cache mode must be off and refusal must be on\n")
        return 2

    for raw_line in sys.stdin.buffer:
        if len(raw_line) > MAX_REQUEST_BYTES + 4096:
            sys.stderr.write("request line exceeds limit\n")
            return 2
        line = raw_line.decode("utf-8", errors="strict").strip()
        if not line:
            continue
        rid = None
        method = ""
        try:
            req = json.loads(line)
            if not isinstance(req, dict) or req.get("jsonrpc") != "2.0":
                raise ValueError("invalid JSON-RPC request")
            rid = req.get("id")
            method = req.get("method", "")
            params = req.get("params", {}) or {}
            if not isinstance(params, dict):
                raise ValueError("params must be an object")
            result = _handle(method, params)
            out = {"jsonrpc": "2.0", "id": rid, "result": result}
        except Exception as exc:
            out = {
                "jsonrpc": "2.0",
                "id": rid,
                "error": {"code": -32000, "message": str(exc)},
            }
        sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        if method == "shutdown":
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
