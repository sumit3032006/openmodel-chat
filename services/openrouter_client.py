"""Thin async wrapper around the OpenRouter API (OpenAI-compatible SDK + httpx).

SDK imports are lazy so the rest of the app (and the tests) work without network or SDK.
The API key is only ever placed in the Authorization header and never in error text.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator

from services.errors import ChatError, from_error_payload, from_status, map_exception
from services.key_store import KeyStore


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class StreamChunk:
    delta: str = ""
    usage: Usage | None = None
    finish_reason: str | None = None


@dataclass(frozen=True)
class KeyInfo:
    is_free_tier: bool | None = None
    usage: float | None = None
    limit: float | None = None


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse_usage(raw: Any) -> Usage | None:
    """Only returns numbers the API actually reported - never estimates."""
    if raw is None:
        return None
    get = raw.get if isinstance(raw, dict) else lambda k, d=None: getattr(raw, k, d)
    prompt = _as_int(get("prompt_tokens"))
    completion = _as_int(get("completion_tokens"))
    total = _as_int(get("total_tokens"))
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    if prompt is None and completion is None and total is None:
        return None
    return Usage(prompt, completion, total)


class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str, timeout: float = 90.0) -> None:
        self._key = KeyStore.normalize(api_key)
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def _secrets(self) -> list[str]:
        return [self._key] if self._key else []

    # ----- key validation ------------------------------------------------
    async def validate_key(self) -> KeyInfo:
        if not KeyStore.looks_valid(self._key):
            raise ChatError("That does not look like an OpenRouter API key.", code="invalid_key")
        import httpx

        headers = {"Authorization": f"Bearer {self._key}"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.get(f"{self._base}/key", headers=headers)
                if resp.status_code == 404:  # older API layout
                    resp = await http.get(f"{self._base}/auth/key", headers=headers)
        except Exception as exc:
            raise map_exception(exc, self._secrets()) from None

        if resp.status_code != 200:
            raise from_status(resp.status_code)
        try:
            data = resp.json().get("data", {})
        except ValueError:
            raise ChatError("OpenRouter returned an unreadable response.", code="bad_response") from None

        def num(v: Any) -> float | None:
            return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

        free = data.get("is_free_tier")
        return KeyInfo(
            is_free_tier=free if isinstance(free, bool) else None,
            usage=num(data.get("usage")),
            limit=num(data.get("limit")),
        )

    # ----- model catalogue (public endpoint) -----------------------------
    async def list_models(self) -> list[dict]:
        import httpx

        headers = {"Authorization": f"Bearer {self._key}"} if self._key else {}
        try:
            async with httpx.AsyncClient(timeout=20.0) as http:
                resp = await http.get(f"{self._base}/models", headers=headers)
        except Exception as exc:
            raise map_exception(exc, self._secrets()) from None
        if resp.status_code != 200:
            raise from_status(resp.status_code)
        try:
            items = resp.json().get("data", [])
        except ValueError:
            raise ChatError("OpenRouter returned an unreadable model list.", code="bad_response") from None
        return [i for i in items if isinstance(i, dict)]

    # ----- streaming chat ------------------------------------------------
    async def stream_chat(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> AsyncIterator[StreamChunk]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self._key,
            base_url=self._base,
            timeout=self._timeout,
            max_retries=1,
            default_headers={"X-Title": "OpenModel Chat"},
        )
        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        try:
            stream = await client.chat.completions.create(**kwargs)
            async with stream:
                async for chunk in stream:
                    extra = getattr(chunk, "model_extra", None) or {}
                    if extra.get("error"):
                        raise from_error_payload(extra["error"], self._secrets())
                    usage = parse_usage(getattr(chunk, "usage", None))
                    delta_text = ""
                    finish = None
                    choices = getattr(chunk, "choices", None) or []
                    if choices:
                        choice = choices[0]
                        delta = getattr(choice, "delta", None)
                        delta_text = (getattr(delta, "content", None) or "") if delta else ""
                        finish = getattr(choice, "finish_reason", None)
                    if delta_text or usage or finish:
                        yield StreamChunk(delta_text, usage, finish)
        except (ChatError, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise map_exception(exc, self._secrets()) from None
        finally:
            try:
                await client.close()
            except Exception:
                pass
