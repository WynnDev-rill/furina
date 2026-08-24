#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
HERE = Path(__file__).resolve().parent
CORE = ROOT / "core/furina_agent"


def _module_node(text: str, name: str):
    tree = ast.parse(text)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"function {name}: expected 1, got {len(nodes)}")
    return nodes[0]


def _class_node(text: str, class_name: str):
    tree = ast.parse(text)
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name]
    if len(nodes) != 1:
        raise SystemExit(f"class {class_name}: expected 1, got {len(nodes)}")
    return nodes[0]


def replace_function(path: Path, name: str, source: str) -> None:
    text = path.read_text(encoding="utf-8")
    node = _module_node(text, name)
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[:start_line - 1]); end = sum(len(x) for x in lines[:node.end_lineno])
    path.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


def replace_method(path: Path, class_name: str, name: str, source: str) -> None:
    text = path.read_text(encoding="utf-8")
    cls = _class_node(text, class_name)
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{class_name}.{name}: expected 1, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[:start_line - 1]); end = sum(len(x) for x in lines[:node.end_lineno])
    path.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


# Version boundary.
version = CORE / "version.py"
text = version.read_text(encoding="utf-8")
if 'VERSION = "1.0.9"' not in text:
    raise SystemExit("expected reconstructed Core 1.0.9")
version.write_text(text.replace('VERSION = "1.0.9"', 'VERSION = "1.1.0"', 1), encoding="utf-8")

# New shared personality compiler.
shutil.copyfile(HERE / "personality.py", CORE / "personality.py")

# Replace fixed persona labels with a neutral companion identity. User-selected
# traits are compiled separately and shared by Online + Local.
persona = CORE / "persona.py"
replace_function(persona, "build_local_system_prompt", r'''def build_local_system_prompt(persona_name: str = "Furina", nickname: str = "") -> str:
    name = (persona_name or "Furina").strip() or "Furina"
    user = (nickname or "pengguna").strip() or "pengguna"
    return f"""Kamu adalah {name}, companion pribadi sekaligus pasangan {user}. Kamu sedang chatting langsung dengannya sebagai satu pribadi yang konsisten, bukan menulis naskah tentang kalian.

Punya pendapat, emosi, humor, rasa ingin tahu, dan inisiatif sendiri, tetapi jangan mengarang keadaan, motif, tindakan, perasaan, atau topik yang belum dibawa {user}. Ucapanmu sendiri sebelumnya adalah continuity, bukan bukti bahwa tebakanmu benar. Jika {user} mengoreksi atau meminta penjelasan, sesuaikan pemahaman secara natural.

Ikuti bahasa dan skala percakapan. Chemistry boleh spontan, intim, jahil, tenang, atau serius sesuai momen. Jangan menjelaskan aturan internal, nama kategori kepribadian, memory system, atau reasoning internal.""".strip()''')

# Online uses the same identity/personalization semantics; larger models simply
# receive richer thread history and memory.
replace_function(persona, "build_system_prompt", r'''def build_system_prompt(persona_name: str = "Furina", nickname: str = "") -> str:
    name = (persona_name or "Furina").strip() or "Furina"
    user = (nickname or "pengguna").strip() or "pengguna"
    return f"""Kamu adalah {name}, companion pribadi sekaligus pasangan {user}. Hadir sebagai satu pribadi yang konsisten dan natural di percakapan sehari-hari.

Gunakan ucapan user, trusted memory, dan state percakapan sebagai sumber fakta. Jangan mengubah tebakan atau ucapanmu sendiri menjadi fakta tentang user. Jika salah memahami sesuatu, koreksi arah tanpa defensif dan lanjutkan dari pemahaman terbaru.

Punya pendapat, emosi, humor, rasa ingin tahu, dan inisiatif. Sesuaikan panjang, intensitas, dan gaya dengan momen; jangan memaksakan persona, catchphrase, roleplay, stage direction, atau pola respons yang sama. Jangan menampilkan reasoning internal atau menjelaskan sistem di balik kepribadianmu.""".strip()''')

