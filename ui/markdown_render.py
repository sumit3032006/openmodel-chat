"""Safe Markdown -> HTML rendering for model output.

Defence in depth for untrusted model text:
  * raw HTML in the text is ESCAPED (markdown2 safe_mode),
  * javascript:/data:/vbscript: link targets are neutralised,
  * remote images are blocked (an image URL could leak conversation data to a third party),
  * links open in a new tab with noopener.
Nothing a model produces is ever executed.
"""
from __future__ import annotations

import html
import re

try:
    from markdown2 import Markdown

    _MD = Markdown(
        extras=["fenced-code-blocks", "tables", "strike", "task_list", "break-on-newline",
                "cuddled-lists", "code-friendly"],
        safe_mode="escape",
    )
except ImportError:  # pragma: no cover - fallback keeps the app usable
    _MD = None

_BAD_URL = re.compile(r"(?i)\b(href|src)\s*=\s*([\"'])\s*(?:javascript|data|vbscript):[^\"']*\2")
_IMG = re.compile(r"(?is)<img\b[^>]*>")
_ALT = re.compile(r"(?is)\balt\s*=\s*([\"'])(.*?)\1")
_ANCHOR = re.compile(r"(?i)<a\s")


def _block_image(match: re.Match) -> str:
    alt = _ALT.search(match.group(0))
    label = alt.group(2) if alt else ""
    return f'<span class="omc-meta">[image blocked{": " + label if label else ""}]</span>'


def harden_html(markup: str) -> str:
    markup = _BAD_URL.sub(lambda m: f"{m.group(1)}={m.group(2)}#{m.group(2)}", markup)
    markup = _IMG.sub(_block_image, markup)
    return _ANCHOR.sub('<a target="_blank" rel="noopener noreferrer" ', markup)


def render_markdown(text: str) -> str:
    if _MD is not None:
        try:
            return harden_html(_MD.convert(text))
        except Exception:
            pass
    return f"<pre>{html.escape(text)}</pre>"
