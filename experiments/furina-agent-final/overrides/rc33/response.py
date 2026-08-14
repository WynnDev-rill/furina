from __future__ import annotations

import re
from dataclasses import dataclass

from .memory import MemoryStore
from .psyche import PsycheEngine


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

    if _GREETING.match(text) or (len(text) <= 18 and "?" not in text):
        name, max_tokens, temp = "REFLEX", 220, 0.78
        instruction = "Balas spontan dan ringkas, biasanya 1-2 kalimat. Jangan memakai pembukaan/tutup customer-service."
    elif _TECH.search(text):
        name, max_tokens, temp = "SHARP", 1800, 0.52
        instruction = "Prioritaskan ketepatan teknis. Psyche tetap terasa dalam diksi, tetapi jangan mengaburkan solusi."
    elif _EMOTION.search(text):
        name, max_tokens, temp = "CLOSE", 1500, 0.72
        instruction = "Tanggapi detail emosional yang benar-benar dikatakan pengguna. Hindari respons konselor generik atau empati template."
    elif _DEEP.search(text) or len(text) > 220:
        name, max_tokens, temp = "DEEP", 2600, 0.66
        instruction = "Jawab lengkap dan bernalar tanpa filler. Pertahankan continuity suara Furina dari MindPacket."
    else:
        name, max_tokens, temp = "CASUAL", 1000, 0.76
        instruction = "Gunakan ritme percakapan natural, biasanya 2-6 kalimat. Boleh punya opini atau keberatan jika sesuai state."

    len_bucket = "short" if len(text) < 30 else "medium" if len(text) < 140 else "long"
    context_key = f"{len_bucket}:{'emotional' if _EMOTION.search(text) else 'technical' if _TECH.search(text) else 'general'}"

    samples, win_rate = store.route_stats(name, context_key)
    if samples >= 8 and win_rate < 0.30 and name in {"REFLEX", "CASUAL"}:
        name = "CASUAL" if name == "REFLEX" else "DEEP"
        max_tokens = 900 if name == "CASUAL" else 1800
        instruction += " Gaya sebelumnya sering tidak cocok; kali ini beri sedikit lebih banyak konteks."
    store.record_route(name, context_key)

    try:
        psyche = PsycheEngine(store)
        packet = psyche.state
        short = packet["short"]
        mid = packet["mid"]
        relation = mid["relationship"]
        notes = []
        emotions = short.get("active_emotions") or []
        if emotions:
            notes.append("emosi aktif cukup relevan; ekspresikan secara implisit, jangan menyebut skornya")
        if relation["friction"] >= 0.45:
            notes.append("ada friction yang masih tersisa; jangan berpura-pura semuanya netral")
        if relation["closeness"] >= 0.68:
            notes.append("hubungan sudah akrab sehingga ritme boleh lebih informal")
        if mid["stress"] >= 0.55:
            notes.append("state sedang tegang; jawaban boleh sedikit lebih pendek/terkendali")
        if notes:
            instruction += " Psyche hint: " + "; ".join(notes) + "."
    except Exception:
        pass

    return ResponseProfile(name, max_tokens, temp, instruction, context_key)