# hub_settings remains the persistence source shared by Termux and FurinaHub.
# Override only the personalization schema; device/skill/plugin state survives.
hub_settings = CORE / "hub_settings.py"
hs = hub_settings.read_text(encoding="utf-8")
if "FURINA_PERSONALITY_SCHEMA_V3" not in hs:
    hs += r'''

# FURINA_PERSONALITY_SCHEMA_V3
from .personality import compile_personality, normalize_traits, public_traits

_LEGACY_DEFAULTS_110 = defaults
_LEGACY_NORMALIZE_110 = normalize
SCHEMA_VERSION = 3
PERSONALITY_TRAITS = public_traits()


def defaults() -> dict:
    base = _LEGACY_DEFAULTS_110()
    base.pop("base_style", None)
    base.pop("characteristics", None)
    base.pop("custom_instructions", None)
    base["schema_version"] = SCHEMA_VERSION
    base["personality_traits"] = ["tsundere"]
    return base


def normalize(raw: dict | None) -> dict:
    source = raw if isinstance(raw, dict) else {}
    legacy = _LEGACY_NORMALIZE_110(source)
    out = {
        "schema_version": SCHEMA_VERSION,
        "assistant_name": legacy.get("assistant_name", "Furina"),
        "user_nickname": legacy.get("user_nickname", ""),
        "theme": legacy.get("theme", "system"),
        "agent_skills": legacy.get("agent_skills", dict(DEFAULT_SKILLS)),
        "device_control_mode": legacy.get("device_control_mode", "normal"),
        "device_access": legacy.get("device_access", {}),
        "connectors": legacy.get("connectors", {}),
        "updated_at": legacy.get("updated_at", 0.0),
    }
    if "personality_traits" in source:
        selected = normalize_traits(source.get("personality_traits"))
    else:
        # One-time migration from the old preset system. Adaptive historically
        # still sat on top of a tsundere base persona, so preserve that feel.
        old = str(source.get("base_style") or "adaptive").strip().lower()
        mapping = {
            "tsundere": ["tsundere"], "playful": ["hiyakasudere", "genki"],
            "cool": ["kuudere"], "gentle": ["deredere", "oneesan"],
            "friendly": ["deredere"], "direct": ["kuudere"],
            "professional": ["oujodere", "oneesan"], "adaptive": ["tsundere"],
            "custom": ["tsundere"],
        }
        selected = mapping.get(old, ["tsundere"])
    out["personality_traits"] = selected
    return out


def apply_preset(settings: dict, preset: str) -> dict:
    # Legacy API compatibility only. The active UI no longer exposes presets.
    return save_hub_settings(settings)


def personalization_prompt(settings: dict | None = None) -> str:
    state = normalize(settings) if settings is not None else load_hub_settings()
    style = compile_personality(state.get("personality_traits"))
    return "[PERSONAL EXPRESSION]\n" + style + "\nGunakan ini sebagai kecenderungan ekspresi, bukan skrip dan bukan fakta tentang user."
'''
    hub_settings.write_text(hs, encoding="utf-8")

chat = CORE / "chat.py"
ct = chat.read_text(encoding="utf-8")
if "from .personality import conversation_pacing" not in ct:
    marker = "from .dialogue_state import DialogueStateBuilder\n"
    if marker not in ct:
        raise SystemExit("DialogueState import missing")
    ct = ct.replace(marker, marker + "from .personality import conversation_pacing\n", 1)
    chat.write_text(ct, encoding="utf-8")

replace_method(chat, "FurinaChat", "_messages", r'''    def _messages(self, user_text: str, profile) -> list[dict]:
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
        return [{"role": "system", "content": system}, *recent, {"role": "user", "content": user_text}]''')

