"""Dialogs: API key configuration and application settings."""
from __future__ import annotations

from nicegui import ui

from models.model_registry import RegistryError
from services import env_file
from services.errors import ChatError
from services.key_store import KeyStore
from ui.helpers import fmt_duration
from ui.state import Session


def open_api_key_dialog(session: Session) -> None:
    s = session.s
    with ui.dialog() as dialog, ui.card().style("width:min(30rem,94vw)").classes("gap-3"):
        ui.label("OpenRouter API key").classes("text-lg font-medium")
        ui.label("Create a key at openrouter.ai/keys. It is kept in memory only while the app runs "
                 "and is never written to the database or Git.").classes("omc-meta")
        if s.key_store.has_key:
            ui.label(f"Active key: {s.key_store.masked()} ({s.key_store.source})").classes("text-sm")
        else:
            ui.label("No key is active yet.").classes("text-sm")
        field = ui.input("Paste your API key", password=True, password_toggle_button=True) \
            .props("outlined dense autocomplete=off").classes("w-full")
        save_env = ui.checkbox("Also save it in the local .env file (this computer only, ignored by Git)")

        async def validate() -> None:
            key = KeyStore.normalize(field.value)
            if not key:
                ui.notify("Paste a key first.", type="warning")
                return
            validate_btn.props("loading")
            try:
                info = await s.client_factory(key).validate_key()
            except ChatError as exc:
                ui.notify(exc.message, type="negative", multi_line=True)
                return
            finally:
                validate_btn.props(remove="loading")
            s.key_store.set_session(key)
            s.key_store.mark_validated()
            if save_env.value:
                try:
                    env_file.save_api_key(s.settings.env_file, key)
                except (OSError, ValueError) as exc:
                    ui.notify(f"Key is active, but could not be saved to .env: {type(exc).__name__}",
                              type="warning")
            field.value = ""
            note = " (free tier)" if info.is_free_tier else ""
            ui.notify(f"API key is valid{note}.", type="positive")
            session.notify_changed("key_status")
            dialog.close()

        def remove() -> None:
            s.key_store.clear_session()
            if save_env.value:
                try:
                    env_file.remove_api_key(s.settings.env_file)
                except OSError:
                    pass
            ui.notify("Key removed from this session."
                      + (" A key from .env, if any, is still used until you edit that file."
                         if s.key_store.has_key else ""), type="info", multi_line=True)
            session.notify_changed("key_status")
            dialog.close()

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Remove key", on_click=remove).props("flat no-caps")
            ui.button("Close", on_click=dialog.close).props("flat no-caps")
            validate_btn = ui.button("Validate and use", on_click=validate).props("unelevated no-caps color=primary")
    dialog.open()


def open_settings_dialog(session: Session) -> None:
    s = session.s
    with ui.dialog() as dialog, ui.card().style("width:min(46rem,95vw)").classes("gap-2"):
        ui.label("Settings").classes("text-lg font-medium")
        with ui.tabs().props("dense align=left no-caps") as tabs:
            t_general = ui.tab("General")
            t_models = ui.tab("Models")
            t_stats = ui.tab("Statistics")
            t_about = ui.tab("About")
        with ui.tab_panels(tabs, value=t_general).classes("w-full").style("background:transparent"):
            with ui.tab_panel(t_general).classes("gap-3 p-0 pt-3"):
                _general_tab(session)
            with ui.tab_panel(t_models).classes("gap-3 p-0 pt-3"):
                _models_tab(session)
            with ui.tab_panel(t_stats).classes("gap-3 p-0 pt-3"):
                _stats_tab(session)
            with ui.tab_panel(t_about).classes("gap-2 p-0 pt-3"):
                _about_tab(session)
        with ui.row().classes("w-full justify-end"):
            ui.button("Close", on_click=dialog.close).props("flat no-caps")
    dialog.open()


def _general_tab(session: Session) -> None:
    s = session.s
    ui.label("System prompt (optional)").classes("text-sm font-medium")
    ui.label("Sent at the start of every request. Leave empty for none.").classes("omc-meta")
    prompt = ui.textarea(value=s.db.get_setting("system_prompt", "")) \
        .props("outlined autogrow dense").classes("w-full")
    raw_temp = s.db.get_setting("temperature", "")
    use_default = ui.checkbox("Use each model's default temperature", value=raw_temp == "")
    temp = ui.slider(min=0, max=2, step=0.1, value=float(raw_temp) if raw_temp else 0.7).props("label-always") \
        .classes("w-full")
    temp.bind_visibility_from(use_default, "value", backward=lambda v: not v)

    def save() -> None:
        s.db.set_setting("system_prompt", (prompt.value or "").strip()[:4000])
        s.db.set_setting("temperature", "" if use_default.value else f"{temp.value:.1f}")
        ui.notify("Settings saved.", type="positive")

    ui.button("Save", on_click=save).props("unelevated no-caps color=primary")


