#!/usr/bin/env python3
"""Build Core 1.1.21: interactive preference Training Room."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"
HERE = Path(__file__).resolve().parent


def append_once(path: Path, marker: str, payload: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text: return
    path.write_text(text.rstrip() + "\n\n" + payload.strip() + "\n", encoding="utf-8")


version = CORE / "version.py"
text = version.read_text(encoding="utf-8")
if 'VERSION = "1.1.20"' not in text: raise SystemExit("expected Core 1.1.20")
version.write_text(text.replace('VERSION = "1.1.20"', 'VERSION = "1.1.21"', 1), encoding="utf-8")

hub = CORE / "hub.py"
text = hub.read_text(encoding="utf-8")
if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r70"' not in text: raise SystemExit("expected dependency r70")
text = text.replace('EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r70"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r71"', 1)
text = text.replace("furina-2026.08.26-termux-1.1.20", "furina-2026.08.26-termux-1.1.21")
text = text.replace('expected_revision = "2026.08.26-r70"', 'expected_revision = "2026.08.26-r71"')
hub.write_text(text, encoding="utf-8")

shutil.copy2(HERE / "training_room.py", CORE / "training_room.py")

append_once(CORE / "chat.py", "FURINA_TERMUX_121_TRAINING_PREFERENCE_RUNTIME", r'''
# FURINA_TERMUX_121_TRAINING_PREFERENCE_RUNTIME
_furina_121_previous_messages = FurinaChat._messages
def _furina_121_messages(self, user_text, profile):
    from .training_room import runtime_preference_contract
    messages = _furina_121_previous_messages(self, user_text, profile)
    contract = runtime_preference_contract()
    if contract and messages and messages[0].get("role") == "system":
        messages[0] = {**messages[0], "content": str(messages[0].get("content") or "") + "\n\n" + contract}
    return messages
FurinaChat._messages = _furina_121_messages
''')

append_once(CORE / "tui.py", "FURINA_TERMUX_121_TRAINING_ROOM", r'''
# FURINA_TERMUX_121_TRAINING_ROOM
def _training_room_121(console):
    from .routing import RoutingLLM
    from .training_room import CATEGORIES, TrainingSession, read_training_key, training_progress
    labels = [item["label"] for item in CATEGORIES.values()]
    by_label = {item["label"]: key for key, item in CATEGORIES.items()}
    while True:
        progress = training_progress()
        _clear(); _header(console, "Training Room")
        console.print(f"[dim]Preferensi tersimpan[/]  {progress['total']} pilihan")
        console.print("[dim]Skenario hanya simulasi dan tidak masuk ke memori atau pengalaman nyata.[/]\n")
        choice = _choose("", labels + ["Kembali"], height=9)
        if choice in {"", "Kembali"}: return
        category_id = by_label.get(choice)
        if not category_id: continue
        cfg = load_config(); llm = RoutingLLM(cfg); session = TrainingSession(category_id, llm)
        pair = None; notice = ""
        while True:
            if pair is None:
                try:
                    _clear(); _header(console, "Training Room")
                    console.print(f"[#5de4c7]{choice}[/]  [dim]Membuat dua respons dari model aktif…[/]")
                    pair = session.generate()
                except Exception as exc:
                    console.print(f"\n[red]Tidak dapat membuat respons[/]  {str(exc)[:220]}")
                    console.print("[dim]Periksa Provider & Model, lalu coba lagi.[/]"); _pause(); break
            _clear(); _header(console, "Training Room")
            console.print(f"[#5de4c7]{choice}[/]  [dim]{pair.scene_title} · giliran {pair.turn_index + 1}/5[/]")
            console.print(f"\n[bold]User simulasi[/]\n{pair.user_text}")
            console.print(f"\n[bold cyan]A[/]\n{pair.response_a}")
            console.print(f"\n[bold cyan]B[/]\n{pair.response_b}")
            if notice: console.print(f"\n[green]{notice}[/]")
            console.print("\n[dim][A/B] pilih · [R] buat ulang · [ESC] keluar[/]", end="", markup=True)
            key = read_training_key()
            if key == "esc":
                summary = session.summary()
                _clear(); _header(console, "Training Room")
                console.print(f"[green]Sesi selesai.[/] {summary['choices']} pilihan baru tersimpan.")
                if summary["recent"]: console.print("[dim]Pola terakhir: " + " · ".join(summary["recent"]) + "[/]")
                _pause(); break
            if key == "r":
                session.reroll(); pair = None; notice = "Dua respons dibuat ulang tanpa menyimpan pilihan."
                continue
            if key in {"a", "b"}:
                result = session.choose(key); pair = None
                notice = f"Pilihan {key.upper()} tersimpan · {result['count']} keputusan dalam sesi ini."


_advanced_settings_121_previous = _advanced_settings_119
def _advanced_settings_121(console):
    from .hub_settings import load_hub_settings, save_hub_settings
    from .training_room import training_progress
    while True:
        state = load_hub_settings(); partner = bool(state.get("partner_mode", False)); full = bool(state.get("full_local_memory", False))
        progress = training_progress()
        _clear(); _header(console, "Lanjutan")
        console.print("[dim]Fitur ini hanya mengubah Core lokal dan dapat dimatikan kapan saja.[/]\n")
        training_label = f"Training Room · {progress['total']} pilihan"
        partner_label = f"Mode pasangan · {'Aktif' if partner else 'Nonaktif'}"
        memory_label = f"Memori penuh lokal · {'Aktif' if full else 'Nonaktif'}"
        choice = _choose("", [training_label, partner_label, memory_label, "Kembali"], height=7)
        if choice in {"", "Kembali"}: return
        if choice == training_label: _training_room_121(console)
        elif choice == partner_label:
            state["partner_mode"] = not partner; save_hub_settings(state)
            console.print(f"[green]Mode pasangan {'diaktifkan' if not partner else 'dinonaktifkan'}.[/]"); _pause()
        elif choice == memory_label:
            if not full and not _confirm("Semua teks percakapan baru akan diarsipkan di perangkat dan dicari saat relevan. Aktifkan?", default=False): continue
            state["full_local_memory"] = not full; save_hub_settings(state)
            note = "Arsip lama tetap tersimpan dan tidak dihapus otomatis." if full else "Mulai sekarang seluruh teks baru disimpan di arsip lokal."
            console.print(f"[green]Memori penuh lokal {'dinonaktifkan' if full else 'diaktifkan'}.[/] {note}"); _pause()


_advanced_settings_119 = _advanced_settings_121
''')

print("FURINA_TERMUX_121_TRAINING_ROOM_OK")
