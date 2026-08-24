#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
PATH = ROOT / "core/furina_agent/chat.py"


def cls_node(text: str) -> ast.ClassDef:
    tree = ast.parse(text)
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "FurinaChat"), None)
    if node is None:
        raise SystemExit("FurinaChat missing")
    return node


def replace_method(name: str, source: str) -> None:
    text = PATH.read_text(encoding="utf-8")
    cls = cls_node(text)
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"FurinaChat.{name}: expected one method, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[: start_line - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    PATH.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


def insert_before(before: str, source: str, guard: str) -> None:
    text = PATH.read_text(encoding="utf-8")
    if guard in text:
        return
    cls = cls_node(text)
    node = next((n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == before), None)
    if node is None:
        raise SystemExit(f"FurinaChat.{before} missing")
    lines = text.splitlines(keepends=True)
    pos = sum(len(x) for x in lines[: node.lineno - 1])
    PATH.write_text(text[:pos] + source.rstrip() + "\n\n" + text[pos:], encoding="utf-8")


text = PATH.read_text(encoding="utf-8")
if "from datetime import datetime, timedelta" not in text:
    # Keep imports deterministic without depending on one historical import order.
    marker = "import time\n"
    if marker not in text:
        raise SystemExit("chat time import marker missing")
    text = text.replace(marker, marker + "from datetime import datetime, timedelta\n", 1)
    PATH.write_text(text, encoding="utf-8")

insert_before("_shared_context", r'''    @staticmethod
    def _assistant_history_safe(content: str) -> bool:
        """Reject assistant text that would teach the next turn a bad loop.

        Visible history is never deleted. This gate only controls what is fed
        back into an inference model, so a malformed local answer cannot become
        self-reinforcing context on the next turn.
        """
        text = " ".join(str(content or "").split())
        if not text or len(text) > 1600:
            return False
        lowered = text.casefold()
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", lowered) if len(s.strip()) >= 18]
        if len(sentences) != len(set(sentences)):
            return False
        words = re.findall(r"[\wÀ-ÿ]+", lowered, flags=re.UNICODE)
        if len(words) >= 24 and len(set(words)) / max(1, len(words)) < 0.43:
            return False
        if len(words) >= 16:
            grams = [tuple(words[i:i + 4]) for i in range(len(words) - 3)]
            if grams:
                repeated = len(grams) - len(set(grams))
                if repeated / len(grams) > 0.12:
                    return False
        return True

    @staticmethod
    def _continuation_query(user_text: str) -> bool:
        q = " ".join(str(user_text or "").casefold().split())
        if not q:
            return False
        if re.search(r"^(iya|ya|yap|nggak|gak|tidak|kenapa|mengapa|kok|lanjut|terus|trus|lalu|maksud|yang tadi|itu|begitu|serius|masa|hah|hmm|hm|oh|oke|okay)\b", q):
            return True
        if len(q) <= 42 and re.search(r"\b(tadi|jawabanmu|katamu|maksudmu|lanjutkan|terusin)\b", q):
            return True
        return False

    def _recent_context(self, user_text: str, limit: int) -> list[dict]:
        """History is user-led; assistant history is opt-in for continuations.

        This prevents one malformed 1.7B answer from becoming the strongest
        next-turn example while keeping enough continuity for "lanjut", "itu",
        "kenapa?", and similar follow-ups.
        """
        rows = self.store.recent_messages(max(12, limit * 4))
        want_assistant = self._continuation_query(user_text)
        selected: list[dict] = []
        user_count = 0
        assistant_added = False
        for row in reversed(rows):
            role = str(row.get("role") or "")
            content = str(row.get("content") or "").strip()
            if not content:
                continue
            if role == "user" and user_count < limit:
                if len(content) > 900:
                    content = content[:430] + " … " + content[-430:]
                selected.append({"role": "user", "content": content})
                user_count += 1
            elif role == "assistant" and want_assistant and not assistant_added and self._assistant_history_safe(content):
                if len(content) > 900:
                    content = content[:430] + " … " + content[-430:]
                selected.append({"role": "assistant", "content": content})
                assistant_added = True
            if user_count >= limit and (not want_assistant or assistant_added):
                break
        selected.reverse()
        return selected

    @staticmethod
    def _temporal_context() -> str:
        now = datetime.now().astimezone()
        tomorrow = now + timedelta(days=1)
        days = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        return (
            f"WAKTU LOKAL TERPERCAYA: sekarang {days[now.weekday()]}, {now.day} {months[now.month-1]} {now.year}, "
            f"pukul {now:%H:%M} ({now.tzname() or 'lokal'}). "
            f"Besok {days[tomorrow.weekday()]}, {tomorrow.day} {months[tomorrow.month-1]} {tomorrow.year}."
        )

    @staticmethod
    def _direct_temporal_answer(user_text: str) -> str | None:
        q = " ".join(str(user_text or "").casefold().strip().rstrip("?!.").split())
        now = datetime.now().astimezone()
        tomorrow = now + timedelta(days=1)
        days = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        if q in {"besok hari apa", "hari apa besok"}:
            return f"Besok {days[tomorrow.weekday()]}, {tomorrow.day} {months[tomorrow.month-1]} {tomorrow.year}."
        if q in {"hari ini hari apa", "sekarang hari apa", "hari apa sekarang"}:
            return f"Hari ini {days[now.weekday()]}, {now.day} {months[now.month-1]} {now.year}."
        if q in {"besok tanggal berapa", "tanggal berapa besok"}:
            return f"Besok tanggal {tomorrow.day} {months[tomorrow.month-1]} {tomorrow.year}."
        if q in {"hari ini tanggal berapa", "tanggal berapa sekarang", "sekarang tanggal berapa"}:
            return f"Sekarang tanggal {now.day} {months[now.month-1]} {now.year}."
        if q in {"jam berapa sekarang", "sekarang jam berapa", "sekarang pukul berapa"}:
            return f"Sekarang pukul {now:%H:%M}."
        return None

    @staticmethod
    def _local_generation_budget(user_text: str, profile) -> tuple[int, float]:
        q = " ".join(str(user_text or "").strip().split())
        lower = q.casefold()
        if re.fullmatch(r"(?:hi|hai|halo|hello|hey|yo|pagi|siang|sore|malam)[!?. ]*", lower):
            return 96, min(float(profile.temperature), 0.68)
        asks_depth = bool(re.search(r"\b(jelaskan|ceritakan|urai|analisis|kenapa|mengapa|bagaimana|menurutmu)\b", lower))
        if len(q) <= 90 and not asks_depth:
            return 192, min(float(profile.temperature), 0.72)
        return max(220, int(profile.max_tokens)), min(float(profile.temperature), 0.78)''', "def _assistant_history_safe")

