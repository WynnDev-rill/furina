from __future__ import annotations

import re
import time

from .character_state_v129 import CharacterSelfState
from .style_v128 import plan_turn


_CHATBOT = re.compile(
    r"\b(?:sebagai (?:asisten|ai|chatbot)|berdasarkan informasi yang diberikan|tentu,? saya (?:akan|bisa)|"
    r"semoga (?:jawaban|informasi) ini membantu|apakah ada (?:hal lain|yang bisa))\b",
    re.I,
)
_TRIVIAL = re.compile(r"^(?:hai+|halo+|pagi|siang|sore|malam|iya+|ya+|oke+|ok|hm+|oh+|sip|makasih|terima kasih)[.!?~ ]*$", re.I)
_FORBIDDEN_ASIDE = re.compile(
    r"\b(?:ai|chatbot|model|prompt|instruksi|sistem|reasoning|history|user|aku harus menjawab|"
    r"aku akan|nanti aku|rencana(?:ku)?|kita akan|kita pergi|menyentuh|memeluk|mencium|menggenggam|"
    r"berjalan|duduk|berdiri|menatap|tersenyum|tertawa|menangis|kamar|rumah|sekolah|kantor|"
    r"kamu harus|kau harus|sayang)\b",
    re.I,
)


def _words(text: str) -> int:
    return len(re.findall(r"\b[^\W_]+(?:[-'][^\W_]+)*\b", str(text or ""), flags=re.UNICODE))


