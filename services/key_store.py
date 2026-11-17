"""In-memory API key holder.

The key typed into the app lives only in this process's memory. It is never written
to SQLite, logs, or Git. A key from the environment (.env) is used as the fallback.
"""
from __future__ import annotations

import hashlib


class KeyStore:
    def __init__(self, env_key: str = "") -> None:
        self._env = self.normalize(env_key)
        self._session = ""
        self._validated_hash: str | None = None

    @staticmethod
    def normalize(key: str | None) -> str:
        return "".join((key or "").split())

    @staticmethod
    def looks_valid(key: str) -> bool:
        key = KeyStore.normalize(key)
        return 10 <= len(key) <= 300 and key.isascii() and key.isprintable()

    @staticmethod
    def _hash(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def set_session(self, key: str) -> None:
        self._session = self.normalize(key)

    def clear_session(self) -> None:
        self._session = ""

    def get(self) -> str:
        return self._session or self._env

    @property
    def has_key(self) -> bool:
        return bool(self.get())

    @property
    def source(self) -> str | None:
        if self._session:
            return "entered in the app"
        if self._env:
            return "environment (.env)"
        return None

    def mark_validated(self) -> None:
        key = self.get()
        self._validated_hash = self._hash(key) if key else None

    def is_validated(self) -> bool:
        key = self.get()
        return bool(key) and self._validated_hash == self._hash(key)

    def masked(self) -> str:
        key = self.get()
        if not key:
            return ""
        if len(key) <= 14:
            return "\u2022" * 8
        return f"{key[:6]}\u2026{key[-4:]}"
