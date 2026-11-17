"""Export a conversation as plain text or Markdown."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Callable, Sequence

from database.chat_database import ConversationRecord, MessageRecord


def _fmt(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso


def safe_filename(title: str, ext: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("._-")[:60] or "conversation"
    return f"{stem}.{ext}"


def _speaker(m: MessageRecord, name_for: Callable[[str | None], str]) -> str:
    return "You" if m.role == "user" else name_for(m.model_id)


def to_markdown(conv: ConversationRecord, messages: Sequence[MessageRecord],
                name_for: Callable[[str | None], str]) -> str:
    out = [f"# {conv.title}", "", f"- Created: {_fmt(conv.created_at)}",
           f"- Selected model: {name_for(conv.model_id)} (`{conv.model_id}`)", "", "---", ""]
    for m in messages:
        out += [f"### {_speaker(m, name_for)} - {_fmt(m.created_at)}", "", m.content, ""]
    return "\n".join(out).rstrip() + "\n"


def to_text(conv: ConversationRecord, messages: Sequence[MessageRecord],
            name_for: Callable[[str | None], str]) -> str:
    out = [conv.title, "=" * len(conv.title), f"Created: {_fmt(conv.created_at)}",
           f"Selected model: {name_for(conv.model_id)} ({conv.model_id})", ""]
    for m in messages:
        out += [f"[{_fmt(m.created_at)}] {_speaker(m, name_for)}:", m.content, ""]
    return "\n".join(out).rstrip() + "\n"
