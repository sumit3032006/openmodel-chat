"""SQLite storage for conversations, messages and app settings.

API keys are NEVER stored here.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DEFAULT_TITLE = "New chat"
MAX_TITLE = 100

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    model_id    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id   TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role              TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content           TEXT NOT NULL,
    model_id          TEXT,
    created_at        TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'complete',
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    response_ms       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class ConversationRecord:
    id: str
    title: str
    model_id: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MessageRecord:
    id: int
    conversation_id: str
    role: str
    content: str
    model_id: str | None
    created_at: str
    status: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    response_ms: int | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class ChatDatabase:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ----- conversations -------------------------------------------------
    @staticmethod
    def _conv(row: sqlite3.Row) -> ConversationRecord:
        return ConversationRecord(row["id"], row["title"], row["model_id"],
                                  row["created_at"], row["updated_at"])

    def create_conversation(self, model_id: str, title: str = DEFAULT_TITLE) -> ConversationRecord:
        cid = uuid.uuid4().hex
        now = _now()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO conversations (id, title, model_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (cid, title[:MAX_TITLE], model_id, now, now),
            )
        return ConversationRecord(cid, title[:MAX_TITLE], model_id, now, now)

    def get_conversation(self, cid: str) -> ConversationRecord | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (cid,)).fetchone()
        return self._conv(row) if row else None

    def list_conversations(self, search: str | None = None, limit: int = 500) -> list[ConversationRecord]:
        with self._conn() as conn:
            if search and search.strip():
                like = f"%{_escape_like(search.strip())}%"
                rows = conn.execute(
                    "SELECT * FROM conversations c WHERE c.title LIKE ? ESCAPE '\\' "
                    "OR EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id "
                    "AND m.content LIKE ? ESCAPE '\\') ORDER BY c.updated_at DESC, c.rowid DESC LIMIT ?",
                    (like, like, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM conversations ORDER BY updated_at DESC, rowid DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._conv(r) for r in rows]

    def rename_conversation(self, cid: str, title: str) -> None:
        title = " ".join((title or "").split())
        if not title:
            raise ValueError("Title cannot be empty.")
        with self._conn() as conn:
            conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title[:MAX_TITLE], cid))

    def set_conversation_model(self, cid: str, model_id: str) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE conversations SET model_id = ? WHERE id = ?", (model_id, cid))

    def delete_conversation(self, cid: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))

    def clear_conversation(self, cid: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (_now(), cid))

    # ----- messages ------------------------------------------------------
    @staticmethod
    def _msg(row: sqlite3.Row) -> MessageRecord:
        return MessageRecord(
            row["id"], row["conversation_id"], row["role"], row["content"], row["model_id"],
            row["created_at"], row["status"], row["prompt_tokens"], row["completion_tokens"],
            row["total_tokens"], row["response_ms"],
        )

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        model_id: str | None = None,
        status: str = "complete",
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        response_ms: int | None = None,
    ) -> MessageRecord:
        now = _now()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO messages (conversation_id, role, content, model_id, created_at, status, "
                "prompt_tokens, completion_tokens, total_tokens, response_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (conversation_id, role, content, model_id, now, status,
                 prompt_tokens, completion_tokens, total_tokens, response_ms),
            )
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
        return self._msg(row)

    def get_messages(self, conversation_id: str) -> list[MessageRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (conversation_id,)
            ).fetchall()
        return [self._msg(r) for r in rows]

    def get_last_message(self, conversation_id: str) -> MessageRecord | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()
        return self._msg(row) if row else None

    def delete_message(self, message_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))

    # ----- settings ------------------------------------------------------
    def get_setting(self, key: str, default: str = "") -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # ----- statistics ----------------------------------------------------
    def stats(self) -> dict:
        """Real numbers only: tokens and timings are summed from values the API returned."""
        with self._conn() as conn:
            convs = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
            users = conn.execute("SELECT COUNT(*) FROM messages WHERE role = 'user'").fetchone()[0]
            replies = conn.execute("SELECT COUNT(*) FROM messages WHERE role = 'assistant'").fetchone()[0]
            tokens = conn.execute("SELECT SUM(total_tokens) FROM messages").fetchone()[0]
            by_model = conn.execute(
                "SELECT model_id, COUNT(*) AS replies, AVG(response_ms) AS avg_ms, "
                "SUM(total_tokens) AS tokens FROM messages "
                "WHERE role = 'assistant' AND model_id IS NOT NULL "
                "GROUP BY model_id ORDER BY replies DESC"
            ).fetchall()
        return {
            "conversations": convs,
            "user_messages": users,
            "assistant_messages": replies,
            "total_tokens": tokens,
            "by_model": [
                {
                    "model_id": r["model_id"],
                    "replies": r["replies"],
                    "avg_response_ms": int(r["avg_ms"]) if r["avg_ms"] is not None else None,
                    "total_tokens": r["tokens"],
                }
                for r in by_model
            ],
        }
