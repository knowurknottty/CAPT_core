"""Install two verified OpenRouter CAPT media routes without dispatching media.

This explicit operator action creates only route configuration, not authorization
for media inference, upload, provider spending, or human verification.
Run via: python -m scripts.seed_verified_media_routes --ui-root ~/.capt/ui --apply
The default invocation is a dry-run and does not edit files.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlsplit

from desktop.media_registry import load_media_routes


def candidate_routes() -> list[dict]:
    return [
        {
            "enabled": True,
            "adapterId": "openrouter-ming-design-r1",
            "provider": "openrouter-image",
            "model": "inclusionai/ming-image-0.1-design",
            "operation": "image_generate",
            "origin": "https://openrouter.ai",
            "transport": "json",
            "submitPath": "/api/v1/images",
            "responseType": "json_base64",
            "mediaTypes": ["image/png", "image/jpeg", "image/webp"],
            "maximumPriceUSD": 0.0,
            "maxAssetBytes": 67108864,
            "authStyle": "bearer",
        },
        {
            "enabled": True,
            "adapterId": "openrouter-deepseek-v41-vision-r1",
            "provider": "openrouter",
            "model": "deepseek/deepseek-v4.1-flash",
            "operation": "image_input",
            "origin": "https://openrouter.ai",
            "transport": "chat_completions",
            "submitPath": "/api/v1/chat/completions",
            "responseType": "json_text",
            "mediaTypes": ["image/png", "image/jpeg", "image/webp", "image/gif"],
            "maximumPriceUSD": 0.05,
            "maxAssetBytes": 12582912,
            "authStyle": "bearer",
        },
    ]


def plan(ui: Path) -> tuple[dict, bool]:
    provider_path = ui / "providers.json"
    route_path = ui / "media-routes.json"
    providers = json.loads(provider_path.read_text(encoding="utf-8"))
    present = {
        p["id"]: p for p in providers.get("providers", [])
        if isinstance(p, dict) and p.get("enabled") is True and isinstance(p.get("id"), str)
    }
    for proposed in candidate_routes():
        provider = present.get(proposed["provider"])
        if provider is None:
            raise ValueError("MEDIA_SEED_PROVIDER_NOT_ENABLED")
        parsed = urlsplit(str(provider.get("base_url") or ""))
        if parsed.scheme + "://" + parsed.netloc != proposed["origin"]:
            raise ValueError("MEDIA_SEED_PROVIDER_ORIGIN_MISMATCH")
        if proposed["model"] not in (provider.get("models") or []):
            raise ValueError("MEDIA_SEED_MODEL_NOT_REGISTERED")
        capabilities = set(provider.get("capabilities") or [])
        required = "image" if proposed["operation"] == "image_generate" else "vision"
        if required not in capabilities:
            raise ValueError("MEDIA_SEED_CAPABILITY_NOT_REGISTERED")

    original = (json.loads(route_path.read_text(encoding="utf-8"))
                if route_path.is_file() else {"schemaVersion": "1.0.0", "routes": []})
    if not isinstance(original, dict) or original.get("schemaVersion") != "1.0.0":
        raise ValueError("MEDIA_SEED_EXISTING_SCHEMA_INVALID")
    old_rows = original.get("routes")
    if not isinstance(old_rows, list):
        raise ValueError("MEDIA_SEED_EXISTING_ROWS_INVALID")
    rows = [dict(row) for row in old_rows]
    by_id = {row.get("adapterId"): row for row in rows if isinstance(row, dict)}
    if len(by_id) != len(rows):
        raise ValueError("MEDIA_SEED_DUPLICATE_OR_NONOBJECT_ROW")
    for proposed in candidate_routes():
        old = by_id.get(proposed["adapterId"])
        if old is not None and old != proposed:
            raise ValueError("MEDIA_SEED_ROUTE_CONFLICT")
        if old is None:
            rows.append(proposed)
    candidate = dict(original)
    candidate["routes"] = rows
    return candidate, candidate != original


def validate_against_provider_registry(ui: Path, config: dict) -> None:
    # Reuse the production loader without modifying the live registry first.
    with tempfile.TemporaryDirectory(prefix="capt-media-stage-") as temporary:
        staging = Path(temporary)
        shutil.copyfile(ui / "providers.json", staging / "providers.json")
        (staging / "media-routes.json").write_text(
            json.dumps(config, sort_keys=True), encoding="utf-8"
        )
        registry, _ = load_media_routes(staging)
        expected = {entry["adapterId"] for entry in candidate_routes()}
        if not expected.issubset(registry.routes):
            raise ValueError("MEDIA_SEED_LOADER_REJECTED_ROUTE")


def install(ui: Path, *, apply: bool = False) -> str:
    ui = ui.expanduser().resolve(strict=True)
    path = ui / "media-routes.json"
    if path.is_symlink():
        raise ValueError("MEDIA_SEED_SYMLINK_REFUSED")
    original_bytes = path.read_bytes() if path.exists() else None
    original_hash = (hashlib.sha256(original_bytes).hexdigest()
                     if original_bytes is not None else None)
    proposed, changed = plan(ui)
    validate_against_provider_registry(ui, proposed)
    if not apply:
        return "VALIDATED_DRY_RUN"
    if not changed:
        return "ALREADY_CONFIGURED"
    current = path.read_bytes() if path.exists() else None
    current_hash = (hashlib.sha256(current).hexdigest()
                    if current is not None else None)
    if original_hash != current_hash:
        raise ValueError("MEDIA_SEED_CONCURRENT_CHANGE_REFUSED")
    backup = None
    if path.exists():
        backup = ui / ("media-routes.backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
        if backup.exists():
            raise ValueError("MEDIA_SEED_BACKUP_COLLISION")
        shutil.copy2(path, backup)
        os.chmod(backup, 0o600)
    content = json.dumps(proposed, indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".media-routes-", suffix=".json", dir=ui)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    # Independent production-loader check after mutation; never dispatch a model.
    try:
        registry, _ = load_media_routes(ui)
        if len({x["adapterId"] for x in candidate_routes()} & set(registry.routes)) != 2:
            raise RuntimeError("MEDIA_SEED_POSTINSTALL_VALIDATION_FAILED")
    except Exception:
        # Do not leave an unverified operator configuration installed.
        if backup is not None:
            os.replace(backup, path)
        elif path.exists():
            path.unlink()
        raise
    return "APPLIED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Explicitly write route registry; no inference")
    args = parser.parse_args()
    print(install(args.ui_root, apply=args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
