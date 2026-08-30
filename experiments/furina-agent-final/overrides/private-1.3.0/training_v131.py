from __future__ import annotations

import hashlib
import re

from .chat_v129 import _CHATBOT, _words
from .chat_v130 import likely_ungrounded_scene
from .style_v128 import plan_turn
from .training_corpus import prompt_fingerprint, sanitize_external_utterance


def install_training_v131(ns: dict) -> None:
    LiveTrainingPair = ns["LiveTrainingPair"]
    load_state = ns["load_training_state"]
    CATEGORIES = ns["CATEGORIES"]
    sanitize = sanitize_external_utterance

    def adaptive_dimension(category_id: str, state: dict) -> str:
        dimensions = CATEGORIES[category_id]["dimensions"]
        category_counts = (state.get("counts") or {}).get(category_id, {})
        ranked = []
        for name, poles in dimensions.items():
            counts = category_counts.get(name, {})
            left, right = int(counts.get(poles[0], 0)), int(counts.get(poles[1], 0))
            total = left + right
            conflict = abs(left - right) / max(1, total)
            ranked.append((total, conflict, name))
        return min(ranked, key=lambda row: (row[0], row[1], row[2]))[2]

    def live_category(text: str) -> str:
        value = " ".join(str(text or "").casefold().split())
        if re.search(r"\b(tapi|namun|padahal|meski)\b", value) and re.search(r"\b(senang|sedih|takut|bangga|marah|capek|lelah|lega|kecewa)\b", value):
            return "mixed_emotion"
        if re.search(r"\b(terserah|iya deh|hebat sekali|bagus banget|serius|maksudnya|beneran)\b", value):
            return "ambiguous_tone"
        if re.search(r"\b(gimana|bagaimana|harus|mending|sebaiknya|bantu|mulai|pilih)\b", value):
            return "initiative"
        if re.search(r"\b(sedih|kecewa|kesal|marah|takut|cemas|capek|lelah|senang|bangga|malu|bingung|stres)\b", value):
            return "emotional"
        if re.search(r"wkwk|haha|hehe|bercanda|lucu|ngakak", value):
            return "playful"
        return "natural"

    def _candidate(chat, messages: list[dict], direction: str, plan, roleplay_mode: bool, user_text: str) -> str:
        rows = [dict(row) for row in messages]
        rows[0]["content"] = str(rows[0].get("content") or "") + "\n\n" + (
            "KANDIDAT PREFERENSI: tulis satu respons final saja. Semua persona, hubungan, memori, kosakata, "
            "panjang adaptif, dan konteks percakapan normal tetap berlaku. Perbedaan utama kandidat ini: "
            f"{direction}. Jangan menyebut pelatihan, kandidat, instruksi, atau proses berpikir."
        )
        configured = max(384, int(getattr(chat.cfg, "max_tokens", 1536) or 1536))
        max_tokens = max(160, min(int(plan.max_tokens), configured))
        answer = ""
        for attempt in range(2):
            answer = sanitize(chat.llm.chat(
                rows,
                max_tokens=max_tokens,
                temperature=min(.76, float(plan.temperature) + .03),
                role="live_training_candidate",
            )) or ""
            invalid = (
                not answer
                or (plan.target_words < 220 and _words(answer) > plan.soft_upper_words)
                or (bool(_CHATBOT.search(answer)) and plan.complexity < .70)
                or likely_ungrounded_scene(answer, user_text, roleplay_mode=roleplay_mode)
            )
            if not invalid:
                return answer
            rows[0]["content"] += (
                "\nQUALITY REPAIR: respons sebelumnya tidak lolos kontrak chat normal. Tulis ulang secara tuntas, "
                f"natural, grounded, sekitar {plan.target_words} kata dan biasanya maksimal {plan.soft_upper_words} kata."
            )
        return ""

    def generate_live(chat, user_text: str) -> LiveTrainingPair:
        from .hub_settings import load_hub_settings
        from .response import choose_profile

        state = load_state()
        category_id = live_category(user_text)
        dimension = adaptive_dimension(category_id, state)
        poles = CATEGORIES[category_id]["dimensions"][dimension]
        flip = hashlib.blake2s(user_text.encode(), digest_size=1).digest()[0] & 1
        pole_a, pole_b = (poles[1], poles[0]) if flip else poles
        profile = choose_profile(user_text, chat.store)
        messages = chat._messages(user_text, profile)
        if not messages or messages[0].get("role") != "system":
            raise RuntimeError("Konteks chat tidak tersedia.")
        # Keep the complete real-chat history. The old generator silently reduced
        # it to system+last user, which made A/B worse than the response after Skip.
        plan = getattr(chat, "_adaptive_turn_plan", None) or plan_turn(
            user_text, chat.store.recent_messages(12), chat.style_memory.profile(user_text), float(profile.temperature)
        )
        roleplay_mode = bool(load_hub_settings().get("roleplay_mode"))
        a = _candidate(chat, messages, pole_a, plan, roleplay_mode, user_text)
        b = _candidate(chat, messages, pole_b, plan, roleplay_mode, user_text)
        if not a or not b or a.casefold() == b.casefold():
            raise ValueError("Model tidak menghasilkan dua pilihan yang setara dengan chat normal.")
        return LiveTrainingPair(category_id, dimension, pole_a, pole_b, a, b, prompt_fingerprint(user_text))

    ns["generate_live_training_pair"] = generate_live
