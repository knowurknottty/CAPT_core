"""Operator seed is fail-closed, deterministic, and does not grant media authority."""
import json
from pathlib import Path

import pytest

from scripts.seed_verified_media_routes import candidate_routes, install


def prepared_ui(tmp_path: Path) -> Path:
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "providers.json").write_text(json.dumps({"providers": [
        {
            "id": "openrouter",
            "enabled": True,
            "models": ["deepseek/deepseek-v4.1-flash"],
            "capabilities": ["vision", "chat"],
            "base_url": "https://openrouter.ai/api/v1",
        },
        {
            "id": "openrouter-image",
            "enabled": True,
            "models": ["inclusionai/ming-image-0.1-design"],
            "capabilities": ["image"],
            "base_url": "https://openrouter.ai/api/v1",
        },
    ]}))
    (ui / "media-routes.json").write_text(json.dumps({
        "schemaVersion": "1.0.0",
        "routes": [{"enabled": False, "adapterId": "placeholder"}],
    }))
    return ui


def test_dry_run_does_not_write_and_validates_loader(tmp_path):
    ui = prepared_ui(tmp_path)
    before = (ui / "media-routes.json").read_bytes()
    assert install(ui) == "VALIDATED_DRY_RUN"
    assert (ui / "media-routes.json").read_bytes() == before


def test_apply_preserves_disabled_rows_and_is_idempotent(tmp_path):
    ui = prepared_ui(tmp_path)
    assert install(ui, apply=True) == "APPLIED"
    path = ui / "media-routes.json"
    obj = json.loads(path.read_text())
    assert len(obj["routes"]) == 3
    assert obj["routes"][0] == {"enabled": False, "adapterId": "placeholder"}
    assert {r["adapterId"] for r in obj["routes"][1:]} == {
        c["adapterId"] for c in candidate_routes()
    }
    assert path.stat().st_mode & 0o777 == 0o600
    assert install(ui, apply=True) == "ALREADY_CONFIGURED"


def test_refuses_to_overwrite_conflicting_operator_route(tmp_path):
    ui = prepared_ui(tmp_path)
    path = ui / "media-routes.json"
    path.write_text(json.dumps({"schemaVersion": "1.0.0", "routes": [
        {"adapterId": "openrouter-ming-design-r1", "enabled": False}
    ]}))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="MEDIA_SEED_ROUTE_CONFLICT"):
        install(ui, apply=True)
    assert path.read_bytes() == before


def test_refuses_unregistered_provider_capability(tmp_path):
    ui = prepared_ui(tmp_path)
    p = ui / "providers.json"
    source = json.loads(p.read_text())
    source["providers"][1]["capabilities"] = ["chat"]
    p.write_text(json.dumps(source))
    original = (ui / "media-routes.json").read_bytes()
    with pytest.raises(ValueError, match="MEDIA_SEED_CAPABILITY_NOT_REGISTERED"):
        install(ui, apply=True)
    assert (ui / "media-routes.json").read_bytes() == original
