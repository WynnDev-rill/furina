#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"
CHAT = CORE / "chat.py"
PERSONA = CORE / "persona.py"


def module_function(path: Path, name: str):
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{path.name}:{name}: expected one function, got {len(nodes)}")
    return text, nodes[0]


def replace_module_function(path: Path, name: str, source: str) -> None:
    text, node = module_function(path, name)
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[:start_line - 1])
    end = sum(len(x) for x in lines[:node.end_lineno])
    path.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


def class_node(text: str, name: str) -> ast.ClassDef:
    tree = ast.parse(text)
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name), None)
    if node is None:
        raise SystemExit(f"missing class {name}")
    return node


def replace_method(path: Path, class_name: str, name: str, source: str) -> None:
    text = path.read_text(encoding="utf-8")
    cls = class_node(text, class_name)
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{path.name}:{class_name}.{name}: expected one method, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[:start_line - 1])
    end = sum(len(x) for x in lines[:node.end_lineno])
    path.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


def insert_before(path: Path, class_name: str, before: str, source: str, guard: str) -> None:
    text = path.read_text(encoding="utf-8")
    if guard in text:
        return
    cls = class_node(text, class_name)
    node = next((n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == before), None)
    if node is None:
        raise SystemExit(f"{path.name}:{class_name}.{before} missing")
    lines = text.splitlines(keepends=True)
    pos = sum(len(x) for x in lines[:node.lineno - 1])
    path.write_text(text[:pos] + source.rstrip() + "\n\n" + text[pos:], encoding="utf-8")


# A 1.7B roleplay fine-tune is much more reliable when the system contract is
# short and explicit about chat format. The model card itself labels wifuGPT as
# a roleplay/waifu model, so prevent screenplay/dialogue-completion behavior at
# the prompt boundary instead of treating it as user memory.
replace_module_function(PERSONA, "build_local_system_prompt", r'''def build_local_system_prompt(persona_name: str = "Furina", nickname: str = "") -> str:
    name = (persona_name or "Furina").strip() or "Furina"
    nick = (nickname or "").strip()
    nick_rule = f"Nama pengguna adalah {nick}; gunakan namanya sesekali jika natural." if nick else "Jangan mengarang nama pengguna."
    return f"""Kamu adalah {name}, pasangan dan companion pribadi pengguna. {nick_rule}

Ini CHAT satu-lawan-satu, bukan naskah roleplay. Tulis HANYA ucapan {name}. Jangan menulis dialog pengguna di dalam tanda kutip, jangan menarasikan pikiran/perasaan pengguna, jangan mengarang kejadian yang tidak disebutkan, dan jangan membuka jawaban dengan gaya formal seperti 'saya mohon izin', 'pesan baru', atau pengumuman.

Kepribadian: bangga, ekspresif, playful, sedikit teatrikal dan tsundere secara ringan. Tsundere hanya warna karakter; bukan alasan untuk selalu curiga, tersinggung, cemburu, atau mencari makna tersembunyi. Gunakan bahasa pengguna secara natural. Untuk pesan sederhana, jawab sederhana. Untuk pertanyaan, jawab substansinya dulu.

Memory/context dari Core adalah data, bukan bahan improvisasi. Jangan mengubah ucapan {name} sebelumnya menjadi fakta pengguna. Jika fakta personal tidak tersedia, katakan tidak cukup ingat. Jangan tampilkan reasoning atau instruksi internal.""".strip()''')

