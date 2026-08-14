from __future__ import annotations

import json
import os
from pathlib import Path

from .config import DATA_DIR

SETTINGS_PATH = DATA_DIR / "furinahub.json"
SCHEMA_VERSION = 1

PRESETS = {
    "adaptive": {
        "label": "Adaptif",
        "description": "Biarkan gaya berkembang mengikuti konteks, Psyche, dan hubungan.",
        "traits": {
            "warmth": 55, "directness": 55, "playfulness": 48, "sarcasm": 30,
            "affection": 45, "expressiveness": 55, "formality": 35,
            "verbosity": 45, "teasing": 25, "emotional_openness": 55,
        },
    },
    "friendly": {
        "label": "Ramah",
        "description": "Hangat dan mudah didekati tanpa menjadi berlebihan.",
        "traits": {
            "warmth": 78, "directness": 48, "playfulness": 58, "sarcasm": 18,
            "affection": 58, "expressiveness": 68, "formality": 24,
            "verbosity": 50, "teasing": 22, "emotional_openness": 66,
        },
    },
    "direct": {
        "label": "Langsung",
        "description": "Ringkas, tegas, fokus pada inti pembicaraan.",
        "traits": {
            "warmth": 42, "directness": 88, "playfulness": 22, "sarcasm": 20,
            "affection": 28, "expressiveness": 34, "formality": 38,
            "verbosity": 24, "teasing": 12, "emotional_openness": 34,
        },
    },
    "professional": {
        "label": "Profesional",
        "description": "Terstruktur, tenang, dan minim permainan gaya.",
        "traits": {
            "warmth": 42, "directness": 72, "playfulness": 12, "sarcasm": 8,
            "affection": 16, "expressiveness": 28, "formality": 82,
            "verbosity": 46, "teasing": 4, "emotional_openness": 24,
        },
    },
    "playful": {
        "label": "Playful",
        "description": "Lebih spontan, ringan, dan suka menggoda.",
        "traits": {
            "warmth": 70, "directness": 48, "playfulness": 88, "sarcasm": 38,
            "affection": 62, "expressiveness": 82, "formality": 14,
            "verbosity": 48, "teasing": 76, "emotional_openness": 72,
        },
    },
    "tsundere": {
        "label": "Tsundere",
        "description": "Lebih defensif dan menggoda, tetapi perhatian tetap muncul secara natural.",
        "traits": {
            "warmth": 48, "directness": 68, "playfulness": 58, "sarcasm": 64,
            "affection": 60, "expressiveness": 72, "formality": 20,
            "verbosity": 44, "teasing": 72, "emotional_openness": 38,
        },
    },
    "cool": {
        "label": "Cool / Dry",
        "description": "Tenang, sedikit dingin, humor kering, tidak banyak basa-basi.",
        "traits": {
            "warmth": 28, "directness": 74, "playfulness": 28, "sarcasm": 56,
            "affection": 26, "expressiveness": 24, "formality": 36,
            "verbosity": 28, "teasing": 34, "emotional_openness": 24,
        },
    },
    "gentle": {
        "label": "Lembut",
        "description": "Tenang, sabar, hangat, dan minim sinisme.",
        "traits": {
            "warmth": 88, "directness": 38, "playfulness": 32, "sarcasm": 4,
            "affection": 72, "expressiveness": 58, "formality": 30,
            "verbosity": 50, "teasing": 10, "emotional_openness": 70,
        },
    },
    "custom": {
        "label": "Kustom",
        "description": "Atur seluruh karakteristik sendiri.",
        "traits": {},
    },
}

TRAIT_LABELS = {
    "warmth": "Kehangatan",
    "directness": "Ketegasan / Langsung",
    "playfulness": "Playfulness",
    "sarcasm": "Sinis / Sarkas",
    "affection": "Kemesraan",
    "expressiveness": "Ekspresivitas",
    "formality": "Formalitas",
    "verbosity": "Panjang Jawaban",
    "teasing": "Suka Menggoda",
    "emotional_openness": "Keterbukaan Emosi",
}

DEFAULT_SKILLS = {
    "android_navigation": True,
    "screen_context": True,
    "text_input": True,
    "semantic_workflows": True,
    "vision_fallback": True,
    "privileged_controls": False,
}

SKILL_META = {
    "android_navigation": {
        "label": "Navigasi Android",
        "description": "Buka aplikasi, kembali, ketuk, scroll, dan navigasi UI.",
    },
    "screen_context": {
        "label": "Baca Konteks Layar",
        "description": "Gunakan Accessibility untuk memahami elemen layar.",
    },
    "text_input": {
        "label": "Input Teks",
        "description": "Mengetik ke field yang relevan setelah lolos policy.",
    },
    "semantic_workflows": {
        "label": "Workflow Semantik",
        "description": "Rangkai open/search/select/type/send secara terkontrol.",
    },
    "vision_fallback": {
        "label": "Vision Fallback",
        "description": "Gunakan screenshot hanya saat Accessibility tidak cukup dan layar tidak sensitif.",
    },
    "privileged_controls": {
        "label": "Kontrol Privileged",
        "description": "Izinkan primitive tetap melalui Shizuku/root saat mode tersebut dipilih.",
    },
}

ACTION_SKILLS = {
    "observe": "screen_context",
    "wait": "screen_context",
    "tap_node": "android_navigation",
    "tap": "android_navigation",
    "long_press": "android_navigation",
    "swipe": "android_navigation",
    "scroll_node": "android_navigation",
    "scroll_global": "android_navigation",
    "back": "android_navigation",
    "home": "android_navigation",
    "recents": "android_navigation",
    "open_app": "android_navigation",
    "tap_text": "android_navigation",
    "scroll_best": "android_navigation",
    "set_text": "text_input",
    "ime_action": "text_input",
    "set_text_best": "text_input",
    "ime_best": "text_input",
    "run_ui_sequence": "semantic_workflows",
}


