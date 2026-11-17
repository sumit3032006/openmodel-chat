"""OpenModel Chat - entry point.  Run with:  python app.py"""
from __future__ import annotations

import logging

from nicegui import ui

from config import settings
from services.container import build_services
from services.errors import RedactingFilter
from ui.page import build_page


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    redactor = RedactingFilter()
    root = logging.getLogger()
    root.addFilter(redactor)
    for handler in root.handlers:
        handler.addFilter(redactor)
    for noisy in ("httpx", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_setup_logging()
services = build_services(settings)


@ui.page("/")
def index() -> None:
    build_page(services)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title=settings.app_name,
        host=settings.host,
        port=settings.port,
        reload=False,
        show=True,
        favicon="\U0001F9E9",
    )
