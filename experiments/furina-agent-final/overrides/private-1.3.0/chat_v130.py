from __future__ import annotations

import hashlib
import re
import time

from .chat_v129 import _CHATBOT, _FORBIDDEN_ASIDE, _sentences, _words
from .style_v128 import plan_turn


_AFFECTION = re.compile(r"\b(?:sayang|cinta|kangen|rindu|manis|gemas|suka kamu|love you|miss you|bersamamu)\b", re.I)
_VULNERABLE = re.compile(r"\b(?:sedih|takut|cemas|capek|lelah|kesepian|malu|gagal|kecewa|bingung|berat)\b", re.I)
_PLAYFUL = re.compile(r"\b(?:wkwk|haha|hehe|goda|ledek|bercanda|lucu|jahil)\b", re.I)
_CONFLICT = re.compile(r"\b(?:kesal|marah|jangan begitu|berhenti|stop|nggak suka|tidak suka|salahmu|kecewa sama kamu)\b", re.I)
_PRACTICAL = re.compile(r"\b(?:cara|kenapa|error|kode|teknis|jelaskan|analisis|langkah|bagaimana membuat)\b", re.I)
_QUESTION = re.compile(r"[?]|\b(?:kenapa|mengapa|bagaimana|gimana|apa|siapa|kapan|dimana|di mana)\b", re.I)
_TRIVIAL = re.compile(r"^(?:hai+|halo+|pagi|siang|sore|malam|iya+|ya+|oke+|ok|hm+|oh+|sip|makasih|terima kasih)[.!?~ ]*$", re.I)
_ADDRESS_PATTERNS = (
    re.compile(r"\b(?:panggil|sebut)(?:lah)?\s+(?:aku|saya)(?:\s+dengan)?(?:\s+panggilan)?\s+[\"']?([A-Za-zÀ-ÖØ-öø-ÿ-]{2,24})", re.I),
    re.compile(r"\b(?:pakai|gunakan)\s+(?:panggilan\s+)?[\"']?([A-Za-zÀ-ÖØ-öø-ÿ-]{2,24})[\"']?\s+(?:daripada|alih-alih)\s+(?:nama|namaku)", re.I),
    re.compile(r"\bpenyebutan\s+([A-Za-zÀ-ÖØ-öø-ÿ-]{2,24}).{0,48}\bdaripada\s+(?:menggunakan\s+)?nama", re.I),
)

_SCENE_RISK = re.compile(
    r"(?:\*[^*]{1,100}\*|\[[^\]]{1,100}\]|\b(?:aku|kita)\s+(?:sedang|lagi|sudah|baru saja|akan)\s+"
    r"(?:menunggu|berjalan|duduk|berdiri|memeluk|mencium|menggenggam|menatap|keluar|pergi|jogging|memasak|membuatkan)|"
    r"\b(?:aku\s+)?(?:memelukmu|menciummu|menggenggam(?:mu| tanganmu)|menatapmu)|"
    r"\b(?:cuaca|udara)\s+(?:cerah|segar|dingin|panas)|\b(?:taman|kamar|rumah|sekolah|kantor)\s+(?:dekat|ini|sini)|"
    r"\baku sudah menunggu(?:mu)?\b|\bkamu punya \d+ detik\b)",
    re.I,
)


