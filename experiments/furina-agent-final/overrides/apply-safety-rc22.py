#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC22 safety marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-safety-rc22.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    agent = core / "agent.py"
    chat = core / "chat_surface.py"
    if not agent.is_file() or not chat.is_file():
        raise SystemExit("missing RC22 safety source")

    a = agent.read_text(encoding="utf-8")
    a = rep(
        a,
        '            needs_approval = (not task_authorized) and risk in {"external", "uncertain", "navigate", "write"}\n',
        '''            # A task-level screen permission only authorizes ordinary navigation/input.
            # External side effects and ambiguous targets always need a fresh, specific confirmation.
            needs_approval = risk in {"external", "uncertain"} or (
                (not task_authorized) and risk in {"navigate", "write"}
            )
''',
        "external approval policy",
    )
    agent.write_text(a, encoding="utf-8")

    c = chat.read_text(encoding="utf-8")
    c = rep(
        c,
        'from rich.markdown import Markdown as RichMarkdown\n',
        'from rich.markdown import Markdown as RichMarkdown\nfrom rich.markup import escape as rich_escape\n',
        "markup escape import",
    )
    c = rep(
        c,
        '''        def __init__(self) -> None:
            super().__init__()
            self._allow_selected = True
        def _body(self) -> str:
''',
        '''        def __init__(self, message: str = "Izin menggunakan layar untuk menyelesaikan tugas ini.", *, default_allow: bool = True) -> None:
            super().__init__()
            self._message = rich_escape(str(message or "Konfirmasi tindakan Furina."))
            self._allow_selected = bool(default_allow)
        def _body(self) -> str:
''',
        "configurable confirmation modal",
    )
    c = rep(
        c,
        r'''                "Izin menggunakan layar untuk menyelesaikan tugas ini.\n\n"
                + allow + "        " + cancel
''',
        r'''                + self._message + "\n\n"
                + allow + "        " + cancel
''',
        "confirmation message",
    )
    c = rep(
        c,
        '''        def _request_device_confirmation(self) -> bool:
            pending = _PendingConfirm(threading.Event())

            def show() -> None:
                def done(value: bool | None) -> None:
                    pending.value = bool(value)
                    pending.event.set()
                self.push_screen(ConfirmScreen(), done)

            self.call_from_thread(show)
            if not pending.event.wait(300):
                return False
            return pending.value
''',
        r'''        def _request_confirmation(self, message: str, *, default_allow: bool) -> bool:
            pending = _PendingConfirm(threading.Event())

            def show() -> None:
                def done(value: bool | None) -> None:
                    pending.value = bool(value)
                    pending.event.set()
                self.push_screen(ConfirmScreen(message, default_allow=default_allow), done)

            self.call_from_thread(show)
            if not pending.event.wait(300):
                return False
            return pending.value

        def _request_device_confirmation(self) -> bool:
            return self._request_confirmation(
                "Izin menggunakan layar untuk menyelesaikan tugas ini.",
                default_allow=True,
            )

        def _approve_agent_action(self, summary, action, risk, detail) -> bool:
            if risk not in {"external", "uncertain"}:
                return True
            if risk == "external":
                prefix = "Aksi berikut dapat mengirim, membagikan, menelepon, atau memberi efek ke luar aplikasi."
            else:
                prefix = "Target tindakan belum cukup pasti."
            label = str(summary or detail or "Tindakan berikutnya").strip()
            if len(label) > 140:
                label = label[:137] + "..."
            return self._request_confirmation(
                prefix + ("\n\n" + label if label else ""),
                default_allow=False,
            )
''',
        "action confirmation callback",
    )
    c = rep(
        c,
        '''                    reply = self.session.agent.run(
                        intent.goal,
                        lambda *_args: True,
                        task_authorized=True,
                    )
''',
        '''                    reply = self.session.agent.run(
                        intent.goal,
                        self._approve_agent_action,
                        task_authorized=True,
                    )
''',
        "real agent approval callback",
    )
    chat.write_text(c, encoding="utf-8")

    for path in (agent, chat):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    checks = [
        (agent, 'needs_approval = risk in {"external", "uncertain"}'),
        (chat, "def _approve_agent_action"),
        (chat, "default_allow=False"),
        (chat, "self._approve_agent_action"),
        (chat, "rich_escape"),
    ]
    missing = [needle for path, needle in checks if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC22 safety incomplete: " + ", ".join(missing))
    if "lambda *_args: True" in chat.read_text(encoding="utf-8"):
        raise SystemExit("unsafe approval bypass still present")
    print("Furina RC22 external-effect confirmation guard: OK")


if __name__ == "__main__":
    main()
