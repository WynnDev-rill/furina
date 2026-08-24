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
if "import re\n" not in text:
    text = text.replace("import queue\n", "import queue\nimport re\n", 1)
    PATH.write_text(text, encoding="utf-8")

replace_method("_belief_context", r'''    @staticmethod
    def _belief_context(store: MemoryStore, user_text: str = "", limit: int = 14, char_budget: int = 2600) -> str:
        beliefs = store.relevant_beliefs(user_text, limit=max(1, limit))
        if not beliefs:
            return "(tidak ada belief relevan yang cukup kuat)"
        lines: list[str] = []
        used = 0
        for belief in beliefs:
            line = f"- {belief.dimension}: {belief.value} [confidence={belief.confidence:.2f}; evidence={belief.evidence}]"
            if used + len(line) > char_budget:
                break
            lines.append(line)
            used += len(line) + 1
        return "\n".join(lines) or "(tidak ada belief relevan yang cukup kuat)"''')

replace_method("_memory_context", r'''    def _memory_context(self, user_text: str, *, local: bool = False) -> str:
        # Retrieval is provider-neutral. Budget affects serialization only, not
        # which database or memory system a model can access.
        limit = max(6, min(8, int(self.cfg.memory_limit or 6)))
        memories = self.store.search(user_text, limit)
        episodes = self.store.search_episodes(user_text, 1 if local else 2)
        budget = 1700 if local else 5200
        lines: list[str] = []
        used = 0
        if memories:
            lines.append("MEMORY PERSONAL RELEVAN:")
            for memory in memories:
                trusted = str(memory.source).casefold() in {"explicit", "furinahub", "user_note", "manual"}
                line = f"- [{'confirmed' if trusted else 'learned'}/{memory.kind}] {memory.text}"
                if used + len(line) > budget:
                    break
                lines.append(line)
                used += len(line) + 1
        if episodes and used < budget:
            lines.append("EPISODE RELEVAN:")
            for episode in episodes:
                line = f"- {episode.summary}" + (f" ({episode.themes})" if episode.themes else "")
                if used + len(line) > budget:
                    break
                lines.append(line)
                used += len(line) + 1
        return "\n".join(lines) or "(tidak ada memory personal relevan yang tersimpan)"''')

insert_before("_local_relationship_context", r'''    def _relationship_context(self) -> str:
        state = self.store.relationship_state()
        notes = self.store.get_state("furina_self_notes", [])
        if not isinstance(notes, list):
            notes = []
        closeness = "akrab" if state.get("closeness", 0) >= 0.65 else "mulai dekat" if state.get("closeness", 0) >= 0.4 else "masih membangun keakraban"
        friction = "ada gesekan baru" if state.get("friction", 0) >= 0.45 else "tidak ada konflik berarti"
        play = "banter kuat" if state.get("playfulness", 0) >= 0.65 else "banter sedang" if state.get("playfulness", 0) >= 0.4 else "banter ringan"
        text = f"Relasi: pasangan; {closeness}; trust={float(state.get('trust', 0.45)):.2f}; {friction}; {play}."
        if notes:
            text += "\nPenyesuaian perilaku tervalidasi: " + " | ".join(str(item) for item in notes[-4:])
        return text''', "def _relationship_context")

insert_before("_messages", r'''    def _shared_context(self, user_text: str, *, local: bool) -> str:
        # This is the existing Core memory architecture made explicit: every
        # inference engine reads the same MemoryStore. Providers do not own a
        # separate personal identity or memory.
        belief = self._belief_context(self.store, user_text, limit=10, char_budget=1100 if local else 2600)
        memory = self._memory_context(user_text, local=local)
        relationship = self._relationship_context()
        return (
            "SHARED PERSONAL CONTEXT — satu-satunya sumber fakta personal Furina tentang pengguna.\n"
            "Model online dan model lokal tidak memiliki memory personal terpisah. Hanya fakta yang tercantum di konteks ini boleh disebut sebagai ingatan personal. "
            "Jika pengguna menanyakan sesuatu yang tidak ditemukan di sini, katakan bahwa Furina belum/tidak cukup mengingatnya. Jangan menebak atau mengarang preferensi, tujuan, kebiasaan, kejadian, atau hubungan. "
            "Ucapan assistant/Furina lama bukan bukti tentang pengguna kecuali sudah masuk sebagai memory/belief tervalidasi.\n\n"
            "BELIEF RELEVAN:\n" + belief + "\n\n" + relationship + "\n\n" + memory
        )''', "def _shared_context")

