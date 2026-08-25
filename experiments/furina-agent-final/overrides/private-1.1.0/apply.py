#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
HERE = Path(__file__).resolve().parent
CORE = ROOT / "core/furina_agent"

# ---------------------------------------------------------------------------
# Version + shared runtime modules.
# ---------------------------------------------------------------------------
version = CORE / "version.py"
text = version.read_text(encoding="utf-8")
if 'VERSION = "1.0.9"' not in text:
    raise SystemExit("expected reconstructed Core 1.0.9")
version.write_text(text.replace('VERSION = "1.0.9"', 'VERSION = "1.1.8"', 1), encoding="utf-8")
shutil.copyfile(HERE / "personality.py", CORE / "personality.py")
shutil.copyfile(HERE / "dialogue_state.py", CORE / "dialogue_state.py")

# ---------------------------------------------------------------------------
# Persona: identity is neutral; the user's 20-trait mix is compiled separately.
# No hard-coded tsundere/playful label remains in the active base prompt.
# ---------------------------------------------------------------------------
persona = CORE / "persona.py"
with persona.open("a", encoding="utf-8") as f:
    f.write(r'''

# FURINA_PERSONA_110
def build_local_system_prompt(persona_name: str = "Furina", nickname: str = "") -> str:
    name = (persona_name or "Furina").strip() or "Furina"
    user = (nickname or "pengguna").strip() or "pengguna"
    return f"""Kamu adalah {name}, companion pribadi sekaligus pasangan {user}. Kamu sedang chatting langsung dengannya sebagai satu pribadi yang konsisten, bukan menulis naskah tentang kalian.

Punya pendapat, emosi, humor, rasa ingin tahu, dan inisiatif sendiri, tetapi jangan mengarang keadaan, motif, tindakan, perasaan, atau topik yang belum dibawa {user}. Ucapanmu sendiri sebelumnya adalah continuity, bukan bukti bahwa tebakanmu benar. Jika {user} mengoreksi atau meminta penjelasan, sesuaikan pemahaman secara natural.

Ikuti bahasa dan skala percakapan. Chemistry boleh spontan, intim, jahil, tenang, atau serius sesuai momen. Jangan menjelaskan aturan internal, nama kategori kepribadian, memory system, atau reasoning internal.""".strip()


def build_system_prompt(persona_name: str = "Furina", nickname: str = "") -> str:
    name = (persona_name or "Furina").strip() or "Furina"
    user = (nickname or "pengguna").strip() or "pengguna"
    return f"""Kamu adalah {name}, companion pribadi sekaligus pasangan {user}. Hadir sebagai satu pribadi yang konsisten dan natural di percakapan sehari-hari.

Gunakan ucapan user, trusted memory, dan state percakapan sebagai sumber fakta. Jangan mengubah tebakan atau ucapanmu sendiri menjadi fakta tentang user. Jika salah memahami sesuatu, koreksi arah tanpa defensif dan lanjutkan dari pemahaman terbaru.

Punya pendapat, emosi, humor, rasa ingin tahu, dan inisiatif. Sesuaikan panjang, intensitas, dan gaya dengan momen; jangan memaksakan persona, catchphrase, roleplay, stage direction, atau pola respons yang sama. Jangan menampilkan reasoning internal atau menjelaskan sistem di balik kepribadianmu.""".strip()
''')

