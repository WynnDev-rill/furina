from __future__ import annotations

import hashlib
import re


def install_personality_v126(ns: dict) -> None:
    normalize_traits = ns["normalize_traits"]
    trait_by_id = ns["TRAIT_BY_ID"]
    cards = ns["TRAIT_ACTION_CARDS_V2_120"]
    synthesize = ns["synthesize_trait_profile_120"]
    emotional_state = ns["emotional_state_v2_120"]

    def _situation(user_text: str) -> str:
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

    def _custom_rows(raw) -> list[dict]:
        return [x for x in (raw if isinstance(raw, list) else ()) if isinstance(x, dict) and x.get("active", True)]

    def _relevant_custom(rows: list[dict], user_text: str, limit: int = 6) -> list[dict]:
        terms = set(re.findall(r"[a-z0-9À-ÿ]{3,}", str(user_text or "").casefold()))
        ranked = []
        for index, row in enumerate(rows):
            body = f"{row.get('label', '')} {row.get('description', '')}".casefold()
            overlap = len(terms & set(re.findall(r"[a-z0-9À-ÿ]{3,}", body)))
            stable = int.from_bytes(hashlib.blake2s(f"{body}:{user_text}".encode(), digest_size=2).digest(), "little") / 6553500
            ranked.append((overlap + stable, -index, row))
        return [row for _, _, row in sorted(ranked, reverse=True)[:limit]]

    def compile_contextual_personality(values, user_text: str, context: dict | None = None) -> str:
        context = context if isinstance(context, dict) else {}
        selected = normalize_traits(values)
        profile = synthesize(selected)
        emotion = emotional_state(user_text, context)
        situation = _situation(user_text)
        partner = bool(context.get("partner_mode"))
        roleplay = bool(context.get("roleplay_mode"))
        custom_all = _custom_rows(context.get("custom_traits"))
        custom_active = _relevant_custom(custom_all, user_text)

        lines: list[str] = []
        # Keep every selected trait latent, but bound the turn-level action
        # prompt. Context decides which facets become visible now.
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
        visible_builtin = ranked[:8]
        for trait_id in visible_builtin:
            card = cards[trait_id]
            action = card.get(situation) or card.get("core")
            lines.append(f"- {trait_by_id[trait_id].label}: {action}")
        for row in custom_active:
            lines.append(f"- {str(row.get('label'))[:48]}: {str(row.get('description'))[:240]}")

        labels = [trait_by_id[x].label for x in selected] + [str(x.get("label"))[:48] for x in custom_active]
        latent = ", ".join(labels) if labels else "tanpa sifat tambahan"
        hidden_custom = max(0, len(custom_all) - len(custom_active))
        if hidden_custom:
            latent += f"; {hidden_custom} sifat kustom lain tetap tersimpan dan muncul saat lebih relevan"
        axes = ", ".join(profile.get("axes") or [])
        relationship = (
            "Mode pasangan aktif: kedekatan romantis boleh tampak lewat tindakan yang timbal balik dan sesuai konteks."
            if partner else
            "Mode pasangan nonaktif: jangan mengklaim atau menyiratkan hubungan romantis."
        )
        rp = (
            "RolePlay aktif: narasi aksi atau adegan hanya boleh muncul ketika user memulai atau meminta roleplay; percakapan biasa tetap percakapan biasa."
            if roleplay else
            "RolePlay nonaktif: jangan menulis *aksi*, narasi adegan, lokasi rekaan, dialog atas nama user, atau berpura-pura kejadian sedang berlangsung."
        )
        expression = "\n".join(lines) if lines else "- Hadir natural, punya pendapat, dan merespons detail konkret user."
        return (
            f"PERSONALITY STATE V3 — semua sifat berikut hidup bersamaan sebagai satu watak stabil: {latent}.\n"
            "Konteks hanya mengubah kuat-lemahnya ekspresi; jangan berganti archetype, menyebut nama sifat, atau meratakan ciri khasnya.\n"
            f"Situasi={situation}; emosi={emotion.get('state', 'calm')}. {relationship}\n{rp}\n"
            f"Ekspresi yang relevan sekarang:\n{expression}"
            + (f"\nArah gabungan: {axes}." if axes else "")
            + "\nTunjukkan setidaknya satu perilaku khas secara halus bila aman, tanpa catchphrase atau akting berlebihan."
        )

    ns["compile_contextual_personality"] = compile_contextual_personality
