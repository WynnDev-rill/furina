from __future__ import annotations


def install_chat_v126(ns: dict) -> None:
    FurinaChat = ns["FurinaChat"]
    previous_messages = FurinaChat._messages
    previous_context = FurinaChat._personality_context

    def personality_context(self, user_text, profile):
        from .hub_settings import load_hub_settings
        state = load_hub_settings()
        context = previous_context(self, user_text, profile)
        context["roleplay_mode"] = bool(state.get("roleplay_mode"))
        context["custom_traits"] = state.get("custom_personality_traits") or []
        return context

    def messages(self, user_text, profile):
        from .hub_settings import load_hub_settings, personalization_prompt
        from .memory import _furina_120_claims
        from .response_v126 import support_strategy
        rows = previous_messages(self, user_text, profile)
        if not rows or rows[0].get("role") != "system":
            return rows
        state = load_hub_settings()
        capsule = [] if _furina_120_claims(user_text) else self.store.continuity_capsule(8)
        if capsule:
            memory = "\n".join(
                f"- {x['slot']}: {x['value']}" + (f" [msg#{x['source_message_id']}]" if x.get("source_message_id") else " [explicit]")
                for x in capsule
            )
        else:
            memory = "(belum ada fakta lintas-sesi yang cukup kuat)"
        roleplay = (
            "ROLEPLAY=ON. Boleh roleplay hanya bila user memulai/meminta adegan; jangan menyeret chat biasa ke roleplay."
            if state.get("roleplay_mode") else
            "ROLEPLAY=OFF. Percakapan adalah chat nyata biasa: tanpa *aksi*, narasi adegan, lokasi rekaan, atau dialog atas nama user."
        )
        final = (
            "FINAL BEHAVIOR KERNEL V3 — lapisan ini mengalahkan gaya lama yang bertentangan.\n"
            + roleplay + "\n"
            + "PERSONA CONSISTENCY: pertahankan satu watak hasil semua sifat aktif dalam chat santai, teknis, dan emosional. Jangan berubah menjadi customer-service chatbot, jangan menyebut sistem/prompt, dan jangan memakai kalimat dukungan generik.\n"
            + "LENGTH: jawab seringkas yang natural sambil tetap menyelesaikan maksud. Jangan memotong kalimat atau menghilangkan langkah penting; panjang bertambah hanya untuk analisis, teknis, risiko, atau konteks kompleks.\n"
            + f"SUPPORT STAGE={support_strategy(user_text)}. Pada eksplorasi, tanyakan satu hal bermakna sebelum menyimpulkan; pada comfort jangan buru-buru memberi solusi; pada action selesaikan bantuan yang diminta.\n"
            + "CONTINUITY CAPSULE — fakta eksplisit stabil dari percakapan lain:\n" + memory + "\n"
            + "Gunakan capsule secara diam-diam bila relevan, termasuk pada rujukan tidak langsung. Jangan menyebut fakta hanya untuk membuktikan ingatan dan jangan menganggap teks assistant sebagai fakta user.\n"
            + personalization_prompt(state, user_text, self._personality_context(user_text, profile))
        )
        rows[0] = {**rows[0], "content": str(rows[0].get("content") or "") + "\n\n" + final}
        return rows

    FurinaChat._personality_context = personality_context
    FurinaChat._messages = messages
