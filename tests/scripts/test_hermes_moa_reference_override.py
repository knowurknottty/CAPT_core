import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ensure_hermes_moa_reference_override.py"
SPEC = importlib.util.spec_from_file_location("hermes_moa_override", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


SOURCE = '''from typing import Optional, Union, Callable, Tuple, Any
_ResolveResult = Tuple[Optional[Any], Optional[str]]
class OpenAI: pass
def _aux_openrouter_settings(): return True, "paid/model"
def _is_free_model(model): return False
def _warn_paid_lane_once(model: str) -> None:
    pass
def _select_pool_entry(name): return False, None
def _scoped_key_env(name): return None
def _describe_openrouter_unavailable(model: str = None) -> str:
    """Return the policy or credential reason OpenRouter was unavailable."""
    free_only, cfg_model = _aux_openrouter_settings()
    or_model = model or cfg_model
    if free_only and not _is_free_model(or_model):
        return "blocked"
    return "none"
'''

SOURCE += '''
def _try_openrouter(explicit_api_key: Optional[Union[str, Callable[[], str]]] = None, model: str = None) -> Tuple[Optional[OpenAI], Optional[str]]:
    free_only, cfg_model = _aux_openrouter_settings()
    or_model = model or cfg_model
    if free_only and not _is_free_model(or_model):
        return None, None
    return OpenAI(), or_model

class _ResolveRequest:
    def __init__(self, task=None, explicit_api_key=None, model=None, provider="openrouter"):
        self.task=task; self.explicit_api_key=explicit_api_key; self.model=model; self.provider=provider

def _route_client(req, client, model): return client, model
def _normalize_resolved_model(model, provider): return model

def _resolve_openrouter_branch(req: _ResolveRequest) -> _ResolveResult:
    """OpenRouter."""
    client, default = _try_openrouter(explicit_api_key=req.explicit_api_key, model=req.model)
    if client is None:
        import logging
        logger=logging.getLogger(__name__)
        logger.warning("resolve_provider_client: openrouter requested but %s",
                       _describe_openrouter_unavailable(model=req.model))
        return None, None
    return _route_client(req, client, _normalize_resolved_model(req.model or default, req.provider))
'''

CONFIG = '''auxiliary:
  free_only: true
  openrouter_model: nvidia/nemotron:free
  moa_reference:
    timeout: 21600
  moa_aggregator:
    timeout: 21600
'''


def test_source_patch_is_narrow_and_idempotent():
    patched = MODULE.patch_source(SOURCE)
    assert MODULE.source_is_patched(patched)
    assert "if free_only and not allow_paid and not _is_free_model(or_model)" in patched
    assert MODULE.patch_source(patched) == patched


def test_config_patch_adds_only_reference_opt_in():
    patched = MODULE.patch_config(CONFIG)
    assert MODULE.config_has_opt_in(patched)
    assert "free_only: true" in patched
    assert "moa_reference:\n    allow_paid: true" in patched


def test_apply_writes_backups_and_conformant_state(tmp_path):
    root = tmp_path / "hermes"
    source = root / "agent" / "auxiliary_client.py"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE)
    config = tmp_path / "config.yaml"
    config.write_text(CONFIG)
    backup = tmp_path / "backups"

    result = MODULE.apply(root, config, backup)
    assert result["conformant"] is True
    assert list(backup.glob("auxiliary_client.*.bak"))
    assert list(backup.glob("config.*.bak"))

