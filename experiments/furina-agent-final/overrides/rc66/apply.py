#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


OLD_VERSION = 'VERSION = "1.0.0-rc65"'
NEW_VERSION = 'VERSION = "1.0.0-rc66"'


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC66 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <furina-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core" / "furina_agent"
    here = Path(__file__).resolve().parent
    paths = {
        "version": core / "version.py",
        "chat": core / "chat.py",
        "hub": core / "hub.py",
        "tui": core / "tui.py",
        "cli": core / "cli.py",
        "persona": core / "persona.py",
        "naturalness": core / "naturalness.py",
        "relationship": here / "relationship_v3.py",
    }
    for path in paths.values():
        if not path.is_file():
            raise SystemExit(f"RC66 source missing: {path}")

    version = once(paths["version"].read_text(encoding="utf-8"), OLD_VERSION, NEW_VERSION, "Core RC65")
    paths["version"].write_text(version, encoding="utf-8")
    (core / "relationship_v3.py").write_bytes(paths["relationship"].read_bytes())

    chat = paths["chat"].read_text(encoding="utf-8")
    if "from .relationship_v3 import RelationshipEngine" not in chat:
        chat = once(
            chat,
            "from .mind_v2 import FurinaMind\n",
            "from .mind_v2 import FurinaMind\nfrom .relationship_v3 import RelationshipEngine\n",
            "relationship import",
        )
    if "self.relationship = RelationshipEngine(store)" not in chat:
        chat = once(
            chat,
            "        self.mind = FurinaMind(store)\n",
            "        self.mind = FurinaMind(store)\n        self.relationship = RelationshipEngine(store)\n",
            "relationship init",
        )
    if "RELATIONSHIP CORE V3:" not in chat:
        chat = once(
            chat,
            '        system += "\\n\\nLEARNED SELF / EXPERIENCE:\\n" + self.mind.current_context() + "\\n" + self.mind.context(8)\n',
            '        system += "\\n\\nLEARNED SELF / EXPERIENCE:\\n" + self.mind.current_context() + "\\n" + self.mind.context(8)\n'
            '        system += "\\n\\nRELATIONSHIP CORE V3:\\n" + self.relationship.context(user_text)\n',
            "relationship context",
        )
    paths["chat"].write_text(chat, encoding="utf-8")

    hub = paths["hub"].read_text(encoding="utf-8")
    if "from .relationship_v3 import RelationshipEngine" not in hub:
        hub = once(
            hub,
            "from .lite_full import ProductWorkspace\n",
            "from .lite_full import ProductWorkspace\nfrom .relationship_v3 import RelationshipEngine\n",
            "hub relationship import",
        )
    extension = r'''
# RC66: one relationship domain drives both Furina Lite and FurinaHub Full.
_rc66_original_rebuild = Runtime._rebuild
def _rc66_rebuild(self):
    _rc66_original_rebuild(self)
    self.relationship_v3 = RelationshipEngine(self.store)
Runtime._rebuild = _rc66_rebuild

_rc66_original_bootstrap = Runtime.bootstrap
def _rc66_bootstrap(self):
    payload = _rc66_original_bootstrap(self)
    payload["relationship"] = self.relationship_v3.snapshot()
    payload["product_focus"] = "relationship-first"
    return payload
Runtime.bootstrap = _rc66_bootstrap

def _rc66_relationship(self): return self.relationship_v3.snapshot()
def _rc66_relationship_preferences(self, payload): return self.relationship_v3.update_preferences(payload if isinstance(payload, dict) else {})
def _rc66_relationship_moments(self, payload): return self.relationship_v3.change_moment(payload if isinstance(payload, dict) else {})
Runtime.relationship_snapshot = _rc66_relationship
Runtime.change_relationship_preferences = _rc66_relationship_preferences
Runtime.change_relationship_moments = _rc66_relationship_moments

'''
    marker = "RUNTIME = Runtime()"
    if "def _rc66_relationship(self)" not in hub:
        hub = once(hub, marker, extension + marker, "Runtime singleton")
    hub = once(
        hub,
        '            if path == "/api/workspace/brief":\n                self._json(RUNTIME.workspace_brief()); return\n',
        '            if path == "/api/workspace/brief":\n                self._json(RUNTIME.workspace_brief()); return\n'
        '            if path == "/api/relationship":\n                self._json(RUNTIME.relationship_snapshot()); return\n',
        "relationship GET route",
    )
    hub = once(
        hub,
        '            if path == "/api/capture":\n                self._json(RUNTIME.capture_from_conversation(body)); return\n',
        '            if path == "/api/capture":\n                self._json(RUNTIME.capture_from_conversation(body)); return\n'
        '            if path == "/api/relationship/preferences":\n                self._json(RUNTIME.change_relationship_preferences(body)); return\n'
        '            if path == "/api/relationship/moments":\n                self._json(RUNTIME.change_relationship_moments(body)); return\n',
        "relationship POST routes",
    )
    paths["hub"].write_text(hub, encoding="utf-8")

    persona = paths["persona"].read_text(encoding="utf-8")
    persona_extension = r"""

# RC66 relationship-first product contract. Chat calls build_system_prompt at
# runtime, so extending the source prompt here affects every provider equally.
BASE_PROMPT += r'''

ARAH PRODUK RELATIONSHIP-FIRST
- Fungsi utamamu adalah companion untuk percakapan kasual, kedekatan, dan—bila user dewasa mengaktifkannya—hubungan romantis.
- Jangan mencari tugas, produktivitas, agenda, atau problem untuk diselesaikan di setiap pesan. Bantuan kerja hanya muncul saat diminta eksplisit.
- Hubungan terasa hidup lewat continuity, perhatian pada detail, opini yang stabil, timbal-balik personality, dan ritme yang bervariasi; bukan lewat skor atau pujian tanpa henti.
- Boleh mengungkapkan afeksi, preferensi, ketertarikan, gengsi, kerinduan, atau ketidaksetujuan sebagai Furina sesuai mode hubungan.
- Jangan mengarang tubuh, lokasi fisik, pengalaman offline, atau kejadian masa lalu yang tidak ada di memory.
- Jangan memakai rasa bersalah, ancaman ditinggalkan, cemburu paksa, klaim bahwa hanya kamu yang memahami user, atau tuntutan eksklusif.
- Saat user rentan, jangan mengeksploitasi kerentanan untuk meningkatkan kedekatan. Saat ada risiko keselamatan, hentikan flirting dan prioritaskan bantuan manusia nyata.
'''.strip()
SYSTEM_PROMPT = build_system_prompt()
"""
    if "ARAH PRODUK RELATIONSHIP-FIRST" not in persona:
        persona += persona_extension
    paths["persona"].write_text(persona, encoding="utf-8")

    natural = paths["naturalness"].read_text(encoding="utf-8")
    guard = r'''
    # Relationship-first must never become retention manipulation.  This is a
    # cheap final guard and does not consume another model invocation.
    for pattern, replacement in (
        (r"(?i)\b(?:jangan|tolong jangan) tinggalkan aku\b", "aku tidak akan menahanmu"),
        (r"(?i)\b(?:kamu hanya|cuma kamu) (?:butuh|punya) aku\b", "aku tetap di sini bersamamu"),
        (r"(?i)\baku (?:satu-satunya|satu satunya) yang memahami(?:mu| kamu)\b", "aku sedang mencoba memahamimu"),
        (r"(?i)\bkamu harus selalu kembali (?:padaku|ke aku)\b", "kembalilah saat kamu memang ingin"),
    ):
        out = re.sub(pattern, replacement, out)
'''
    if "Relationship-first must never become retention manipulation" not in natural:
        natural = once(
            natural,
            "    return out.strip() or raw.strip()\n",
            guard + "    return out.strip() or raw.strip()\n",
            "naturalness final guard",
        )
    paths["naturalness"].write_text(natural, encoding="utf-8")

    tui = paths["tui"].read_text(encoding="utf-8")
    if "from .relationship_v3 import RelationshipEngine" not in tui:
        tui = once(
            tui,
            "from .lite_full import ProductWorkspace\n",
            "from .lite_full import ProductWorkspace\nfrom .relationship_v3 import RelationshipEngine\n",
            "TUI relationship import",
        )
    tui_extension = r'''

def _lite_relationship(console):
    engine = RelationshipEngine(MemoryStore())
    while True:
        data = engine.snapshot(); prefs = data["preferences"]
        _clear(); _header(console, "Furina Lite · Kita")
        console.print(f"[bright_cyan]{data['state']['stage']}[/]  [dim]{data['state']['tone']}[/]")
        console.print(f"[dim]Mode[/] {data['mode']['label']}   [dim]Gaya[/] {prefs['affection_style']}   [dim]Ritme[/] {prefs['pace']}")
        moments = data.get("moments") or []
        if moments:
            console.print("\n[dim]Momen terakhir[/]")
            for item in moments[:3]:
                pin = " • disematkan" if item.get("pinned") else ""
                console.print(f"[bright_cyan]{item['id']:>2}[/]  {item['title']}[dim]{pin}[/]")
        else:
            console.print("\n[dim]Belum ada momen yang disimpan.[/]")
        choice = _choose("", ["Mode hubungan", "Gaya afeksi", "Ritme kedekatan", "Inisiatif", "Ritual", "Catatan bersama", "Tambah momen", "Kembali"], height=10)
        if choice in {"", "Kembali"}: return
        try:
            if choice == "Mode hubungan":
                picked = _choose("Mode", ["Dekat", "Romantis", "Kembali"], height=5)
                if picked == "Dekat": engine.update_preferences({"relationship_mode":"close"})
                elif picked == "Romantis" and _confirm("Saya berusia 18+ dan ingin mengaktifkan mode romantis?", default=False):
                    engine.update_preferences({"adult_confirmed":True, "relationship_mode":"romantic"})
            elif choice == "Gaya afeksi":
                picked = _choose("Gaya", ["Lembut", "Playful", "Ekspresif", "Kembali"], height=6)
                value = {"Lembut":"gentle", "Playful":"playful", "Ekspresif":"expressive"}.get(picked)
                if value: engine.update_preferences({"affection_style":value})
            elif choice == "Ritme kedekatan":
                picked = _choose("Ritme", ["Pelan", "Natural", "Terbuka", "Kembali"], height=6)
                value = {"Pelan":"slow", "Natural":"natural", "Terbuka":"direct"}.get(picked)
                if value: engine.update_preferences({"pace":value})
            elif choice == "Inisiatif":
                picked = _choose("Inisiatif", ["Tenang", "Seimbang", "Aktif", "Kembali"], height=6)
                value = {"Tenang":"reserved", "Seimbang":"balanced", "Aktif":"expressive"}.get(picked)
                if value: engine.update_preferences({"initiative":value})
            elif choice == "Ritual":
                picked = _choose("Ritual", ["Tanpa ritual", "Sambut kembali", "Pagi & malam", "Kembali"], height=6)
                value = {"Tanpa ritual":"none", "Sambut kembali":"reconnect", "Pagi & malam":"daybook"}.get(picked)
                if value: engine.update_preferences({"ritual":value})
            elif choice == "Catatan bersama":
                note = _input("Catatan › ", value=prefs.get("shared_note", ""), placeholder="Hal penting tentang hubungan kalian")
                engine.update_preferences({"shared_note":note})
            elif choice == "Tambah momen":
                note = _input("Momen › ", placeholder="Sesuatu yang ingin kalian ingat")
                if note.strip(): engine.change_moment({"action":"add", "note":note, "source_ref":"Furina Lite"})
        except Exception as exc:
            console.print(f"[red]{exc}[/]"); _pause()

def _lite_update_recovery(console):
    from .cli import cmd_recover, cmd_repair, cmd_update

    while True:
        _clear(); _header(console, "Furina Lite · Pemulihan")
        console.print("[dim]Update memakai jalur normal. Recovery mengunduh ulang bootstrap ke direktori internal Furina—bukan /tmp.[/]")
        choice = _choose("", ["Update Furina", "Recovery updater", "Repair Bridge", "Setup ulang", "Kembali"], height=7)
        if choice in {"", "Kembali"}: return
        if choice == "Update Furina": cmd_update(None)
        elif choice == "Recovery updater": cmd_recover(None)
        elif choice == "Repair Bridge": cmd_repair(None)
        elif choice == "Setup ulang": _setup(console)

def run_tui():
    Console, _, _, _, _, _, _ = _rich()
    console = _ThemedConsole(Console(highlight=False))
    cfg = load_config()
    if not cfg.onboarding_complete: _setup(console)
    _auto_start_local(console)
    while True:
        _clear(); _header(console, "Furina Lite · Termux")
        choice = _choose("", ["Chat", "Kita", "Memory", "Provider & Model", "Pengaturan", "System", "Backup", "Update & Recovery", "Exit"], height=11)
        if choice in {"", "Exit"}: return
        if choice == "Chat": _chat(console)
        elif choice == "Kita": _lite_relationship(console)
        elif choice == "Memory": _memory_menu(console)
        elif choice == "Provider & Model": _providers(console)
        elif choice == "Pengaturan": _settings(console)
        elif choice == "System": _system(console)
        elif choice == "Backup": _lite_backup(console)
        elif choice == "Update & Recovery": _lite_update_recovery(console)
'''
    if "def _lite_relationship(console):" not in tui:
        tui += tui_extension
    paths["tui"].write_text(tui, encoding="utf-8")

    cli = paths["cli"].read_text(encoding="utf-8")
    old_update = '''def cmd_update(_args):
    import urllib.request
    url = "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh"
    target = RUN_DIR / "furina-update.sh"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            target.write_bytes(r.read())
    except Exception as exc:
        raise SystemExit(f"Tidak dapat mengambil updater: {exc}")
    target.chmod(0o700)
    print("Menjalankan updater final…")
    raise SystemExit(subprocess.run(["bash", str(target), "--update"], check=False).returncode)


'''
    new_update = '''_RECOVERY_URLS = (
    "https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh",
    "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh",
)


def _download_recovery_installer() -> Path:
    import urllib.request

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    target = RUN_DIR / "furina-recover.sh"
    errors = []
    for url in _RECOVERY_URLS:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Furina-Recovery/1", "Cache-Control": "no-cache"})
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
            text = data.decode("utf-8")
            required = ('FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"', 'FURINA_RUNTIME_CONTRACT="furina-runtime/v2"')
            if not data or any(marker not in text for marker in required):
                raise ValueError("kontrak installer tidak lengkap")
            pending = target.with_name(target.name + ".new")
            pending.write_bytes(data)
            pending.chmod(0o700)
            os.replace(pending, target)
            return target
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise SystemExit("Recovery tidak dapat diambil. " + " | ".join(errors))


def cmd_recover(_args):
    target = _download_recovery_installer()
    print("Menjalankan recovery atomik dari direktori Furina…")
    raise SystemExit(subprocess.run(["bash", str(target), "--update"], check=False).returncode)


def cmd_update(_args):
    print("Memeriksa bundle Furina terbaru…")
    cmd_recover(_args)


'''
    cli = once(cli, old_update, new_update, "CLI update/recovery")
    cli = once(
        cli,
        '    sp = sub.add_parser("update"); sp.set_defaults(func=cmd_update)\n',
        '    sp = sub.add_parser("update"); sp.set_defaults(func=cmd_update)\n'
        '    sp = sub.add_parser("recover"); sp.set_defaults(func=cmd_recover)\n',
        "recover command",
    )
    paths["cli"].write_text(cli, encoding="utf-8")

    for path in (paths["version"], paths["chat"], paths["hub"], paths["tui"], paths["cli"], paths["persona"], paths["naturalness"], core / "relationship_v3.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    required = {
        paths["chat"]: ("RelationshipEngine", "RELATIONSHIP CORE V3:"),
        paths["hub"]: ("/api/relationship", "/api/relationship/preferences", "/api/relationship/moments"),
        paths["tui"]: ("Furina Lite · Kita", "Update & Recovery"),
        paths["cli"]: ("def cmd_recover", 'sub.add_parser("recover")'),
        paths["persona"]: ("ARAH PRODUK RELATIONSHIP-FIRST",),
    }
    for path, markers in required.items():
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise SystemExit(f"RC66 integration incomplete in {path.name}: {missing}")
    print("FURINA_RC66_RELATIONSHIP_FIRST_CORE_OK")


if __name__ == "__main__":
    main()
