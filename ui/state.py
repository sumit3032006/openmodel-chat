"""Per-browser-tab UI session. Components register refresh callbacks here."""
from __future__ import annotations

import asyncio
from typing import Callable

from nicegui import ui

from services.container import Services
from services.errors import ChatError


class Session:
    def __init__(self, services: Services) -> None:
        self.s = services
        self.conversation_id: str | None = None
        saved = services.db.get_setting("model_id")
        self.model_id: str = saved if services.registry.get(saved) else services.registry.default_id
        self.search = ""
        self.generating = False
        self.task: asyncio.Task | None = None
        self.last_error: ChatError | None = None
        self.callbacks: dict[str, Callable[[], None]] = {}
        self.chat = None  # set by page.py (ChatView)

    # ----- wiring --------------------------------------------------------
    def notify_changed(self, *names: str) -> None:
        for name in names:
            callback = self.callbacks.get(name)
            if callback:
                callback()

    # ----- settings ------------------------------------------------------
    def system_prompt(self) -> str:
        return self.s.db.get_setting("system_prompt", "")

    def temperature(self) -> float | None:
        raw = self.s.db.get_setting("temperature", "")
        try:
            return float(raw) if raw != "" else None
        except ValueError:
            return None

    # ----- conversations and models --------------------------------------
    def _busy(self) -> bool:
        if self.generating:
            ui.notify("Stop the current response first.", type="warning")
        return self.generating

    def new_conversation(self) -> None:
        if self._busy():
            return
        self.conversation_id = None
        self.last_error = None
        self.notify_changed("sidebar_list", "header", "chat")

    def open_conversation(self, conversation_id: str) -> None:
        if self._busy():
            return
        conv = self.s.db.get_conversation(conversation_id)
        if conv is None:
            return
        self.conversation_id = conv.id
        self.model_id = conv.model_id
        self.last_error = None
        self.notify_changed("model_select", "model_panel", "sidebar_list", "header", "chat")

    def select_model(self, model_id: str) -> None:
        if not model_id or model_id == self.model_id:
            return
        self.model_id = model_id
        self.s.db.set_setting("model_id", model_id)
        if self.conversation_id:
            self.s.db.set_conversation_model(self.conversation_id, model_id)
        self.notify_changed("model_panel", "header", "chat")

    def delete_conversation(self, conversation_id: str) -> None:
        if self._busy():
            return
        self.s.db.delete_conversation(conversation_id)
        if self.conversation_id == conversation_id:
            self.conversation_id = None
        self.notify_changed("sidebar_list", "header", "chat")

    # ----- API key gate ----------------------------------------------------
    async def ensure_key_ready(self) -> bool:
        keys = self.s.key_store
        if not keys.has_key:
            ui.notify("Add your OpenRouter API key to start chatting.", type="warning")
            self.notify_changed("open_key_dialog")
            return False
        if keys.is_validated():
            return True
        try:
            await self.s.client_factory(keys.get()).validate_key()
        except ChatError as exc:
            ui.notify(exc.message, type="negative", multi_line=True)
            if exc.code in ("invalid_key", "bad_response"):
                self.notify_changed("open_key_dialog")
            return False
        keys.mark_validated()
        self.notify_changed("key_status")
        return True