replace_method("_relationship_context", r'''    def _relationship_context(self) -> str:
        # Relationship metrics are shared Core state. Legacy model-authored
        # behavior notes remain stored but are deliberately not injected as
        # personal facts or instructions after the 1.0.5 quality repair.
        state = self.store.relationship_state()
        closeness = "akrab" if state.get("closeness", 0) >= 0.65 else "mulai dekat" if state.get("closeness", 0) >= 0.4 else "masih membangun keakraban"
        friction = "ada gesekan baru" if state.get("friction", 0) >= 0.45 else "tidak ada konflik berarti"
        play = "banter kuat" if state.get("playfulness", 0) >= 0.65 else "banter sedang" if state.get("playfulness", 0) >= 0.4 else "banter ringan"
        return f"Relasi: pasangan; {closeness}; trust={float(state.get('trust', 0.45)):.2f}; {friction}; {play}."''')

replace_method("_memory_context", r'''    def _memory_context(self, user_text: str, *, local: bool = False) -> str:
        # Facts come from the same trusted MemoryStore for every provider.
        # Legacy generated episodes are kept on disk but excluded here because
        # old releases did not carry reliable user-evidence provenance.
        limit = max(6, min(8, int(self.cfg.memory_limit or 6)))
        memories = self.store.search(user_text, limit)
        budget = 1700 if local else 5000
        lines: list[str] = []
        used = 0
        if memories:
            lines.append("MEMORY PERSONAL TERPERCAYA:")
            for memory in memories:
                line = f"- [{memory.kind}] {memory.text}"
                if used + len(line) > budget:
                    break
                lines.append(line)
                used += len(line) + 1
        return "\n".join(lines) or "(tidak ada memory personal relevan yang terverifikasi)"''')