def _models_tab(session: Session) -> None:
    s = session.s

    @ui.refreshable
    def rows() -> None:
        for m in s.registry.list():
            status = s.model_service.availability(m.id)
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                ui.element("span").classes(f"omc-dot omc-dot-{status.value}")
                with ui.column().classes("grow gap-0 min-w-0"):
                    ui.label(m.name).classes("text-sm font-medium")
                    ui.label(m.id).classes("omc-mono")
                ui.label("built-in" if m.builtin else "added by you").classes("omc-meta")
                if not m.builtin:
                    ui.button(icon="delete", on_click=lambda mid=m.id: remove(mid)) \
                        .props("flat round dense size=sm").tooltip("Remove")

    def remove(model_id: str) -> None:
        try:
            s.registry.remove_custom(model_id)
        except RegistryError as exc:
            ui.notify(str(exc), type="warning")
            return
        rows.refresh()
        session.notify_changed("model_select", "model_panel")

    async def check() -> None:
        check_btn.props("loading")
        try:
            ok = await s.model_service.refresh(force=True)
        finally:
            check_btn.props(remove="loading")
        ui.notify("Availability updated." if ok else (s.model_service.last_error or "Could not check."),
                  type="positive" if ok else "negative")
        rows.refresh()
        session.notify_changed("model_panel")

    rows()
    check_btn = ui.button("Check availability on OpenRouter", icon="sync", on_click=check) \
        .props("flat no-caps")
    ui.separator()
    ui.label("Add a model").classes("text-sm font-medium")
    ui.label("Copy the model ID from openrouter.ai/models (for example vendor/model-name:free).").classes("omc-meta")
    with ui.row().classes("w-full no-wrap gap-2"):
        name = ui.input("Display name").props("outlined dense").classes("col")
        model_id = ui.input("Model ID").props("outlined dense").classes("col")

    def add() -> None:
        try:
            s.registry.add_custom(name.value, model_id.value)
        except RegistryError as exc:
            ui.notify(str(exc), type="warning")
            return
        name.value = model_id.value = ""
        rows.refresh()
        session.notify_changed("model_select")
        ui.notify("Model added. Use 'Check availability' to verify it.", type="positive")

    ui.button("Add model", icon="add", on_click=add).props("unelevated no-caps color=primary")


def _stats_tab(session: Session) -> None:
    stats = session.s.db.stats()
    ui.label("Counts come from your local history. Token numbers are shown only when the provider "
             "reported them; nothing is estimated.").classes("omc-meta")
    with ui.row().classes("gap-6"):
        for label, value in (("Conversations", stats["conversations"]),
                             ("Your messages", stats["user_messages"]),
                             ("Model replies", stats["assistant_messages"]),
                             ("Tokens reported", f"{stats['total_tokens']:,}" if stats["total_tokens"] else "none")):
            with ui.column().classes("gap-0"):
                ui.label(str(value)).classes("text-xl font-semibold")
                ui.label(label).classes("omc-meta")
    rows = [
        {
            "model": session.s.registry.name_for(r["model_id"]),
            "replies": r["replies"],
            "avg": fmt_duration(r["avg_response_ms"]) if r["avg_response_ms"] is not None else "not recorded",
            "tokens": f"{r['total_tokens']:,}" if r["total_tokens"] else "not reported",
        }
        for r in stats["by_model"]
    ]
    if rows:
        columns = [
            {"name": "model", "label": "Model", "field": "model", "align": "left"},
            {"name": "replies", "label": "Replies", "field": "replies", "align": "right"},
            {"name": "avg", "label": "Avg response time", "field": "avg", "align": "right"},
            {"name": "tokens", "label": "Tokens", "field": "tokens", "align": "right"},
        ]
        ui.table(columns=columns, rows=rows, row_key="model").props("dense flat").classes("w-full")
    else:
        ui.label("No model replies yet.").classes("omc-meta")


def _about_tab(session: Session) -> None:
    cfg = session.s.settings
    ui.label(f"{cfg.app_name} v{cfg.version}").classes("text-sm font-medium")
    ui.label("Open-source multi-model chat for OpenRouter. MIT licensed.").classes("omc-meta")
    ui.label("Privacy: your messages go only to OpenRouter and the model provider you choose. "
             "Conversations are stored locally in data/chats.db. API keys are never stored in the "
             "database. Free-model availability is controlled by OpenRouter and its providers.") \
        .classes("omc-meta")
