"""CAPT Solo v0.4 — shared JSON column helpers.

SQLite stores list/dict fields as JSON strings. These helpers parse them back
safely and VALIDATE the decoded type. They never silently reinterpret a scalar
as a list or object. Malformed JSON and wrong-type JSON both fail loudly
(raise) rather than returning a wrong-shaped value.

All foundry modules (Capability, Evidence, Skill) MUST use these helpers
instead of duplicating subtly different parsers.
"""

from __future__ import annotations

import json
from typing import Any, List, Dict, Optional


class ColumnDecodeError(ValueError):
    """Raised when a JSON column cannot be decoded to the expected type."""


def decode_list(value: Any, *, field: str = "<list>") -> List[Any]:
    """Decode a DB/list value into a list. Never returns a non-list.

    Accepts:
      - already a list/tuple -> returned as list
      - a JSON string encoding a list -> decoded list
    Rejects (raises ColumnDecodeError):
      - JSON string encoding a scalar/object
      - malformed JSON
      - None / missing (unless you pass default)
      - a bare string that is not JSON
    """
    if value is None:
        raise ColumnDecodeError(f"field {field}: expected list, got None")
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            raise ColumnDecodeError(f"field {field}: empty string is not a list")
        try:
            decoded = json.loads(s)
        except (ValueError, TypeError) as e:
            raise ColumnDecodeError(f"field {field}: malformed JSON ({e})") from e
        if isinstance(decoded, list):
            return decoded
        raise ColumnDecodeError(
            f"field {field}: JSON decoded to {type(decoded).__name__}, expected list")
    raise ColumnDecodeError(
        f"field {field}: cannot decode {type(value).__name__} to list")


def decode_dict(value: Any, *, field: str = "<dict>") -> Dict[str, Any]:
    """Decode a DB/dict value into a dict. Never returns a non-dict.

    Same acceptance/rejection rules as decode_list but for dicts.
    """
    if value is None:
        raise ColumnDecodeError(f"field {field}: expected dict, got None")
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            raise ColumnDecodeError(f"field {field}: empty string is not a dict")
        try:
            decoded = json.loads(s)
        except (ValueError, TypeError) as e:
            raise ColumnDecodeError(f"field {field}: malformed JSON ({e})") from e
        if isinstance(decoded, dict):
            return decoded
        raise ColumnDecodeError(
            f"field {field}: JSON decoded to {type(decoded).__name__}, expected dict")
    raise ColumnDecodeError(
        f"field {field}: cannot decode {type(value).__name__} to dict")


def decode_list_safe(value: Any, *, field: str = "<list>",
                     default: Optional[List[Any]] = None) -> List[Any]:
    """Like decode_list but returns `default` (or []) on any failure."""
    try:
        return decode_list(value, field=field)
    except ColumnDecodeError:
        return list(default) if default is not None else []


def decode_dict_safe(value: Any, *, field: str = "<dict>",
                     default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Like decode_dict but returns `default` (or {}) on any failure."""
    try:
        return decode_dict(value, field=field)
    except ColumnDecodeError:
        return dict(default) if default is not None else {}
