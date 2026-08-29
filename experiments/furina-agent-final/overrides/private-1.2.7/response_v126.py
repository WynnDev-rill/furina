from __future__ import annotations

import re


def support_strategy(user_text: str) -> str:
    text = " ".join(str(user_text or "").strip().split())
    low = text.casefold()
    emotional = bool(re.search(r"\b(sedih|takut|cemas|kesepian|kecewa|capek|lelah|marah|gagal|hancur|masalah)\b", low))
    asks_advice = bool(re.search(r"\b(harus bagaimana|sebaiknya|apa yang harus|minta saran|solusinya|bantu aku)\b", low))
    enough = len(text.split()) >= 34 or bool(re.search(r"\b(karena|setelah|sejak|jadi|akibatnya)\b", low))
    no_question = bool(re.search(r"\b(jangan tanya|tanpa pertanyaan|cuma dengarkan|cukup dengar)\b", low))
    if not emotional:
        return "none"
    if asks_advice:
        return "action"
    if not enough and not no_question:
        return "explore"
    return "comfort"


def install_response_v126(ns: dict) -> None:
    previous = ns["choose_profile"]

    def choose_profile(user_text, store):
        profile = previous(user_text, store)
        strategy = support_strategy(user_text)
        words = len(str(user_text or "").split())
        if strategy == "explore":
            profile.name = "CLOSE"
            profile.max_tokens = min(int(profile.max_tokens), 300)
            profile.instruction += " Tahap dukungan=eksplorasi: tanggapi satu detail konkret lalu ajukan tepat satu pertanyaan yang membantu memahami kejadian atau kebutuhan user. Jangan langsung menyimpulkan, mengasihani, menasihati, atau memberi solusi."
        elif strategy == "comfort":
            profile.name = "CLOSE"
            profile.max_tokens = min(int(profile.max_tokens), 420)
            profile.instruction += " Tahap dukungan=menemani: refleksikan detail konkret tanpa simpulan besar; jangan memberi solusi kecuali diminta."
        elif strategy == "action":
            profile.max_tokens = max(int(profile.max_tokens), 420)
            profile.instruction += " Tahap dukungan=aksi: jawab kebutuhan yang diminta dengan langkah yang realistis setelah mengakui konteks singkat."
        elif words <= 4:
            profile.max_tokens = min(int(profile.max_tokens), 110)
            profile.instruction += " Ini percakapan ringan: biasanya cukup satu atau dua kalimat lengkap."
        elif profile.name == "CASUAL":
            profile.max_tokens = min(int(profile.max_tokens), 220)
            profile.instruction += " Utamakan jawaban singkat yang selesai—biasanya dua sampai empat kalimat; tambah panjang hanya bila informasi user memang memerlukannya."
        profile.context_key += ":support-" + strategy
        return profile

    ns["support_strategy"] = support_strategy
    ns["choose_profile"] = choose_profile
