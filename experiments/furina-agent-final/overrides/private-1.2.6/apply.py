#!/usr/bin/env python3
"""Build Core 1.1.25: neutral conversation corpus and optional live choices."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"
HERE = Path(__file__).resolve().parent


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing {label}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: Path, marker: str, payload: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + payload.strip() + "\n", encoding="utf-8")


for name in ("training_corpus.py", "neutral_corpus.py", "training_v125.py", "tui_v125.py", "chat_v125.py"):
    shutil.copy2(HERE / name, CORE / name)
shutil.copy2(HERE / "CORPUS_NOTICE.md", CORE / "training_corpus.NOTICE.md")

replace_once(CORE / "version.py", 'VERSION = "1.1.24"', 'VERSION = "1.1.25"', "Core 1.1.24")
replace_once(CORE / "hub.py", 'EXPECTED_DEPENDENCY_REVISION = "2026.08.27-r74"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.27-r75"', "dependency r74")
replace_once(CORE / "hub.py", "furina-2026.08.27-termux-1.1.24", "furina-2026.08.27-termux-1.1.25", "bundle 1.1.24")
replace_once(CORE / "hub.py", 'expected_revision = "2026.08.27-r74"', 'expected_revision = "2026.08.27-r75"', "expected revision r74")

append_once(CORE / "training_room.py", "FURINA_TERMUX_125_NEUTRAL_CORPUS", r'''
# FURINA_TERMUX_125_NEUTRAL_CORPUS
from .training_v125 import install_training_v125
install_training_v125(globals())
''')
append_once(CORE / "chat.py", "FURINA_TERMUX_125_LIVE_TRAINING_COMMIT", r'''
# FURINA_TERMUX_125_LIVE_TRAINING_COMMIT
from .chat_v125 import install_chat_v125
install_chat_v125(globals())
''')
append_once(CORE / "tui.py", "FURINA_TERMUX_125_NEUTRAL_TRAINING_TUI", r'''
# FURINA_TERMUX_125_NEUTRAL_TRAINING_TUI
from .tui_v125 import install_tui_v125
install_tui_v125(globals())
''')

settings = CORE / "hub_settings.py"
replace_once(settings, '    base["full_local_memory"] = False\n    return base', '    base["full_local_memory"] = False\n    base["training_suggestions"] = False\n    return base', "settings default")
replace_once(settings, '    base["full_local_memory"] = bool(raw.get("full_local_memory", False))\n', '    base["full_local_memory"] = bool(raw.get("full_local_memory", False))\n    base["training_suggestions"] = bool(raw.get("training_suggestions", False))\n', "settings normalize")

surface = CORE / "chat_surface.py"
replace_once(surface, '''    class ChatApp(App[None]):''', r'''    @dataclass
    class _PendingChoice:
        event: threading.Event
        value: str = "skip"

    class LiveChoiceScreen(ModalScreen[str]):
        CSS = """
        LiveChoiceScreen {
            align: center middle;
            background: rgba(0, 0, 0, 0.80);
        }
        #live-choice-scroll {
            width: 94%;
            max-width: 86;
            height: 90%;
            padding: 1 2;
            background: #080f0d;
            color: #e7eee9;
            border: solid #1f6e5a;
        }
        #live-choice-box {
            width: 100%;
            height: auto;
            background: #080f0d;
            color: #e7eee9;
        }
        """
        BINDINGS = [
            Binding("left", "previous", "", show=False, priority=True),
            Binding("right", "next", "", show=False, priority=True),
            Binding("enter", "confirm", "", show=False, priority=True),
            Binding("escape", "skip", "", show=False, priority=True),
        ]
        def __init__(self, response_a: str, response_b: str) -> None:
            super().__init__()
            self._responses = (rich_escape(response_a), rich_escape(response_b))
            self._selected = 0
        def _body(self) -> str:
            labels = ("A", "B", "Lewati")
            strip = "  [#1f6e5a]│[/]  ".join(
                f"[bold #9efce7]› {label} ‹[/]" if i == self._selected else f"[#3d6b5e]{label}[/]"
                for i, label in enumerate(labels)
            )
            card = (
                f"[bold cyan]Respons A[/]\n\n{self._responses[0]}\n\n"
                f"[bold cyan]Respons B[/]\n\n{self._responses[1]}"
            )
            if self._selected == 2:
                card += "\n\n[bold #e8b86d]Lewati: buat satu jawaban baru tanpa menyimpan preferensi.[/]"
            return (
                "[bold #9efce7]Saran latihan[/]  [dim]Pilih jawaban yang lebih cocok[/]\n"
                "[#1f6e5a]────────────────────────────────[/]\n\n" + card + "\n\n" + strip
            )
        def compose(self) -> ComposeResult:
            yield VerticalScroll(Static(self._body(), id="live-choice-box", markup=True), id="live-choice-scroll")
        def _refresh(self) -> None:
            self.query_one("#live-choice-box", Static).update(self._body())
        def action_previous(self) -> None:
            self._selected = (self._selected - 1) % 3
            self._refresh()
        def action_next(self) -> None:
            self._selected = (self._selected + 1) % 3
            self._refresh()
        def action_confirm(self) -> None:
            self.dismiss(("a", "b", "skip")[self._selected])
        def action_skip(self) -> None:
            self.dismiss("skip")

    class ChatApp(App[None]):''', "live choice modal")
replace_once(surface, '''            self._assistant_seq = 0
''', '''            self._assistant_seq = 0
            self._live_offers = 0
''', "live offer session counter")
replace_once(surface, '''        def _request_device_confirmation(self) -> bool:
''', '''        def _request_live_choice(self, response_a: str, response_b: str) -> str:
            pending = _PendingChoice(threading.Event())

            def show() -> None:
                def done(value: str | None) -> None:
                    pending.value = value if value in {"a", "b"} else "skip"
                    pending.event.set()
                self.push_screen(LiveChoiceScreen(response_a, response_b), done)

            self.call_from_thread(show)
            if not pending.event.wait(300):
                return "skip"
            return pending.value

        def _request_device_confirmation(self) -> bool:
''', "live choice request")
replace_once(surface, '''                pieces: list[str] = []
''', '''                try:
                    from .training_room import (
                        generate_live_training_pair,
                        record_live_training_choice,
                        record_live_training_skip,
                        should_offer_live_training,
                    )
                    if should_offer_live_training(text, session_offers=self._live_offers):
                        self.call_from_thread(self._set_status, "Menyiapkan dua pilihan singkat…")
                        pair = generate_live_training_pair(self.session.chat, text)
                        choice = self._request_live_choice(pair.response_a, pair.response_b)
                        self._live_offers += 1
                        if choice in {"a", "b"}:
                            answer = record_live_training_choice(pair, choice)
                            self.session.chat.commit_preferred_response(text, answer)
                            self.call_from_thread(self._finalize, assistant_id, answer)
                            return
                        record_live_training_skip()
                        self.call_from_thread(self._set_status, f"{self.persona_name} membuat jawaban baru…")
                except Exception as live_exc:
                    try:
                        self.session.store.log_event("live_training_fallback", {"error": str(live_exc)[:300]})
                    except Exception:
                        pass

                pieces: list[str] = []
''', "live suggestion integration")

print("FURINA_TERMUX_125_NEUTRAL_LIVE_TRAINING_OK")
