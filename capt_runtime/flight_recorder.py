"""Read-only CAPT Cognitive Black Box / `.capt-flight` exporter.

A flight bundle is a forensic/support artifact over authoritative CAPT data.
It is NOT authoritative state, a replay grant, a verification result, or a
ClaimGuard decision. The exporter only reads EventStore projections and emits
a content-addressed archive that can be independently integrity-checked.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Set, Union

from .contracts import canonical_json
from .errors import IntegrityViolation
from .store import EventStore

FLIGHT_SCHEMA_VERSION = "1.0.0"
_REDACTED = "<redacted>"
_DEFAULT_SECRET_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "accesstoken",
        "refresh_token",
        "refreshtoken",
        "password",
        "secret",
        "client_secret",
        "clientsecret",
        "bearer_token",
        "bearertoken",
    }
)


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def _normalized_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_")


def redact(
    value: Any,
    *,
    secret_keys: Optional[Iterable[str]] = None,
    secret_values: Optional[Iterable[str]] = None,
) -> Any:
    """Recursively redact explicit secret fields and known secret values.

    Redaction is deliberately conservative: references such as ``key_ref`` or
    provider/model identifiers are preserved because they are provenance, not
    credential material. Callers may add deployment-specific key names and
    exact secret values.
    """
    keys: Set[str] = set(_DEFAULT_SECRET_KEYS)
    keys.update(_normalized_key(k) for k in (secret_keys or ()))
    values = {str(v) for v in (secret_values or ()) if v is not None and str(v)}

    def walk(node: Any) -> Any:
        if isinstance(node, Mapping):
            out: Dict[str, Any] = {}
            for key, item in node.items():
                skey = str(key)
                if _normalized_key(skey) in keys:
                    out[skey] = _REDACTED
                else:
                    out[skey] = walk(item)
            return out
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, tuple):
            return [walk(item) for item in node]
        if isinstance(node, str):
            if node in values or node.lower().startswith("bearer "):
                return _REDACTED
            replaced = node
            for secret in sorted(values, key=len, reverse=True):
                if secret and secret in replaced:
                    replaced = replaced.replace(secret, _REDACTED)
            return replaced
        return node

    return walk(value)


def _manifest_digest(manifest: Mapping[str, Any]) -> str:
    material = {k: v for k, v in manifest.items() if k != "manifestDigest"}
    return _sha256_bytes(_json_bytes(material))


def _zip_write(zf: zipfile.ZipFile, name: str, payload: bytes) -> None:
    """Write deterministic ZIP members (fixed timestamp and permissions)."""
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    zf.writestr(info, payload)


def export_flight(
    store: EventStore,
    destination: Union[str, Path],
    *,
    bundle_id: str,
    created_at: str,
    after_sequence: int = 0,
    checkpoint_manifest: Optional[Mapping[str, Any]] = None,
    runtime_metadata: Optional[Mapping[str, Any]] = None,
    artifact_refs: Optional[Sequence[Mapping[str, Any]]] = None,
    secret_keys: Optional[Iterable[str]] = None,
    secret_values: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Export an integrity-checkable, read-only `.capt-flight` bundle.

    The bundle captures only data already observable from EventStore plus
    caller-supplied non-authoritative environment/artifact references.
    """
    if not bundle_id:
        raise ValueError("bundle_id is required")
    if not created_at:
        raise ValueError("created_at is required for deterministic provenance")
    if after_sequence < 0:
        raise ValueError("after_sequence must be >= 0")

    custom_secret_keys = tuple(secret_keys or ())
    explicit_secret_values = tuple(secret_values or ())

    ledger_digest = store.verify_chain()
    head = store.head_sequence()
    if after_sequence > head:
        raise ValueError("after_sequence exceeds ledger head")

    events = redact(
        store.read_events(after_sequence=after_sequence),
        secret_keys=custom_secret_keys,
        secret_values=explicit_secret_values,
    )
    aggregate_inventory = []
    aggregate_states: Dict[str, Any] = {}
    for stream_id, kind, version in store.all_aggregates():
        aggregate_inventory.append(
            {"streamId": stream_id, "kind": kind, "version": version}
        )
        aggregate_states[stream_id] = redact(
            store.load_state(stream_id),
            secret_keys=custom_secret_keys,
            secret_values=explicit_secret_values,
        )

    members: Dict[str, bytes] = {
        "events.json": _json_bytes(events),
        "aggregates.json": _json_bytes(
            {
                "inventory": aggregate_inventory,
                "states": aggregate_states,
            }
        ),
        "runtime_metadata.json": _json_bytes(
            redact(
                dict(runtime_metadata or {}),
                secret_keys=custom_secret_keys,
                secret_values=explicit_secret_values,
            )
        ),
        "artifact_refs.json": _json_bytes(
            redact(
                list(artifact_refs or ()),
                secret_keys=custom_secret_keys,
                secret_values=explicit_secret_values,
            )
        ),
    }
    if checkpoint_manifest is not None:
        members["checkpoint.json"] = _json_bytes(
            redact(
                dict(checkpoint_manifest),
                secret_keys=custom_secret_keys,
                secret_values=explicit_secret_values,
            )
        )

    files = {
        name: {"digest": _sha256_bytes(payload), "size": len(payload)}
        for name, payload in sorted(members.items())
    }
    manifest: Dict[str, Any] = {
        "schemaVersion": FLIGHT_SCHEMA_VERSION,
        "kind": "CAPTFlightManifest",
        "bundleId": bundle_id,
        "createdAt": created_at,
        "authority": {
            "classification": "forensic_projection_only",
            "isAuthoritativeRuntimeState": False,
            "isVerificationResult": False,
            "isClaimDecision": False,
            "mayDispatch": False,
        },
        "ledger": {
            "digest": ledger_digest,
            "sequenceStartExclusive": after_sequence,
            "sequenceEndInclusive": head,
        },
        "files": files,
        "redaction": {
            "defaultSecretKeys": sorted(_DEFAULT_SECRET_KEYS),
            "customSecretKeyCount": len(custom_secret_keys),
            "explicitSecretValueCount": len(explicit_secret_values),
        },
        "manifestDigest": "",
    }
    manifest["manifestDigest"] = _manifest_digest(manifest)
    manifest_bytes = _json_bytes(manifest)

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(path), "w") as zf:
        _zip_write(zf, "manifest.json", manifest_bytes)
        for name in sorted(members):
            _zip_write(zf, name, members[name])
    return manifest