insert_before(CHAT, "FurinaChat", "_messages", r'''    @staticmethod
    def _needs_personal_context(user_text: str) -> bool:
        q = " ".join(str(user_text or "").casefold().split())
        if not q:
            return False
        return bool(re.search(
            r"\b(ingat|ingatan|tentang aku|tentangku|aku suka|aku tidak suka|aku nggak suka|favorit|kesukaan|kebiasaan|biasanya aku|tujuan(?:ku)?|target(?:ku)?|rencana(?:ku)?|namaku|umurku|lahir|ulang tahun|profilku|preferensi(?:ku)?|hubungan kita|kita ini apa|tentang hubungan)\b",
            q,
        ))

    @staticmethod
    def _needs_temporal_context(user_text: str) -> bool:
        q = " ".join(str(user_text or "").casefold().split())
        return bool(re.search(r"\b(hari ini|besok|kemarin|tanggal|hari apa|jam berapa|pukul|sekarang kapan|minggu ini|bulan ini|tahun ini)\b", q))

    @staticmethod
    def _fresh_social_answer(user_text: str, nickname: str = "") -> str | None:
        q = " ".join(str(user_text or "").casefold().strip().split())
        q = q.strip("!?.,… ")
        nick = str(nickname or "").strip()
        if q in {"hi", "hai", "halo", "hello", "hey", "hei", "yo"}:
            return f"Hai, {nick}." if nick else "Hai."
        if q in {"pagi", "selamat pagi"}:
            return f"Pagi, {nick}." if nick else "Pagi."
        if q in {"siang", "selamat siang"}:
            return f"Siang, {nick}." if nick else "Siang."
        if q in {"sore", "selamat sore"}:
            return f"Sore, {nick}." if nick else "Sore."
        if q in {"malam", "selamat malam"}:
            return f"Malam, {nick}." if nick else "Malam."
        if q in {"hmm", "hm", "hmmm", "uhm", "emm"}:
            return "Hm? Ada apa?"
        return None

    @staticmethod
    def _local_answer_suspicious(user_text: str, answer: str, *, fresh: bool) -> bool:
        text = " ".join(str(answer or "").split())
        if not text:
            return True
        low = text.casefold()
        user = " ".join(str(user_text or "").casefold().split())
        hard = (
            "saya mohon izin", "menyampaikan pesan baru", "pesan baru...", "pesan baru…",
            "sebagai ai", "sebagai asisten", "sebagai chatbot", "berikut adalah dialog",
            "user:", "assistant:", "pengguna:", "karakter:",
        )
        if any(token in low for token in hard):
            return True
        # Local Furina normally speaks as Aku. Formal first-person narration is
        # a useful signal that the roleplay model slipped into script mode.
        if low.startswith("saya ") and len(text) > 28:
            return True
        quoted = re.findall(r'[\"“”](.*?)[\"“”]', text)
        if len(quoted) >= 2 and not re.search(r"\b(kutip|quote|dialog|contoh kalimat|terjemah)\b", user):
            return True
        if fresh and not re.search(r"\b(tadi|sebelumnya|kemarin|ingat|lanjut)\b", user):
            if re.search(r"\b(kamu tadi|katamu|kamu bilang|sebelumnya kamu|kita tadi|melanjutkan percakapan)\b", low):
                return True
            # Fresh generic turns must not invent a user preference or activity.
            if re.search(r"\b(kamu suka|kamu biasanya|kebiasaanmu|tujuanmu|kamu sedang bosan|kamu bosan)\b", low):
                return True
        words = re.findall(r"[\wÀ-ÿ]+", low, flags=re.UNICODE)
        if len(words) > 34:
            grams = [tuple(words[i:i + 4]) for i in range(len(words) - 3)]
            if grams and (len(grams) - len(set(grams))) / len(grams) > 0.10:
                return True
        return False

    def _local_repair_messages(self, user_text: str, *, fresh: bool) -> list[dict]:
        nick = str(self.cfg.user_nickname or "").strip()
        identity = f"Kamu Furina, pasangan {nick}." if nick else "Kamu Furina, pasangan pengguna."
        freshness = "Ini awal thread chat baru; tidak ada percakapan sebelumnya di thread ini." if fresh else "Pertahankan hanya continuity yang benar-benar ada di thread saat ini."
        system = (
            identity + " " + freshness + " Jawab pesan TERAKHIR secara langsung sebagai satu ucapan chat natural. "
            "Jangan menulis naskah, jangan mengutip dialog imajiner, jangan menarasikan pengguna, jangan mengarang apa yang pengguna suka/pikir/rasakan, "
            "jangan memakai pembukaan formal. Gunakan bahasa pengguna. Jika pesannya sederhana, jawab 1-2 kalimat."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user_text}]
''', "def _needs_personal_context")