replace_method("_messages", r'''    def _messages(self, user_text: str, profile) -> list[dict]:
        local = self.cfg.routing_mode == "local"
        shared = self._shared_context(user_text, local=local)
        if local:
            recent_limit = 6 if profile.name in {"DEEP", "CLOSE"} else 4
            recent = self.store.recent_messages(recent_limit)
            system = (
                build_local_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)
                + "\n\n" + shared
                + "\n\nATURAN RECALL: jika pengguna meminta apa yang Furina ingat, jawab hanya dari SHARED PERSONAL CONTEXT. Tidak adanya fakta adalah jawaban yang valid."
                + "\n\nAturan akhir: jawab pesan terbaru sebagai Furina; prioritaskan pesan terbaru, continuity, lalu shared memory relevan."
            )
            messages = [{"role": "system", "content": system}]
            for row in recent:
                content = str(row["content"])
                if len(content) > 700:
                    content = content[:320] + " … " + content[-320:]
                messages.append({"role": row["role"], "content": content})
            messages.append({"role": "user", "content": user_text})
            return messages

        recent_limit = 14 if profile.name in {"DEEP", "CLOSE"} else 10
        recent = self.store.recent_messages(recent_limit)
        system = (
            build_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)
            + "\n\nRESPONSE MODE SAAT INI:\n" + profile.instruction
            + "\n\n" + shared
            + "\n\nATURAN RECALL: jika pengguna meminta apa yang diingat tentang dirinya, jawab hanya dari SHARED PERSONAL CONTEXT. Jangan gunakan pengetahuan model sebagai memory personal."
            + "\n\nPOST-HISTORY RULE:\nJawab pesan terbaru sebagai Furina. Prioritaskan pesan terbaru, continuity, lalu shared memory relevan."
        )
        messages = [{"role": "system", "content": system}]
        messages.extend({"role": row["role"], "content": row["content"]} for row in recent)
        messages.append({"role": "user", "content": user_text})
        return messages''')