def verify_flight(path: Union[str, Path]) -> Dict[str, Any]:
    """Independently verify archive structure and content digests."""
    bundle = Path(path)
    if not bundle.is_file():
        raise IntegrityViolation("flight bundle does not exist: %s" % bundle)
    try:
        with zipfile.ZipFile(str(bundle), "r") as zf:
            names = set(zf.namelist())
            if "manifest.json" not in names:
                raise IntegrityViolation("flight bundle missing manifest.json")
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            if manifest.get("schemaVersion") != FLIGHT_SCHEMA_VERSION:
                raise IntegrityViolation("unsupported flight schema version")
            expected_manifest = manifest.get("manifestDigest")
            if expected_manifest != _manifest_digest(manifest):
                raise IntegrityViolation("flight manifest digest mismatch")
            for name, meta in manifest.get("files", {}).items():
                if name not in names:
                    raise IntegrityViolation("flight bundle missing member %s" % name)
                payload = zf.read(name)
                if len(payload) != int(meta["size"]):
                    raise IntegrityViolation("flight member size mismatch: %s" % name)
                if _sha256_bytes(payload) != meta["digest"]:
                    raise IntegrityViolation("flight member digest mismatch: %s" % name)
            extra = names.difference(set(manifest.get("files", {}))).difference({"manifest.json"})
            if extra:
                raise IntegrityViolation("flight bundle contains unmanifested members: %s" % sorted(extra))
            return manifest
    except zipfile.BadZipFile as exc:
        raise IntegrityViolation("invalid flight archive") from exc