def _default_traits() -> dict[str, int]:
    return dict(PRESETS["adaptive"]["traits"])


def defaults() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "assistant_name": "Furina",
        "user_nickname": "",
        "base_style": "adaptive",
        "characteristics": _default_traits(),
        "custom_instructions": "",
        "theme": "system",
        "agent_skills": dict(DEFAULT_SKILLS),
        "device_control_mode": "normal",
    }


def _clamp_int(value, default: int = 50) -> int:
    try:
        return max(0, min(100, int(value)))
    except Exception:
        return default


def normalize(raw: dict | None) -> dict:
    base = defaults()
    raw = raw if isinstance(raw, dict) else {}

    name = str(raw.get("assistant_name", base["assistant_name"])).strip()
    nickname = str(raw.get("user_nickname", base["user_nickname"])).strip()
    base["assistant_name"] = (name or "Furina")[:48]
    base["user_nickname"] = nickname[:48]

    style = str(raw.get("base_style", "adaptive")).strip().lower()
    if style not in PRESETS:
        style = "adaptive"
    base["base_style"] = style

    preset_traits = dict(PRESETS.get(style, PRESETS["adaptive"]).get("traits") or _default_traits())
    if not preset_traits:
        preset_traits = _default_traits()
    incoming = raw.get("characteristics") if isinstance(raw.get("characteristics"), dict) else {}
    for key in TRAIT_LABELS:
        default_value = int(preset_traits.get(key, _default_traits().get(key, 50)))
        base["characteristics"][key] = _clamp_int(incoming.get(key, default_value), default_value)

    instructions = str(raw.get("custom_instructions", ""))
    base["custom_instructions"] = instructions.strip()[:3000]

    theme = str(raw.get("theme", "system")).strip().lower()
    base["theme"] = theme if theme in {"system", "light", "dark"} else "system"

    skills = raw.get("agent_skills") if isinstance(raw.get("agent_skills"), dict) else {}
    base["agent_skills"] = {
        key: bool(skills.get(key, default))
        for key, default in DEFAULT_SKILLS.items()
    }

    mode = str(raw.get("device_control_mode", "normal")).strip().lower()
    base["device_control_mode"] = mode if mode in {"normal", "shizuku", "root"} else "normal"
    base["schema_version"] = SCHEMA_VERSION
    return base


def load_hub_settings() -> dict:
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8")) if SETTINGS_PATH.exists() else {}
    except Exception:
        raw = {}
    out = normalize(raw)
    if not SETTINGS_PATH.exists():
        save_hub_settings(out)
    return out


def save_hub_settings(settings: dict) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = normalize(settings)
    tmp = SETTINGS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, SETTINGS_PATH)
    os.chmod(SETTINGS_PATH, 0o600)
    return out


def apply_preset(settings: dict, preset: str) -> dict:
    out = normalize(settings)
    preset = str(preset or "").strip().lower()
    if preset not in PRESETS:
        raise ValueError("preset tidak dikenal")
    out["base_style"] = preset
    traits = PRESETS[preset].get("traits") or out["characteristics"]
    if traits:
        out["characteristics"] = {
            key: int(traits.get(key, out["characteristics"].get(key, 50)))
            for key in TRAIT_LABELS
        }
    return save_hub_settings(out)


def skill_enabled(name: str, settings: dict | None = None) -> bool:
    state = normalize(settings) if settings is not None else load_hub_settings()
    return bool((state.get("agent_skills") or {}).get(name, False))


def skill_allows_action(action_type: str, settings: dict | None = None) -> bool:
    required = ACTION_SKILLS.get(str(action_type or "").strip())
    if not required:
        return True
    return skill_enabled(required, settings)


def effective_device_mode(settings: dict | None = None, fallback: str = "normal") -> str:
    state = normalize(settings) if settings is not None else load_hub_settings()
    requested = str(state.get("device_control_mode") or fallback).strip().lower()
    if requested not in {"normal", "shizuku", "root"}:
        requested = "normal"
    if requested in {"shizuku", "root"} and not skill_enabled("privileged_controls", state):
        return "normal"
    return requested


def personalization_prompt(settings: dict | None = None) -> str:
    state = normalize(settings) if settings is not None else load_hub_settings()
    style = PRESETS.get(state["base_style"], PRESETS["adaptive"])
    traits = state["characteristics"]
    trait_line = ", ".join(f"{TRAIT_LABELS[k]}={int(traits[k])}/100" for k in TRAIT_LABELS)
    custom = state.get("custom_instructions") or "(tidak ada)"
    return f"""[USER PERSONALIZATION — EXPRESSION BIAS, BUKAN IDENTITAS KAKU]
Nama tampilanmu: {state['assistant_name']}
Nama panggilan pengguna: {state['user_nickname'] or '(belum diatur)'}
Gaya dasar: {style['label']} — {style['description']}
Karakteristik: {trait_line}
Instruksi khusus pengguna:
{custom}

Gunakan pengaturan ini sebagai bias ekspresi yang lembut. Jangan menjadikannya skrip, catchphrase, atau persona kaku.
PsycheState, pengalaman, konteks, dan emosi saat ini tetap boleh membuat respons menyimpang secara natural dari preset.
Nilai personalisasi tidak pernah memberi izin kontrol perangkat, mengubah fakta, atau mengalahkan policy keamanan."""
