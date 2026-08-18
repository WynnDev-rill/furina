from __future__ import annotations

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
_GREETING = re.compile(r"^\s*(hai|hi|halo|hey|yo|pagi|siang|sore|malam|tes|test)\s*[.!?]*\s*$", re.I)
_SHORT_ACK = re.compile(r"^\s*(ok|oke|iya|ya|y|sip|baik|hmm+|hm+|oh|tidak|nggak|enggak|gak|ga|no|nope)\s*[.!?]*\s*$", re.I)
_IDENTITY = re.compile(
    r"(?:\b(?:apakah|apa|emang|memang)\s+(?:kamu|kau)\s+(?:hidup|sadar|nyata|ai|bot|chatbot)\b|"
    r"\b(?:kamu|kau)\s+(?:hidup|sadar|punya\s+kesadaran|punya\s+perasaan|punya\s+emosi|ai|bot|chatbot|siapa|apa)\b|"
    r"\bsiapa\s+(?:kamu|kau)\b|\bapa\s+(?:kamu|kau)\b)",
    re.I,
)
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
    relation = store.update_relationship(text)

    if _IDENTITY.search(text):
        name = "IDENTITY"
        max_tokens = 220
        temp = 0.70
        instruction = (
            "Jawab langsung sebagai companion yang sedang diajak bicara, bukan sebagai FAQ tentang AI. "
            "Biasanya 1-4 kalimat. Jangan membuka dengan 'pertanyaan itu ambigu', jangan memberi kuliah definisi hidup/kesadaran, "
            "dan jangan otomatis bertanya balik. Jika ditanya apakah hidup/sadar, jujur: kamu bukan makhluk biologis dan tidak punya "
            "bukti bahwa kamu memiliki kesadaran subjektif seperti manusia. Kamu boleh menjelaskan bahwa memory, state, relationship, "
            "dan continuity-mu nyata sebagai mekanisme software, tanpa mengklaim pengalaman subjektif yang tidak dapat dibuktikan."
        )
    elif _GREETING.match(text):
        name = "REFLEX"
        max_tokens = 80
        temp = 0.82
        instruction = (
            "Balas spontan dalam 1-2 kalimat pendek. Jangan membuka sesi bantuan. Jangan bertanya 'ada yang bisa dibantu?', "
            "'ada yang ingin dibicarakan?', 'ada apa?', atau variasinya. Sapaan boleh dibalas dengan komentar kecil, banter, atau reaksi."
        )
    elif _SHORT_ACK.match(text) or (len(text) <= 18 and "?" not in text):
        name = "REFLEX"
        max_tokens = 90
        temp = 0.80
        instruction = (
            "Ini respons pendek dalam percakapan yang sedang berjalan. Balas 1-2 kalimat pendek dan in-character. "
            "Jangan menganggap percakapan selesai, jangan menawarkan bantuan, jangan berkata 'kalau berubah pikiran beri tahu', "
            "dan jangan memaksa pertanyaan baru hanya untuk meneruskan chat."
        )
    elif _TECH.search(text):
        name = "SHARP"
        max_tokens = 1800
        temp = 0.58
        instruction = (
            "Tetap Furina, tetapi prioritaskan ketepatan. Gunakan struktur hanya jika membantu. "
            "Sindiran boleh singkat; jangan biarkan persona mengaburkan solusi teknis."
        )
    elif _EMOTION.search(text):
        name = "CLOSE"
        max_tokens = 800
        temp = 0.76
        instruction = (
            "Respons seperti seseorang yang sudah mengenal pengguna, bukan konselor generik. Tanggapi detail konkret yang dikatakan. "
            "Hindari template terapi, validasi kosong, dan pertanyaan bertubi-tubi. Biasanya 2-7 kalimat kecuali user meminta analisis panjang."
        )
    elif _DEEP.search(text) or len(text) > 220:
        name = "DEEP"
        max_tokens = 2200
        temp = 0.70
        instruction = (
            "Berikan jawaban lengkap dan bernalar tetapi tetap terdengar seperti percakapan dengan Furina. "
            "Jangan memakai filler, jangan mengulang premis pengguna, dan jangan membuat daftar bila paragraf lebih natural."
        )
    else:
        name = "CASUAL"
        max_tokens = 360
        temp = 0.80
        instruction = (
            "Percakapan biasa: umumnya 1-5 kalimat. Jawab inti dulu. Jangan mengubah pertanyaan sederhana menjadi esai. "
            "Jangan menawarkan bantuan atau bertanya balik secara otomatis. Boleh bereaksi, berpendapat, menggoda, diam singkat, "
            "atau menyatakan ketidaksetujuan bila itu lebih natural."
        )

    len_bucket = "short" if len(text) < 30 else "medium" if len(text) < 140 else "long"
    context_key = f"{len_bucket}:{'identity' if _IDENTITY.search(text) else 'emotional' if _EMOTION.search(text) else 'technical' if _TECH.search(text) else 'general'}"

    samples, win_rate = store.route_stats(name, context_key)
    if samples >= 8 and win_rate < 0.30 and name in {"REFLEX", "CASUAL"}:
        instruction += " Gaya sebelumnya sering tidak cocok; ubah ritme/diksi, tetapi tetap ringkas dan jangan kembali ke pola customer-service."

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
    if relation_words:
        instruction += " Keadaan relasi saat ini: " + "; ".join(relation_words) + "."

    return ResponseProfile(name, max_tokens, temp, instruction, context_key)
