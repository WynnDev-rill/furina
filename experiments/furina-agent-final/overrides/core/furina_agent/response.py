from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass

from .memory import MemoryStore


@dataclass
class ResponseProfile:
    name: str
    max_tokens: int
    temperature: float
    instruction: str
    context_key: str


_TECH = re.compile(r"\b(error|bug|fix|debug|kode|code|script|install|termux|api|json|http|github|build|apk|model|provider|database|sql|python|java|gradle)\b", re.I)
_DEEP = re.compile(r"\b(analisis|analyze|bandingkan|compare|strategi|strategy|rencana|plan|evaluasi|evaluate|kenapa|mengapa|menurutmu|bagaimana jika|what if)\b", re.I)
_EMOTION = re.compile(r"\b(aku merasa|sedih|marah|takut|cemas|kesepian|capek|lelah|sakit hati|putus asa|bingung|kecewa|tertekan|frustrasi)\b", re.I)
_GREETING = re.compile(r"^\s*(hai|hi|halo|hey|yo|pagi|siang|sore|malam|tes|test|ok|oke)\s*[.!?]*\s*$", re.I)
_POSITIVE = re.compile(r"\b(makasih|terima kasih|bagus|mantap|pas|tepat|berhasil|nah gitu|iya benar|lanjut)\b", re.I)
_NEGATIVE = re.compile(r"\b(salah|payah|jelek|nggak sesuai|tidak sesuai|bukan begitu|masih gagal|gagal lagi|terpotong|terlalu|jangan begitu)\b", re.I)


def _state(store: MemoryStore, user_text: str) -> dict:
    raw = store.get_state("companion_state", {})
    if not isinstance(raw, dict):
        raw = {}
    s = {
        "irritation": float(raw.get("irritation", 0.08) or 0.08),
        "curiosity": float(raw.get("curiosity", 0.55) or 0.55),
        "energy": float(raw.get("energy", 0.72) or 0.72),
    }
    low = user_text.lower()
    if _NEGATIVE.search(low):
        s["irritation"] += 0.06
    else:
        s["irritation"] *= 0.91
    if "?" in user_text or len(user_text) > 80:
        s["curiosity"] += 0.025
    else:
        s["curiosity"] *= 0.995
    hour = _dt.datetime.now().hour
    target_energy = 0.48 if hour >= 23 or hour <= 5 else 0.78
    s["energy"] = s["energy"] * 0.9 + target_energy * 0.1
    for k in s:
        s[k] = round(max(0.0, min(1.0, s[k])), 4)
    store.set_state("companion_state", s)
    return s


def register_previous_outcome(store: MemoryStore, user_text: str) -> None:
    if _NEGATIVE.search(user_text):
        store.mark_last_route_outcome("negative")
    elif _POSITIVE.search(user_text):
        store.mark_last_route_outcome("positive")
    else:
        store.mark_last_route_outcome("neutral")


def choose_profile(user_text: str, store: MemoryStore) -> ResponseProfile:
    text = " ".join(user_text.strip().split())
    register_previous_outcome(store, text)
    relation = store.update_relationship(text)
    state = _state(store, text)

    if _GREETING.match(text) or (len(text) <= 18 and "?" not in text):
        name = "REFLEX"
        max_tokens = 220
        temp = 0.82
        instruction = (
            "Balas seperti percakapan spontan: 1-2 kalimat, hidup, tidak formal. "
            "Boleh menggoda atau sedikit sok penting. Jangan menutup dengan kalimat customer-service."
        )
    elif _TECH.search(text):
        name = "SHARP"
        max_tokens = 1800
        temp = 0.58
        instruction = (
            "Tetap Furina, tetapi prioritaskan ketepatan. Gunakan struktur hanya jika memang membantu. "
            "Sindiran boleh singkat; jangan biarkan persona mengaburkan solusi teknis."
        )
    elif _EMOTION.search(text):
        name = "CLOSE"
        max_tokens = 1500
        temp = 0.78
        instruction = (
            "Respons sebagai seseorang yang sudah mengenal pengguna, bukan konselor generik. "
            "Kurangi lelucon bila situasinya berat, tetapi jangan berubah menjadi lembek atau penuh kalimat template. "
            "Tanggapi detail yang benar-benar dikatakan pengguna."
        )
    elif _DEEP.search(text) or len(text) > 220:
        name = "DEEP"
        max_tokens = 2600
        temp = 0.72
        instruction = (
            "Berikan jawaban lengkap dan bernalar, tetapi tetap terdengar seperti Furina yang sedang berbicara. "
            "Jangan memakai filler, jangan mengulang premis pengguna, dan jangan membuat daftar bila paragraf lebih natural."
        )
    else:
        name = "CASUAL"
        max_tokens = 1000
        temp = 0.82
        instruction = (
            "Gunakan ritme percakapan manusia: biasanya 2-6 kalimat, variasikan panjang kalimat, boleh fragment singkat. "
            "Jangan selalu menawarkan bantuan atau bertanya balik. Boleh punya opini, keberatan, atau rasa ingin tahu sendiri."
        )

    len_bucket = "short" if len(text) < 30 else "medium" if len(text) < 140 else "long"
    context_key = f"{len_bucket}:{'emotional' if _EMOTION.search(text) else 'technical' if _TECH.search(text) else 'general'}"

    # Only let learned outcomes override when there is enough evidence. This is
    # intentionally conservative: weak feedback should not rewrite personality.
    samples, win_rate = store.route_stats(name, context_key)
    if samples >= 8 and win_rate < 0.30 and name in {"REFLEX", "CASUAL"}:
        name = "CASUAL" if name == "REFLEX" else "DEEP"
        max_tokens = 900 if name == "CASUAL" else 1800
        instruction += " Riwayat menunjukkan gaya sebelumnya sering tidak cocok; kali ini beri sedikit lebih banyak konteks."

    store.record_route(name, context_key)
    relation_words = []
    if relation["closeness"] >= 0.65:
        relation_words.append("hubungan sudah akrab")
    elif relation["closeness"] <= 0.25:
        relation_words.append("hubungan masih relatif baru")
    if relation["friction"] >= 0.45:
        relation_words.append("ada sedikit gesekan dari percakapan terbaru")
    if relation["playfulness"] >= 0.65:
        relation_words.append("banter boleh lebih terasa")
    if state["irritation"] >= 0.5:
        relation_words.append("Furina sedang agak jengkel tetapi tetap kompeten")

    if relation_words:
        instruction += " Keadaan relasi saat ini: " + "; ".join(relation_words) + "."

    return ResponseProfile(name, max_tokens, temp, instruction, context_key)
