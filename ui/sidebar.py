"""Sidebar: logo, new chat, model picker, conversation history, settings, API key."""
from __future__ import annotations

from nicegui import ui

from ui.settings import open_api_key_dialog, open_settings_dialog
from ui.state import Session

_OPTION_SLOT = """
<q-item v-bind="props.itemProps">
  <q-item-section>
    <q-item-label>{{ props.opt.label }}</q-item-label>
    <q-item-label caption style="font-family:monospace;word-break:break-all">{{ props.opt.value }}</q-item-label>
  </q-item-section>
</q-item>
"""


def build_sidebar(session: Session, dark: ui.dark_mode) -> None:
    s = session.s

    def model_options() -> dict[str, str]:
        options = {m.id: m.name for m in s.registry.list()}
        if session.model_id not in options:
            options[session.model_id] = f"{session.model_id} (not in list)"
        return options

    with ui.column().classes("w-full no-wrap gap-3").style("height: calc(100dvh - 2rem)"):
        # brand
        with ui.row().classes("items-center no-wrap gap-2"):
            ui.icon("hub").classes("omc-logo")
            ui.label(s.settings.app_name).classes("omc-brand")

        ui.button("New chat", icon="add", on_click=session.new_conversation) \
            .props("unelevated no-caps color=primary").classes("w-full")

        # model picker
        ui.label("Model").classes("omc-section")

        def on_model_change(event) -> None:
            if not event.value or event.value == session.model_id:
                return
            had_messages = bool(session.conversation_id and s.db.get_last_message(session.conversation_id))
            session.select_model(event.value)
            if s.model_service.availability(event.value).value == "unavailable":
                ui.notify("This model is not listed on OpenRouter right now. It may fail.", type="warning")
            elif had_messages:
                ui.notify("Model changed. Earlier messages may be interpreted differently.", type="info")

        select = ui.select(model_options(), value=session.model_id, on_change=on_model_change) \
            .props("outlined dense options-dense").classes("w-full")
        select.add_slot("option", _OPTION_SLOT)

        @ui.refreshable
        def model_panel() -> None:
            info = s.registry.get(session.model_id)
            status = s.model_service.availability(session.model_id)
            remote = s.model_service.remote(session.model_id)
            with ui.column().classes("omc-model-card w-full gap-1"):
                with ui.row().classes("items-center no-wrap gap-2"):
                    ui.element("span").classes(f"omc-dot omc-dot-{status.value}")
                    ui.label(s.model_service.status_text(session.model_id)).classes("omc-meta")
                ui.label(session.model_id).classes("omc-mono")
                desc = (info.description if info and info.description else (remote.description if remote else ""))
                if desc:
                    ui.label(desc if len(desc) <= 200 else desc[:200].rstrip() + "\u2026").classes("omc-meta")
                facts = []
                if remote and remote.context_length:
                    facts.append(f"{remote.context_length:,} token context")
                if remote and remote.input_modalities:
                    facts.append("accepts " + ", ".join(remote.input_modalities))
                for fact in facts:
                    ui.label(fact).classes("omc-meta")

        model_panel()

        # search + history
        ui.input(placeholder="Search chats", on_change=lambda e: _on_search(e.value)) \
            .props("outlined dense clearable debounce=250").classes("w-full") \
            .add_slot("prepend", '<q-icon name="search" size="18px" />')

        def _on_search(value: str | None) -> None:
            session.search = value or ""
            conversation_list.refresh()

        with ui.column().classes("w-full gap-1").style(
                "flex:1 1 0; min-height:0; overflow-y:auto; flex-wrap:nowrap"):

            @ui.refreshable
            def conversation_list() -> None:
                items = s.db.list_conversations(session.search)
                if not items:
                    ui.label("No matching chats." if session.search else "No conversations yet.") \
                        .classes("omc-meta px-2")
                for conv in items:
                    active = conv.id == session.conversation_id
                    row = ui.row().classes(f"omc-conv w-full items-center no-wrap {'active' if active else ''}")
                    row.on("click", lambda c=conv: session.open_conversation(c.id))
                    with row:
                        ui.label(conv.title).classes("omc-conv-title grow")
                        with ui.button(icon="more_horiz").props("flat round dense size=sm") \
                                .on("click.stop", lambda: None):
                            with ui.menu():
                                ui.menu_item("Rename", on_click=lambda c=conv: _rename(c))
                                ui.menu_item("Export as Markdown", on_click=lambda c=conv: session.chat.export(c.id, "md"))
                                ui.menu_item("Export as TXT", on_click=lambda c=conv: session.chat.export(c.id, "txt"))
                                ui.separator()
                                ui.menu_item("Delete", on_click=lambda c=conv: _delete(c))

            conversation_list()

        def _rename(conv) -> None:
            with ui.dialog() as dialog, ui.card().style("width:min(24rem,92vw)"):
                ui.label("Rename conversation").classes("text-base font-medium")
                field = ui.input(value=conv.title).props("outlined dense autofocus").classes("w-full")

                def save() -> None:
                    try:
                        s.db.rename_conversation(conv.id, field.value)
                    except ValueError:
                        ui.notify("Title cannot be empty.", type="warning")
                        return
                    dialog.close()
                    session.notify_changed("sidebar_list", "header")

                field.on("keydown.enter", save)
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat no-caps")
                    ui.button("Save", on_click=save).props("unelevated no-caps color=primary")
            dialog.open()

        def _delete(conv) -> None:
            with ui.dialog() as dialog, ui.card().style("width:min(24rem,92vw)"):
                ui.label("Delete this conversation?").classes("text-base font-medium")
                ui.label(conv.title).classes("omc-meta")

                def confirm() -> None:
                    dialog.close()
                    session.delete_conversation(conv.id)

                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat no-caps")
                    ui.button("Delete", on_click=confirm).props("unelevated no-caps color=negative")
            dialog.open()

        # bottom actions
        ui.separator()

        @ui.refreshable
        def key_status() -> None:
            keys = s.key_store
            state = "available" if keys.has_key else "unavailable"
            with ui.row().classes("items-center no-wrap gap-2"):
                ui.element("span").classes(f"omc-dot omc-dot-{state}")
                ui.label("API key set" if keys.has_key else "No API key").classes("omc-meta")

        key_status()

        with ui.row().classes("w-full no-wrap gap-1"):
            ui.button("API key", icon="key", on_click=lambda: open_api_key_dialog(session)) \
                .props("flat dense no-caps align=left").classes("col")
            ui.button("Settings", icon="settings", on_click=lambda: open_settings_dialog(session)) \
                .props("flat dense no-caps align=left").classes("col")
        with ui.row().classes("w-full no-wrap gap-1"):
            ui.button("Clear chat", icon="delete_sweep", on_click=lambda: session.chat.confirm_clear()) \
                .props("flat dense no-caps align=left").classes("col")

            def toggle_theme() -> None:
                dark.toggle()
                s.db.set_setting("theme", "dark" if dark.value else "light")

            ui.button("Theme", icon="contrast", on_click=toggle_theme) \
                .props("flat dense no-caps align=left").classes("col")

    session.callbacks["sidebar_list"] = conversation_list.refresh
    session.callbacks["model_panel"] = model_panel.refresh
    session.callbacks["key_status"] = key_status.refresh
    session.callbacks["model_select"] = lambda: select.set_options(model_options(), value=session.model_id)
    session.callbacks["open_key_dialog"] = lambda: open_api_key_dialog(session)
