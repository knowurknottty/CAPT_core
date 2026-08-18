"""CAPT-UPG-012 tests for the read-only `.capt-flight` forensic bundle."""

import json
import zipfile

import pytest

from capt_runtime.errors import IntegrityViolation
from capt_runtime.flight_recorder import export_flight, verify_flight
from capt_runtime.store import EventStore


def test_flight_bundle_is_deterministic_redacted_read_only_and_verifiable(tmp_path):
    store = EventStore(str(tmp_path / "runtime.db"))
    before_head = store.head_sequence()
    before_aggregates = store.all_aggregates()

    metadata = {
        "runtime": "capt-test",
        "api_key": "sk-should-never-appear",
        "nested": {
            "Authorization": "Bearer abc123",
            "safe": "visible",
            "message": "prefix explicit-secret suffix",
        },
    }
    kwargs = dict(
        bundle_id="flight-test-1",
        created_at="2026-08-18T00:00:00Z",
        runtime_metadata=metadata,
        artifact_refs=[
            {
                "path": "artifact.txt",
                "digest": "sha256:" + "1" * 64,
                "credentialNote": "explicit-secret",
            }
        ],
        secret_keys=("credentialNote",),
        secret_values=("explicit-secret",),
    )

    first_path = tmp_path / "first.capt-flight"
    second_path = tmp_path / "second.capt-flight"
    first = export_flight(store, first_path, **kwargs)
    second = export_flight(store, second_path, **kwargs)

    assert first["manifestDigest"] == second["manifestDigest"]
    assert first["authority"] == {
        "classification": "forensic_projection_only",
        "isAuthoritativeRuntimeState": False,
        "isVerificationResult": False,
        "isClaimDecision": False,
        "mayDispatch": False,
    }
    assert store.head_sequence() == before_head
    assert store.all_aggregates() == before_aggregates

    verified = verify_flight(first_path)
    assert verified["manifestDigest"] == first["manifestDigest"]

    with zipfile.ZipFile(str(first_path), "r") as zf:
        runtime_metadata = json.loads(zf.read("runtime_metadata.json").decode("utf-8"))
        artifact_refs = json.loads(zf.read("artifact_refs.json").decode("utf-8"))
        assert runtime_metadata["api_key"] == "<redacted>"
        assert runtime_metadata["nested"]["Authorization"] == "<redacted>"
        assert runtime_metadata["nested"]["safe"] == "visible"
        assert runtime_metadata["nested"]["message"] == "prefix <redacted> suffix"
        assert artifact_refs[0]["credentialNote"] == "<redacted>"
        archive_bytes = first_path.read_bytes()
        assert b"sk-should-never-appear" not in archive_bytes
        assert b"Bearer abc123" not in archive_bytes
        assert b"explicit-secret" not in archive_bytes

    store.close()


def test_flight_bundle_tamper_is_detected(tmp_path):
    store = EventStore(str(tmp_path / "runtime.db"))
    source = tmp_path / "source.capt-flight"
    export_flight(
        store,
        source,
        bundle_id="flight-tamper-1",
        created_at="2026-08-18T00:00:00Z",
        runtime_metadata={"safe": "original"},
    )
    store.close()

    tampered = tmp_path / "tampered.capt-flight"
    with zipfile.ZipFile(str(source), "r") as src, zipfile.ZipFile(str(tampered), "w") as dst:
        for info in src.infolist():
            payload = src.read(info.filename)
            if info.filename == "runtime_metadata.json":
                payload = b'{"safe":"tampered"}'
            dst.writestr(info, payload)

    with pytest.raises(IntegrityViolation, match="digest mismatch"):
        verify_flight(tampered)


def test_flight_bundle_rejects_unmanifested_members(tmp_path):
    store = EventStore(str(tmp_path / "runtime.db"))
    source = tmp_path / "source.capt-flight"
    export_flight(
        store,
        source,
        bundle_id="flight-extra-1",
        created_at="2026-08-18T00:00:00Z",
    )
    store.close()

    altered = tmp_path / "extra.capt-flight"
    with zipfile.ZipFile(str(source), "r") as src, zipfile.ZipFile(str(altered), "w") as dst:
        for info in src.infolist():
            dst.writestr(info, src.read(info.filename))
        dst.writestr("untracked.txt", b"unexpected")

    with pytest.raises(IntegrityViolation, match="unmanifested"):
        verify_flight(altered)
