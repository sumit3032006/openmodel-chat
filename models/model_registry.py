"""Model registry: the single source of truth for which models the app offers.

Built-in models live in models/models.json. Models added by the user are stored in
data/user_models.json (Git-ignored). No model ID is hardcoded anywhere else.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# provider/model-name or provider/model-name:variant (e.g. ":free")
MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*/[A-Za-z0-9][A-Za-z0-9._\-:]*$")


def is_valid_model_id(model_id: str) -> bool:
    return bool(model_id) and len(model_id) <= 200 and bool(MODEL_ID_RE.match(model_id))


class RegistryError(Exception):
    """Raised for invalid registry input or an unreadable built-in model file."""


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    provider: str = ""
    description: str = ""
    builtin: bool = True


class ModelRegistry:
    def __init__(self, builtin_path: Path, user_path: Path) -> None:
        self._builtin_path = Path(builtin_path)
        self._user_path = Path(user_path)
        self._models: dict[str, ModelInfo] = {}
        self._default_id = ""
        self.load()

    # ----- loading -------------------------------------------------------
    def load(self) -> None:
        models: dict[str, ModelInfo] = {}
        try:
            raw = json.loads(self._builtin_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RegistryError(f"Cannot read built-in model list: {exc}") from None

        for item in raw.get("models", []):
            info = self._parse(item, builtin=True)
            if info:
                models[info.id] = info

        for item in self._read_user_models():
            info = self._parse(item, builtin=False)
            if info and info.id not in models:
                models[info.id] = info

        if not models:
            raise RegistryError("No valid models found in models/models.json")

        self._models = models
        wanted = str(raw.get("default_model", ""))
        self._default_id = wanted if wanted in models else next(iter(models))

    def _read_user_models(self) -> list[dict]:
        if not self._user_path.exists():
            return []
        try:
            data = json.loads(self._user_path.read_text(encoding="utf-8"))
            items = data.get("models", [])
            return items if isinstance(items, list) else []
        except (OSError, ValueError, AttributeError):
            log.warning("Ignoring unreadable user model file: %s", self._user_path.name)
            return []

    @staticmethod
    def _parse(item: object, *, builtin: bool) -> ModelInfo | None:
        if not isinstance(item, dict):
            return None
        model_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        if not is_valid_model_id(model_id) or not name:
            log.warning("Skipping invalid model entry: %r", model_id)
            return None
        provider = str(item.get("provider") or model_id.split("/", 1)[0]).strip()
        return ModelInfo(
            id=model_id,
            name=name[:80],
            provider=provider[:60],
            description=str(item.get("description", ""))[:400],
            builtin=builtin,
        )

    # ----- queries -------------------------------------------------------
    @property
    def default_id(self) -> str:
        return self._default_id

    def list(self) -> list[ModelInfo]:
        return list(self._models.values())

    def get(self, model_id: str) -> ModelInfo | None:
        return self._models.get(model_id)

    def name_for(self, model_id: str | None) -> str:
        if not model_id:
            return "Unknown model"
        info = self._models.get(model_id)
        return info.name if info else model_id

    # ----- user models ---------------------------------------------------
    def add_custom(self, name: str, model_id: str, description: str = "") -> ModelInfo:
        name = (name or "").strip()
        model_id = (model_id or "").strip()
        if not name:
            raise RegistryError("Please enter a display name.")
        if len(name) > 80:
            raise RegistryError("Display name is too long (max 80 characters).")
        if not is_valid_model_id(model_id):
            raise RegistryError(
                "Model ID must look like provider/model-name (for example vendor/model:free)."
            )
        if model_id in self._models:
            raise RegistryError("This model ID is already in the list.")
        info = ModelInfo(
            id=model_id,
            name=name,
            provider=model_id.split("/", 1)[0],
            description=(description or "").strip()[:400],
            builtin=False,
        )
        self._models[model_id] = info
        self._save_user_models()
        return info

    def remove_custom(self, model_id: str) -> None:
        info = self._models.get(model_id)
        if info is None:
            return
        if info.builtin:
            raise RegistryError("Built-in models cannot be removed.")
        del self._models[model_id]
        self._save_user_models()

    def _save_user_models(self) -> None:
        custom = [
            {"name": m.name, "id": m.id, "provider": m.provider, "description": m.description}
            for m in self._models.values()
            if not m.builtin
        ]
        self._user_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._user_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"models": custom}, indent=2), encoding="utf-8")
        os.replace(tmp, self._user_path)
