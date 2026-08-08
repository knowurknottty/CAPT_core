"""Model Manager (UI-1 / Phase 3).

Users never edit configuration files. This layer owns:
- installed/available models per provider,
- favorites,
- default model,
- mission override,
- temporary override,
- provider badge,
- context size,
- health,
and persists the active selection.

Thin client: selection is operator preference state, not runtime authority.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .contract import ModelScope
from .providers import ProviderManager


@dataclass
class ModelEntry:
    provider_id: str
    model_id: str
    provider_name: str = ""
    kind: str = "LOCAL"
    context: int = 0
    favorite: bool = False
    scopes: List[str] = field(default_factory=list)  # where this is active


class ModelManager:
    def __init__(self, config_dir: Optional[Path] = None, providers: Optional[ProviderManager] = None) -> None:
        self._providers = providers or ProviderManager(config_dir)
        cfg = config_dir or self._default_config_dir()
        cfg.mkdir(parents=True, exist_ok=True)
        self._file = cfg / "models.json"
        self._state: Dict[str, Any] = {
            "favorites": [],
            "default": None,          # {provider, model}
            "mission_override": None,  # {mission, provider, model}
            "temporary_override": None,# {provider, model}
            "workflow": {},
        }
        self._load()

    @staticmethod
    def _default_config_dir() -> Path:
        override = os.environ.get("CAPT_SOLO_HOME") or os.environ.get("CAPT_STATE_DIR")
        if override:
            return Path(override).expanduser() / "ui"
        return Path.home() / ".capt" / "ui"

    def _load(self) -> None:
        if self._file.exists():
            try:
                self._state.update(json.loads(self._file.read_text()))
            except Exception:  # noqa: BLE001 - corrupt -> defaults
                pass

    def save(self) -> None:
        self._file.write_text(json.dumps(self._state, indent=2))

    # -- available models ------------------------------------------------
    def available(self) -> List[ModelEntry]:
        """Merged available models across enabled providers."""
        out: List[ModelEntry] = []
        for p in self._providers.list():
            if not p.enabled:
                continue
            for mid in p.models or []:
                out.append(ModelEntry(
                    provider_id=p.id, model_id=mid,
                    provider_name=p.name, kind=self._providers.label(p),
                    context=p.context_limit,
                    favorite=mid in self._state.get("favorites", []),
                ))
        return out

    def favorites(self) -> List[ModelEntry]:
        faves = set(self._state.get("favorites", []))
        return [m for m in self.available() if m.model_id in faves]

    def toggle_favorite(self, model_id: str) -> bool:
        faves = set(self._state.get("favorites", []))
        if model_id in faves:
            faves.discard(model_id)
            fav = False
        else:
            faves.add(model_id)
            fav = True
        self._state["favorites"] = sorted(faves)
        self.save()
        return fav

    # -- active model (always visible) -----------------------------------
    def active(self) -> ModelEntry:
        """Resolve the current active model by scope precedence:
        temporary > mission > workflow > default > first available."""
        st = self._state
        temp = st.get("temporary_override")
        if temp and temp.get("model"):
            return self._entry(temp["provider"], temp["model"])
        miss = st.get("mission_override")
        if miss and miss.get("model"):
            return self._entry(miss["provider"], miss["model"])
        default = st.get("default")
        if default and default.get("model"):
            return self._entry(default["provider"], default["model"])
        av = self.available()
        if av:
            return av[0]
        return ModelEntry(provider_id="", model_id="", kind="UNKNOWN")

    def _entry(self, provider_id: str, model_id: str) -> ModelEntry:
        p = self._providers.get(provider_id)
        return ModelEntry(
            provider_id=provider_id, model_id=model_id,
            provider_name=p.name if p else provider_id,
            kind=self._providers.label(p) if p else "UNKNOWN",
            context=p.context_limit if p else 0,
        )

    # -- setters ----------------------------------------------------------
    def set_default(self, provider_id: str, model_id: str) -> None:
        self._state["default"] = {"provider": provider_id, "model": model_id}
        self.save()

    def set_mission_override(self, mission_id: str, provider_id: str, model_id: str) -> None:
        self._state["mission_override"] = {
            "mission": mission_id, "provider": provider_id, "model": model_id,
        }
        self.save()

    def clear_mission_override(self) -> None:
        self._state["mission_override"] = None
        self.save()

    def set_temporary(self, provider_id: str, model_id: str) -> None:
        self._state["temporary_override"] = {"provider": provider_id, "model": model_id}
        self.save()

    def clear_temporary(self) -> None:
        self._state["temporary_override"] = None
        self.save()

    def set_workflow(self, workflow_id: str, provider_id: str, model_id: str) -> None:
        self._state["workflow"][workflow_id] = {"provider": provider_id, "model": model_id}
        self.save()

    # -- summary ----------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        active = self.active()
        return {
            "active": {
                "provider": active.provider_id,
                "model": active.model_id,
                "kind": active.kind,
                "context": active.context,
            },
            "default": self._state.get("default"),
            "mission_override": self._state.get("mission_override"),
            "temporary_override": self._state.get("temporary_override"),
            "favorites": self._state.get("favorites", []),
        }