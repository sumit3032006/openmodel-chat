"""Checks which models OpenRouter currently lists, and exposes live model metadata."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from services.errors import ChatError

log = logging.getLogger(__name__)


class Availability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RemoteModel:
    id: str
    name: str = ""
    description: str = ""
    context_length: int | None = None
    input_modalities: tuple[str, ...] = ()
    expiration_date: str | None = None


def _parse(item: dict) -> RemoteModel | None:
    model_id = item.get("id")
    if not isinstance(model_id, str) or not model_id:
        return None
    arch = item.get("architecture") if isinstance(item.get("architecture"), dict) else {}
    modalities = arch.get("input_modalities")
    ctx = item.get("context_length")
    exp = item.get("expiration_date")
    return RemoteModel(
        id=model_id,
        name=str(item.get("name") or ""),
        description=str(item.get("description") or ""),
        context_length=ctx if isinstance(ctx, int) and not isinstance(ctx, bool) else None,
        input_modalities=tuple(str(m) for m in modalities) if isinstance(modalities, list) else (),
        expiration_date=str(exp) if exp else None,
    )


class ModelService:
    def __init__(self, client_factory: Callable[[], Any], ttl_seconds: float = 600.0) -> None:
        self._factory = client_factory
        self._ttl = ttl_seconds
        self._catalog: dict[str, RemoteModel] | None = None
        self._fetched_at = 0.0
        self.last_error: str | None = None

    @property
    def loaded(self) -> bool:
        return self._catalog is not None

    async def refresh(self, force: bool = False) -> bool:
        """Fetch the live catalogue. Returns True on success. Keeps old data on failure."""
        fresh = self._catalog is not None and (time.monotonic() - self._fetched_at) < self._ttl
        if fresh and not force:
            return True
        try:
            items = await self._factory().list_models()
        except ChatError as exc:
            self.last_error = exc.message
            log.warning("Model catalogue refresh failed: %s", exc.code)
            return False
        catalog: dict[str, RemoteModel] = {}
        for item in items:
            parsed = _parse(item)
            if parsed:
                catalog[parsed.id] = parsed
        self._catalog = catalog
        self._fetched_at = time.monotonic()
        self.last_error = None
        return True

    def availability(self, model_id: str) -> Availability:
        if self._catalog is None:
            return Availability.UNKNOWN
        return Availability.AVAILABLE if model_id in self._catalog else Availability.UNAVAILABLE

    def remote(self, model_id: str) -> RemoteModel | None:
        return self._catalog.get(model_id) if self._catalog else None

    def status_text(self, model_id: str) -> str:
        status = self.availability(model_id)
        if status is Availability.AVAILABLE:
            return "Listed on OpenRouter"
        if status is Availability.UNAVAILABLE:
            return "Not listed on OpenRouter - it may be deprecated or renamed"
        return "Availability not checked yet" if not self.last_error else "Could not check availability"