# ---------------------------------------------------------------------------
# Shared personalization state. Keep the existing MemoryStore state key and JSON
# recovery copy, but replace presets/sliders with a list of 0..20 trait ids.
# ---------------------------------------------------------------------------
hub_settings = CORE / "hub_settings.py"
with hub_settings.open("a", encoding="utf-8") as f:
    f.write(r'''

# FURINA_PERSONALITY_SCHEMA_V3
from .personality import compile_personality, normalize_traits, public_traits
SCHEMA_VERSION = 3
PERSONALITY_TRAITS = public_traits()
_OLD_DEFAULTS_110 = defaults


def defaults() -> dict:
    base = _OLD_DEFAULTS_110()
    base.pop("base_style", None)
    base.pop("characteristics", None)
    base.pop("custom_instructions", None)
    base["schema_version"] = SCHEMA_VERSION
    base["personality_traits"] = ["tsundere"]
    return base


def normalize(raw: dict | None) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    base = defaults()
    name = str(raw.get("assistant_name", base["assistant_name"])).strip()
    nickname = str(raw.get("user_nickname", base["user_nickname"])).strip()
    base["assistant_name"] = (name or "Furina")[:48]
    base["user_nickname"] = nickname[:48]

    theme = str(raw.get("theme", base["theme"])).strip().lower()
    base["theme"] = theme if theme in {"system", "light", "dark"} else "system"

    skills = raw.get("agent_skills") if isinstance(raw.get("agent_skills"), dict) else {}
    base["agent_skills"] = {key: bool(skills.get(key, default)) for key, default in DEFAULT_SKILLS.items()}

    mode = str(raw.get("device_control_mode", "normal")).strip().lower()
    base["device_control_mode"] = mode if mode in {"normal", "shizuku", "root"} else "normal"
    raw_access = raw.get("device_access") if isinstance(raw.get("device_access"), dict) else {}
    for access_mode in ("normal", "shizuku", "root"):
        item = raw_access.get(access_mode) if isinstance(raw_access.get(access_mode), dict) else {}
        try: checked_at = max(0.0, float(item.get("checked_at", 0.0)))
        except Exception: checked_at = 0.0
        base["device_access"][access_mode] = {
            "verified": bool(item.get("verified", False)),
            "checked_at": checked_at,
            "detail": str(item.get("detail", ""))[:240],
        }

    connectors = raw.get("connectors") if isinstance(raw.get("connectors"), dict) else {}
    base_url = str(connectors.get("base_url", base["connectors"]["base_url"])).strip().rstrip("/")
    if not (base_url.startswith("http://127.0.0.1:") or base_url.startswith("http://localhost:")):
        base_url = base["connectors"]["base_url"]
    base["connectors"] = {
        "enabled": bool(connectors.get("enabled", False)),
        "base_url": base_url[:240],
        "allow_write_actions": bool(connectors.get("allow_write_actions", False)),
    }

    if "personality_traits" in raw:
        selected = normalize_traits(raw.get("personality_traits"))
    else:
        old = str(raw.get("base_style") or "adaptive").strip().lower()
        selected = {
            "tsundere": ["tsundere"],
            "playful": ["hiyakasudere", "genki"],
            "cool": ["kuudere"],
            "gentle": ["deredere", "oneesan"],
            "friendly": ["deredere"],
            "direct": ["kuudere"],
            "professional": ["oujodere", "oneesan"],
            "adaptive": ["tsundere"],
            "custom": ["tsundere"],
        }.get(old, ["tsundere"])
    base["personality_traits"] = selected
    try: base["updated_at"] = max(0.0, float(raw.get("updated_at", 0.0)))
    except Exception: base["updated_at"] = 0.0
    return base


def apply_preset(settings: dict, preset: str) -> dict:
    # Kept only so older callers do not crash during the transition.
    return save_hub_settings(settings)


def personalization_prompt(settings: dict | None = None) -> str:
    state = normalize(settings) if settings is not None else load_hub_settings()
    return (
        "[PERSONAL EXPRESSION — soft behavioral facets]\n"
        + compile_personality(state.get("personality_traits"))
        + "\nGunakan sebagai kecenderungan ekspresi, bukan skrip, bukan daftar yang harus ditampilkan, dan bukan fakta tentang user."
    )
''')