def romantic_turn_policy(user_text: str, *, partner_mode: bool, roleplay_mode: bool, nickname: str = "") -> str:
    if not partner_mode:
        return "MODE PASANGAN NONAKTIF: gunakan kedekatan companion non-romantis; jangan mengklaim hubungan romantis."
    text = " ".join(str(user_text or "").split())
    if _CONFLICT.search(text):
        move = "repair: dengarkan bagian spesifik, akui dampak atau batas yang relevan, lalu jawab tanpa godaan"
    elif _VULNERABLE.search(text):
        move = "responsiveness: tanggapi detail yang ia berikan, beri rasa ditemani, lalu tanyakan satu hal hanya bila masih perlu memahami"
    elif _AFFECTION.search(text):
        move = "reciprocity: balas afeksi secara jujur; boleh ada rasa senang, malu, gengsi, atau godaan kecil sesuai sifat aktif"
    elif _PLAYFUL.search(text):
        move = "playfulness: balas candaan pada detail yang sama tanpa menaikkan intensitas secara berlebihan"
    elif _PRACTICAL.search(text):
        move = "practical care: selesaikan isi dengan jelas; kehangatan pasangan cukup di tepi respons, bukan mengganggu jawaban"
    elif _QUESTION.search(text):
        move = "engagement: jawab langsung lalu tunjukkan minat pribadi yang relevan, tanpa wawancara atau pujian generik"
    else:
        move = "everyday intimacy: reaksi singkat, akrab, dan punya pendapat; boleh hangat atau menggoda sesuai momentum"
    address = (
        f"Panggilan eksplisit user adalah {nickname}; boleh dipakai bila memberi tekanan emosional yang natural, bukan di setiap respons."
        if nickname else
        "Jangan mengarang panggilan romantis baru; kedekatan tetap dapat terasa lewat responsivitas dan pilihan kata."
    )
    grounding = (
        "RolePlay aktif, tetapi adegan/narasi hanya jika user sedang memulainya."
        if roleplay_mode else
        "RolePlay nonaktif: romantis lewat ucapan langsung. Jangan mengarang tubuh, sentuhan, lokasi, cuaca, aktivitas bersama, atau seolah kalian hadir fisik di tempat yang sama."
    )
    return (
        "MODE PASANGAN ADAPTIF: kalian berpacaran. Buat hubungan terasa melalui responsivitas, afeksi timbal balik, "
        "keterbukaan diri kecil, humor, perhatian sehari-hari, dan repair—pilih yang cocok, jangan menumpuk semuanya.\n"
        f"GERAK GILIRAN: {move}.\n{address}\n{grounding}\n"
        "Hindari pola pasangan generik: panggilan terus-menerus, posesif, memerintah, hitung mundur, janji kosong, atau romantisasi yang mengalahkan isi pesan."
    )


def _remembered_address(store, fallback: str = "") -> str:
    saved = store.get_state("partner_address_v130", {}) or {}
    if str(saved.get("value") or "").strip():
        return str(saved["value"]).strip()[:24]
    candidates: list[str] = []
    try:
        candidates.extend(str(x.value) for x in store.beliefs("preference", min_confidence=.55, limit=40))
    except Exception:
        pass
    try:
        candidates.extend(str(x.text) for x in store.list_memories(80) if getattr(x, "kind", "") in {"preference", "explicit"})
    except Exception:
        pass
    for text in candidates:
        for pattern in _ADDRESS_PATTERNS:
            match = pattern.search(text)
            if match:
                value = match.group(1).strip().title()
                store.set_state("partner_address_v130", {"value": value, "source": "explicit_memory"})
                return value
    return " ".join(str(fallback or "").split())[:24]


def _observe_address(store, user_text: str) -> str:
    for pattern in _ADDRESS_PATTERNS:
        match = pattern.search(str(user_text or ""))
        if match:
            value = match.group(1).strip().title()
            store.set_state("partner_address_v130", {"value": value, "source": "explicit_user"})
            return value
    if re.search(r"\b(?:jangan|tidak usah|nggak usah)\s+(?:panggil|sebut).{0,24}\b(?:sayang|cinta|beb|dear)\b", str(user_text or ""), re.I):
        store.set_state("partner_address_v130", {})
    return ""


def likely_ungrounded_scene(answer: str, user_text: str, *, roleplay_mode: bool) -> bool:
    if roleplay_mode:
        return False
    answer = str(answer or "")
    if not _SCENE_RISK.search(answer):
        return False
    # Quoting or directly discussing the user's words is not automatically enactment.
    shared = {w for w in re.findall(r"\b\w{5,}\b", str(user_text or "").casefold())}
    risky = {w for w in re.findall(r"\b\w{5,}\b", answer.casefold()) if _SCENE_RISK.search(w)}
    return not risky or not risky.issubset(shared)