replace_method("_shared_context", r'''    def _shared_context(self, user_text: str, *, local: bool) -> str:
        belief = self._belief_context(self.store, user_text, limit=8, char_budget=900 if local else 2200)
        memory = self._memory_context(user_text, local=local)
        relationship = self._relationship_context()
        return (
            "SHARED PERSONAL CONTEXT — sumber fakta personal yang sama untuk Online dan Local.\n"
            "Hanya fakta di bagian ini boleh diperlakukan sebagai ingatan tentang pengguna. Jika tidak ada, jangan mengisi celah dengan tebakan. "
            "Teks assistant lama bukan bukti tentang pengguna. Jangan mengubah ucapan Furina sebelumnya menjadi preferensi, tujuan, kebiasaan, atau kejadian milik pengguna.\n\n"
            "BELIEF TERPERCAYA YANG RELEVAN:\n" + belief + "\n\n" + relationship + "\n\n" + memory
        )''')

replace_method("_messages", r'''    def _messages(self, user_text: str, profile) -> list[dict]:
        local = self.cfg.routing_mode == "local"
        shared = self._shared_context(user_text, local=local)
        temporal = self._temporal_context()
        if local:
            recent_limit = 5 if profile.name in {"DEEP", "CLOSE"} else 3
            recent = self._recent_context(user_text, recent_limit)
            system = (
                build_local_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)
                + "\n\n" + temporal
                + "\n\n" + shared
                + "\n\nATURAN KUALITAS LOCAL: jawab fakta sederhana secara langsung. Jangan menafsirkan sapaan sederhana sebagai konflik, kecemburuan, penolakan, atau pesan tersembunyi. "
                  "Jangan mengulang frasa dari jawaban lama hanya untuk mempertahankan gaya. Jika konteks tidak mendukung klaim personal, jangan klaim itu."
                + "\n\nAturan akhir: pesan terbaru > fakta waktu terpercaya > shared memory relevan > continuity."
            )
            return [{"role": "system", "content": system}, *recent, {"role": "user", "content": user_text}]

        recent_limit = 10 if profile.name in {"DEEP", "CLOSE"} else 7
        recent = self._recent_context(user_text, recent_limit)
        system = (
            build_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)
            + "\n\nRESPONSE MODE SAAT INI:\n" + profile.instruction
            + "\n\n" + temporal
            + "\n\n" + shared
            + "\n\nATURAN KUALITAS: assistant history hanya continuity, bukan bukti fakta personal. Jangan mewarisi kesalahan atau frasa aneh dari jawaban lama."
            + "\n\nPOST-HISTORY RULE: jawab pesan terbaru sebagai Furina; fakta sederhana lebih penting daripada improvisasi persona."
        )
        return [{"role": "system", "content": system}, *recent, {"role": "user", "content": user_text}]''')

replace_method("_consolidate", r'''    def _consolidate(self, user_text: str, answer: str) -> None:
        prompt = f"""Analisis SATU pertukaran untuk memory companion jangka panjang.
HANYA ucapan USER boleh menjadi bukti fakta personal pengguna. Jawaban Furina BUKAN bukti. Jangan mengarang.

USER:
{user_text[:3000]}

FURINA (BUKAN BUKTI):
{answer[:1600]}

Output satu JSON:
{{"memories":[{{"text":"...","kind":"identity|profile|preference|goal|event|relationship|fact","importance":0.0,"confidence":0.0,"emotion":0.0,"evidence":"kutipan user"}}],"beliefs":[{{"dimension":"identity|profile|preference|pattern|trigger|need|goal|relationship","value":"...","confidence":0.0,"evidence":"kutipan user"}}]}}
Maksimal 4 memories dan 3 beliefs. Jika bukti user tidak cukup, gunakan array kosong."""
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": "Memory consolidator internal. Output JSON valid saja. User text adalah satu-satunya bukti fakta pengguna."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
                temperature=0.05,
                json_mode=True,
                role="memory",
            )
            obj = _first_json_object(raw) or {}
            for item in (obj.get("memories") or [])[:4]:
                if not isinstance(item, dict) or not self._evidence_supported(user_text, str(item.get("evidence") or "")):
                    continue
                self.store.add_memory(
                    str(item.get("text", "")), str(item.get("kind", "fact")), float(item.get("importance", 0.5)),
                    confidence=float(item.get("confidence", 0.6)), emotion=float(item.get("emotion", 0.3)), source="user_evidence",
                )
            for item in (obj.get("beliefs") or [])[:3]:
                if not isinstance(item, dict) or not self._evidence_supported(user_text, str(item.get("evidence") or "")):
                    continue
                self.store.upsert_belief(
                    str(item.get("dimension", "pattern")), str(item.get("value", "")), float(item.get("confidence", 0.55)), source="user_evidence",
                )
        except Exception as exc:
            self.store.log_event("memory_consolidation_error", {"error": str(exc)[:300]})''')