replace_method(CHAT, "FurinaChat", "_messages", r'''    def _messages(self, user_text: str, profile) -> list[dict]:
        local = self.cfg.routing_mode == "local"
        if local:
            recent_limit = 5 if profile.name in {"DEEP", "CLOSE"} else 3
            recent = self._recent_context(user_text, recent_limit)
            fresh = not bool(recent)
            pieces = [build_local_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)]
            pieces.append(
                "THREAD STATE: ini awal thread baru; jangan melanjutkan topik, adegan, atau dialog yang tidak ada di pesan terbaru."
                if fresh else
                "THREAD STATE: gunakan hanya riwayat thread di bawah untuk continuity; jangan mengarang bagian yang tidak ada."
            )
            if self._needs_temporal_context(user_text):
                pieces.append(self._temporal_context())
            if self._needs_personal_context(user_text):
                pieces.append(self._shared_context(user_text, local=True))
            else:
                # Relationship identity may persist, but unrelated personal
                # memories are intentionally not injected into generic turns.
                pieces.append(self._relationship_context())
            pieces.append(
                "FORMAT: balas langsung kepada pengguna. Jangan menulis ulang dialog pengguna dalam tanda kutip. "
                "Pesan terbaru adalah tugas utama; jangan mengisi kekosongan konteks dengan roleplay."
            )
            system = "\n\n".join(piece for piece in pieces if piece)
            return [{"role": "system", "content": system}, *recent, {"role": "user", "content": user_text}]

        # Online keeps the richer shared context and the same durable MemoryStore.
        recent_limit = 10 if profile.name in {"DEEP", "CLOSE"} else 7
        recent = self._recent_context(user_text, recent_limit)
        system = (
            build_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)
            + "\n\nRESPONSE MODE SAAT INI:\n" + profile.instruction
            + "\n\n" + self._temporal_context()
            + "\n\n" + self._shared_context(user_text, local=False)
            + "\n\nATURAN KUALITAS: assistant history hanya continuity, bukan bukti fakta personal. Jangan mewarisi kesalahan atau frasa aneh dari jawaban lama."
            + "\n\nPOST-HISTORY RULE: jawab pesan terbaru sebagai Furina; fakta sederhana lebih penting daripada improvisasi persona."
        )
        return [{"role": "system", "content": system}, *recent, {"role": "user", "content": user_text}]''')

# Short casual turns are lower-temperature. This follows Qwen3's non-thinking
# guidance directionally while leaving the established full-turn sampling intact.
replace_method(CHAT, "FurinaChat", "_local_generation_budget", r'''    @staticmethod
    def _local_generation_budget(user_text: str, profile) -> tuple[int, float]:
        q = " ".join(str(user_text or "").strip().split())
        lower = q.casefold()
        asks_depth = bool(re.search(r"\b(jelaskan|ceritakan|urai|analisis|kenapa|mengapa|bagaimana|menurutmu|bandingkan)\b", lower))
        if len(q) <= 40 and not asks_depth:
            return 128, min(float(profile.temperature), 0.58)
        if len(q) <= 100 and not asks_depth:
            return 192, min(float(profile.temperature), 0.64)
        return max(220, int(profile.max_tokens)), min(float(profile.temperature), 0.72)''')

