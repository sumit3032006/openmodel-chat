"""Main chat area: welcome screen, message thread, streaming, composer."""
from __future__ import annotations

import asyncio
import logging
import time

from nicegui import ui

from database.chat_database import MessageRecord
from services import exporter
from services.errors import ChatError
from ui.helpers import (avatar_style, fmt_duration, fmt_time, initials, make_html,
                        model_hue, scroll_to_bottom, set_html)
from ui.markdown_render import render_markdown
from ui.state import Session

log = logging.getLogger(__name__)

SUGGESTIONS = [
    "Explain how a hash map works, with a short Python example.",
    "Give me a 3-day study plan to learn SQL basics.",
    "Summarise the pros and cons of microservices vs a monolith.",
    "Write a polite email asking a client for a payment update.",
]


class ChatView:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.box: ui.column | None = None
        self.input: ui.textarea | None = None
        self.send_btn: ui.button | None = None
        self.stop_btn: ui.button | None = None
        session.chat = self

    # ----- layout --------------------------------------------------------
    def build_thread(self) -> None:
        self.box = ui.column().classes("omc-thread w-full gap-5")
        self.session.callbacks["chat"] = self.render
        self.render()

    def build_footer(self) -> None:
        with ui.footer().classes("omc-footer"):
            with ui.column().classes("omc-composer w-full gap-1"):
                with ui.row().classes("omc-box w-full items-end no-wrap gap-1"):
                    self.input = (
                        ui.textarea(placeholder="Message the selected model...")
                        .props("borderless autogrow dense")
                        .classes("omc-input grow")
                    )
                    self.send_btn = (
                        ui.button(icon="arrow_upward", on_click=self.send)
                        .props("round unelevated color=primary id=omc-send")
                        .tooltip("Send (Enter)")
                    )
                    self.stop_btn = (
                        ui.button(icon="stop", on_click=self.stop)
                        .props("round unelevated color=negative")
                        .tooltip("Stop generating")
                    )
                ui.label("Enter to send, Shift+Enter for a new line. AI replies can be wrong.") \
                    .classes("omc-foot-note")
        self._sync_controls()

    def _sync_controls(self) -> None:
        if self.send_btn is not None:
            self.send_btn.set_visibility(not self.session.generating)
        if self.stop_btn is not None:
            self.stop_btn.set_visibility(self.session.generating)

    # ----- rendering -----------------------------------------------------
    def render(self) -> None:
        s = self.session
        assert self.box is not None
        self.box.clear()
        messages = s.s.db.get_messages(s.conversation_id) if s.conversation_id else []
        with self.box:
            if not messages and not s.generating:
                self._welcome()
                return
            self._model_switch_notice(messages)
            for index, message in enumerate(messages):
                if message.role == "user":
                    self._user_message(message)
                else:
                    self._assistant_message(message, is_last=index == len(messages) - 1)
            if s.last_error is not None and not s.generating:
                self._error_card(s.last_error)
        with self.box:
            scroll_to_bottom(force=True)

    def _welcome(self) -> None:
        s = self.session
        with ui.column().classes("omc-welcome w-full gap-4"):
            ui.label("Pick a model. Ask anything.").classes("omc-hero")
            ui.label("Every model below answers through your own OpenRouter key. Switch whenever you "
                     "like and the conversation stays.").classes("omc-lede")
            if not s.s.key_store.has_key:
                with ui.row().classes("omc-notice w-full items-center no-wrap gap-3"):
                    ui.icon("key").classes("text-lg")
                    ui.label("Add your OpenRouter API key to start.").classes("grow")
                    ui.button("Add key", on_click=lambda: s.notify_changed("open_key_dialog")) \
                        .props("unelevated dense no-caps color=primary")
            with ui.element("div").classes("omc-model-grid"):
                for m in s.s.registry.list():
                    status = s.s.model_service.availability(m.id)
                    card = ui.element("div").classes(
                        f"omc-mcard {'selected' if m.id == s.model_id else ''}"
                    ).style(f"--h:{model_hue(m.id)}")
                    card.on("click", lambda mid=m.id: self._choose_model(mid))
                    with card:
                        with ui.row().classes("items-center no-wrap gap-2 w-full"):
                            ui.label(initials(m.name)).classes("omc-avatar").style(avatar_style(m.id))
                            ui.label(m.name).classes("omc-mcard-name grow")
                            ui.element("span").classes(f"omc-dot omc-dot-{status.value}")
                        ui.label(m.id).classes("omc-mono")
            ui.label("Try asking").classes("omc-section mt-2")
            with ui.row().classes("w-full gap-2"):
                for text in SUGGESTIONS:
                    ui.label(text).classes("omc-suggest").on("click", lambda t=text: self._use_suggestion(t))

    def _choose_model(self, model_id: str) -> None:
        self.session.select_model(model_id)
        self.session.notify_changed("model_select")

    def _use_suggestion(self, text: str) -> None:
        if self.input is not None:
            self.input.value = text
            self.input.run_method("focus")

    def _model_switch_notice(self, messages: list[MessageRecord]) -> None:
        last_ai = next((m for m in reversed(messages) if m.role == "assistant" and m.model_id), None)
        if last_ai and last_ai.model_id != self.session.model_id:
            old = self.session.s.registry.name_for(last_ai.model_id)
            new = self.session.s.registry.name_for(self.session.model_id)
            ui.label(
                f"Model switched from {old} to {new}. The earlier messages will be sent to the new "
                "model, which may interpret them differently."
            ).classes("omc-notice w-full")

    def _user_message(self, m: MessageRecord) -> None:
        with ui.column().classes("w-full items-end gap-1"):
            ui.label(m.content).classes("omc-msg-user")
            ui.label(fmt_time(m.created_at)).classes("omc-meta")

    def _assistant_header(self, model_id: str | None) -> None:
        name = self.session.s.registry.name_for(model_id)
        with ui.row().classes("items-center no-wrap gap-2"):
            ui.label(initials(name)).classes("omc-avatar").style(avatar_style(model_id))
            ui.label(name).classes("omc-model-name")
            if model_id:
                ui.label(model_id).classes("omc-mono")

    def _assistant_message(self, m: MessageRecord, is_last: bool) -> None:
        with ui.column().classes("omc-ai w-full gap-1").style(f"--h:{model_hue(m.model_id)}"):
            self._assistant_header(m.model_id)
            make_html(render_markdown(m.content)).classes("omc-md w-full")
            meta = [fmt_time(m.created_at)]
            if m.response_ms is not None:
                meta.append(f"{fmt_duration(m.response_ms)} response time")
            if m.total_tokens is not None:
                if m.prompt_tokens is not None and m.completion_tokens is not None:
                    meta.append(f"{m.total_tokens:,} tokens ({m.prompt_tokens:,} in, {m.completion_tokens:,} out)")
                else:
                    meta.append(f"{m.total_tokens:,} tokens")
            if m.status == "stopped":
                meta.append("stopped early")
            elif m.status == "error":
                meta.append("interrupted by an error")
            with ui.row().classes("items-center gap-1"):
                ui.label(", ".join(meta)).classes("omc-meta")
                ui.button(icon="content_copy", on_click=lambda c=m.content: self._copy(c)) \
                    .props("flat round dense size=sm").tooltip("Copy response")
                if is_last:
                    ui.button(icon="refresh", on_click=self.regenerate) \
                        .props("flat round dense size=sm").tooltip("Regenerate response")

    def _error_card(self, err: ChatError) -> None:
        with ui.column().classes("omc-error w-full gap-2"):
            ui.label(err.message).classes("text-sm")
            with ui.row().classes("gap-2"):
                ui.button("Retry", icon="refresh", on_click=self.regenerate).props("unelevated dense no-caps")
                if err.code in ("no_key", "invalid_key"):
                    ui.button("API key", icon="key",
                              on_click=lambda: self.session.notify_changed("open_key_dialog")
                              ).props("flat dense no-caps")

    @staticmethod
    def _copy(text: str) -> None:
        ui.clipboard.write(text)
        ui.notify("Copied to clipboard", type="positive", timeout=1200)

    # ----- actions -------------------------------------------------------
    async def send(self) -> None:
        s = self.session
        if s.generating or self.input is None:
            return
        text = (self.input.value or "").strip()
        if not text:
            return
        if not await s.ensure_key_ready():
            return
        try:
            if s.conversation_id is None:
                conv = s.s.db.create_conversation(s.model_id)
                s.conversation_id = conv.id
            s.s.chat_service.add_user_message(s.conversation_id, text)
        except ChatError as exc:
            ui.notify(exc.message, type="warning")
            return
        self.input.value = ""
        s.last_error = None
        s.notify_changed("sidebar_list", "header")
        await self.start_generation()

    async def regenerate(self) -> None:
        s = self.session
        if s.generating or not s.conversation_id:
            return
        last = s.s.db.get_last_message(s.conversation_id)
        if last is not None and last.role == "assistant":
            s.s.db.delete_message(last.id)
        s.last_error = None
        if not await s.ensure_key_ready():
            self.render()
            return
        await self.start_generation()

    def stop(self) -> None:
        task = self.session.task
        if task is not None and not task.done():
            task.cancel()

    async def start_generation(self) -> None:
        s = self.session
        s.generating = True
        self._sync_controls()
        self.render()
        with self.box:  # gives the background task a valid UI context
            s.task = asyncio.create_task(self._run())
        await s.task

    async def _run(self) -> None:
        s = self.session
        assert self.box is not None and s.conversation_id
        conversation_id, model_id = s.conversation_id, s.model_id
        with self.box:
            with ui.column().classes("omc-streaming omc-ai w-full gap-1").style(f"--h:{model_hue(model_id)}"):
                self._assistant_header(model_id)
                html = make_html("").classes("omc-md w-full")
        buffer, last_paint = "", 0.0
        try:
            async for event in s.s.chat_service.generate(
                conversation_id, model_id,
                system_prompt=s.system_prompt(), temperature=s.temperature(),
            ):
                if event.kind == "delta":
                    buffer += event.text
                    now = time.monotonic()
                    if now - last_paint > 0.08:
                        set_html(html, render_markdown(buffer))
                        last_paint = now
                        scroll_to_bottom()
        except asyncio.CancelledError:
            ui.notify("Generation stopped.", type="info", timeout=1500)
        except ChatError as exc:
            s.last_error = exc
        except Exception as exc:  # keep the UI alive; never echo raw exception text
            log.error("Unexpected error while generating: %s", type(exc).__name__)
            s.last_error = ChatError("Something went wrong while generating. See the console.",
                                     code="unexpected")
        finally:
            s.generating = False
            s.task = None
            self._sync_controls()
            self.render()
            s.notify_changed("sidebar_list")

    # ----- clear / export --------------------------------------------------
    def confirm_clear(self) -> None:
        s = self.session
        if not s.conversation_id:
            ui.notify("There is no conversation to clear.", type="info")
            return
        if s.generating:
            ui.notify("Stop the current response first.", type="warning")
            return
        with ui.dialog() as dialog, ui.card().style("width:min(24rem,92vw)"):
            ui.label("Clear this conversation?").classes("text-base font-medium")
            ui.label("All messages in it will be deleted. The conversation itself stays.").classes("omc-meta")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat no-caps")
                ui.button("Clear", on_click=lambda: self._do_clear(dialog)).props("unelevated no-caps color=negative")
        dialog.open()

    def _do_clear(self, dialog) -> None:
        s = self.session
        if s.conversation_id:
            s.s.db.clear_conversation(s.conversation_id)
        s.last_error = None
        dialog.close()
        self.render()
        s.notify_changed("sidebar_list")

    def export(self, conversation_id: str, fmt: str) -> None:
        db = self.session.s.db
        conv = db.get_conversation(conversation_id)
        if conv is None:
            return
        messages = db.get_messages(conversation_id)
        name_for = self.session.s.registry.name_for
        if fmt == "md":
            content = exporter.to_markdown(conv, messages, name_for)
        else:
            content = exporter.to_text(conv, messages, name_for)
        ui.download(content.encode("utf-8"), exporter.safe_filename(conv.title, fmt))
