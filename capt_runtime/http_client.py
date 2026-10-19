"""Credential-safe outbound HTTP for CAPT (CAPT-UPG-027).

CPython's default ``urllib`` opener follows 301/302/303 redirects by re-issuing
the request as GET to the ``Location`` origin and keeps every non-content header,
including ``Authorization``, across origins. A provider, proxy, or compromised
endpoint can therefore harvest a bearer token with one redirect.

Every shipped network call goes through :func:`open_url`, whose opener refuses
redirects: urllib then raises :class:`urllib.error.HTTPError` with the 3xx code,
so existing ``except HTTPError`` handling treats a redirect as a failed request.
``tests/capt_runtime/test_http_client_redirects.py`` fails on any new bare
``urlopen`` (or ``build_opener`` without a no-redirect handler) in shipped code.

:func:`open_url` is looked up as a module attribute by callers so tests can
substitute it with ``monkeypatch.setattr(http_client, "open_url", fake)``.
"""
from __future__ import annotations

import urllib.request
from http.client import HTTPResponse
from typing import Any, Protocol

__all__ = ["DEFAULT_MAX_RESPONSE_BYTES", "NoRedirectHandler", "ResponseTooLarge", "open_url", "read_bounded"]

DEFAULT_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class ResponseTooLarge(ValueError):
    """A response body exceeded the caller's byte ceiling."""


class _Readable(Protocol):
    def read(self, size: int = ..., /) -> bytes: ...


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect.

    Returning ``None`` from ``redirect_request`` makes urllib fall through to
    its default error handler, which raises ``HTTPError(code=3xx)``. No request
    is ever sent to the redirect target, so no header can leak to it.
    """

    def redirect_request(  # type: ignore[override]
        self, req: urllib.request.Request, fp: Any, code: int, msg: str,
        headers: Any, newurl: str,
    ) -> None:
        return None


def open_url(request: urllib.request.Request | str, *, timeout: float) -> HTTPResponse:
    """Open ``request`` with proxy support and without following redirects.

    The opener is built per call so proxy environment changes (``HTTPS_PROXY``
    et al.) are honoured exactly as ``urllib.request.urlopen`` would.
    """
    opener = urllib.request.build_opener(NoRedirectHandler())
    return opener.open(request, timeout=timeout)  # type: ignore[no-any-return]


def read_bounded(response: _Readable, *, limit: int = DEFAULT_MAX_RESPONSE_BYTES) -> bytes:
    """Read at most ``limit`` bytes; raise :class:`ResponseTooLarge` beyond it."""
    if limit < 1:
        raise ValueError("HTTP_RESPONSE_LIMIT_INVALID")
    raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ResponseTooLarge(f"HTTP_RESPONSE_TOO_LARGE:>{limit}")
    return raw