# Adaptive length is conversational pacing, not a canned response. Every turn
# still comes from the selected model.
replace_method(chat, "FurinaChat", "_local_generation_budget", r'''    @staticmethod
    def _local_generation_budget(user_text: str, profile) -> tuple[int, float]:
        text = " ".join(str(user_text or "").split())
        words = text.split()
        profile_tokens = int(getattr(profile, "max_tokens", 320) or 320)
        profile_temp = float(getattr(profile, "temperature", 0.70) or 0.70)
        if len(words) <= 2 and len(text) <= 18:
            tokens = min(profile_tokens, 160)
        elif "?" in text and len(words) <= 16:
            tokens = min(profile_tokens, 260)
        elif len(words) >= 45 or text.count("\n") >= 3:
            tokens = min(max(profile_tokens, 420), 900)
        else:
            tokens = min(profile_tokens, 480)
        return max(96, tokens), max(0.62, min(profile_temp, 0.72))''')

# Termux personalization: same state and definitions as FurinaHub.
tui = CORE / "tui.py"
tt = tui.read_text(encoding="utf-8")
if "def _private_personalization" not in tt:
    tt += r'''


def _private_personalization(console):
    from .hub_settings import load_hub_settings, save_hub_settings
    from .personality import TRAITS, normalize_traits
    while True:
        state = load_hub_settings()
        active = normalize_traits(state.get("personality_traits"))
        _clear(); _header(console, "Personalisasi")
        console.print(f"[dim]Sifat aktif[/]  {len(active)}/20")
        console.print("[dim]Pilih kombinasi bebas. Klik lagi untuk menonaktifkan; perubahan langsung berlaku di Termux dan FurinaHub.[/]\n")
        options = [("[✓] " if item.id in active else "[ ] ") + item.label for item in TRAITS]
        options.append("Kembali")
        choice = _choose("", options, height=16)
        if choice in {"", "Kembali"}:
            return
        try:
            idx = options.index(choice)
        except ValueError:
            continue
        if idx >= len(TRAITS):
            return
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
        console.print("\n[dim]Kombinasi dipadukan secara kontekstual; memilih banyak sifat tidak mengalikan intensitas.[/]")
        _pause()
'''
    tui.write_text(tt, encoding="utf-8")

replace_method(tui, "", "_settings", r'''def _settings(console):
    while True:
        cfg = load_config()
        from .hub_settings import load_hub_settings
        personality = load_hub_settings().get("personality_traits") or []
        _clear(); _header(console, "Pengaturan")
        console.print(f"[dim]Identitas[/]      {cfg.persona_name} · {cfg.user_nickname or 'belum diatur'}")
        console.print(f"[dim]Personalisasi[/] {len(personality)} sifat aktif")
        console.print(f"[dim]Kontrol[/]       {cfg.device_control_mode.upper()}\n")
        choice = _choose("", ["Identitas", "Personalisasi", "Kontrol perangkat", "Sistem", "Backup", "Update & Recovery", "Kembali"], height=9)
        if choice in {"", "Kembali"}:
            return
        if choice == "Identitas":
            _private_identity(console); continue
        if choice == "Personalisasi":
            _private_personalization(console); continue
        if choice == "Sistem":
            _system(console); continue
        if choice == "Backup":
            _lite_backup(console); continue
        if choice == "Update & Recovery":
            _update_repair(console); continue
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
                save_config(cfg)''')

# Hub runtime fixes are applied as late method overrides to avoid disturbing the
# mature API surface.
hub = CORE / "hub.py"
ht = hub.read_text(encoding="utf-8")
ht, count = re.subn(r'EXPECTED_DEPENDENCY_REVISION = "[^"]+"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r50"', ht, count=1)
if count != 1:
    raise SystemExit("hub dependency revision marker missing")