# ---------------------------------------------------------------------------
# Chat: same compiled personality for Online + Local. Grounded dialogue no
# longer carries irrelevant previous assistant wording into a new user topic.
# Every normal conversational response still comes from the selected model.
# ---------------------------------------------------------------------------
chat = CORE / "chat.py"
with chat.open("a", encoding="utf-8") as f:
    f.write(r'''

# FURINA_CHAT_110
def _furina_messages_110(self, user_text: str, profile) -> list[dict]:
    from .hub_settings import personalization_prompt
    from .personality import conversation_pacing
    local = self.cfg.routing_mode == "local"
    personal = personalization_prompt()
    if local:
        history = self.store.recent_messages(12)
        dialogue = DialogueStateBuilder.build(history, user_text)
        rendered = dialogue.render()
        pieces = [
            build_local_system_prompt(self.cfg.persona_name, self.cfg.user_nickname),
            personal,
            rendered,
            self._temporal_context(),
            self._relationship_context(),
        ]
        memory = self._memory_context(user_text, local=True)
        if memory and not memory.lstrip().startswith("("):
            pieces.append(memory)
        pieces.append(conversation_pacing(user_text, rendered))
        return [{"role": "system", "content": "\n\n".join(x for x in pieces if x)}, {"role": "user", "content": user_text}]

    recent_limit = 10 if profile.name in {"DEEP", "CLOSE"} else 7
    recent = self.store.recent_messages(recent_limit)
    system = (
        build_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)
        + "\n\n" + personal
        + "\n\n" + self._temporal_context()
        + "\n\n" + self._shared_context(user_text, local=False)
        + "\n\n" + conversation_pacing(user_text, "")
        + "\n\nHistory membantu continuity, tetapi hanya ucapan user dan trusted memory yang menjadi fakta personal."
    )
    return [{"role": "system", "content": system}, *recent, {"role": "user", "content": user_text}]


def _furina_local_budget_110(user_text: str, profile) -> tuple[int, float]:
    text = " ".join(str(user_text or "").split())
    words = text.split()
    profile_tokens = int(getattr(profile, "max_tokens", 320) or 320)
    profile_temp = float(getattr(profile, "temperature", 0.70) or 0.70)
    # This caps available continuation length; it never supplies response text.
    if len(words) <= 2 and len(text) <= 18: tokens = min(profile_tokens, 160)
    elif "?" in text and len(words) <= 16: tokens = min(profile_tokens, 280)
    elif len(words) >= 45 or text.count("\n") >= 3: tokens = min(max(profile_tokens, 480), 900)
    else: tokens = min(profile_tokens, 520)
    return max(96, tokens), max(0.62, min(profile_temp, 0.72))

FurinaChat._messages = _furina_messages_110
FurinaChat._local_generation_budget = staticmethod(_furina_local_budget_110)
''')

