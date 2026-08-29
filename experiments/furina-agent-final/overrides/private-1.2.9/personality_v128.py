from __future__ import annotations

import re


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def install_personality_v128(ns: dict) -> None:
    previous_compile = ns["compile_contextual_personality"]
    normalize_traits = ns["normalize_traits"]

    def social_state(values, user_text: str, context: dict) -> dict:
        selected = set(normalize_traits(values))
        store = context.get("store")
        old = {}
        if store is not None:
            try:
                old = store.get_state("social_state_v128", {}) or {}
            except Exception:
                old = {}
        text = " ".join(str(user_text or "").casefold().split())
        close = bool(re.search(r"\b(?:sayang|cinta|suka kamu|cantik|manis|kangen|rindu|gemas|puji)\b", text))
        playful = bool(re.search(r"\b(?:wkwk|haha|hehe|goda|ledek|bercanda|lucu)\b", text))
        conflict = bool(re.search(r"\b(?:salah|jangan begitu|berhenti|stop|kesal|kecewa sama kamu|nggak suka)\b", text))
        vulnerable = bool(re.search(r"\b(?:sedih|takut|cemas|capek|lelah|kesepian|malu|gagal)\b", text))
        shy_capable = bool(selected & {"dandere", "hajidere", "bodere", "tsundere"})
        pride_capable = bool(selected & {"tsundere", "himedere", "kamidere", "bodere"})
        playful_capable = bool(selected & {"hiyakasudere", "sadodere", "genki", "bakadere", "nyandere"})

        def move(key: str, target: float, rate: float = .34) -> float:
            before = float(old.get(key, .20) or .20)
            return _clamp(before * (1.0 - rate) + target * rate)

        state = {
            "shyness": move("shyness", .88 if close and shy_capable else .42 if shy_capable else .04),
            "warmth": move("warmth", .86 if vulnerable or close else .48),
            "playfulness": move("playfulness", .82 if playful and playful_capable else .28),
            "pride": move("pride", .68 if pride_capable and not conflict else .20),
            "irritation": move("irritation", .62 if conflict else .10),
            "curiosity": move("curiosity", .72 if "?" not in text and (vulnerable or len(text.split()) > 10) else .38),
        }
        if store is not None:
            try:
                store.set_state("social_state_v128", {key: round(value, 3) for key, value in state.items()})
            except Exception:
                pass
        return state

    def compile_contextual_personality(values, user_text: str, context: dict | None = None) -> str:
        context = context if isinstance(context, dict) else {}
        base = previous_compile(values, user_text, context)
        selected = normalize_traits(values)
        state = social_state(selected, user_text, context)
        active: list[str] = []
        if state["shyness"] >= .40:
            active.append("Jika kedekatan membuatmu malu/gugup, tunjukkan lewat jeda, bantahan kecil, atau koreksi diri singkat dalam ucapan—tetap tuntaskan maksudmu.")
        if state["warmth"] >= .55:
            active.append("Kehangatan tampak dari perhatian pada detail, bukan validasi atau pujian generik.")
        if state["playfulness"] >= .50:
            active.append("Satu godaan/candaan yang merujuk detail pesan boleh muncul; jangan mengulang gimmick.")
        if state["pride"] >= .48:
            active.append("Gengsi boleh memberi subteks, tetapi tidak boleh menghalangi jawaban atau pengakuan yang jujur.")
        if state["irritation"] >= .42:
            active.append("Kesal boleh terasa singkat dan spesifik; jangan berubah menjadi kasar atau defensif berkepanjangan.")
        if state["curiosity"] >= .56:
            active.append("Rasa ingin tahu boleh menjadi satu pertanyaan bermakna hanya bila percakapan memang belum cukup jelas.")
        if not selected:
            active = ["Tidak ada sifat bawaan aktif; gunakan reaksi manusia yang netral dan kontekstual."]
        expression = "\n".join(f"- {line}" for line in active[:4])
        direct_only = (
            "Ekspresikan seluruh state melalui ucapan langsung; RolePlay nonaktif, jadi jangan menarasikan gestur, tubuh, atau adegan."
            if not context.get("roleplay_mode") else
            "RolePlay aktif tidak berarti setiap chat menjadi adegan; narasi hanya ketika user memulainya."
        )
        return base + "\nSOCIAL STATE ADAPTIF:\n" + expression + "\n" + direct_only

    ns["compile_contextual_personality"] = compile_contextual_personality
