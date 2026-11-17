"""Error types, friendly error messages, and secret redaction."""
from __future__ import annotations

import logging
import re
from typing import Any, Iterable

_OR_KEY = re.compile(r"sk-or-[A-Za-z0-9_\-]{6,}")
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}")


def redact(text: object, secrets: Iterable[str] = ()) -> str:
    """Remove API keys from any text before it is shown or logged."""
    out = str(text)
    for secret in secrets:
        if secret and len(secret) >= 6:
            out = out.replace(secret, "[redacted]")
    out = _OR_KEY.sub("[redacted]", out)
    out = _BEARER.sub(r"\1[redacted]", out)
    return out


class RedactingFilter(logging.Filter):
    """Logging filter that scrubs API keys from every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = ()
        except Exception:  # never let logging crash the app
            pass
        return True


class ChatError(Exception):
    """A user-presentable error. `message` never contains secrets."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "error",
        retryable: bool = False,
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.status = status


def _detail_from_exception(exc: BaseException, secrets: Iterable[str]) -> str:
    body = getattr(exc, "body", None)
    message: Any = None
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict):
            message = err.get("message")
            meta = err.get("metadata")
            if isinstance(meta, dict) and meta.get("provider_name"):
                message = f"{message or ''} (provider: {meta['provider_name']})".strip()
        elif isinstance(err, str):
            message = err
    if not message:
        message = getattr(exc, "message", None)
    if not message or not isinstance(message, str):
        return ""
    return redact(message, secrets).strip()[:300]


def from_status(status: int | None, detail: str = "") -> ChatError:
    suffix = f" Details: {detail}" if detail else ""
    if status == 401:
        return ChatError(
            "OpenRouter rejected your API key. Check the key and try again.",
            code="invalid_key", status=status,
        )
    if status == 402:
        return ChatError(
            "Insufficient OpenRouter credits for this request. Add credits or use a free model.",
            code="insufficient_credits", status=status,
        )
    if status == 403:
        return ChatError(
            "Access was denied (403). The key may lack permission or the content was flagged."
            + suffix, code="forbidden", status=status,
        )
    if status == 404:
        return ChatError(
            "This model is not available on OpenRouter right now (it may be deprecated, renamed, "
            "or have no active provider). Choose another model." + suffix,
            code="model_unavailable", status=status,
        )
    if status == 408:
        return ChatError("The request timed out. Please try again.",
                         code="timeout", retryable=True, status=status)
    if status == 429:
        return ChatError(
            "Rate limit reached. Free models have strict limits - wait a moment and retry, "
            "or switch to another model." + suffix,
            code="rate_limited", retryable=True, status=status,
        )
    if status is not None and status >= 500:
        return ChatError(
            f"The model provider reported a server error ({status}). Retry, or switch models."
            + suffix, code="provider_error", retryable=True, status=status,
        )
    if status in (400, 413, 422):
        return ChatError("The request was rejected by the provider." + suffix,
                         code="bad_request", status=status)
    return ChatError("The request failed." + suffix, code="error", status=status)


def map_exception(exc: BaseException, secrets: Iterable[str] = ()) -> ChatError:
    """Translate SDK / network exceptions into a safe, friendly ChatError."""
    if isinstance(exc, ChatError):
        return exc
    secrets = list(secrets)
    name = type(exc).__name__
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return from_status(status, _detail_from_exception(exc, secrets))
    if "Timeout" in name:
        return ChatError("The request timed out. Check your connection and try again.",
                         code="timeout", retryable=True)
    if any(part in name for part in ("Connection", "Connect", "Network")):
        return ChatError("Could not reach OpenRouter. Check your internet connection.",
                         code="network", retryable=True)
    return ChatError(f"Unexpected error ({name}). See the console for details.",
                     code="unexpected")


def from_error_payload(payload: Any, secrets: Iterable[str] = ()) -> ChatError:
    """Build a ChatError from an error object that arrives inside a stream."""
    secrets = list(secrets)
    code = None
    message = ""
    if isinstance(payload, dict):
        code = payload.get("code")
        message = str(payload.get("message", ""))
    elif isinstance(payload, str):
        message = payload
    status = code if isinstance(code, int) else None
    return from_status(status, redact(message, secrets).strip()[:300])
