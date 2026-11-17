"""Assembles the page: sidebar drawer, header, chat thread, composer."""
from __future__ import annotations

from nicegui import ui

from services.container import Services
from ui.chat_interface import ChatView
from ui.helpers import avatar_style, initials
from ui.sidebar import build_sidebar
from ui.state import Session
from ui.theme import apply_theme


def build_page(services: Services) -> None:
    session = Session(services)
    apply_theme()
    dark = ui.dark_mode(value=services.db.get_setting("theme", "light") == "dark")
    chat = ChatView(session)

    with ui.left_drawer(fixed=True, bordered=True).props("width=310 breakpoint=900") as drawer:
        build_sidebar(session, dark)

    with ui.header().classes("items-center no-wrap gap-3 px-3").style("min-height:52px"):
        ui.button(icon="menu", on_click=drawer.toggle).props("flat round dense").classes("lt-md")

        @ui.refreshable
        def header() -> None:
            conv = services.db.get_conversation(session.conversation_id) if session.conversation_id else None
            ui.label(conv.title if conv else "New chat").classes("text-base font-medium ellipsis grow")
            name = services.registry.name_for(session.model_id)
            with ui.row().classes("omc-chip items-center no-wrap gap-2"):
                ui.label(initials(name)).classes("omc-avatar").style(
                    avatar_style(session.model_id) + "width:22px;height:22px;border-radius:7px;font-size:.58rem;")
                ui.label(name).classes("gt-xs")

        header()

    chat.build_thread()
    chat.build_footer()
    session.callbacks["header"] = header.refresh

    async def load_catalogue() -> None:
        await services.model_service.refresh()
        session.notify_changed("model_panel")

    ui.timer(0.3, load_catalogue, once=True)