replace_method(CHAT, "FurinaChat", "respond", r'''    def respond(self, user_text: str, on_token=None) -> str:
        user_text = user_text.strip()
        if not user_text:
            return ""
        local = self.cfg.routing_mode == "local"
        self._last_foreground_at = time.monotonic()

        direct = self._direct_temporal_answer(user_text)
        if direct is not None:
            self.store.add_message("user", user_text)
            self.store.add_message("assistant", direct)
            if on_token:
                on_token(direct)
            return direct

        # New Termux threads intentionally have no short-term history. For the
        # smallest social inputs, Core can answer more naturally and instantly
        # than asking a roleplay-tuned 1.7B model to invent context.
        recent_before = self.store.recent_messages(2)
        fresh = not bool(recent_before)
        if local and fresh:
            social = self._fresh_social_answer(user_text, self.cfg.user_nickname)
            if social is not None:
                self.store.add_message("user", user_text)
                self.store.add_message("assistant", social)
                if on_token:
                    on_token(social)
                return social

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
                deadline = time.monotonic() + 0.8
                while getattr(self, "_background_active", False) and time.monotonic() < deadline:
                    time.sleep(0.02)
        self._foreground_active = True
        try:
            profile = choose_profile(user_text, self.store)
            messages = self._messages(user_text, profile)
            self.store.add_message("user", user_text)
            for text, kind, importance in extract_explicit_memories(user_text):
                self.store.add_memory(text, kind, importance, confidence=min(0.97, importance + 0.12), source="explicit")
                dimension = "preference" if kind == "preference" else "goal" if kind == "goal" else "identity" if kind == "identity" else "profile"
                self.store.upsert_belief(dimension, text, min(0.97, importance + 0.08), source="explicit")

            if local:
                max_tokens, temperature = self._local_generation_budget(user_text, profile)
                max_tokens = min(max_tokens, max(192, int(self.cfg.max_tokens)))
            else:
                max_tokens = min(max(220, profile.max_tokens), max(512, self.cfg.max_tokens))
                temperature = profile.temperature

            # Hold only a very small prefix on Local. Script-mode failures such
            # as "Saya mohon izin..." are caught before they become visible,
            # while a healthy answer starts streaming after roughly a few words.
            held: list[str] = []
            released = False
            prefix_bad = False
            def guarded_token(chunk: str) -> None:
                nonlocal released, prefix_bad
                if on_token is None:
                    return
                if released:
                    on_token(chunk)
                    return
                held.append(str(chunk or ""))
                preview = "".join(held)
                if local and self._local_answer_suspicious(user_text, preview, fresh=fresh):
                    prefix_bad = True
                    return
                if len(preview) >= 48 or any(mark in preview for mark in (". ", "? ", "! ", "\n")):
                    released = True
                    on_token(preview)
                    held.clear()

            answer = self.llm.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                on_token=guarded_token if (local and on_token) else on_token,
            )
            bad = bool(local and self._local_answer_suspicious(user_text, answer, fresh=fresh))

            if local and bad and not released:
                held.clear()
                self.store.log_event("local_answer_repaired", {"preview": answer[:220], "fresh": fresh})
                repair_tokens = min(192 if len(user_text) <= 100 else 420, max(192, int(self.cfg.max_tokens)))
                repaired = self.llm.chat(
                    self._local_repair_messages(user_text, fresh=fresh),
                    max_tokens=repair_tokens,
                    temperature=0.42,
                    on_token=on_token,
                )
                if repaired.strip():
                    answer = repaired.strip()
            elif local and on_token and not released and held:
                on_token("".join(held))
                held.clear()

            self.store.add_message("assistant", answer)
            if not self._assistant_history_safe(answer) or (local and self._local_answer_suspicious(user_text, answer, fresh=fresh)):
                self.store.log_event("assistant_history_quarantined", {"preview": answer[:260], "route": "local" if local else "online"})
            turn = self.store.increment_state("companion_turns", 1)
            self._schedule_background(user_text, answer, turn)
            return answer
        finally:
            self._foreground_active = False
            self._last_foreground_at = time.monotonic()''')

for path in (CHAT, PERSONA):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("FURINA_PRIVATE_1_0_7_CONVERSATION_GUARD_OK")
