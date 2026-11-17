"""Chat orchestration: validates input, streams a reply, and saves real metrics."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable

from database.chat_database import DEFAULT_TITLE, ChatDatabase, MessageRecord
from models.model_registry import is_valid_model_id
from services.errors import ChatError
from services.key_store import KeyStore

MAX_MESSAGE_CHARS = 20_000


@dataclass
class GenerationEvent:
    kind: str  # "delta" | "final"
    text: str = ""
    message: MessageRecord | None = None


def make_title(text: str, limit: int = 48) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else line[: limit - 1].rstrip() + "\u2026"


class ChatService:
    def __init__(self, db: ChatDatabase, key_store: KeyStore,
                 client_factory: Callable[[str], Any]) -> None:
        self._db = db
        self._keys = key_store
        self._client_factory = client_factory

    def add_user_message(self, conversation_id: str, text: str) -> MessageRecord:
        text = (text or "").strip()
        if not text:
            raise ChatError("Type a message first.", code="empty")
        if len(text) > MAX_MESSAGE_CHARS:
            raise ChatError(f"Message is too long (max {MAX_MESSAGE_CHARS:,} characters).",
                            code="too_long")
        conv = self._db.get_conversation(conversation_id)
        if conv is None:
            raise ChatError("This conversation no longer exists.", code="missing")
        msg = self._db.add_message(conversation_id, "user", text)
        if conv.title == DEFAULT_TITLE:
            self._db.rename_conversation(conversation_id, make_title(text))
        return msg

    def build_payload(self, conversation_id: str, system_prompt: str = "") -> list[dict[str, str]]:
        payload: list[dict[str, str]] = []
        if system_prompt.strip():
            payload.append({"role": "system", "content": system_prompt.strip()})
        for m in self._db.get_messages(conversation_id):
            if m.content.strip():
                payload.append({"role": m.role, "content": m.content})
        return payload

    async def generate(
        self,
        conversation_id: str,
        model_id: str,
        *,
        system_prompt: str = "",
        temperature: float | None = None,
    ) -> AsyncIterator[GenerationEvent]:
        key = self._keys.get()
        if not key:
            raise ChatError("Add your OpenRouter API key first (sidebar -> API key).", code="no_key")
        if not is_valid_model_id(model_id):
            raise ChatError("The selected model ID is not valid.", code="bad_model")
        payload = self.build_payload(conversation_id, system_prompt)
        if not any(m["role"] == "user" for m in payload):
            raise ChatError("There is no message to send.", code="empty")

        client = self._client_factory(key)
        parts: list[str] = []
        usage = None
        started = time.perf_counter()

        def elapsed_ms() -> int:
            return int((time.perf_counter() - started) * 1000)

        def save_partial(status: str) -> None:
            text = "".join(parts)
            if text.strip():
                self._db.add_message(conversation_id, "assistant", text, model_id=model_id,
                                     status=status, response_ms=elapsed_ms())

        try:
            async for chunk in client.stream_chat(model_id, payload, temperature=temperature):
                if chunk.delta:
                    parts.append(chunk.delta)
                    yield GenerationEvent("delta", chunk.delta)
                if chunk.usage:
                    usage = chunk.usage
        except asyncio.CancelledError:
            save_partial("stopped")
            raise
        except ChatError:
            save_partial("error")
            raise

        text = "".join(parts)
        if not text.strip():
            raise ChatError("The model returned an empty response. Try again or switch models.",
                            code="empty_response", retryable=True)
        message = self._db.add_message(
            conversation_id, "assistant", text, model_id=model_id, status="complete",
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            response_ms=elapsed_ms(),
        )
        yield GenerationEvent("final", message=message)