insert_before("_integrate_experience", r'''    @staticmethod
    def _evidence_supported(user_text: str, evidence: str) -> bool:
        source = " ".join(str(user_text or "").casefold().split())
        evidence = " ".join(str(evidence or "").casefold().split())
        if len(evidence) < 4:
            return False
        if evidence in source:
            return True
        words = lambda value: set(re.findall(r"[\wÀ-ÿ]{3,}", value, flags=re.UNICODE))
        evidence_words = words(evidence)
        source_words = words(source)
        return bool(evidence_words) and len(evidence_words & source_words) / max(1, len(evidence_words)) >= 0.72

    def _consolidate(self, user_text: str, answer: str) -> None:
        prompt = f"""Analisis SATU pertukaran untuk memory companion jangka panjang.
HANYA ucapan USER boleh menjadi bukti fakta personal pengguna. Jawaban Furina membantu konteks saja dan BUKAN bukti. Jangan mengarang.

USER:
{user_text[:3000]}

FURINA (BUKAN BUKTI):
{answer[:2000]}

Output satu JSON:
{{"memories":[{{"text":"...","kind":"identity|profile|preference|goal|event|relationship|fact","importance":0.0,"confidence":0.0,"emotion":0.0,"evidence":"kutipan user"}}],"beliefs":[{{"dimension":"identity|profile|preference|pattern|trigger|need|goal|relationship","value":"...","confidence":0.0,"evidence":"kutipan user"}}],"episode":null}}
Maksimal 4 memories dan 3 beliefs. Jika bukti user tidak cukup, gunakan array kosong."""
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": "Memory consolidator internal. Output JSON valid saja. User text adalah satu-satunya bukti fakta pengguna."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=650,
                temperature=0.08,
                json_mode=True,
                role="memory",
            )
            obj = _first_json_object(raw) or {}
            for item in (obj.get("memories") or [])[:4]:
                if not isinstance(item, dict) or not self._evidence_supported(user_text, str(item.get("evidence") or "")):
                    continue
                self.store.add_memory(
                    str(item.get("text", "")), str(item.get("kind", "fact")), float(item.get("importance", 0.5)),
                    confidence=float(item.get("confidence", 0.6)), emotion=float(item.get("emotion", 0.3)), source="consolidation",
                )
            for item in (obj.get("beliefs") or [])[:3]:
                if not isinstance(item, dict) or not self._evidence_supported(user_text, str(item.get("evidence") or "")):
                    continue
                self.store.upsert_belief(
                    str(item.get("dimension", "pattern")), str(item.get("value", "")), float(item.get("confidence", 0.55)), source="consolidation",
                )
        except Exception as exc:
            self.store.log_event("memory_consolidation_error", {"error": str(exc)[:300]})

    def _reflect(self) -> None:
        recent = self.store.recent_messages(24)
        user_rows = [row for row in recent if str(row.get("role")) == "user"]
        if len(user_rows) < 4:
            return
        history = "\n".join(f"user: {row['content']}" for row in user_rows)[-7000:]
        prompt = f"""Cari pola pengguna yang DIDUKUNG BERULANG oleh ucapan user berikut. Jangan memakai jawaban assistant sebagai bukti.
{history}

Output JSON: {{"new_beliefs":[{{"dimension":"pattern|trigger|need|goal|preference|relationship","value":"...","confidence":0.0,"evidence":["kutipan user 1","kutipan user 2"]}}],"behavior_notes":["..."]}}.
Setiap belief wajib punya minimal dua bukti berbeda. Maksimal 3 belief dan 3 behavior_notes."""
        try:
            raw = self.llm.chat(
                [{"role": "system", "content": "Reflection engine internal. Output JSON valid saja."}, {"role": "user", "content": prompt}],
                max_tokens=620,
                temperature=0.10,
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
                    str(belief.get("dimension", "pattern")), str(belief.get("value", "")), float(belief.get("confidence", 0.55)), source="reflection",
                )
            notes = [str(item).strip()[:240] for item in (obj.get("behavior_notes") or []) if str(item).strip()][:3]
            if notes:
                old = self.store.get_state("furina_self_notes", [])
                old = old if isinstance(old, list) else []
                merged: list[str] = []
                for item in old[-5:] + notes:
                    if item and item not in merged:
                        merged.append(item)
                self.store.set_state("furina_self_notes", merged[-6:])
        except Exception as exc:
            self.store.log_event("memory_reflection_error", {"error": str(exc)[:300]})''', "def _consolidate")

replace_method("_background_worker_loop", r'''    def _background_worker_loop(self) -> None:
        while True:
            item = self._background_queue.get()
            batch = [item]
            gather_until = time.monotonic() + 1.0
            while len(batch) < 8 and time.monotonic() < gather_until:
                try:
                    batch.append(self._background_queue.get(timeout=max(0.01, gather_until - time.monotonic())))
                except queue.Empty:
                    break
            for user_text, answer, turn in batch:
                started_after = float(getattr(self, "_last_foreground_at", 0.0) or 0.0)
                requeue = False
                try:
                    if self.cfg.routing_mode == "local":
                        while True:
                            last = float(getattr(self, "_last_foreground_at", 0.0) or 0.0)
                            idle = time.monotonic() - last if last else 9999.0
                            if not getattr(self, "_foreground_active", False) and idle >= 120.0:
                                break
                            time.sleep(min(1.0, max(0.05, 120.0 - idle)))
                    started_after = float(getattr(self, "_last_foreground_at", 0.0) or 0.0)
                    self._background_active = True
                    self._consolidate(user_text, answer)
                    if turn % 8 == 0 and not getattr(self, "_foreground_active", False):
                        self._reflect()
                    if turn % 16 == 0:
                        self.store.decay_memories()
                except Exception as exc:
                    self.store.log_event("memory_worker_error", {"error": str(exc)[:300]})
                finally:
                    self._background_active = False
                    requeue = self.cfg.routing_mode == "local" and float(getattr(self, "_last_foreground_at", 0.0) or 0.0) > started_after
                    try:
                        self._background_queue.task_done()
                    except Exception:
                        pass
                if requeue:
                    try:
                        self._background_queue.put_nowait((user_text, answer, turn))
                    except queue.Full:
                        self.store.log_event("memory_worker_requeue_full", {"turn": int(turn)})''')

text = PATH.read_text(encoding="utf-8")
compile(text, str(PATH), "exec")
print("FURINA_PRIVATE_1_0_4_CHAT_FIX_OK")
