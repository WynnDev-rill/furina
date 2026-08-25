#!/usr/bin/env python3
"""Private final follow-up: shared cross-surface context and no device control."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"

version = CORE / "version.py"
text = version.read_text(encoding="utf-8")
if 'VERSION = "1.1.11"' not in text:
    raise SystemExit("expected Core 1.1.11")
version.write_text(text.replace('VERSION = "1.1.11"', 'VERSION = "1.1.12"', 1), encoding="utf-8")

memory = CORE / "memory.py"
with memory.open("a", encoding="utf-8") as out:
    out.write(r'''

# FURINA_FINAL_113_SHARED_CONTEXT
def _furina_113_cross_surface_messages(self, limit=8):
    """Recent turns from the other UI only; histories remain separately listed."""
    current = self.active_conversation_id()
    row = self._conn().execute("SELECT surface FROM conversations WHERE id=?", (current,)).fetchone()
    surface = str(row[0]) if row else "hub"
    rows = self._conn().execute("""SELECT m.role,m.content,m.created_at,c.surface
      FROM messages m JOIN conversations c ON c.id=m.conversation_id
      WHERE c.surface<>? ORDER BY m.id DESC LIMIT ?""", (surface, max(1, min(int(limit), 16)))).fetchall()
    return [dict(row) for row in reversed(rows)]
MemoryStore.cross_surface_recent_messages = _furina_113_cross_surface_messages
''')

chat = CORE / "chat.py"
with chat.open("a", encoding="utf-8") as out:
    out.write(r'''

# FURINA_FINAL_113_SHARED_CONTEXT
_furina_113_messages = FurinaChat._messages
def _furina_113_messages_with_other_surface(self, user_text, profile):
    messages = _furina_113_messages(self, user_text, profile)
    try: other = self.store.cross_surface_recent_messages(8)
    except Exception: other = []
    if not other or not messages or messages[0].get("role") != "system":
        return messages
    rendered = "\n".join(f"{('Pengguna' if x.get('role') == 'user' else 'Furina')}: {str(x.get('content') or '')[:700]}" for x in other)
    bridge = ("\n\n[CONTINUITY LINTAS PERMUKAAN]\n"
              "Ini adalah percakapan terbaru dari permukaan lain (Termux atau FurinaHub). "
              "Gunakan hanya untuk kesinambungan dan jangan menyebut asal permukaannya kecuali pengguna bertanya.\n" + rendered)
    messages[0] = {**messages[0], "content": str(messages[0].get("content") or "") + bridge}
    return messages
FurinaChat._messages = _furina_113_messages_with_other_surface
''')

# Device actions must never be selected from either Termux or Hub chat.
companion = CORE / "companion.py"
with companion.open("a", encoding="utf-8") as out:
    out.write(r'''

# FURINA_FINAL_113_CHAT_ONLY_CLASSIFIER
def _furina_113_chat_only_intent(self, text):
    return Intent(mode="chat", goal=str(text or "").strip())
CompanionSession.classify = _furina_113_chat_only_intent
''')

# Historical config files can still contain a Shizuku/Root choice.  Keep the
# old field harmless and ensure it is normalized whenever Termux reads/saves.
config = CORE / "config.py"
with config.open("a", encoding="utf-8") as out:
    out.write(r'''

# FURINA_FINAL_113_DISABLE_LEGACY_DEVICE_MODE
_furina_113_load_config = load_config
def load_config(*args, **kwargs):
    cfg = _furina_113_load_config(*args, **kwargs)
    cfg.device_control_mode = "normal"
    cfg.auto_start = False
    return cfg

_furina_113_save_config = save_config
def save_config(cfg, *args, **kwargs):
    cfg.device_control_mode = "normal"
    cfg.auto_start = False
    return _furina_113_save_config(cfg, *args, **kwargs)
''')

hub = CORE / "hub.py"
text = hub.read_text(encoding="utf-8")
text = text.replace('EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r61"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r62"', 1)
text = text.replace('furina-2026.08.25-private-1.1.11', 'furina-2026.08.25-private-1.1.12')
hub.write_text(text, encoding="utf-8")

tui = CORE / "tui.py"
with tui.open("a", encoding="utf-8") as out:
    out.write(r'''

# FURINA_FINAL_113_NO_DEVICE_CONTROL
def _settings_113(console):
    while True:
        cfg = load_config()
        from .hub_settings import load_hub_settings
        personality = load_hub_settings().get("personality_traits") or []
        _clear(); _header(console, "Pengaturan")
        console.print(f"[dim]Identitas[/]      {cfg.persona_name} · {cfg.user_nickname or 'belum diatur'}")
        console.print(f"[dim]Personalisasi[/] {len(personality)} sifat aktif · tersedia di menu utama\n")
        choice = _choose("", ["Identitas", "Sistem", "Backup", "Update & Recovery", "Kembali"], height=7)
        if choice in {"", "Kembali"}: return
        if choice == "Identitas": _private_identity(console)
        elif choice == "Sistem": _system(console)
        elif choice == "Backup": _lite_backup(console)
        elif choice == "Update & Recovery": _update_repair(console)
_settings = _settings_113
''')

print("FURINA_FINAL_113_CORE_OK")
