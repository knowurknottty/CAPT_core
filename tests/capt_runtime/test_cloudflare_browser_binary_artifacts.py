from __future__ import annotations

import base64
import hashlib
from datetime import date, datetime, timezone

import pytest

from capt_runtime.tools.backends.cloudflare_artifacts import (
    MAX_CLOUDFLARE_ARTIFACT_CHUNK_BYTES,
    CloudflareBinaryArtifactSpool,
)
from capt_runtime.tools.backends.cloudflare_native import (
    CloudflareBrowserAction,
    CloudflareBrowserRunner,
    CloudflareNativeIndeterminate,
)
from capt_runtime.tools.backends.cloudflare_native_api import (
    CloudflareNativeAPIBridge,
    CloudflareNativeAPIProfile,
)

PNG = b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * 256
PDF = b"%PDF-1.7\\n" + b"p" * 512

def test_binary_artifact_spool_persists_digest_and_bounded_chunks(tmp_path):
    spool = CloudflareBinaryArtifactSpool(tmp_path / "artifacts")
    manifest = spool.capture(
        operation_id="browser-bin-1",
        action=CloudflareBrowserAction.SCREENSHOT,
        media_type="image/png",
        data=PNG,
    )
    assert manifest["ref"].startswith("cloudflare-artifact://")
    assert manifest["sha256"] == "sha256:" + hashlib.sha256(PNG).hexdigest()
    assert manifest["bytes"] == len(PNG)
    reopened = CloudflareBinaryArtifactSpool(tmp_path / "artifacts")
    first = reopened.read(
        operation_id="browser-bin-1", ref=manifest["ref"], offset=0, limit=64
    )
    assert base64.b64decode(first["dataBase64"]) == PNG[:64]
    with pytest.raises(PermissionError, match="cloudflare_artifact_operation_mismatch"):
        reopened.read(operation_id="other-op", ref=manifest["ref"], offset=0, limit=64)
    with pytest.raises(ValueError, match="cloudflare_artifact_limit_out_of_range"):
        reopened.read(
            operation_id="browser-bin-1",
            ref=manifest["ref"],
            offset=0,
            limit=MAX_CLOUDFLARE_ARTIFACT_CHUNK_BYTES + 1,
        )

class BinaryResponse:
    def __init__(self, data: bytes, content_type: str):
        self.data = data
        self.headers = {"Content-Type": content_type}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size=-1):
        return self.data if size is None or size < 0 else self.data[:size]

class BinaryRecorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def __call__(self, request, timeout):
        self.calls.append(request)
        return self.responses.pop(0)

def profile():
    return CloudflareNativeAPIProfile(
        account_id="acct-1",
        api_token_env="CF_API_TOKEN",
        worker_base_url="https://capt-control.example.workers.dev",
        worker_auth_env="CF_WORKER_TOKEN",
    )

@pytest.mark.parametrize(
    ("action", "payload", "media_type", "expected"),
    [
        (CloudflareBrowserAction.SCREENSHOT, PNG, "image/png", "encoding=binary"),
        (CloudflareBrowserAction.PDF, PDF, "application/pdf", "/browser-rendering/pdf"),
    ],
)
def test_bridge_spools_binary_browser_artifacts(
    tmp_path, monkeypatch, action, payload, media_type, expected
):
    monkeypatch.setenv("CF_API_TOKEN", "secret")
    spool = CloudflareBinaryArtifactSpool(tmp_path / "artifacts")
    opener = BinaryRecorder([BinaryResponse(payload, media_type)])
    bridge = CloudflareNativeAPIBridge(profile(), opener=opener, artifact_spool=spool)
    result = bridge.browser_run(
        operation_id=f"browser-{action.value}",
        action=action,
        arguments={"url": "https://example.com"},
        estimated_seconds=3,
    )
    assert expected in opener.calls[0].full_url
    assert result["artifactRef"].startswith("cloudflare-artifact://")
    assert result["artifactSha256"] == "sha256:" + hashlib.sha256(payload).hexdigest()
    assert result["artifactBytes"] == len(payload)
    assert result["mediaType"] == media_type
    assert result["artifactAction"] == action.value

