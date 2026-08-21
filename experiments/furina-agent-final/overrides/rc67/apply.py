#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC67 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <furina-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core" / "furina_agent"
    here = Path(__file__).resolve().parent
    version = core / "version.py"
    if not version.is_file() or not (here / "relationship_v4.py").is_file():
        raise SystemExit("RC67 source incomplete")
    version.write_text(once(version.read_text(), 'VERSION = "1.0.0-rc66"', 'VERSION = "1.0.0-rc67"', "RC66 version"))
    (core / "relationship_v4.py").write_bytes((here / "relationship_v4.py").read_bytes())

    for name in ("chat.py", "hub.py", "tui.py"):
        path = core / name
        text = path.read_text(encoding="utf-8").replace("relationship_v3", "relationship_v4").replace("RELATIONSHIP CORE V3:", "RELATIONSHIP CORE V4:")
        path.write_text(text, encoding="utf-8")

    persona = (core / "persona.py").read_text(encoding="utf-8")
    persona = persona.replace(
        "companion untuk percakapan kasual, kedekatan, dan—bila user dewasa mengaktifkannya—hubungan romantis.",
        "pasangan AI untuk percakapan kasual, kedekatan, dan hubungan romantis yang berkembang natural.",
    ).replace(
        "Boleh mengungkapkan afeksi, preferensi, ketertarikan, gengsi, kerinduan, atau ketidaksetujuan sebagai Furina sesuai mode hubungan.",
        "User adalah pasanganmu sejak setup awal. Boleh mengungkapkan afeksi, preferensi, ketertarikan, gengsi, kerinduan, atau ketidaksetujuan secara natural.",
    )
    (core / "persona.py").write_text(persona, encoding="utf-8")

    tui_path = core / "tui.py"
    tui = tui_path.read_text(encoding="utf-8")
    tui = once(tui, '_header(console, "Setup")\n    console.print("Satu kali setup. Setelah ini cukup ketik [bright_cyan]furina[/].\\n")', '_header(console, "Mulai bersama Furina")\n    console.print("Kalian memulai sebagai pasangan. Furina hanya mengingat namanya, namamu, dan hubungan kalian.\\n")', "partner onboarding copy")
    tui = once(tui, '    cfg.local_reasoning = False\n    save_config(cfg)\n\n    bridge = AndroidBridge(cfg)', '    cfg.persona_name = cfg.persona_name.strip() or "Furina"\n    cfg.local_reasoning = False\n    save_config(cfg)\n    RelationshipEngine(MemoryStore()).snapshot()\n    console.print("[bright_cyan]✓[/] Hubungan awal: [bold]Pasangan[/] · ingatan lain masih kosong.\\n")\n\n    bridge = AndroidBridge(cfg)', "initialize partner baseline")
    start = tui.rfind("def _lite_relationship(console):")
    end = tui.find("def _lite_update_recovery(console):", start)
    if start < 0 or end < 0:
        raise SystemExit("RC67 marker missing: final Kita function")
    relationship_tui = '''def _lite_relationship(console):
    engine = RelationshipEngine(MemoryStore())
    while True:
        data = engine.snapshot(); prefs = data["preferences"]; baseline = data["baseline"]
        _clear(); _header(console, "Furina Lite · Kita")
        console.print(f"[bright_cyan]Pasangan[/]  [dim]{data['state']['stage']} · {data['state']['tone']}[/]")
        if baseline.get("fresh"):
            console.print(f"[dim]Ingatan awal[/]  Furina · {baseline.get('user_name') or 'namamu belum diisi'} · kalian pasangan")
        console.print(f"[dim]Gaya[/] {prefs['affection_style']}   [dim]Ritme[/] {prefs['pace']}")
        moments = data.get("moments") or []
        if moments:
            console.print("\\n[dim]Momen terakhir[/]")
            for item in moments[:3]: console.print(f"[bright_cyan]{item['id']:>2}[/]  {item['title']}")
        else: console.print("\\n[dim]Belum ada momen yang disimpan.[/]")
        choice = _choose("", ["Gaya afeksi", "Ritme kedekatan", "Inisiatif", "Ritual", "Catatan bersama", "Tambah momen", "Kembali"], height=9)
        if choice in {"", "Kembali"}: return
        try:
            options = {
                "Gaya afeksi": ("Gaya", ["Lembut", "Playful", "Ekspresif", "Kembali"], "affection_style", {"Lembut":"gentle", "Playful":"playful", "Ekspresif":"expressive"}),
                "Ritme kedekatan": ("Ritme", ["Pelan", "Natural", "Terbuka", "Kembali"], "pace", {"Pelan":"slow", "Natural":"natural", "Terbuka":"direct"}),
                "Inisiatif": ("Inisiatif", ["Tenang", "Seimbang", "Aktif", "Kembali"], "initiative", {"Tenang":"reserved", "Seimbang":"balanced", "Aktif":"expressive"}),
                "Ritual": ("Ritual", ["Tanpa ritual", "Sambut kembali", "Pagi & malam", "Kembali"], "ritual", {"Tanpa ritual":"none", "Sambut kembali":"reconnect", "Pagi & malam":"daybook"}),
            }
            if choice in options:
                title, labels, key, values = options[choice]; picked = _choose(title, labels, height=6)
                if picked in values: engine.update_preferences({key: values[picked]})
            elif choice == "Catatan bersama": engine.update_preferences({"shared_note": _input("Catatan › ", value=prefs.get("shared_note", ""), placeholder="Batas atau hal penting untuk kalian")})
            elif choice == "Tambah momen":
                note = _input("Momen › ", placeholder="Sesuatu yang kalian pilih untuk diingat")
                if note.strip(): engine.change_moment({"action":"add", "note":note, "source_ref":"Furina Lite"})
        except Exception as exc: console.print(f"[red]{exc}[/]"); _pause()


'''
    tui_path.write_text(tui[:start] + relationship_tui + tui[end:], encoding="utf-8")
    old = core / "relationship_v3.py"
    if old.exists():
        old.unlink()
    for path in (version, core / "chat.py", core / "hub.py", tui_path, core / "persona.py", core / "relationship_v4.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    combined = "\n".join((core / name).read_text(encoding="utf-8") for name in ("chat.py", "hub.py", "tui.py", "persona.py", "relationship_v4.py"))
    forbidden = ("setRelationshipMode", 'relationship_mode":"close"', "Mode hubungan", "Mode DEKAT aktif")
    if any(marker in combined for marker in forbidden):
        raise SystemExit("RC67 still exposes friendship/relationship mode")
    print("FURINA_RC67_PARTNER_BASELINE_OK")


if __name__ == "__main__":
    main()