def _aside_score(user_text: str, answer: str, state_context: str) -> float:
    text = str(user_text or "")
    if _TRIVIAL.fullmatch(text.strip()):
        return .04
    score = .10
    if _AFFECTION.search(text): score += .43
    if _VULNERABLE.search(text): score += .28
    if _PLAYFUL.search(text): score += .20
    if _CONFLICT.search(text): score += .30
    if re.search(r"\b(?:aku suka kamu|bersamamu|menurutmu tentangku|kamu sayang aku|cantik|manis)\b", text, re.I): score += .18
    if re.search(r"\b(?:tapi|sebenarnya|jujur|entah|mungkin|jangan salah paham)\b", answer, re.I): score += .10
    if re.search(r"emotion=(?:shy|nervous|amused|concerned|lightly_annoyed)", state_context, re.I): score += .12
    return min(1.0, score)


def format_private_reply_v130(answer: str, aside: str, insert_after: int) -> str:
    parts = _sentences(answer)
    aside = re.sub(r"[\r\n]+", " ", str(aside or "")).strip(" *`_>\t")
    if len(parts) < 2 or not aside:
        return str(answer or "").strip()
    position = max(1, min(int(insert_after), len(parts) - 1))
    return " ".join(parts[:position]).strip() + f"\n\n> {aside}\n\n" + " ".join(parts[position:]).strip()


def _valid_aside(text: str, *, partner_mode: bool) -> bool:
    text = re.sub(r"\s+", " ", str(text or "")).strip(" *`_>\t")
    if _words(text) < 3 or _words(text) > 14 or len(text) > 140 or "?" in text:
        return False
    if _FORBIDDEN_ASIDE.search(text) or re.search(r"[*\[\]{}<>]", text):
        return False
    if not partner_mode and re.search(r"\b(?:cinta|pacar|pasangan|milikku|mencintai)\b", text, re.I):
        return False
    return True