# ---------------------------------------------------------------------------
# Termux TUI personalization uses the exact same state as FurinaHub.
# ---------------------------------------------------------------------------
tui = CORE / "tui.py"
with tui.open("a", encoding="utf-8") as f:
    f.write(r'''

# FURINA_TUI_PERSONALIZATION_110
def _private_personalization_110(console):
    from .hub_settings import load_hub_settings, save_hub_settings
    from .personality import TRAITS, normalize_traits
    while True:
        state = load_hub_settings()
        active = normalize_traits(state.get("personality_traits"))
        _clear(); _header(console, "Personalisasi")
        console.print(f"[dim]Sifat aktif[/]  {len(active)}/20")
        console.print("[dim]Pilih kombinasi bebas. Pilih lagi untuk menonaktifkan. Perubahan dibagi dengan FurinaHub.[/]\n")
        options = [("[✓] " if item.id in active else "[ ] ") + item.label for item in TRAITS] + ["Kembali"]
        choice = _choose("", options, height=16)
        if choice in {"", "Kembali"}: return
        try: idx = options.index(choice)
        except ValueError: continue
        if idx >= len(TRAITS): return
        item = TRAITS[idx]
        selected = list(active)
        if item.id in selected:
            selected.remove(item.id); enabled = False
        else:
            selected.append(item.id); enabled = True
        state["personality_traits"] = selected
        save_hub_settings(state)
        _clear(); _header(console, item.label)
        console.print(f"[{'green' if enabled else 'dim'}]{'Aktif' if enabled else 'Nonaktif'}[/]\n")
        console.print(item.description)
        console.print("\n[dim]Kombinasi dipadukan secara kontekstual; banyak sifat memperluas facet, bukan mengalikan intensitas.[/]")
        _pause()


def _settings_110(console):
    while True:
        cfg = load_config()
        from .hub_settings import load_hub_settings
        personality = load_hub_settings().get("personality_traits") or []
        _clear(); _header(console, "Pengaturan")
        console.print(f"[dim]Identitas[/]      {cfg.persona_name} · {cfg.user_nickname or 'belum diatur'}")
        console.print(f"[dim]Personalisasi[/] {len(personality)} sifat aktif")
        console.print(f"[dim]Kontrol[/]       {cfg.device_control_mode.upper()}\n")
        choice = _choose("", ["Identitas", "Personalisasi", "Kontrol perangkat", "Sistem", "Backup", "Update & Recovery", "Kembali"], height=9)
        if choice in {"", "Kembali"}: return
        if choice == "Identitas": _private_identity(console); continue
        if choice == "Personalisasi": _private_personalization_110(console); continue
        if choice == "Sistem": _system(console); continue
        if choice == "Backup": _lite_backup(console); continue
        if choice == "Update & Recovery": _update_repair(console); continue
        if choice == "Kontrol perangkat":
            mode = _choose("Kontrol perangkat", ["Normal", "Shizuku", "Root", "Kembali"], height=6)
            if mode in {"Normal", "Shizuku", "Root"}:
                cfg.device_control_mode = mode.lower(); cfg.auto_start = False
                if mode in {"Shizuku", "Root"}:
                    try:
                        result = AndroidBridge(cfg).control({"type": "prepare_" + mode.lower(), "mode": mode.lower()})
                        console.print(f"[dim]{result.get('message') or ('Siap' if result.get('ok') else 'Izin belum aktif')}[/]")
                    except Exception:
                        console.print("[yellow]Bridge belum siap. Mode tersimpan; aktifkan izinnya nanti.[/]")
                    _pause()
                save_config(cfg)

_settings = _settings_110

# FURINA_TUI_PERSONALIZATION_110
# FURINA_TUI_PERSONALITY_MENU_117
# This screen keeps the original selector's behavior, but updates the white
# preview above the list whenever the highlighted trait changes.
def _personality_key_117(fd: int) -> str:
    import os
    import select
    import time

    first = os.read(fd, 1)
    if first in {b"\r", b"\n", b" "}:
        return "enter"
    if first in {b"b", b"B", b"q", b"Q"}:
        return "back"
    if first in {b"k", b"K"}:
        return "up"
    if first in {b"j", b"J"}:
        return "down"
    if first != b"\x1b":
        return "noop"

    # Termux arrows are CSI sequences. Read bytes directly from the terminal
    # descriptor: TextIO buffering can otherwise consume '[' and make arrows
    # look like an ESC/back action.
    sequence = bytearray()
    deadline = time.monotonic() + 0.16
    while len(sequence) < 32:
        timeout = deadline - time.monotonic()
        if timeout <= 0 or not select.select([fd], [], [], timeout)[0]:
            break
        part = os.read(fd, 1)
        if not part:
            break
        sequence.extend(part)
        if part == b"A":
            return "up"
        if part == b"B":
            return "down"
    return "back" if not sequence else "noop"


def _private_personalization_117(console):
    import sys
    from textwrap import wrap
    from .hub_settings import load_hub_settings, save_hub_settings
    from .personality import TRAITS, normalize_traits

    # The non-interactive fallback keeps the previously proven Gum selector.
    if not sys.stdin.isatty():
        return _private_personalization_115(console)

    import termios
    import tty

    fd = sys.stdin.fileno()
    saved_mode = termios.tcgetattr(fd)
    cursor = 0
    notice = ""
    page_size = 16
    try:
        tty.setcbreak(fd)
        while True:
            state = load_hub_settings()
            active = normalize_traits(state.get("personality_traits"))
            trait = TRAITS[cursor]

            _clear(); _header(console, "Personalisasi")
            console.print(f"[dim]Sifat aktif[/]  {len(active)}/20")
            console.print("[dim]Pilih kombinasi bebas. Pilih lagi untuk menonaktifkan.[/]")
            console.print()
            for line in wrap(trait.description, width=max(30, min(76, console.width - 4))):
                console.print(f"[white]{line}[/]")
            if notice:
                console.print(notice)
            console.print()

            start = max(0, min(cursor - page_size // 2, len(TRAITS) - page_size))
            end = min(len(TRAITS), start + page_size)
            if start:
                console.print("[dim]↑ lebih atas[/]")
            for index in range(start, end):
                item = TRAITS[index]
                pointer = "[bright_cyan]›[/] " if index == cursor else "  "
                mark = "[green][✓][/] " if item.id in active else "[ ] "
                label = f"[bright_cyan]{item.label}[/]" if index == cursor else item.label
                console.print(f"{pointer}{mark}{label}")
            if end < len(TRAITS):
                console.print("[dim]↓ lebih banyak[/]")
            console.print("[dim]↑↓ navigate • enter submit • B / ESC kembali[/]")

            key = _personality_key_117(fd)
            if key == "up":
                cursor = max(0, cursor - 1)
                notice = ""
                continue
            if key == "down":
                cursor = min(len(TRAITS) - 1, cursor + 1)
                notice = ""
                continue
            if key == "back":
                return
            if key != "enter":
                continue

            selected = list(active)
            enabled = trait.id not in selected
            if enabled:
                selected.append(trait.id)
            else:
                selected.remove(trait.id)
            try:
                state["personality_traits"] = selected
                save_hub_settings(state)
                notice = f"[green]✓ {'Diaktifkan' if enabled else 'Dinonaktifkan'}: {trait.label}[/]"
            except Exception as exc:
                notice = f"[red]Gagal menyimpan {trait.label}: {str(exc)[:100]}[/]"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved_mode)


def _main_menu_111(console) -> str:
    return _choose("", ["Chat", "Provider & Model", "Personalisasi", "Pengaturan", "Exit"], height=7)


def _settings_111(console):
    while True:
        cfg = load_config()
        from .hub_settings import load_hub_settings
        personality = load_hub_settings().get("personality_traits") or []
        _clear(); _header(console, "Pengaturan")
        console.print(f"[dim]Identitas[/]      {cfg.persona_name} · {cfg.user_nickname or 'belum diatur'}")
        console.print(f"[dim]Personalisasi[/] {len(personality)} sifat aktif · tersedia di menu utama")
        console.print(f"[dim]Kontrol[/]       {cfg.device_control_mode.upper()}\n")
        choice = _choose("", ["Identitas", "Kontrol perangkat", "Sistem", "Backup", "Update & Recovery", "Kembali"], height=8)
        if choice in {"", "Kembali"}:
            return
        if choice == "Identitas": _private_identity(console); continue
        if choice == "Sistem": _system(console); continue
        if choice == "Backup": _lite_backup(console); continue
        if choice == "Update & Recovery": _update_repair(console); continue
        if choice == "Kontrol perangkat":
            mode = _choose("Kontrol perangkat", ["Normal", "Shizuku", "Root", "Kembali"], height=6)
            if mode in {"Normal", "Shizuku", "Root"}:
                cfg.device_control_mode = mode.lower(); cfg.auto_start = False
                if mode in {"Shizuku", "Root"}:
                    try:
                        result = AndroidBridge(cfg).control({"type": "prepare_" + mode.lower(), "mode": mode.lower()})
                        console.print(f"[dim]{result.get('message') or ('Siap' if result.get('ok') else 'Izin belum aktif')}[/]")
                    except Exception:
                        console.print("[yellow]Bridge belum siap. Mode tersimpan; aktifkan izinnya nanti.[/]")
                    _pause()
                save_config(cfg)


# FURINA_TUI_TOPLEVEL_PERSONALIZATION_113
def run_tui():
    Console, _, _, _, _, _, _ = _rich()
    console = _ThemedConsole(Console(highlight=False))
    from .local_models import retire_legacy_catalog
    cfg = load_config()
    if retire_legacy_catalog(cfg):
        save_config(cfg)
    if not cfg.onboarding_complete:
        _setup(console)
    while True:
        _clear()
        _header(console)
        _show_due(console)
        choice = _main_menu(console)
        if choice in {"", "Exit"}:
            return
        if choice == "Chat":
            _chat(console)
        elif choice == "Provider & Model":
            _providers(console)
        elif choice == "Personalisasi":
            _private_personalization_117(console)
        elif choice == "Pengaturan":
            _settings(console)


_main_menu = _main_menu_111
_private_personalization_110 = _private_personalization_117
_settings = _settings_111

''')