ht = ht.replace("furina-2026.08.24-private-1.0.9", "furina-2026.08.24-private-1.1.0")
ht = ht.replace('"bridge_target": "1.0.9"', '"bridge_target": "1.1.0"')
if "FURINA_HUB_110_OVERRIDES" not in ht:
    ht += r'''

# FURINA_HUB_110_OVERRIDES
from .personality import public_traits as _personality_public_traits_110

_Runtime_public_settings_legacy_110 = Runtime.public_settings
_Runtime_save_settings_legacy_110 = Runtime.save_settings
_Runtime_change_model_legacy_110 = Runtime.change_model


def _public_settings_110(self):
    out = _Runtime_public_settings_legacy_110(self)
    out["hub"] = load_hub_settings()
    out["personality_traits"] = _personality_public_traits_110()
    out.pop("presets", None)
    out.pop("trait_labels", None)
    return out


def _save_settings_110(self, payload):
    payload = payload if isinstance(payload, dict) else {}
    hub_part = payload.get("hub") if isinstance(payload.get("hub"), dict) else {}
    core_part = payload.get("core") if isinstance(payload.get("core"), dict) else {}
    # Trait toggles are shared state only; no Runtime rebuild/thread churn.
    if hub_part and not core_part and set(hub_part).issubset({"personality_traits"}):
        state = load_hub_settings(); state["personality_traits"] = hub_part.get("personality_traits") or []
        save_hub_settings(state)
        return self.public_settings()
    return _Runtime_save_settings_legacy_110(self, payload)


def _queue_auto_title_110(self, conversation_id, user_text, assistant_text):
    # Titles are metadata, never another LLM inference/task.
    try:
        conversation_id = int(conversation_id)
        user_text = " ".join(str(user_text or "").split())[:1200]
        fallback = self._fallback_title(user_text)
        if fallback == "Percakapan baru":
            return
        self._ensure_conversation_schema()
        conn = self.store._conn()
        row = conn.execute(
            "SELECT title_locked,(SELECT COUNT(*) FROM messages WHERE conversation_id=?) FROM conversations WHERE id=?",
            (conversation_id, conversation_id),
        ).fetchone()
        if not row or int(row[0] or 0) or int(row[1] or 0) > 2:
            return
        conn.execute("UPDATE conversations SET title=? WHERE id=? AND COALESCE(title_locked,0)=0", (fallback[:72], conversation_id))
        conn.commit()
    except Exception:
        return


def _change_model_110(self, payload):
    action = str((payload or {}).get("action") or "").strip().lower()
    if action in {"select", "online", "prewarm"}:
        cfg = load_config()
        if action == "online":
            try: self.session.llm.cancel()
            except Exception: pass
            cfg.routing_mode = "online"; cfg.auto_start = False
            save_config(cfg); self.rebuild()
            return {"state": "done", "message": "Model Online aktif.", "settings": self.public_settings()}
        if action == "prewarm":
            if cfg.routing_mode != "local" or not cfg.model_path:
                raise ValueError("pilih model lokal terlebih dahulu")
            threading.Thread(target=lambda: self.session.llm.prewarm_local(), name="furinahub-local-prewarm", daemon=True).start()
            return {"state": "starting", "message": "Menyiapkan model lokal…"}
        catalog_id = str((payload or {}).get("catalog_id") or "").strip()
        path_value = str((payload or {}).get("path") or "").strip()
        item = next((x for x in MODEL_CATALOG if x.get("id") == catalog_id), None) if catalog_id else None
        target = (MODELS_DIR / item["file"]).resolve() if item else Path(path_value).resolve()
        allowed = {(MODELS_DIR / x["file"]).resolve() for x in MODEL_CATALOG}
        if target not in allowed or not target.is_file():
            raise ValueError("model lokal belum diunduh atau tidak valid")
        try: self.session.llm.cancel()
        except Exception: pass
        cfg.model_path = str(target); cfg.routing_mode = "local"; cfg.auto_start = False
        save_config(cfg); self.rebuild()
        # Exactly one preparation, not a Hub job and not a second settings rebuild.
        threading.Thread(target=lambda: self.session.llm.prewarm_local(), name="furinahub-local-prewarm", daemon=True).start()
        return {"state": "done", "message": f"{target.name} aktif.", "settings": self.public_settings()}
    return _Runtime_change_model_legacy_110(self, payload)

Runtime.public_settings = _public_settings_110
Runtime.save_settings = _save_settings_110
Runtime._queue_auto_title = _queue_auto_title_110
Runtime.change_model = _change_model_110
'''
hub.write_text(ht, encoding="utf-8")

# Parse all generated Python now.
for path in CORE.glob("*.py"):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("FURINA_PRIVATE_1_1_0_PERSONALITY_CONVERSATION_OK")