replace_method("_reflect", r'''    def _reflect(self) -> None:
        recent = self.store.recent_messages(30)
        user_rows = [row for row in recent if str(row.get("role")) == "user"]
        if len(user_rows) < 6:
            return
        history = "\n".join(f"user: {row['content']}" for row in user_rows)[-7600:]
        prompt = f"""Cari pola pengguna yang DIDUKUNG BERULANG oleh ucapan USER berikut. Jangan memakai jawaban assistant sebagai bukti.
{history}

Output JSON: {{"new_beliefs":[{{"dimension":"pattern|trigger|need|goal|preference|relationship","value":"...","confidence":0.0,"evidence":["kutipan user 1","kutipan user 2"]}}]}}.
Setiap belief wajib punya minimal dua bukti berbeda. Maksimal 3 belief."""
        try:
            raw = self.llm.chat(
                [{"role": "system", "content": "Reflection engine internal. Output JSON valid saja."}, {"role": "user", "content": prompt}],
                max_tokens=520,
                temperature=0.05,
                json_mode=True,
                role="memory",
            )
            obj = _first_json_object(raw) or {}
            full_user_text = "\n".join(str(row.get("content") or "") for row in user_rows)
            for belief in (obj.get("new_beliefs") or [])[:3]:
                if not isinstance(belief, dict):
                    continue
                evidence = [str(item) for item in (belief.get("evidence") or []) if str(item).strip()]
                supported = sum(1 for item in evidence[:4] if self._evidence_supported(full_user_text, item))
                if supported < 2:
                    continue
                self.store.upsert_belief(
                    str(belief.get("dimension", "pattern")), str(belief.get("value", "")), float(belief.get("confidence", 0.55)), source="user_evidence_pattern",
                )
        except Exception as exc:
            self.store.log_event("memory_reflection_error", {"error": str(exc)[:300]})''')

replace_method("respond", r'''    def respond(self, user_text: str, on_token=None) -> str:
        user_text = user_text.strip()
        if not user_text:
            return ""
        local = self.cfg.routing_mode == "local"
        self._last_foreground_at = time.monotonic()

        # Exact temporal questions are Core facts, not a language-model guess.
        direct = self._direct_temporal_answer(user_text)
        if direct is not None:
            self.store.add_message("user", user_text)
            self.store.add_message("assistant", direct)
            if on_token:
                on_token(direct)
            return direct

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
                local_tokens, local_temp = self._local_generation_budget(user_text, profile)
                max_tokens = min(local_tokens, max(192, int(self.cfg.max_tokens)))
                temperature = local_temp
            else:
                max_tokens = min(max(220, profile.max_tokens), max(512, self.cfg.max_tokens))
                temperature = profile.temperature

            answer = self.llm.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                on_token=on_token,
            )
            # Keep visible history intact, but malformed assistant text will be
            # filtered by _recent_context and can no longer poison later turns.
            self.store.add_message("assistant", answer)
            if not self._assistant_history_safe(answer):
                self.store.log_event("assistant_history_quarantined", {"preview": answer[:260], "route": "local" if local else "online"})
            turn = self.store.increment_state("companion_turns", 1)
            self._schedule_background(user_text, answer, turn)
            return answer
        finally:
            self._foreground_active = False
            self._last_foreground_at = time.monotonic()''')

text = PATH.read_text(encoding="utf-8")
compile(text, str(PATH), "exec")
print("FURINA_PRIVATE_1_0_5_CHAT_QUALITY_OK")