def install_chat_v130(ns: dict) -> None:
    FurinaChat = ns["FurinaChat"]
    previous_init = FurinaChat.__init__
    previous_messages = FurinaChat._messages
    choose_profile = ns["choose_profile"]
    extract_explicit_memories = ns["extract_explicit_memories"]
    first_json = ns["_first_json_object"]

    def init(self, cfg, store, llm):
        previous_init(self, cfg, store, llm)
        self.last_private_aside = ""

    def messages(self, user_text, profile):
        from .hub_settings import load_hub_settings
        rows = previous_messages(self, user_text, profile)
        if rows and rows[0].get("role") == "system":
            settings = load_hub_settings()
            observed = _observe_address(self.store, user_text)
            address = observed or _remembered_address(self.store, str(settings.get("user_nickname") or getattr(self.cfg, "user_nickname", "") or ""))
            rows[0] = {**rows[0], "content": str(rows[0].get("content") or "") + "\n\n" + romantic_turn_policy(
                user_text,
                partner_mode=bool(settings.get("partner_mode")),
                roleplay_mode=bool(settings.get("roleplay_mode")),
                nickname=address,
            )}
        return rows

    def compose_private_aside(self, user_text: str, answer: str, *, source_message_id: int | None, turn: int) -> tuple[str, int]:
        from .hub_settings import load_hub_settings
        from .output_v128 import leaks_machine_identity, leaks_roleplay_v128

        settings = load_hub_settings()
        parts = _sentences(answer)
        if not settings.get("inner_thoughts") or len(parts) < 2:
            return "", 0
        director = self.store.get_state("private_aside_director_v130", {}) or {}
        state_context = self.character_self_state.prompt_context()
        score = _aside_score(user_text, answer, state_context)
        misses = max(0, int(director.get("eligible_misses", 0) or 0))
        last_turn = int(director.get("last_shown_turn", -99) or -99)
        cooldown = max(0, turn - last_turn)
        threshold = max(.40, .54 - min(3, misses) * .05)
        eligible = score >= threshold and (cooldown >= 2 or score >= .82)
        if not eligible:
            if score >= .32:
                director["eligible_misses"] = min(4, misses + 1)
            self.store.set_state("private_aside_director_v130", director)
            return "", 0

        partner_mode = bool(settings.get("partner_mode"))
        roleplay_mode = bool(settings.get("roleplay_mode"))
        indexed = "\n".join(f"{i + 1}. {part}" for i, part in enumerate(parts))
        prompt = f"""
Tulis satu subteks batin karakter untuk disisipkan di antara dua bagian ucapan. Ini bukan reasoning, analisis, atau penjelasan teknis.

Pesan user:
{str(user_text)[:1200]}

Ucapan final bernomor:
{indexed[:2400]}

Keadaan ekspresi:
{state_context}

Momen ini sudah dipilih penentu relevansi (salience={score:.2f}); output show=true kecuali tidak mungkin menulis subteks yang aman.
- Aside adalah hal kecil yang karakter rasakan tetapi tidak ia ucapkan: malu, senang diam-diam, ragu, geli, khawatir, atau kesal ringan.
- Tulis orang pertama 3-12 kata. Jangan menyapa user, bertanya, mengulang ucapan, atau menjelaskan niat menjawab.
- Jangan buat fakta, rahasia besar, ingatan, aktivitas, tubuh, tempat, masa lalu, atau rencana baru.
- Jangan berisi AI, sistem, prompt, reasoning, instruksi, atau proses kerja.
- RolePlay={'aktif' if roleplay_mode else 'nonaktif'}; saat nonaktif tidak ada aksi/adegan.
- Mode pasangan={'aktif' if partner_mode else 'nonaktif'}; saat nonaktif jangan klaim romansa.
- insert_after harus 1 sampai {len(parts) - 1}; pilih titik setelah kalimat yang memicu subteks, bukan selalu posisi pertama.

Output JSON saja:
{{"show":true,"insert_after":1,"aside":"...","state":{{"emotion":"shy","stance":"reserved","intensity":0.5,"confidence":0.8,"ttl_turns":2}}}}
""".strip()
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": "Kamu adalah director subteks karakter. Tidak pernah mengeluarkan chain-of-thought. Output JSON valid saja."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=170, temperature=.48, json_mode=True, role="character_private_aside",
            )
            obj = first_json(raw) or {}
            aside = re.sub(r"\s+", " ", str(obj.get("aside") or obj.get("private_aside") or "")).strip(" *`_>\t")
            position = int(obj.get("insert_after", 0) or 0)
            safe = (
                obj.get("show") is not False and _valid_aside(aside, partner_mode=partner_mode)
                and not leaks_machine_identity(aside) and not leaks_roleplay_v128(aside)
                and 1 <= position < len(parts)
            )
            self.character_self_state.update(obj.get("state") or {}, source_message_id=source_message_id, turn=turn)
            if not safe:
                director["eligible_misses"] = min(4, misses + 1)
                self.store.set_state("private_aside_director_v130", director)
                return "", 0
            digest = hashlib.sha256(aside.casefold().encode("utf-8")).hexdigest()[:16]
            if digest in set(director.get("recent_hashes") or []):
                return "", 0
            director.update({"last_shown_turn": turn, "eligible_misses": 0, "recent_hashes": ([digest] + list(director.get("recent_hashes") or []))[:6]})
            self.store.set_state("private_aside_director_v130", director)
            return aside, position
        except Exception as exc:
            try: self.store.log_event("private_aside_error", {"error": str(exc)[:240], "version": "v130"})
            except Exception: pass
            return "", 0

    def respond(self, user_text: str, on_token=None) -> str:
        from .hub_settings import load_hub_settings
        user_text = str(user_text or "").strip()
        if not user_text: return ""
        local = self.cfg.routing_mode == "local"
        self._last_foreground_at = time.monotonic()
        self.style_memory.observe_user(user_text)
        if self.lexicon is not None:
            try: self.lexicon.observe(user_text, "CASUAL")
            except Exception: pass
        if local:
            try: self.llm.prewarm_local()
            except Exception: pass
            if getattr(self, "_background_active", False):
                try: self.llm.cancel()
                except Exception: pass
                deadline = time.monotonic() + .8
                while getattr(self, "_background_active", False) and time.monotonic() < deadline: time.sleep(.02)
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
            answer = self.llm.chat(messages_for_turn, max_tokens=max_tokens, temperature=float(plan.temperature), on_token=None).strip()
            settings = load_hub_settings()
            overlong = plan.target_words < 220 and _words(answer) > plan.soft_upper_words
            chatbot = bool(_CHATBOT.search(answer)) and plan.complexity < .70
            scene = likely_ungrounded_scene(answer, user_text, roleplay_mode=bool(settings.get("roleplay_mode")))
            if overlong or chatbot or scene:
                reason = "mengarang adegan/kehadiran fisik" if scene else "terlalu panjang untuk momentum giliran" if overlong else "terdengar seperti chatbot"
                repaired = [dict(row) for row in messages_for_turn]
                repaired[0]["content"] = str(repaired[0].get("content") or "") + "\n\n" + (
                    f"REPAIR FINAL: Kandidat pertama {reason}. Tulis ulang dari awal, tetap tuntas dan tetap romantis bila Mode pasangan aktif. "
                    f"Target sekitar {plan.target_words} kata dan biasanya maksimal {plan.soft_upper_words} kata. "
                    "RolePlay nonaktif berarti romantis melalui ucapan dan responsivitas, bukan tempat, cuaca, sentuhan, tubuh, atau aktivitas bersama yang dikarang. "
                    "Jangan menyebut revisi, sistem, atau proses ini."
                )
                candidate = self.llm.chat(repaired, max_tokens=max_tokens, temperature=min(float(plan.temperature), .64), on_token=None).strip()
                if candidate and not likely_ungrounded_scene(candidate, user_text, roleplay_mode=bool(settings.get("roleplay_mode"))):
                    answer = candidate
            if self.lexicon is not None:
                try: self.lexicon.mark_used(answer)
                except Exception: pass
            self.store.add_message("assistant", answer)
            turn = self.store.increment_state("companion_turns", 1)
            self._schedule_background(user_text, answer, turn)
            aside, position = compose_private_aside(self, user_text, answer, source_message_id=source_message_id, turn=turn)
            self.last_private_aside = aside; self.last_inner_thought = aside; self.last_spoken_response = answer
            shown = format_private_reply_v130(answer, aside, position)
            if on_token and shown: on_token(shown)
            return shown
        finally:
            self._foreground_active = False
            self._last_foreground_at = time.monotonic()

    def commit_preferred_response(self, user_text: str, answer: str) -> str:
        user_text, answer = str(user_text or "").strip(), str(answer or "").strip()
        if not user_text or not answer: raise ValueError("Pesan dan respons terpilih tidak boleh kosong.")
        self.style_memory.observe_user(user_text)
        if self.lexicon is not None:
            try: self.lexicon.observe(user_text, "CASUAL"); self.lexicon.mark_used(answer)
            except Exception: pass
        source_message_id = self.store.add_message("user", user_text)
        for text, kind, importance in extract_explicit_memories(user_text):
            self.store.add_memory(text, kind, importance, confidence=min(.97, importance + .12), source="explicit", source_message_id=source_message_id, source_evidence=user_text)
        self.store.add_message("assistant", answer)
        turn = self.store.increment_state("companion_turns", 1)
        self._schedule_background(user_text, answer, turn)
        aside, position = compose_private_aside(self, user_text, answer, source_message_id=source_message_id, turn=turn)
        self.last_private_aside = aside; self.last_inner_thought = aside; self.last_spoken_response = answer
        return format_private_reply_v130(answer, aside, position)

    FurinaChat.__init__ = init
    FurinaChat._messages = messages
    FurinaChat._compose_private_aside_v130 = compose_private_aside
    FurinaChat.respond = respond
    FurinaChat.commit_preferred_response = commit_preferred_response
    ns["romantic_turn_policy_v130"] = romantic_turn_policy
    ns["likely_ungrounded_scene_v130"] = likely_ungrounded_scene
    ns["format_private_reply_v130"] = format_private_reply_v130
