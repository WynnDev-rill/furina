#!/usr/bin/env python3
from __future__ import annotations
import pathlib, sys

def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text: return text
    if text.count(old) != 1: raise SystemExit(f"RC20 marker mismatch {label}: {text.count(old)}")
    return text.replace(old, new, 1)

def main() -> None:
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    agent = core / "agent.py"
    chat = core / "chat_surface.py"
    version = core / "version.py"
    a = agent.read_text(encoding="utf-8")
    a = rep(a, '''        left_termux = False
        cancel_event = threading.Event()
        task_started = time.monotonic()
        def watch_user_return():
            seen_outside = False
            while not cancel_event.is_set() and time.monotonic() - task_started < 300:
                package = str(self.store.get_state("device_foreground_package", "") or "")
                if package and package not in TERMUX_PACKAGES:
                    seen_outside = True
                elif seen_outside and package in TERMUX_PACKAGES:
                    cancel_event.set()
                    return
                time.sleep(0.05)
''', '''        left_termux = False
        termux_return_candidate_at = 0.0
        cancel_event = threading.Event()
        task_started = time.monotonic()
        def watch_user_return():
            seen_outside = False
            returned_at = 0.0
            while not cancel_event.is_set() and time.monotonic() - task_started < 300:
                package = str(self.store.get_state("device_foreground_package", "") or "")
                now = time.monotonic()
                if package and package not in TERMUX_PACKAGES:
                    seen_outside = True
                    returned_at = 0.0
                elif seen_outside and package in TERMUX_PACKAGES:
                    if returned_at <= 0.0:
                        returned_at = now
                    elif now - returned_at >= 0.75:
                        cancel_event.set()
                        return
                else:
                    returned_at = 0.0
                time.sleep(0.05)
''', "return watcher")
    a = rep(a, '''        def user_returned_to_termux(screen: dict) -> bool:
            nonlocal left_termux
            package = str(screen.get("package") or "")
            if package and package not in TERMUX_PACKAGES:
                left_termux = True
                return False
            return bool(left_termux and package in TERMUX_PACKAGES)
''', '''        def user_returned_to_termux(screen: dict) -> bool:
            nonlocal left_termux, termux_return_candidate_at
            package = str(screen.get("package") or "")
            now = time.monotonic()
            if package and package not in TERMUX_PACKAGES:
                left_termux = True
                termux_return_candidate_at = 0.0
                return False
            if left_termux and package in TERMUX_PACKAGES:
                if termux_return_candidate_at <= 0.0:
                    termux_return_candidate_at = now
                    return False
                return now - termux_return_candidate_at >= 0.75
            termux_return_candidate_at = 0.0
            return False
''', "snapshot return")
    agent.write_text(a, encoding="utf-8")
    c = chat.read_text(encoding="utf-8")
    start = c.find("    class ConfirmScreen(ModalScreen[bool]):\n")
    end = c.find("    class ChatApp(App[None]):\n", start)
    confirm = '''    class ConfirmScreen(ModalScreen[bool]):
        CSS = """
        ConfirmScreen { align: center middle; background: rgba(0,0,0,0.55); }
        #confirm-box { width: 88%; max-width: 58; height: auto; padding: 1 2; background: #101010; color: #e8e8e8; border: solid #3a3a3a; }
        """
        BINDINGS = [
            Binding("left", "choose_allow", "", show=False, priority=True),
            Binding("right", "choose_cancel", "", show=False, priority=True),
            Binding("enter", "confirm", "", show=False, priority=True),
            Binding("escape", "cancel", "", show=False, priority=True),
        ]
        def __init__(self) -> None:
            super().__init__(); self._allow_selected = True
        def _body(self) -> str:
            allow = "[bold bright_cyan]› Izinkan[/]" if self._allow_selected else "  Izinkan"
            cancel = "[bold bright_cyan]› Batal[/]" if not self._allow_selected else "  Batal"
            return "[bold]Furina perlu menggunakan layar untuk menjalankan perintah ini.[/]\\n\\n" + allow + "        " + cancel + "\\n\\n[dim]← → pilih · Enter konfirmasi · Esc batal[/]"
        def compose(self) -> ComposeResult: yield Static(self._body(), id="confirm-box", markup=True)
        def _refresh_choice(self) -> None: self.query_one("#confirm-box", Static).update(self._body())
        def action_choose_allow(self) -> None: self._allow_selected = True; self._refresh_choice()
        def action_choose_cancel(self) -> None: self._allow_selected = False; self._refresh_choice()
        def action_confirm(self) -> None: self.dismiss(bool(self._allow_selected))
        def action_cancel(self) -> None: self.dismiss(False)
'''
    if start < 0 or end < 0: raise SystemExit("RC20 ConfirmScreen markers missing")
    c = c[:start] + confirm + "\n" + c[end:]
    c = rep(c, '            Binding("escape", "back", "", show=False, priority=True),\n', '            Binding("escape", "back", "", show=False),\n', "parent escape")
    chat.write_text(c, encoding="utf-8")
    v = version.read_text(encoding="utf-8").replace('VERSION = "1.0.0-rc19"', 'VERSION = "1.0.0-rc20"', 1)
    version.write_text(v, encoding="utf-8")
    for path in (agent, chat, version): compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print("Furina Core RC20: OK")

if __name__ == "__main__": main()
