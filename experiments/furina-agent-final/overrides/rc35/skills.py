from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .config import DATA_DIR, ensure_dirs

PATH = DATA_DIR / "furinahub_agent_skills.json"

CATALOG = {
    "app_control": {
        "label": "Kontrol Aplikasi",
        "description": "Membuka aplikasi dan berpindah antar aplikasi sesuai tujuan.",
        "default": True,
    },
    "ui_navigation": {
        "label": "Navigasi UI",
        "description": "Ketuk, scroll, kembali, Home, dan navigasi antarelemen.",
        "default": True,
    },
    "screen_inspection": {
        "label": "Baca Konten Layar",
        "description": "Menggunakan Accessibility untuk memahami konten yang relevan dengan tugas.",
        "default": True,
    },
    "text_input": {
        "label": "Tulis & Input",
        "description": "Mengetik teks atau menjalankan aksi IME pada field Android.",
        "default": True,
    },
    "messaging": {
        "label": "Pesan & Aksi Eksternal",
        "description": "Menyiapkan workflow pesan/post/share/call. Aksi eksternal tetap butuh konfirmasi policy.",
        "default": True,
    },
    "privileged_control": {
        "label": "Kontrol Lanjutan",
        "description": "Mengizinkan backend Shizuku/root yang dipilih user untuk primitive yang didukung.",
        "default": True,
    },
    "vision_fallback": {
        "label": "Vision Fallback",
        "description": "Memakai screenshot hanya ketika Accessibility tidak cukup dan layar tidak sensitif.",
        "default": True,
    },
}

_PATTERNS = {
    "app_control": re.compile(r"\b(?:buka|bukain|open|jalankan|launch|masuk\s+ke)\b", re.I),
    "screen_inspection": re.compile(r"\b(?:baca|lihat|cek|periksa|tampilkan|informasi|status|screen|layar)\b", re.I),
    "text_input": re.compile(r"\b(?:ketik|tulis|isi|input|type|masukkan)\b", re.I),
    "messaging": re.compile(r"\b(?:kirim|send|balas|reply|post|publish|share|bagikan|telepon|call|panggil)\b", re.I),
}


def _defaults() -> dict:
    return {key: bool(meta["default"]) for key, meta in CATALOG.items()}


def normalize(raw: dict | None) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    out = _defaults()
    for key in out:
        if key in raw:
            out[key] = bool(raw[key])
    return out


def load_skills() -> dict:
    ensure_dirs()
    if not PATH.exists():
        data = _defaults()
        save_skills(data)
        return data
    try:
        raw = json.loads(PATH.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    return normalize(raw)


def save_skills(raw: dict) -> dict:
    ensure_dirs()
    data = normalize(raw)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, PATH)
    return data


class SkillRegistry:
    def __init__(self):
        self.state = load_skills()

    def enabled(self, name: str) -> bool:
        return bool(self.state.get(name, False))

    def update(self, name: str, enabled: bool) -> dict:
        if name not in CATALOG:
            raise ValueError(f"Skill tidak dikenal: {name}")
        self.state[name] = bool(enabled)
        self.state = save_skills(self.state)
        return self.state

    def blocked_reason(self, goal: str) -> str | None:
        text = str(goal or "")
        for key, pattern in _PATTERNS.items():
            if not self.enabled(key) and pattern.search(text):
                return f"Skill Agent '{CATALOG[key]['label']}' sedang dimatikan di FurinaHub."
        if not self.enabled("ui_navigation") and re.search(
            r"\b(?:buka|open|cari|search|ketuk|tap|scroll|geser|kembali|back|home|recent)\b",
            text,
            re.I,
        ):
            return f"Skill Agent '{CATALOG['ui_navigation']['label']}' sedang dimatikan di FurinaHub."
        return None


def catalog_with_state() -> list[dict]:
    state = load_skills()
    return [
        {
            "id": key,
            "label": meta["label"],
            "description": meta["description"],
            "enabled": bool(state.get(key)),
        }
        for key, meta in CATALOG.items()
    ]
