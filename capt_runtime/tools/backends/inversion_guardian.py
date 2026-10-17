"""Standalone privilege-free egress guardian for CAPT InversionSandbox.

This module intentionally uses only the Python standard library so its exact
source can run inside a pinned local guardian image via ``python3 -c``.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import selectors
import socket
import socketserver
import sys
from dataclasses import dataclass
from urllib.parse import urlsplit

MAX_HEADER_BYTES = 64 * 1024
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 18080


class GuardianProtocolError(ValueError):
    """The proxy request is malformed or outside the supported protocol."""


@dataclass(frozen=True)
class ProxyRequest:
    method: str
    host: str
    port: int
    version: str
    forward_target: str
    headers: tuple[tuple[str, str], ...]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def policy_digest(policy: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(policy).encode("utf-8")).hexdigest()


def _host(value: str) -> str:
    host = value.strip().lower().rstrip(".")
    if not host or len(host) > 253 or any(ch.isspace() for ch in host):
        raise GuardianProtocolError("invalid destination host")
    return host


def _domain_matches(rule: str, host: str) -> bool:
    if rule.startswith("*."):
        suffix = rule[2:]
        return host != suffix and host.endswith("." + suffix)
    return host == rule


def _network(rule: str):
    try:
        return ipaddress.ip_network(rule, strict=False)
    except ValueError:
        return None


def _ip_values(values: list[str] | tuple[str, ...]) -> tuple[ipaddress._BaseAddress, ...]:
    out = []
    for value in values:
        try:
            out.append(ipaddress.ip_address(value))
        except ValueError:
            return ()
    return tuple(out)


# Immutable deny floor, applied in every mode IN ADDITION to the profile's
# platformDeny. It is not part of the canonical policy (so profile/lease digests
# are unchanged) and a profile cannot narrow it. These ranges are reachable only
# because of the guardian's network position (host loopback, cloud metadata,
# the operator's LAN, carrier NAT, fake-IP DNS resolvers).
_BUILTIN_DENY = tuple(
    ipaddress.ip_network(value)
    for value in (
        "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
        "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.168.0.0/16",
        "198.18.0.0/15", "224.0.0.0/4", "240.0.0.0/4",
        "::/96",  # unspecified, loopback and deprecated IPv4-compatible ::a.b.c.d
        "fc00::/7", "fe80::/10", "fec0::/10", "ff00::/8",
        "64:ff9b:1::/48",  # RFC 8215 local-use NAT64: embedding is site-defined
    )
)
_NAT64_WELL_KNOWN = ipaddress.ip_network("64:ff9b::/96")  # RFC 6052


def _effective_addresses(
    ip: ipaddress._BaseAddress,
) -> tuple[ipaddress._BaseAddress, ...]:
    """The address plus every IPv4 address it can deliver traffic to.

    An AAAA answer of ``::ffff:169.254.169.254`` is connected over IPv4 by a
    dual-stack socket, so it must be judged as 169.254.169.254. Same for NAT64
    (RFC 6052 well-known prefix), 6to4 (2002::/16) and Teredo (2001::/32).
    Version-mismatched CIDR rules otherwise skip these silently.
    """
    out: list[ipaddress._BaseAddress] = [ip]
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            out.append(ip.ipv4_mapped)
        if ip.sixtofour is not None:
            out.append(ip.sixtofour)
        if ip.teredo is not None:
            out.extend(ip.teredo)
        if ip in _NAT64_WELL_KNOWN:
            out.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    return tuple(out)


def _builtin_denied(ips: tuple[ipaddress._BaseAddress, ...]) -> bool:
    for ip in ips:
        for address in _effective_addresses(ip):
            if any(address.version == net.version and address in net for net in _BUILTIN_DENY):
                return True
    return False


def _rule_matches_host_or_ips(
    rule: str, host: str, ips: tuple[ipaddress._BaseAddress, ...]
) -> bool:
    network = _network(rule)
    if network is not None:
        return any(ip.version == network.version and ip in network for ip in ips)
    return _domain_matches(rule, host)


def destination_allowed(
    policy: dict[str, object], host: str, resolved_ips: list[str] | tuple[str, ...]
) -> bool:
    """Apply immutable deny precedence, then mode-specific admission."""
    try:
        normalized_host = _host(host)
    except GuardianProtocolError:
        return False
    ips = _ip_values(resolved_ips)
    if not ips or len(ips) != len(resolved_ips):
        return False
    deny = policy.get("platformDeny")
    allow = policy.get("allow")
    mode = policy.get("mode")
    if not isinstance(deny, list) or not all(isinstance(v, str) for v in deny):
        return False
    if not isinstance(allow, list) or not all(isinstance(v, str) for v in allow):
        return False
    if mode not in {"none", "allowlist", "unrestricted"}:
        return False
    if _builtin_denied(ips):
        return False
    # Profile deny rules are judged against embedded IPv4 too (::ffff:10.0.0.5
    # must hit a 10.0.0.0/8 rule).
    expanded = tuple(address for ip in ips for address in _effective_addresses(ip))
    if any(_rule_matches_host_or_ips(rule, normalized_host, expanded) for rule in deny):
        return False
    if mode == "none":
        return False
    if mode == "unrestricted":
        return True
    if any(_network(rule) is None and _domain_matches(rule, normalized_host) for rule in allow):
        return True
    network_rules = tuple(net for rule in allow if (net := _network(rule)) is not None)
    return bool(network_rules) and all(
        any(ip.version == net.version and ip in net for net in network_rules) for ip in ips
    )


def _parse_authority(value: str, *, default_port: int | None = None) -> tuple[str, int]:
    try:
        parts = urlsplit("//" + value)
        host = parts.hostname
        port = parts.port if parts.port is not None else default_port
    except ValueError as exc:
        raise GuardianProtocolError("invalid proxy authority") from exc
    if host is None or port is None or not (1 <= port <= 65535):
        raise GuardianProtocolError("proxy authority requires a valid host and port")
    return _host(host), port


def parse_request_head(data: bytes) -> ProxyRequest:
    if len(data) > MAX_HEADER_BYTES:
        raise GuardianProtocolError("proxy request head exceeds 64 KiB")
    if b"\r\n\r\n" not in data:
        raise GuardianProtocolError("incomplete proxy request head")
    try:
        text = data.decode("iso-8859-1")
    except UnicodeDecodeError as exc:
        raise GuardianProtocolError("proxy request head is not decodable") from exc
    lines = text.split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) != 3:
        raise GuardianProtocolError("malformed proxy request line")
    method, target, version = parts
    if not method.isalpha() or not version.startswith("HTTP/1."):
        raise GuardianProtocolError("unsupported proxy request line")
    headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        if not line:
            break
        if ":" not in line:
            raise GuardianProtocolError("malformed proxy header")
        name, value = line.split(":", 1)
        if not name or any(ch.isspace() for ch in name):
            raise GuardianProtocolError("malformed proxy header name")
        headers.append((name, value.lstrip()))
    if method.upper() == "CONNECT":
        host, port = _parse_authority(target)
        return ProxyRequest("CONNECT", host, port, version, target, tuple(headers))
    parsed = urlsplit(target)
    if parsed.scheme != "http" or parsed.hostname is None:
        raise GuardianProtocolError("HTTP proxy requests must use absolute http:// form")
    try:
        port = parsed.port or 80
    except ValueError as exc:
        raise GuardianProtocolError("invalid HTTP proxy port") from exc
    host = _host(parsed.hostname)
    forward = parsed.path or "/"
    if parsed.query:
        forward += "?" + parsed.query
    return ProxyRequest(method.upper(), host, port, version, forward, tuple(headers))


def _resolve(host: str, port: int) -> list[tuple[int, str]]:
    rows = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    seen: set[tuple[int, str]] = set()
    out: list[tuple[int, str]] = []
    for family, _socktype, _proto, _canon, sockaddr in rows:
        value = (family, sockaddr[0])
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _connect_resolved(rows: list[tuple[int, str]], port: int) -> socket.socket:
    last_error: OSError | None = None
    for family, address in rows:
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(10.0)
        try:
            sock.connect((address, port))
            sock.settimeout(None)
            return sock
        except OSError as exc:
            last_error = exc
            sock.close()
    raise last_error or OSError("no resolved destination could be connected")


def _relay(left: socket.socket, right: socket.socket) -> None:
    selector = selectors.DefaultSelector()
    selector.register(left, selectors.EVENT_READ, right)
    selector.register(right, selectors.EVENT_READ, left)
    try:
        while True:
            events = selector.select(timeout=60.0)
            if not events:
                return
            for key, _mask in events:
                source = key.fileobj
                target = key.data
                chunk = source.recv(65536)
                if not chunk:
                    return
                target.sendall(chunk)
    finally:
        selector.close()


def _filtered_headers(headers: tuple[tuple[str, str], ...]) -> bytes:
    blocked = {"proxy-authorization", "proxy-connection", "connection"}
    rows = [f"{name}: {value}\r\n" for name, value in headers if name.lower() not in blocked]
    rows.append("Connection: close\r\n")
    return "".join(rows).encode("iso-8859-1")


def _read_head(client: socket.socket) -> bytes:
    data = bytearray()
    while b"\r\n\r\n" not in data:
        chunk = client.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > MAX_HEADER_BYTES:
            raise GuardianProtocolError("proxy request head exceeds 64 KiB")
    return bytes(data)


class _GuardianHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        client: socket.socket = self.request
        try:
            raw = _read_head(client)
            request = parse_request_head(raw)
            resolved = _resolve(request.host, request.port)
            addresses = [address for _family, address in resolved]
            policy = self.server.policy
            if not destination_allowed(policy, request.host, addresses):
                client.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
                return
            upstream = _connect_resolved(resolved, request.port)
            try:
                if request.method == "CONNECT":
                    client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    _relay(client, upstream)
                else:
                    first = f"{request.method} {request.forward_target} {request.version}\r\n".encode("ascii")
                    upstream.sendall(first + _filtered_headers(request.headers) + b"\r\n")
                    _relay(client, upstream)
            finally:
                upstream.close()
        except GuardianProtocolError:
            client.sendall(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
        except (OSError, socket.gaierror):
            try:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            except OSError:
                pass


class _GuardianServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], policy: dict[str, object]):
        self.policy = policy
        super().__init__(address, _GuardianHandler)


def _load_policy() -> dict[str, object]:
    encoded = os.environ.get("CAPT_GUARDIAN_POLICY_B64", "")
    expected = os.environ.get("CAPT_GUARDIAN_POLICY_DIGEST", "")
    if not encoded or not expected:
        raise RuntimeError("guardian policy environment is incomplete")
    try:
        raw = base64.b64decode(encoded, validate=True)
        policy = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("guardian policy environment is invalid") from exc
    if not isinstance(policy, dict) or policy_digest(policy) != expected:
        raise RuntimeError("guardian policy digest mismatch")
    return policy


def main() -> int:
    try:
        policy = _load_policy()
        server = _GuardianServer((LISTEN_HOST, LISTEN_PORT), policy)
    except (OSError, RuntimeError) as exc:
        print(f"CAPT_GUARDIAN_FATAL {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 2
    print(f"CAPT_GUARDIAN_READY {policy_digest(policy)}", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
