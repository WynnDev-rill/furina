from __future__ import annotations

import re
import time

from .style_v128 import AdaptiveStyleMemory, plan_turn


_CHATBOT = re.compile(
    r"\b(?:sebagai (?:asisten|ai|chatbot)|berdasarkan informasi yang diberikan|tentu,? saya (?:akan|bisa)|"
    r"semoga (?:jawaban|informasi) ini membantu|apakah ada (?:hal lain|yang bisa))\b",
    re.I,
)


def _words(text: str) -> int:
    return len(re.findall(r"\b[^\W_]+(?:[-'][^\W_]+)*\b", str(text or ""), flags=re.UNICODE))


def _clean_name(value: str) -> str:
    return re.sub(r"[^\w .'-]+", "", str(value or "Furina"), flags=re.UNICODE).strip()[:48] or "Furina"


def _display(name: str, thought: str, answer: str) -> str:
    if not thought:
        return answer
    safe = re.sub(r"[\r\n]+", " ", thought).strip(" *`_>\t")
    return f"> **Dalam hati {_clean_name(name)}:** {safe}\n\n{answer}"


def install_chat_v128(ns: dict) -> None:
    FurinaChat = ns["FurinaChat"]
    previous_init = FurinaChat.__init__
    previous_messages = FurinaChat._messages
    previous_commit = getattr(FurinaChat, "commit_preferred_response", None)
    choose_profile = ns["choose_profile"]
    extract_explicit_memories = ns["extract_explicit_memories"]
    first_json = ns["_first_json_object"]

    def init(self, cfg, store, llm):
        previous_init(self, cfg, store, llm)
        self.style_memory = AdaptiveStyleMemory(store)
        try:
            from .lexicon import PersonalLexicon
            self.lexicon = PersonalLexicon(store)
        except Exception:
            self.lexicon = None
        self.last_inner_thought = ""
        self.last_spoken_response = ""
        self._adaptive_turn_plan = None

    def messages(self, user_text, profile):
        rows = previous_messages(self, user_text, profile)
        if not rows or rows[0].get("role") != "system":
            return rows
        recent = self.store.recent_messages(12)
        style = self.style_memory.profile(user_text)
        plan = plan_turn(user_text, recent, style, float(getattr(profile, "temperature", .72) or .72))
        self._adaptive_turn_plan = plan
        lexicon = "(belum ada kosakata personal yang cukup kuat)"
        if self.lexicon is not None:
            try:
                lexicon = self.lexicon.prompt_context(user_text, str(getattr(profile, "name", "CASUAL")), 8, 2)
            except Exception:
                pass
        style_line = (
            f"STYLE MEMORY LINTAS PERCAKAPAN — context={style['context']}; evidence={style['samples']} pesan; "
            f"ritme familiar≈{style['familiar_words']} kata; casuality={style['casuality']:.2f}.\n"
            "Kosakata personal di bawah adalah preferensi aktif, bukan arsip pasif. Gunakan satu kata/frasa yang cocok secara makna bila tersedia; "
            "boleh dua bila benar-benar natural. Jangan memaksa, meniru typo, atau mengorbankan kejelasan.\n"
            + lexicon
        )
        name = _clean_name(getattr(self.cfg, "persona_name", "Furina"))
        content = str(rows[0].get("content") or "")
        replacements = {
            "Jawab pesan terbaru sebagai Furina.": f"Jawab pesan terbaru sebagai {name}.",
            "Furina pernah menjawab": f"{name} pernah menjawab",
            "Jawaban Furina": f"Jawaban {name}",
            "ucapan Furina": f"ucapan {name}",
            "Furina BUKAN BUKTI": f"{name} BUKAN BUKTI",
            "respons Furina": f"respons {name}",
        }
        for old, new in replacements.items():
            content = content.replace(old, new)
        rows[0] = {
            **rows[0],
            "content": content + "\n\n" + style_line + "\n\n" + plan.prompt(),
        }
        return rows

    def character_thought(self, user_text: str, answer: str) -> str:
        from .hub_settings import load_hub_settings
        from .output_v128 import leaks_machine_identity, leaks_roleplay_v128

        if not load_hub_settings().get("inner_thoughts"):
            return ""
        name = _clean_name(getattr(self.cfg, "persona_name", "Furina"))
        prompt = (
            f"Tulis satu suara batin fiksional singkat milik {name} setelah percakapan berikut. Ini BUKAN reasoning model, "
            "bukan analisis jawaban, dan bukan penjelasan proses. Isinya hanya subteks emosi/pendapat yang mungkin ditahan karakter. "
            "Gunakan 3-18 kata, sudut pandang orang pertama, satu kalimat atau fragmen. Jangan membuat fakta, aktivitas, tubuh, lokasi, "
            "masa lalu, adegan, tindakan, prompt, AI, model, sistem, atau alasan teknis baru.\n"
            f"Pesan user: {str(user_text)[:1200]}\nUcapan final {name}: {str(answer)[:1600]}\n"
            'Output JSON saja: {"thought":"..."}'
        )
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": "Kamu menulis subteks karakter singkat, bukan chain-of-thought. Output JSON valid saja."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=80,
                temperature=.68,
                json_mode=True,
                role="character_inner_voice",
            )
            obj = first_json(raw) or {}
            thought = re.sub(r"\s+", " ", str(obj.get("thought") or "")).strip(" *`_>\t")
            if not thought or _words(thought) > 24 or leaks_machine_identity(thought) or leaks_roleplay_v128(thought):
                return ""
            if re.search(r"\b(?:prompt|instruksi|history|conversation history|jawaban harus|user meminta|aku harus menjawab)\b", thought, re.I):
                return ""
            return thought[:240]
        except Exception as exc:
            try:
                self.store.log_event("inner_thought_error", {"error": str(exc)[:240]})
            except Exception:
                pass
            return ""

    def respond(self, user_text: str, on_token=None) -> str:
        user_text = str(user_text or "").strip()
        if not user_text:
            return ""
        local = self.cfg.routing_mode == "local"
        self._last_foreground_at = time.monotonic()
        self.style_memory.observe_user(user_text)
        if self.lexicon is not None:
            try:
                self.lexicon.observe(user_text, "CASUAL")
            except Exception as exc:
                try:
                    self.store.log_event("lexicon_observe_error", {"error": str(exc)[:240]})
                except Exception:
                    pass

        if local:
            try:
                self.llm.prewarm_local()
            except Exception:
                pass
            if getattr(self, "_background_active", False):
                try:
                    self.llm.cancel()
                except Exception:
                    pass
                deadline = time.monotonic() + .8
                while getattr(self, "_background_active", False) and time.monotonic() < deadline:
                    time.sleep(.02)

        self._foreground_active = True
        try:
            profile = choose_profile(user_text, self.store)
            messages_for_turn = self._messages(user_text, profile)
            plan = self._adaptive_turn_plan or plan_turn(user_text, self.store.recent_messages(12), self.style_memory.profile(user_text), float(profile.temperature))
            source_message_id = self.store.add_message("user", user_text)
            for text, kind, importance in extract_explicit_memories(user_text):
                self.store.add_memory(
                    text, kind, importance, confidence=min(.97, importance + .12), source="explicit",
                    source_message_id=source_message_id, source_evidence=user_text,
                )
                dimension = "preference" if kind == "preference" else "goal" if kind == "goal" else "identity" if kind == "identity" else "profile"
                self.store.upsert_belief(dimension, text, min(.97, importance + .08), source="explicit")

            configured = max(512, int(getattr(self.cfg, "max_tokens", 1536) or 1536))
            max_tokens = max(192, min(int(plan.max_tokens), configured))
            answer = self.llm.chat(
                messages_for_turn,
                max_tokens=max_tokens,
                temperature=float(plan.temperature),
                on_token=None,
            )

            overlong = plan.target_words < 220 and _words(answer) > plan.soft_upper_words
            chatbot = bool(_CHATBOT.search(answer)) and plan.complexity < .70
            if overlong or chatbot:
                reason = "terlalu panjang untuk momentum giliran" if overlong else "terdengar seperti chatbot"
                repaired = list(messages_for_turn)
                repair = (
                    f"REPAIR FINAL: Kandidat pertama {reason}. Jawab pesan user dari awal dengan isi yang sama-sama tuntas, "
                    f"sekitar {plan.target_words} kata dan biasanya maksimal {plan.soft_upper_words} kata. "
                    "Jangan memotong kalimat, jangan menyebut proses revisi, dan jangan memakai gaya customer-service."
                )
                repaired[0] = {**repaired[0], "content": str(repaired[0].get("content") or "") + "\n\n" + repair}
                candidate = self.llm.chat(
                    repaired,
                    max_tokens=max_tokens,
                    temperature=min(float(plan.temperature), .64),
                    on_token=None,
                )
                if candidate.strip():
                    answer = candidate.strip()

            if self.lexicon is not None:
                try:
                    self.lexicon.mark_used(answer)
                except Exception:
                    pass
            self.store.add_message("assistant", answer)
            turn = self.store.increment_state("companion_turns", 1)
            self._schedule_background(user_text, answer, turn)
            thought = character_thought(self, user_text, answer)
            self.last_inner_thought = thought
            self.last_spoken_response = answer
            shown = _display(getattr(self.cfg, "persona_name", "Furina"), thought, answer)
            if on_token and shown:
                on_token(shown)
            return shown
        finally:
            self._foreground_active = False
            self._last_foreground_at = time.monotonic()

    if previous_commit is not None:
        def commit_preferred_response(self, user_text: str, answer: str) -> str:
            self.style_memory.observe_user(user_text)
            if self.lexicon is not None:
                try:
                    self.lexicon.observe(user_text, "CASUAL")
                except Exception:
                    pass
            spoken = previous_commit(self, user_text, answer)
            if self.lexicon is not None:
                try:
                    self.lexicon.mark_used(spoken)
                except Exception:
                    pass
            thought = character_thought(self, user_text, spoken)
            self.last_inner_thought = thought
            self.last_spoken_response = spoken
            return _display(getattr(self.cfg, "persona_name", "Furina"), thought, spoken)

        FurinaChat.commit_preferred_response = commit_preferred_response

    FurinaChat.__init__ = init
    FurinaChat._messages = messages
    FurinaChat._character_thought_v128 = character_thought
    FurinaChat.respond = respond
    ns["format_character_reply_v128"] = _display