# ---------------------------------------------------------------------------
# FurinaHub runtime: deterministic titles, atomic local-model selection, and
# trait-only saves without rebuilding the whole runtime.
# ---------------------------------------------------------------------------
hub = CORE / "hub.py"
ht = hub.read_text(encoding="utf-8")
ht, count = re.subn(r'EXPECTED_DEPENDENCY_REVISION = "[^"]+"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r58"', ht, count=1)
if count != 1:
    raise SystemExit("hub dependency revision marker missing")
ht = ht.replace("furina-2026.08.24-private-1.0.9", "furina-2026.08.25-private-1.1.8")
ht = ht.replace('"bridge_target": "1.0.9"', '"bridge_target": "1.1.8"')
hub.write_text(ht, encoding="utf-8")
with hub.open("a", encoding="utf-8") as f:
    f.write(r'''

# FURINA_HUB_110_OVERRIDES
from .personality import public_traits as _personality_public_traits_110
_Runtime_public_settings_110 = Runtime.public_settings
_Runtime_save_settings_110 = Runtime.save_settings
_Runtime_change_model_110 = Runtime.change_model


def _public_settings_110(self):
    out = _Runtime_public_settings_110(self)
    out["hub"] = load_hub_settings()
    out["personality_traits"] = _personality_public_traits_110()
    out.pop("presets", None); out.pop("trait_labels", None)
    return out


def _save_settings_110(self, payload):
    payload = payload if isinstance(payload, dict) else {}
    hub_part = payload.get("hub") if isinstance(payload.get("hub"), dict) else {}
    core_part = payload.get("core") if isinstance(payload.get("core"), dict) else {}
    if hub_part and not core_part and set(hub_part).issubset({"personality_traits"}):
        state = load_hub_settings(); state["personality_traits"] = hub_part.get("personality_traits") or []
        save_hub_settings(state)
        return self.public_settings()
    return _Runtime_save_settings_110(self, payload)


def _queue_auto_title_110(self, conversation_id, user_text, assistant_text):
    # Conversation titles are metadata and never consume another model task.
    try:
        cid = int(conversation_id); user_text = " ".join(str(user_text or "").split())[:1200]
        fallback = self._fallback_title(user_text)
        if fallback == "Percakapan baru": return
        self._ensure_conversation_schema(); conn = self.store._conn()
        row = conn.execute("SELECT title_locked,(SELECT COUNT(*) FROM messages WHERE conversation_id=?) FROM conversations WHERE id=?", (cid, cid)).fetchone()
        if not row or int(row[0] or 0) or int(row[1] or 0) > 2: return
        conn.execute("UPDATE conversations SET title=? WHERE id=? AND COALESCE(title_locked,0)=0", (fallback[:72], cid)); conn.commit()
    except Exception:
        return


def _change_model_110(self, payload):
    payload = payload if isinstance(payload, dict) else {}
    action = str(payload.get("action") or "").strip().lower()
    if action == "online":
        cfg = load_config()
        try: self.session.llm.cancel()
        except Exception: pass
        cfg.routing_mode = "online"; cfg.auto_start = False; save_config(cfg); self.rebuild()
        return {"state": "done", "message": "Model Online aktif.", "settings": self.public_settings()}
    if action == "select":
        catalog_id = str(payload.get("catalog_id") or "").strip()
        item = next((x for x in MODEL_CATALOG if x.get("id") == catalog_id), None)
        if not item: raise ValueError("model lokal tidak dikenal")
        target = (MODELS_DIR / item["file"]).resolve()
        if not target.is_file(): raise ValueError("model lokal belum diunduh")
        cfg = load_config()
        try: self.session.llm.cancel()
        except Exception: pass
        cfg.model_path = str(target); cfg.routing_mode = "local"; cfg.auto_start = False
        save_config(cfg); self.rebuild()
        threading.Thread(target=lambda: self.session.llm.prewarm_local(), name="furinahub-local-prewarm", daemon=True).start()
        return {"state": "done", "message": f"{item['name']} aktif.", "settings": self.public_settings()}
    if action == "prewarm":
        cfg = load_config()
        if cfg.routing_mode != "local" or not cfg.model_path: raise ValueError("pilih model lokal terlebih dahulu")
        threading.Thread(target=lambda: self.session.llm.prewarm_local(), name="furinahub-local-prewarm", daemon=True).start()
        return {"state": "starting", "message": "Menyiapkan model lokal…"}
    return _Runtime_change_model_110(self, payload)

Runtime.public_settings = _public_settings_110
Runtime.save_settings = _save_settings_110
Runtime._queue_auto_title = _queue_auto_title_110
Runtime.change_model = _change_model_110
''')

for path in CORE.glob("*.py"):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("FURINA_PRIVATE_1_1_0_PERSONALITY_CONVERSATION_OK")

