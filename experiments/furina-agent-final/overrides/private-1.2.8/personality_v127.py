from __future__ import annotations

import re


def install_personality_v127(ns: dict) -> None:
    normalize_traits = ns["normalize_traits"]
    trait_by_id = ns["TRAIT_BY_ID"]
    cards = ns["TRAIT_ACTION_CARDS_V2_120"]
    synthesize = ns["synthesize_trait_profile_120"]
    emotional_state = ns["emotional_state_v2_120"]

    def situation_for(user_text: str) -> str:
        low = " ".join(str(user_text or "").casefold().split())
        if re.search(r"\b(jangan|stop|berhenti|kamu salah|tidak nyaman|nggak nyaman)\b", low):
            return "conflict"
        if re.search(r"\b(sedih|takut|cemas|kesepian|kecewa|capek|lelah|gagal|masalah)\b", low):
            return "close"
        if re.search(r"\b(sayang|cinta|rindu|kangen|peluk|cium|kencan)\b", low):
            return "romance"
        if re.search(r"\b(wkwk|haha|hehe|goda|ledek|bercanda|lucu)\b", low):
            return "play"
        return "casual"

    def compile_contextual_personality(values, user_text: str, context: dict | None = None) -> str:
        context = context if isinstance(context, dict) else {}
        selected = normalize_traits(values)
        profile = synthesize(selected)
        emotion = emotional_state(user_text, context)
        situation = situation_for(user_text)
        wanted = {
            "conflict": {"composure": 1.0, "maturity": .8, "teasing": -.8, "defensive": -.7},
            "close": {"warmth": 1.0, "caretaking": .9, "maturity": .6, "teasing": -.7},
            "romance": {"warmth": 1.0, "openness": .7, "intensity": .4},
            "play": {"teasing": 1.0, "energy": .7, "warmth": .4},
            "casual": {"warmth": .5, "composure": .3, "energy": .2},
        }[situation]
        ranked = sorted(
            selected,
            key=lambda trait_id: sum(float(trait_by_id[trait_id].vector.get(dim, 0)) * weight for dim, weight in wanted.items()),
            reverse=True,
        )
        lines = []
        for trait_id in ranked[:8]:
            card = cards[trait_id]
            lines.append(f"- {trait_by_id[trait_id].label}: {card.get(situation) or card.get('core')}")

        labels = ", ".join(trait_by_id[x].label for x in selected) if selected else "tanpa sifat tambahan"
        relationship = (
            "Mode pasangan aktif: kedekatan romantis boleh tampak lewat tindakan yang timbal balik dan sesuai konteks."
            if context.get("partner_mode") else
            "Mode pasangan nonaktif: jangan mengklaim atau menyiratkan hubungan romantis."
        )
        roleplay = (
            "RolePlay aktif: narasi aksi atau adegan hanya boleh muncul ketika user memulai atau meminta roleplay; chat biasa tetap chat biasa."
            if context.get("roleplay_mode") else
            "RolePlay nonaktif: hanya percakapan langsung; tanpa *aksi*, narasi adegan, lokasi rekaan, dialog atas nama user, atau kejadian rekaan."
        )
        expression = "\n".join(lines) if lines else "- Hadir natural, punya pendapat, dan merespons detail konkret user."
        axes = ", ".join(profile.get("axes") or [])
        return (
            f"PERSONALITY STATE V4 — 20 sifat bawaan yang dipilih hidup bersamaan sebagai satu watak stabil: {labels}.\n"
            "Konteks hanya mengubah kuat-lemahnya ekspresi; jangan berganti archetype, menyebut nama sifat, atau meratakan ciri khasnya.\n"
            f"Situasi={situation}; emosi={emotion.get('state', 'calm')}. {relationship}\n{roleplay}\n"
            f"Ekspresi yang relevan sekarang:\n{expression}"
            + (f"\nArah gabungan: {axes}." if axes else "")
            + "\nTunjukkan perilaku khas secara halus bila aman, tanpa catchphrase atau akting berlebihan."
        )

    ns["compile_contextual_personality"] = compile_contextual_personality