def _sentences(answer: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", str(answer or "")).strip()
    if not text:
        return []
    parts = [part.strip() for part in re.split(r"(?<=[.!?…])\s+|\n{2,}", text) if part.strip()]
    return parts


def format_private_reply(answer: str, aside: str, insert_after: int) -> str:
    parts = _sentences(answer)
    aside = re.sub(r"[\r\n]+", " ", str(aside or "")).strip(" *`_>\t")
    if len(parts) < 2 or not aside:
        return str(answer or "").strip()
    position = max(1, min(int(insert_after), len(parts) - 1))
    before = " ".join(parts[:position]).strip()
    after = " ".join(parts[position:]).strip()
    return f"{before}\n\n> {aside}\n\n{after}"


def _valid_aside(text: str, *, partner_mode: bool) -> bool:
    text = re.sub(r"\s+", " ", str(text or "")).strip(" *`_>\t")
    count = _words(text)
    if count < 3 or count > 14 or len(text) > 140 or "?" in text:
        return False
    if _FORBIDDEN_ASIDE.search(text) or re.search(r"[*\[\]{}<>]", text):
        return False
    if not partner_mode and re.search(r"\b(?:cinta|pacar|pasangan|milikku|mencintai)\b", text, re.I):
        return False
    return True


def install_chat_v129(ns: dict) -> None:
    FurinaChat = ns["FurinaChat"]
    previous_init = FurinaChat.__init__
    previous_messages = FurinaChat._messages
    choose_profile = ns["choose_profile"]
    extract_explicit_memories = ns["extract_explicit_memories"]
    first_json = ns["_first_json_object"]

    def init(self, cfg, store, llm):
        previous_init(self, cfg, store, llm)
        self.character_self_state = CharacterSelfState(store)
        self.last_private_aside = ""

    def messages(self, user_text, profile):
        rows = previous_messages(self, user_text, profile)
        if rows and rows[0].get("role") == "system":
            rows[0] = {
                **rows[0],
                "content": str(rows[0].get("content") or "")
                + "\n\nCHARACTER SELF-STATE SEMENTARA:\n"
                + self.character_self_state.prompt_context()
                + "\nKeadaan ini hanya mengatur ekspresi. Jangan ubah menjadi fakta tentang user, hubungan, lokasi, tubuh, atau aktivitas.",
            }
        return rows

    def compose_private_aside(self, user_text: str, answer: str, *, source_message_id: int | None, turn: int) -> tuple[str, int]:
        from .hub_settings import load_hub_settings
        from .output_v128 import leaks_machine_identity, leaks_roleplay_v128

        settings = load_hub_settings()
        if not settings.get("inner_thoughts"):
            return "", 0
        parts = _sentences(answer)
        if len(parts) < 2 or _TRIVIAL.fullmatch(str(user_text or "").strip()):
            return "", 0
        partner_mode = bool(settings.get("partner_mode"))
        roleplay_mode = bool(settings.get("roleplay_mode"))
        indexed = "\n".join(f"{i + 1}. {part}" for i, part in enumerate(parts))
        prompt = f"""
Buat keputusan komposisi untuk satu balasan karakter manusia fiktif. Ini BUKAN chain-of-thought, reasoning model, analisis, atau proses teknis.

Pesan user:
{str(user_text)[:1200]}

Kalimat ucapan final:
{indexed[:2400]}

Keadaan sebelumnya:
{self.character_self_state.prompt_context()}

Aturan:
- "aside" adalah fragmen subteks orang pertama yang sengaja diperlihatkan sebagai teks biru tanpa label.
- Tampilkan hanya jika ada ketegangan sosial/emosi yang nyata: menahan rasa senang, malu, ragu, geli, khawatir, atau kesal ringan.
- Sapaan, jawaban informatif biasa, dan respons tanpa subteks harus show=false.
- Aside 3-12 kata, tidak bertanya, tidak menyapa user, tidak menjelaskan jawaban, dan tidak mengulang ucapan.
- Jangan membuat fakta, rahasia, ingatan, hubungan, aktivitas, tubuh, tempat, masa lalu, atau rencana baru.
- RolePlay={'aktif' if roleplay_mode else 'nonaktif'}; ketika nonaktif, larang aksi/adegan sepenuhnya.
- Mode pasangan={'aktif' if partner_mode else 'nonaktif'}; ketika nonaktif, jangan mengklaim romansa atau memakai panggilan pasangan.
- insert_after harus berada antara 1 dan {len(parts) - 1}; aside tidak boleh menjadi bagian pertama atau terakhir.
- state hanya emosi ekspresi saat ini, bukan fakta. emotion: neutral|warm|shy|nervous|curious|amused|relieved|careful|lightly_annoyed|concerned. stance: open|reserved|playful|gentle|direct|careful.

Output JSON saja:
{{"show":false,"insert_after":1,"aside":"","state":{{"emotion":"neutral","stance":"open","intensity":0.0,"confidence":0.0,"ttl_turns":2}}}}
""".strip()
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": "Kamu mengatur ekspresi karakter yang aman dan singkat. Jangan pernah mengeluarkan reasoning. Output JSON valid saja."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=150,
                temperature=.42,
                json_mode=True,
                role="character_private_aside",
            )
            obj = first_json(raw) or {}
            if obj.get("show") is not True:
                self.character_self_state.update(obj.get("state") or {}, source_message_id=source_message_id, turn=turn)
                return "", 0
            aside = re.sub(r"\s+", " ", str(obj.get("aside") or "")).strip(" *`_>\t")
            if not _valid_aside(aside, partner_mode=partner_mode):
                return "", 0
            if leaks_machine_identity(aside) or leaks_roleplay_v128(aside):
                return "", 0
            position = int(obj.get("insert_after", 0) or 0)
            if position < 1 or position >= len(parts):
                return "", 0
            self.character_self_state.update(obj.get("state") or {}, source_message_id=source_message_id, turn=turn)
            return aside, position
        except Exception as exc:
            try:
                self.store.log_event("private_aside_error", {"error": str(exc)[:240]})
            except Exception:
                pass
            return "", 0

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
                self.store.add_memory(text, kind, importance, confidence=min(.97, importance + .12), source="explicit", source_message_id=source_message_id, source_evidence=user_text)
                dimension = "preference" if kind == "preference" else "goal" if kind == "goal" else "identity" if kind == "identity" else "profile"
                self.store.upsert_belief(dimension, text, min(.97, importance + .08), source="explicit")
            configured = max(512, int(getattr(self.cfg, "max_tokens", 1536) or 1536))
            max_tokens = max(192, min(int(plan.max_tokens), configured))
            answer = self.llm.chat(messages_for_turn, max_tokens=max_tokens, temperature=float(plan.temperature), on_token=None)
            overlong = plan.target_words < 220 and _words(answer) > plan.soft_upper_words
            chatbot = bool(_CHATBOT.search(answer)) and plan.complexity < .70
            if overlong or chatbot:
                reason = "terlalu panjang untuk momentum giliran" if overlong else "terdengar seperti chatbot"
                repaired = list(messages_for_turn)
                repaired[0] = {**repaired[0], "content": str(repaired[0].get("content") or "") + "\n\n" + (
                    f"REPAIR FINAL: Kandidat pertama {reason}. Jawab pesan user dari awal dengan isi yang sama-sama tuntas, "
                    f"sekitar {plan.target_words} kata dan biasanya maksimal {plan.soft_upper_words} kata. "
                    "Jangan memotong kalimat, jangan menyebut proses revisi, dan jangan memakai gaya customer-service."
                )}
                candidate = self.llm.chat(repaired, max_tokens=max_tokens, temperature=min(float(plan.temperature), .64), on_token=None)
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
            aside, position = compose_private_aside(self, user_text, answer, source_message_id=source_message_id, turn=turn)
            self.last_private_aside = aside
            self.last_inner_thought = aside
            self.last_spoken_response = answer
            shown = format_private_reply(answer, aside, position)
            if on_token and shown:
                on_token(shown)
            return shown
        finally:
            self._foreground_active = False
            self._last_foreground_at = time.monotonic()

    def commit_preferred_response(self, user_text: str, answer: str) -> str:
        user_text = str(user_text or "").strip()
        answer = str(answer or "").strip()
        if not user_text or not answer:
            raise ValueError("Pesan dan respons terpilih tidak boleh kosong.")
        self.style_memory.observe_user(user_text)
        if self.lexicon is not None:
            try:
                self.lexicon.observe(user_text, "CASUAL")
                self.lexicon.mark_used(answer)
            except Exception:
                pass
        source_message_id = self.store.add_message("user", user_text)
        for text, kind, importance in extract_explicit_memories(user_text):
            self.store.add_memory(text, kind, importance, confidence=min(.97, importance + .12), source="explicit", source_message_id=source_message_id, source_evidence=user_text)
            dimension = "preference" if kind == "preference" else "goal" if kind == "goal" else "identity" if kind == "identity" else "profile"
            self.store.upsert_belief(dimension, text, min(.97, importance + .08), source="explicit")
        self.store.add_message("assistant", answer)
        turn = self.store.increment_state("companion_turns", 1)
        self._schedule_background(user_text, answer, turn)
        aside, position = compose_private_aside(self, user_text, answer, source_message_id=source_message_id, turn=turn)
        self.last_private_aside = aside
        self.last_inner_thought = aside
        self.last_spoken_response = answer
        return format_private_reply(answer, aside, position)

    FurinaChat.__init__ = init
    FurinaChat._messages = messages
    FurinaChat._compose_private_aside_v129 = compose_private_aside
    FurinaChat.respond = respond
    FurinaChat.commit_preferred_response = commit_preferred_response
    ns["format_private_reply_v129"] = format_private_reply
