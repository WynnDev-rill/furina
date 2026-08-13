#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC12 postfix marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-ui-rc12-postfix.py <termux-root>")

    root = pathlib.Path(sys.argv[1]).resolve()
    tui = root / "core/furina_agent/tui.py"
    chat = root / "core/furina_agent/chat_surface.py"
    if not tui.is_file() or not chat.is_file():
        raise SystemExit("RC12 postfix source missing")

    text = tui.read_text(encoding="utf-8")
    duplicate = "def _main_menu(console) -> str:\ndef _main_menu(console) -> str:\n"
    if duplicate in text:
        text = text.replace(duplicate, "def _main_menu(console) -> str:\n", 1)
    elif text.count("def _main_menu(console) -> str:") != 1:
        raise SystemExit("RC12 main menu marker is not deterministic")

    chat_text = chat.read_text(encoding="utf-8")

    # Keep Textual mouse reporting disabled on Android/Termux. Enabling it makes
    # the terminal consume taps as TUI mouse events, which can prevent the soft
    # keyboard from opening when the user taps the composer. Kira likewise uses
    # keyboard-driven chat scrolling, so make those controls authoritative.
    if "from textual.binding import Binding\n" not in chat_text:
        chat_text = replace_once(
            chat_text,
            "        from textual.app import App, ComposeResult\n",
            "        from textual.app import App, ComposeResult\n        from textual.binding import Binding\n",
            "Binding import",
        )

    old_bindings = '''        BINDINGS = [
            ("escape", "back", ""),
            ("pageup", "scroll_up", ""),
            ("pagedown", "scroll_down", ""),
            ("ctrl+l", "clear_view", ""),
        ]
'''
    new_bindings = '''        BINDINGS = [
            Binding("escape", "back", "", show=False, priority=True),
            Binding("up", "scroll_up", "", show=False, priority=True),
            Binding("down", "scroll_down", "", show=False, priority=True),
            Binding("pageup", "scroll_page_up", "", show=False, priority=True),
            Binding("pagedown", "scroll_page_down", "", show=False, priority=True),
            Binding("shift+up", "history_up", "", show=False, priority=True),
            Binding("shift+down", "history_down", "", show=False, priority=True),
            Binding("ctrl+l", "clear_view", "", show=False, priority=True),
        ]
'''
    chat_text = replace_once(chat_text, old_bindings, new_bindings, "priority scroll bindings")

    # The thin scrollbar remains a position indicator. The explicit hint makes
    # the actual Termux controls discoverable instead of implying drag support.
    chat_text = chat_text.replace(
        "Esc kembali  ·  /back",
        "↑↓ scroll  ·  Esc kembali  ·  /back",
    )

    old_actions = '''        def action_scroll_up(self) -> None:
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
'''
    new_actions = '''        def action_scroll_up(self) -> None:
            self.query_one("#messages", VerticalScroll).scroll_relative(y=-3, animate=False)

        def action_scroll_down(self) -> None:
            self.query_one("#messages", VerticalScroll).scroll_relative(y=3, animate=False)

        def action_scroll_page_up(self) -> None:
            self.query_one("#messages", VerticalScroll).scroll_relative(y=-20, animate=False)

        def action_scroll_page_down(self) -> None:
            self.query_one("#messages", VerticalScroll).scroll_relative(y=20, animate=False)

        def action_clear_view(self) -> None:
            if not self.busy:
                self.query_one("#messages", VerticalScroll).remove_children()

        def action_history_up(self) -> None:
            if self.busy or not self._history:
                return
            composer = self.query_one("#composer", Input)
            if self._history_index < 0:
                self._history_draft = composer.value
                self._history_index = len(self._history) - 1
            elif self._history_index > 0:
                self._history_index -= 1
            composer.value = self._history[self._history_index]
            composer.cursor_position = len(composer.value)

        def action_history_down(self) -> None:
            if self.busy or self._history_index < 0:
                return
            composer = self.query_one("#composer", Input)
            if self._history_index < len(self._history) - 1:
                self._history_index += 1
                composer.value = self._history[self._history_index]
            else:
                self._history_index = -1
                composer.value = self._history_draft
            composer.cursor_position = len(composer.value)
'''
    chat_text = replace_once(chat_text, old_actions, new_actions, "Kira-style scroll and history controls")

    # Fail while the new Core is still staged. Never allow invalid Python to
    # replace the currently working installation.
    compile(text, str(tui), "exec")
    compile(chat_text, str(chat), "exec")

    required_chat = [
        "ChatApp().run(mouse=False)",
        'Binding("up", "scroll_up", "", show=False, priority=True)',
        'Binding("down", "scroll_down", "", show=False, priority=True)',
        'Binding("pageup", "scroll_page_up", "", show=False, priority=True)',
        'Binding("pagedown", "scroll_page_down", "", show=False, priority=True)',
        'Binding("shift+up", "history_up", "", show=False, priority=True)',
        "↑↓ scroll  ·  Esc kembali  ·  /back",
        "def action_scroll_page_up(self) -> None:",
        "def action_history_up(self) -> None:",
    ]
    missing = [marker for marker in required_chat if marker not in chat_text]
    if missing:
        raise SystemExit("RC12 mobile chat scroll contract incomplete: " + ", ".join(missing))
    if "class _ThemedConsole:" not in text:
        raise SystemExit("RC12 unified theme missing")

    tui.write_text(text, encoding="utf-8")
    chat.write_text(chat_text, encoding="utf-8")
    print("Furina RC12 UI postfix + syntax/scroll guard: OK")


if __name__ == "__main__":
    main()
