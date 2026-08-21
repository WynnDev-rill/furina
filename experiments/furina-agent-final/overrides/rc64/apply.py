#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

OLD_VERSION = 'VERSION = "1.0.0-rc63"'
NEW_VERSION = 'VERSION = "1.0.0-rc64"'


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC64 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <furina-root>")
    root = Path(sys.argv[1]).resolve(); core = root / "core" / "furina_agent"; here = Path(__file__).resolve().parent
    version = core / "version.py"; hub = core / "hub.py"; tui = core / "tui.py"
    for path in (version, hub, tui, here / "lite_full.py"):
        if not path.is_file():
            raise SystemExit(f"RC64 source missing: {path}")
    v = once(version.read_text(encoding="utf-8"), OLD_VERSION, NEW_VERSION, "Core RC63")
    h = hub.read_text(encoding="utf-8")
    if "from .lite_full import ProductWorkspace" not in h:
        h = h.replace("from .hub_settings import (", "from .lite_full import ProductWorkspace\nfrom .hub_settings import (", 1)
    marker = "RUNTIME = Runtime()"
    extension = r'''
# RC64: one local product workspace serves Furina Lite and FurinaHub Full.
_rc64_original_rebuild = Runtime._rebuild
def _rc64_rebuild(self):
    _rc64_original_rebuild(self)
    self.workspace = ProductWorkspace(self.store)
Runtime._rebuild = _rc64_rebuild

_rc64_original_bootstrap = Runtime.bootstrap
def _rc64_bootstrap(self):
    payload = _rc64_original_bootstrap(self)
    payload["surface"] = {"termux": "lite", "furinahub": "full", "shared_workspace": True}
    payload["workspace"] = self.workspace.snapshot()
    return payload
Runtime.bootstrap = _rc64_bootstrap

_rc64_original_memory = Runtime.memory_snapshot
def _rc64_memory(self):
    payload = _rc64_original_memory(self)
    payload.update(self.workspace.snapshot())
    return payload
Runtime.memory_snapshot = _rc64_memory

def _rc64_workspace(self): return self.workspace.snapshot()
def _rc64_focus(self, payload): return self.workspace.change_focus(payload if isinstance(payload, dict) else {})
def _rc64_memory_inbox(self, payload):
    payload = payload if isinstance(payload, dict) else {}
    action = str(payload.get("action") or "").lower()
    if action == "propose": return self.workspace.propose_memory(payload.get("text"), payload.get("source_ref"))
    if action in {"accept", "reject"}: return self.workspace.decide_memory(payload.get("id"), action, payload.get("text"))
    raise ValueError("aksi Kotak Masuk Memori tidak valid")
def _rc64_profile(self, payload): return self.workspace.set_profile((payload or {}).get("profile"))
def _rc64_backup(self): return self.workspace.create_backup()
Runtime.workspace_snapshot = _rc64_workspace
Runtime.change_focus = _rc64_focus
Runtime.change_memory_inbox = _rc64_memory_inbox
Runtime.change_response_profile = _rc64_profile
Runtime.create_workspace_backup = _rc64_backup

'''
    if extension not in h:
        h = once(h, marker, extension + marker, "Runtime singleton")
    h = once(h, '            if path == "/api/system":\n                self._json(RUNTIME.system_snapshot()); return\n', '            if path == "/api/system":\n                self._json(RUNTIME.system_snapshot()); return\n            if path == "/api/workspace":\n                self._json(RUNTIME.workspace_snapshot()); return\n', "workspace GET route")
    h = once(h, '            if path == "/api/memory":\n                self._json(RUNTIME.change_memory(body)); return\n', '            if path == "/api/memory":\n                self._json(RUNTIME.change_memory(body)); return\n            if path == "/api/memory/inbox":\n                self._json(RUNTIME.change_memory_inbox(body)); return\n            if path == "/api/focus":\n                self._json(RUNTIME.change_focus(body)); return\n            if path == "/api/profile":\n                self._json(RUNTIME.change_response_profile(body)); return\n            if path == "/api/backup":\n                self._json(RUNTIME.create_workspace_backup()); return\n', "workspace POST routes")
    t = tui.read_text(encoding="utf-8")
    if "from .lite_full import ProductWorkspace" not in t:
        t = t.replace("from .llm import LocalLLM\n", "from .llm import LocalLLM\nfrom .lite_full import ProductWorkspace\n", 1)
    tui_extension = r'''

def _lite_workspace():
    return ProductWorkspace(MemoryStore())

def _lite_focus(console):
    workspace = _lite_workspace()
    while True:
        _clear(); _header(console, "Furina Lite · Fokus")
        rows = workspace.focus_list()
        if rows:
            for item in rows[:12]:
                due = float(item.get("due_at") or 0)
                when = time.strftime("%d %b · %H:%M", time.localtime(due)) if due else "tanpa waktu"
                console.print(f"[bright_cyan]{item['id']:>2}[/]  {item['text']}  [dim]{when}[/]")
        else:
            console.print("[dim]Belum ada fokus aktif.[/]")
        choice = _choose("", ["Tambah fokus", "Selesaikan", "Tunda", "Kembali"], height=7)
        if choice in {"", "Kembali"}: return
        if choice == "Tambah fokus":
            text = _input("Fokus › ", placeholder="Mis. selesaikan desain FurinaHub")
            when = _input("Waktu (opsional) › ", placeholder="besok sore")
            try: workspace.change_focus({"action":"add", "text":text, "when":when})
            except Exception as exc: console.print(f"[red]{exc}[/]")
        else:
            item_id = _input("Nomor fokus › ")
            try:
                workspace.change_focus({"action":"done" if choice == "Selesaikan" else "snooze", "id":item_id, "when": _input("Tunda sampai › ", placeholder="besok sore") if choice == "Tunda" else ""})
            except Exception as exc: console.print(f"[red]{exc}[/]")
        _pause()

def _lite_profile(console):
    workspace = _lite_workspace(); data = workspace.profile()
    _clear(); _header(console, "Furina Lite · Profil respons")
    console.print("[dim]Profil yang sama juga dipakai FurinaHub.[/]\n")
    options = [f"{p['label']}" + ("  · aktif" if p['id'] == data['current'] else "") for p in data['profiles']] + ["Kembali"]
    picked = _choose("", options, height=8)
    if picked and picked != "Kembali":
        profile = data['profiles'][options.index(picked)]['id']
        workspace.set_profile(profile)
        console.print("[green]Profil disimpan untuk Lite dan FurinaHub.[/]"); _pause()

def _lite_backup(console):
    _clear(); _header(console, "Furina Lite · Backup")
    console.print("[dim]Ekspor berisi memori dan konfigurasi non-rahasia. API key, provider secret, model, dan log tidak ikut.[/]")
    if _confirm("Buat ekspor lokal sekarang?", default=False):
        try:
            item = _lite_workspace().create_backup()
            console.print(f"[green]Selesai[/]  {item['path']}")
        except Exception as exc: console.print(f"[red]Backup gagal[/]  {exc}")
        _pause()

def _lite_actions(console):
    _clear(); _header(console, "Furina Lite · Aksi & Skill")
    cfg = load_config()
    console.print(f"[dim]Mode perangkat[/]  {cfg.device_control_mode.upper()}")
    console.print("[dim]Aksi eksternal tetap meminta persetujuan saat dijalankan. Kelola detail kemampuan dari Pengaturan atau FurinaHub.[/]")
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
        choice = _choose("", ["Chat", "Fokus & Reminder", "Memory", "Profil respons", "Provider & Model", "Aksi & Skill", "System", "Backup", "Update", "Exit"], height=12)
        if choice in {"", "Exit"}: return
        if choice == "Chat": _chat(console)
        elif choice == "Fokus & Reminder": _lite_focus(console)
        elif choice == "Memory": _memory_menu(console)
        elif choice == "Profil respons": _lite_profile(console)
        elif choice == "Provider & Model": _providers(console)
        elif choice == "Aksi & Skill": _lite_actions(console)
        elif choice == "System": _system(console)
        elif choice == "Backup": _lite_backup(console)
        elif choice == "Update": _update_repair(console)
'''
    if "def _lite_workspace():" not in t:
        t += tui_extension
    (core / "lite_full.py").write_text((here / "lite_full.py").read_text(encoding="utf-8"), encoding="utf-8")
    version.write_text(v, encoding="utf-8"); hub.write_text(h, encoding="utf-8"); tui.write_text(t, encoding="utf-8")
    print("FURINA_RC64_LITE_FULL_SHARED_WORKSPACE_OK")


if __name__ == "__main__":
    main()