@pytest.mark.parametrize(
    ("action", "media_type"),
    [
        (CloudflareBrowserAction.SCREENSHOT, "application/pdf"),
        (CloudflareBrowserAction.PDF, "image/png"),
    ],
)
def test_binary_browser_media_mismatch_is_post_dispatch_indeterminate(
    tmp_path, monkeypatch, action, media_type
):
    monkeypatch.setenv("CF_API_TOKEN", "secret")
    payload = PDF if media_type == "application/pdf" else PNG
    opener = BinaryRecorder([BinaryResponse(payload, media_type)])
    bridge = CloudflareNativeAPIBridge(
        profile(),
        opener=opener,
        artifact_spool=CloudflareBinaryArtifactSpool(tmp_path / "artifacts"),
    )
    with pytest.raises(RuntimeError, match="cloudflare_browser_binary_media_type_mismatch"):
        bridge.browser_run(
            operation_id="browser-media-bad",
            action=action,
            arguments={"url": "https://example.com"},
            estimated_seconds=2,
        )
    assert len(opener.calls) == 1

def test_browser_runner_keeps_reservation_locked_on_binary_evidence_failure(tmp_path):
    from capt_runtime.tools.backends.cloudflare_free_planner import (
        CloudflareFreeExecutionPlanner,
    )
    from capt_runtime.tools.backends.cloudflare_free_router import (
        CloudflareFreeTierRouter,
    )
    from capt_runtime.tools.backends.cloudflare_usage import CloudflareUsageLedger
    router = CloudflareFreeTierRouter.default()
    ledger = CloudflareUsageLedger(tmp_path / "usage.sqlite", router=router)
    planner = CloudflareFreeExecutionPlanner(
        ledger, router, now=lambda: datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    )
    class Bridge:
        def browser_run(self, **kwargs):
            raise RuntimeError("cloudflare_browser_binary_media_type_mismatch")
    runner = CloudflareBrowserRunner(planner, Bridge())
    with pytest.raises(
        CloudflareNativeIndeterminate, match="browser_run_outcome_unclassified"
    ):
        runner.run(
            operation_id="browser-indeterminate-1",
            action=CloudflareBrowserAction.PDF,
            arguments={"url": "https://example.com"},
            estimated_seconds=2,
            day=date(2026, 9, 9),
        )
    assert ledger.snapshot(day=date(2026, 9, 9)).browser_seconds == 2
    ledger.close()


def test_browser_runner_preserves_binary_artifact_manifest(tmp_path):
    from capt_runtime.tools.backends.cloudflare_free_planner import (
        CloudflareFreeExecutionPlanner,
    )
    from capt_runtime.tools.backends.cloudflare_free_router import (
        CloudflareFreeTierRouter,
    )
    from capt_runtime.tools.backends.cloudflare_usage import CloudflareUsageLedger

    router = CloudflareFreeTierRouter.default()
    ledger = CloudflareUsageLedger(tmp_path / "manifest-usage.sqlite", router=router)
    planner = CloudflareFreeExecutionPlanner(
        ledger, router, now=lambda: datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    )

    class Bridge:
        def browser_run(self, **kwargs):
            return {
                "browserSeconds": 2,
                "artifactRef": "cloudflare-artifact://" + "a" * 64,
                "artifactSha256": "sha256:" + "b" * 64,
                "artifactBytes": 512,
                "mediaType": "application/pdf",
                "artifactAction": "pdf",
                "usageBasis": "reserved_ceiling",
            }

    result = CloudflareBrowserRunner(planner, Bridge()).run(
        operation_id="browser-manifest-1",
        action=CloudflareBrowserAction.PDF,
        arguments={"url": "https://example.com"},
        estimated_seconds=2,
        day=date(2026, 9, 9),
    )
    assert result.artifact_sha256 == "sha256:" + "b" * 64
    assert result.artifact_bytes == 512
    assert result.media_type == "application/pdf"
    assert result.artifact_action == "pdf"
    ledger.close()


def test_binary_artifact_read_detects_same_size_tampering(tmp_path):
    spool = CloudflareBinaryArtifactSpool(tmp_path / "tamper")
    manifest = spool.capture(
        operation_id="browser-tamper-1",
        action=CloudflareBrowserAction.PDF,
        media_type="application/pdf",
        data=PDF,
    )
    token = manifest["ref"].split("://", 1)[1]
    data_path = spool.root / f"{token}.bin"
    data_path.write_bytes(b"z" * len(PDF))
    with pytest.raises(RuntimeError, match="cloudflare_artifact_digest_integrity_mismatch"):
        spool.read(
            operation_id="browser-tamper-1",
            ref=manifest["ref"],
            offset=0,
            limit=64,
        )
