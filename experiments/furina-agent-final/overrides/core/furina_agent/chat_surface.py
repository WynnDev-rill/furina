from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass

from rich.markdown import Markdown as RichMarkdown
from rich.table import Table
from rich.text import Text

from .companion import CompanionSession
from .config import load_config
from .memory import MemoryStore
from .routing import RoutingLLM

_NAME_CLEAN = re.compile(r"[\[\]\r\n\t]+")


def _clean_name(value: str, fallback: str) -> str:
    value = _NAME_CLEAN.sub(" ", str(value or "")).strip()
    value = " ".join(value.split())[:28]
    return value or fallback


def _message_renderable(name: str, body: str, *, assistant: bool):
    table = Table.grid(padding=(0, 1))
    table.add_column(no_wrap=True)
    table.add_column(ratio=1, overflow="fold")
    label = Text(f"[{name}] :", style="bold bright_magenta" if assistant else "bold bright_cyan")
    if assistant:
        content = RichMarkdown(str(body or " "), hyperlinks=False, code_theme="monokai")
    else:
        content = Text(str(body or " "))
    table.add_row(label, content)
    return table


@dataclass
class _PendingConfirm:
    event: threading.Event
    value: bool = False


def run_chat_surface() -> None:
    try:
        from textual import work
        from textual.app import App, ComposeResult
        from textual.containers import VerticalScroll
        from textual.screen import ModalScreen
        from textual.widgets import Input, Static
    except ImportError as exc:
        raise RuntimeError("Textual belum tersedia") from exc

    class ConfirmScreen(ModalScreen[bool]):
        CSS = """
        ConfirmScreen {
            align: center middle;
            background: rgba(0, 0, 0, 0.55);
        }
        #confirm-box {
            width: 88%;
            max-width: 58;
            height: auto;
            padding: 1 2;
            background: #101010;
            color: #e8e8e8;
            border: solid #3a3a3a;
        }
        """
        BINDINGS = [
            ("enter", "allow", ""),
            ("y", "allow", ""),
            ("escape", "cancel", ""),
            ("n", "cancel", ""),
        ]

        def compose(self) -> ComposeResult:
            yield Static(
                "[bold]Furina perlu menggunakan layar untuk menjalankan perintah ini.[/]\n\n"
                "[bright_cyan]Enter[/] izinkan    [dim]Esc[/] batal",
                id="confirm-box",
                markup=True,
            )

        def action_allow(self) -> None:
            self.dismiss(True)

        def action_cancel(self) -> None:
            self.dismiss(False)

    class ChatApp(App[None]):
        CSS = """
        Screen {
            background: #000000;
            color: #e6e6e6;
        }

        #header {
            height: 2;
            padding: 0 1;
            background: #000000;
            color: #f0f0f0;
        }

        #messages {
            height: 1fr;
            padding: 0 1;
            background: #000000;
            scrollbar-size: 1 1;
            scrollbar-color: #3a3a3a;
            scrollbar-color-hover: #555555;
            scrollbar-background: #000000;
        }

        .message {
            width: 100%;
            height: auto;
            margin: 0 0 1 0;
            background: #000000;
            color: #e8e8e8;
        }

        #status {
            height: 1;
            padding: 0 1;
            color: #6f6f6f;
            background: #000000;
        }

        #composer {
            height: 3;
            padding: 0 1;
            border: none;
            border-top: solid #262626;
            background: #080808;
            color: #f2f2f2;
        }

        #composer:focus {
            border: none;
            border-top: solid #343434;
        }
        """
        BINDINGS = [
            ("escape", "back", ""),
            ("pageup", "scroll_up", ""),
            ("pagedown", "scroll_down", ""),
            ("ctrl+l", "clear_view", ""),
        ]

        def __init__(self) -> None:
            super().__init__()
            cfg = load_config()
            self.cfg = cfg
            self.persona_name = _clean_name(getattr(cfg, "persona_name", "") or "Furina", "Furina")
            self.user_name = _clean_name(getattr(cfg, "user_nickname", "") or "You", "You")
            self.session = CompanionSession(cfg, MemoryStore(), RoutingLLM(cfg))
            self.busy = False
            self._history: list[str] = []
            self._history_index = -1
            self._history_draft = ""
            self._assistant_seq = 0

        def compose(self) -> ComposeResult:
            yield Static(
                Text.assemble(
                    (f"{self.persona_name} By Wynn", "bold bright_cyan"),
                    ("  ·  Chat\n", "bold"),
                    ("/back untuk kembali", "dim"),
                ),
                id="header",
            )
            yield VerticalScroll(id="messages")
            yield Static("", id="status")
            yield Input(placeholder="Tulis pesan…", id="composer")

        def on_mount(self) -> None:
            self.query_one("#composer", Input).focus()

        def _append_message(self, role: str, body: str, *, widget_id: str | None = None) -> Static:
            assistant = role == "assistant"
            name = self.persona_name if assistant else self.user_name
            widget = Static(
                _message_renderable(name, body, assistant=assistant),
                classes="message",
                id=widget_id,
            )
            container = self.query_one("#messages", VerticalScroll)
            container.mount(widget)
            container.scroll_end(animate=False)
            return widget

        def _set_status(self, text: str) -> None:
            self.query_one("#status", Static).update(text)

        def _set_busy(self, busy: bool) -> None:
            self.busy = busy
            composer = self.query_one("#composer", Input)
            composer.disabled = busy
            if not busy:
                composer.focus()

        def _assistant_id(self) -> str:
            self._assistant_seq += 1
            return f"assistant-{self._assistant_seq}"

        def _update_assistant(self, widget_id: str, body: str) -> None:
            try:
                widget = self.query_one(f"#{widget_id}", Static)
            except Exception:
                return
            widget.update(_message_renderable(self.persona_name, body, assistant=True))
            self.query_one("#messages", VerticalScroll).scroll_end(animate=False)

        def _finalize(self, widget_id: str, body: str) -> None:
            self._update_assistant(widget_id, body or "…")
            self._set_status("")
            self._set_busy(False)

        def _fail(self, widget_id: str) -> None:
            self._update_assistant(widget_id, "Aku tidak bisa menyelesaikan respons itu.")
            self._set_status("")
            self._set_busy(False)

        def _request_device_confirmation(self) -> bool:
            pending = _PendingConfirm(threading.Event())

            def show() -> None:
                def done(value: bool | None) -> None:
                    pending.value = bool(value)
                    pending.event.set()
                self.push_screen(ConfirmScreen(), done)

            self.call_from_thread(show)
            pending.event.wait()
            return pending.value

        def on_input_submitted(self, event: Input.Submitted) -> None:
            if self.busy:
                return
            text = event.value.strip()
            event.input.value = ""
            self._history_index = -1
            self._history_draft = ""
            if not text:
                return
            if text.casefold() in {"/back", "/exit", "/quit"}:
                self.exit()
                return
            if text.casefold() == "/clear":
                self.query_one("#messages", VerticalScroll).remove_children()
                return

            if not self._history or self._history[-1] != text:
                self._history.append(text)
                if len(self._history) > 100:
                    self._history = self._history[-100:]

            self._append_message("user", text)
            assistant_id = self._assistant_id()
            self._append_message("assistant", "…", widget_id=assistant_id)
            self._set_status(f"{self.persona_name} sedang mengetik…")
            self._set_busy(True)
            self._respond(text, assistant_id)

        @work(thread=True, exclusive=True)
        def _respond(self, text: str, assistant_id: str) -> None:
            try:
                intent = self.session.classify(text)
                if intent.mode == "device":
                    allowed = self._request_device_confirmation()
                    if not allowed:
                        self.call_from_thread(
                            self._finalize,
                            assistant_id,
                            "Baik. Aku tidak menyentuh layar.",
                        )
                        return
                    self.call_from_thread(self._set_status, f"{self.persona_name} menjalankan tugas…")
                    self.session.store.add_message("user", text)
                    reply = self.session.agent.run(
                        intent.goal,
                        lambda *_args: True,
                        task_authorized=True,
                    )
                    self.session.store.add_message("assistant", reply)
                    self.call_from_thread(self._finalize, assistant_id, reply)
                    return

                pieces: list[str] = []
                last_draw = 0.0

                def on_token(piece: str) -> None:
                    nonlocal last_draw
                    pieces.append(piece)
                    now = time.monotonic()
                    if now - last_draw < 0.035 and len(piece) < 32:
                        return
                    last_draw = now
                    self.call_from_thread(
                        self._update_assistant,
                        assistant_id,
                        "".join(pieces),
                    )

                answer = self.session.chat.respond(text, on_token=on_token)
                self.call_from_thread(self._finalize, assistant_id, answer)
            except Exception:
                self.call_from_thread(self._fail, assistant_id)

        def action_back(self) -> None:
            if not self.busy:
                self.exit()

        def action_scroll_up(self) -> None:
            self.query_one("#messages", VerticalScroll).scroll_relative(y=-10, animate=False)

        def action_scroll_down(self) -> None:
            self.query_one("#messages", VerticalScroll).scroll_relative(y=10, animate=False)

        def action_clear_view(self) -> None:
            if not self.busy:
                self.query_one("#messages", VerticalScroll).remove_children()

        def on_key(self, event) -> None:
            if self.busy:
                return
            try:
                composer = self.query_one("#composer", Input)
            except Exception:
                return
            if self.focused is not composer:
                return
            if event.key == "up":
                if not self._history:
                    return
                if self._history_index < 0:
                    self._history_draft = composer.value
                    self._history_index = len(self._history) - 1
                elif self._history_index > 0:
                    self._history_index -= 1
                composer.value = self._history[self._history_index]
                composer.cursor_position = len(composer.value)
                event.stop()
            elif event.key == "down" and self._history_index >= 0:
                if self._history_index < len(self._history) - 1:
                    self._history_index += 1
                    composer.value = self._history[self._history_index]
                else:
                    self._history_index = -1
                    composer.value = self._history_draft
                composer.cursor_position = len(composer.value)
                event.stop()

    ChatApp().run()
