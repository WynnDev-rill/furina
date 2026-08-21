#!/usr/bin/env python3
"""RC65: capture useful context at the conversation, without a second data silo."""
from __future__ import annotations

import sys
from pathlib import Path


OLD_VERSION = 'VERSION = "1.0.0-rc64"'
NEW_VERSION = 'VERSION = "1.0.0-rc65"'


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC65 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <furina-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core" / "furina_agent"
    version, hub, tui, workspace = (core / "version.py", core / "hub.py", core / "tui.py", core / "lite_full.py")
    for path in (version, hub, tui, workspace):
        if not path.is_file():
            raise SystemExit(f"RC65 source missing: {path}")

    version.write_text(once(version.read_text(encoding="utf-8"), OLD_VERSION, NEW_VERSION, "Core RC64"), encoding="utf-8")

    w = workspace.read_text(encoding="utf-8")
    methods = r'''
    def brief(self) -> dict:
        """Small, bounded snapshot for the Lite home and FurinaHub Today page."""
        focus = self.focus_list()
        inbox = self.inbox_list()
        return {
            "next_focus": focus[0] if focus else None,
            "focus_count": len(focus),
            "memory_inbox_count": len(inbox),
            "profile": self.profile(),
        }

    def capture(self, payload: dict) -> dict:
        """Turn an explicit user action on a message into a reviewable item.

        This is deliberately opt-in.  The assistant does not silently convert
        every sentence into memory or todos, which avoids stale/noisy context.
        """
        action = str(payload.get("action") or "").strip().lower()
        text = self._text(payload.get("text"), low=4, high=600)
        source_ref = str(payload.get("source_ref") or "conversation")[:160]
        if action == "memory":
            return self.propose_memory(text, source_ref)
        if action == "focus":
            return self.change_focus({"action": "add", "text": text, "when": payload.get("when"), "source": "conversation"})
        raise ValueError("aksi tangkap percakapan tidak valid")

'''
    if "    def brief(self) -> dict:" not in w:
        w = once(w, "    def snapshot(self) -> dict:\n", methods + "    def snapshot(self) -> dict:\n", "workspace snapshot")
    w = once(
        w,
        '        return {"profile": self.profile(), "focus": self.focus_list(), "memory_inbox": self.inbox_list()}\n',
        '        return {"profile": self.profile(), "focus": self.focus_list(), "memory_inbox": self.inbox_list(), "brief": self.brief()}\n',
        "workspace snapshot payload",
    )
    workspace.write_text(w, encoding="utf-8")

    h = hub.read_text(encoding="utf-8")
    extension = r'''
# RC65: conversation capture is explicit, reviewable, and shared by both surfaces.
def _rc65_workspace_brief(self): return self.workspace.brief()
def _rc65_capture(self, payload): return self.workspace.capture(payload if isinstance(payload, dict) else {})
Runtime.workspace_brief = _rc65_workspace_brief
Runtime.capture_from_conversation = _rc65_capture

'''
    marker = "RUNTIME = Runtime()"
    if extension not in h:
        h = once(h, marker, extension + marker, "Runtime singleton")
    h = once(
        h,
        '            if path == "/api/workspace":\n                self._json(RUNTIME.workspace_snapshot()); return\n',
        '            if path == "/api/workspace":\n                self._json(RUNTIME.workspace_snapshot()); return\n            if path == "/api/workspace/brief":\n                self._json(RUNTIME.workspace_brief()); return\n',
        "workspace brief GET route",
    )
    h = once(
        h,
        '            if path == "/api/backup":\n                self._json(RUNTIME.create_workspace_backup()); return\n',
        '            if path == "/api/backup":\n                self._json(RUNTIME.create_workspace_backup()); return\n            if path == "/api/capture":\n                self._json(RUNTIME.capture_from_conversation(body)); return\n',
        "conversation capture POST route",
    )
    hub.write_text(h, encoding="utf-8")

    t = tui.read_text(encoding="utf-8")
    tui_extension = r'''

def _lite_today(console):
    workspace = _lite_workspace(); brief = workspace.brief()
    _clear(); _header(console, "Furina Lite · Hari ini")
    item = brief.get("next_focus")
    if item:
        due = float(item.get("due_at") or 0)
        when = time.strftime("%d %b · %H:%M", time.localtime(due)) if due else "tanpa waktu"
        console.print(f"[bright_cyan]Berikutnya[/]  {item['text']}  [dim]{when}[/]")
    else:
        console.print("[dim]Belum ada Fokus aktif. Tambahkan hanya hal yang memang ingin kamu tindaklanjuti.[/]")
    console.print(f"[dim]Fokus aktif:[/] {brief['focus_count']}   [dim]Memori menunggu tinjauan:[/] {brief['memory_inbox_count']}")
    console.print(f"[dim]Profil respons:[/] {brief['profile']['current']}")
    _pause()

def run_tui():
    Console, _, _, _, _, _, _ = _rich()
    console = _ThemedConsole(Console(highlight=False))
    cfg = load_config()
    if not cfg.onboarding_complete: _setup(console)
    _auto_start_local(console)
    while True:
        _clear(); _header(console, "Furina Lite · Termux")
        _show_due(console)
        choice = _choose("", ["Hari ini", "Chat", "Fokus & Reminder", "Memory", "Profil respons", "Provider & Model", "Aksi & Skill", "System", "Backup", "Update", "Exit"], height=13)
        if choice in {"", "Exit"}: return
        if choice == "Hari ini": _lite_today(console)
        elif choice == "Chat": _chat(console)
        elif choice == "Fokus & Reminder": _lite_focus(console)
        elif choice == "Memory": _memory_menu(console)
        elif choice == "Profil respons": _lite_profile(console)
        elif choice == "Provider & Model": _providers(console)
        elif choice == "Aksi & Skill": _lite_actions(console)
        elif choice == "System": _system(console)
        elif choice == "Backup": _lite_backup(console)
        elif choice == "Update": _update_repair(console)
'''
    if "def _lite_today(console):" not in t:
        t += tui_extension
    tui.write_text(t, encoding="utf-8")
    print("FURINA_RC65_CONVERSATION_CAPTURE_AND_TODAY_OK")


if __name__ == "__main__":
    main()
