"""Small UI helpers."""
from __future__ import annotations

import re
import zlib
from datetime import datetime

from nicegui import ui


def model_hue(model_id: str | None) -> int:
    """Stable colour per model so a switch of model is visible in the thread."""
    return zlib.crc32((model_id or "").encode("utf-8")) % 360


def avatar_style(model_id: str | None) -> str:
    return f"background: hsl({model_hue(model_id)} 50% 40%); color: #fff;"


def initials(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name)
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def fmt_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%H:%M, %d %b %Y")
    except ValueError:
        return iso


def fmt_duration(ms: int) -> str:
    return f"{ms} ms" if ms < 1000 else f"{ms / 1000:.1f} s"


def make_html(content: str):
    """Create an HTML element across NiceGUI 2.x and 3.x (content is already escaped)."""
    try:
        return ui.html(content, sanitize=False)
    except TypeError:
        return ui.html(content)


def set_html(element, content: str) -> None:
    try:
        element.set_content(content)
    except AttributeError:
        element.content = content


def scroll_to_bottom(force: bool = False) -> None:
    flag = "true" if force else "false"
    try:
        ui.run_javascript(
            "(()=>{const e=document.scrollingElement;"
            f"if({flag}||e.scrollHeight-e.scrollTop-e.clientHeight<260)"
            "e.scrollTo({top:e.scrollHeight});})()"
        )
    except RuntimeError:  # no live page context (tab closed); scrolling is cosmetic
        pass
