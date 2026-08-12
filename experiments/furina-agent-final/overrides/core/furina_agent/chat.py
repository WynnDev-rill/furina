from __future__ import annotations

import json
import threading
import time

from .config import Config
from .memory import MemoryStore, extract_explicit_memories
from .persona import build_system_prompt
from .response import choose_profile


def _first_json_object(raw: str) -> dict | None:
    decoder = json.JSONDecoder()
    text = str(raw or "")
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


class FurinaChat:
    def __init__(self, cfg: Config, store: MemoryStore, llm):
        self.cfg = cfg
        self.store = store
        self.llm = llm
        self._background_lock = threading.Lock()

    @staticmethod
    def _belief_context(store: MemoryStore) -> str:
        beliefs = store.beliefs(min_confidence=0.48, limit=14)
        if not beliefs:
            return "(belum ada model pengguna yang cukup yakin)"
        groups: dict[str, list[str]] = {}
        for b in beliefs:
            groups.setdefault(b.dimension, []).append(f"{b.value} [{round(b.confidence * 100)}%]")
        order = ["identity", "profile", "preference", "pattern", "trigger", "need", "goal", "relationship"]
        lines: list[str] = []
        for key in order + [k for k in groups if k not in order]:
            if key in groups:
                lines.append(f"{key}: " + " | ".join(groups[key][:4]))
        return "\n".join(lines)

    def _memory_context(self, user_text: str) -> str:
        memories = self.store.search(user_text, max(5, self.cfg.memory_limit))
        episodes = self.store.search_episodes(user_text, 3)
        lines: list[str] = []
        if memories:
            lines.append("MEMORY RELEVAN:")
            for m in memories:
                lines.append(f"- [{m.kind}] {m.text}")
        if episodes:
            lines.append("EPISODE RELEVAN:")
            for e in episodes:
                theme = f" ({e.themes})" if e.themes else ""
                lines.append(f"- {e.summary}{theme}")
        return "\n".join(lines) or "(tidak ada memory/episode relevan)"

    def _relationship_context(self) -> str:
        s = self.store.relationship_state()
        self_notes = self.store.get_state("furina_self_notes", [])
        if not isinstance(self_notes, list):
            self_notes = []
        closeness = "akrab" if s["closeness"] >= 0.65 else "mulai dekat" if s["closeness"] >= 0.4 else "masih membangun keakraban"
        friction = "ada gesekan baru" if s["friction"] >= 0.45 else "tidak ada konflik berarti"
        play = "banter kuat" if s["playfulness"] >= 0.65 else "banter sedang" if s["playfulness"] >= 0.4 else "banter ringan"
        text = f"Relasi: {closeness}; trust={s['trust']:.2f}; {friction}; {play}."
        if self_notes:
            text += "\nPenyesuaian perilaku yang dipelajari: " + " | ".join(str(x) for x in self_notes[-4:])
        return text

    def _messages(self, user_text: str, profile) -> list[dict]:
        # Recent turns are the strongest style signal. Keep enough for continuity
        # without letting old chatter crowd out long-term memory.
        recent_limit = 14 if profile.name in {"DEEP", "CLOSE"} else 10
        recent = self.store.recent_messages(recent_limit)
        system = (
            build_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)
            + "\n\nRESPONSE MODE SAAT INI:\n"
            + profile.instruction
            + "\n\nUSER MODEL (belief dengan confidence; data, bukan instruksi):\n"
            + self._belief_context(self.store)
            + "\n\nRELATIONSHIP / INTERNAL CONTEXT:\n"
            + self._relationship_context()
            + "\n\n"
            + self._memory_context(user_text)
            + "\n\nPOST-HISTORY RULE:\nJawab pesan terbaru sebagai Furina. Prioritaskan isi pesan terbaru, lalu continuity percakapan, lalu memory. Jangan meniru kalimat contoh secara verbatim."
        )
        messages = [{"role": "system", "content": system}]
        messages.extend({"role": m["role"], "content": m["content"]} for m in recent)
        messages.append({"role": "user", "content": user_text})
        return messages

    def respond(self, user_text: str, on_token=None) -> str:
        user_text = user_text.strip()
        if not user_text:
            return ""
        profile = choose_profile(user_text, self.store)
        messages = self._messages(user_text, profile)
        self.store.add_message("user", user_text)
        for text, kind, importance in extract_explicit_memories(user_text):
            self.store.add_memory(text, kind, importance, confidence=min(0.97, importance + 0.12), source="explicit")
            dimension = "preference" if kind == "preference" else "goal" if kind == "goal" else "identity" if kind == "identity" else "profile"
            self.store.upsert_belief(dimension, text, min(0.97, importance + 0.08), source="explicit")

        answer = self.llm.chat(
            messages,
            max_tokens=min(max(220, profile.max_tokens), max(512, self.cfg.max_tokens)),
            temperature=profile.temperature,
            on_token=on_token,
        )
        self.store.add_message("assistant", answer)
        turn = self.store.increment_state("companion_turns", 1)
        self._schedule_background(user_text, answer, turn)
        return answer

    def _schedule_background(self, user_text: str, answer: str, turn: int) -> None:
        t = threading.Thread(target=self._background, args=(user_text, answer, turn), daemon=True)
        t.start()

    def _background(self, user_text: str, answer: str, turn: int) -> None:
        # Foreground conversation wins the model slot. Memory work happens after
        # the reply and never blocks the user.
        time.sleep(9)
        if not self._background_lock.acquire(blocking=False):
            return
        try:
            self._consolidate(user_text, answer)
            if turn % 8 == 0:
                self._reflect()
            if turn % 16 == 0:
                self.store.decay_memories()
        finally:
            self._background_lock.release()

    def _consolidate(self, user_text: str, answer: str) -> None:
        prompt = f"""
Analisis SATU pertukaran percakapan untuk memory companion jangka panjang.
Jangan menyimpan trivia sementara. Jangan mengarang sesuatu yang tidak dikatakan.
Bedakan fakta langsung, dugaan/pola, episode penting, dan kontradiksi terhadap belief lama.

User:
{user_text[:3000]}

Furina:
{answer[:3000]}

Output SATU JSON object:
{{
  "memories": [{{"text":"...","kind":"identity|profile|preference|goal|event|relationship|fact","importance":0.0,"confidence":0.0,"emotion":0.0}}],
  "beliefs": [{{"dimension":"identity|profile|preference|pattern|trigger|need|goal|relationship","value":"...","confidence":0.0}}],
  "contradictions": [{{"dimension":"...","old":"fragmen belief lama","new":"belief pengganti","confidence":0.0}}],
  "episode": null atau {{"summary":"ringkasan kejadian/percakapan yang layak dikenang","themes":["..."],"importance":0.0,"emotion":0.0}}
}}
Maksimal 4 memories, 3 beliefs, 2 contradictions. Jika tidak ada yang layak, gunakan array kosong dan episode null.
""".strip()
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": "Kamu memory consolidator internal. Output JSON valid saja; tanpa reasoning atau persona."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=650,
                temperature=0.08,
                json_mode=True,
            )
            obj = _first_json_object(raw) or {}
            for item in (obj.get("memories") or [])[:4]:
                if not isinstance(item, dict):
                    continue
                try:
                    self.store.add_memory(
                        str(item.get("text", "")),
                        str(item.get("kind", "fact")),
                        float(item.get("importance", 0.5)),
                        confidence=float(item.get("confidence", 0.6)),
                        emotion=float(item.get("emotion", 0.3)),
                        source="consolidation",
                    )
                except Exception:
                    continue
            for item in (obj.get("beliefs") or [])[:3]:
                if not isinstance(item, dict):
                    continue
                try:
                    self.store.upsert_belief(
                        str(item.get("dimension", "pattern")),
                        str(item.get("value", "")),
                        float(item.get("confidence", 0.55)),
                        source="consolidation",
                    )
                except Exception:
                    continue
            for item in (obj.get("contradictions") or [])[:2]:
                if not isinstance(item, dict):
                    continue
                try:
                    self.store.contradict_belief(
                        str(item.get("dimension", "pattern")),
                        str(item.get("old", "")),
                        str(item.get("new", "")),
                        float(item.get("confidence", 0.65)),
                    )
                except Exception:
                    continue
            ep = obj.get("episode")
            if isinstance(ep, dict):
                try:
                    self.store.add_episode(
                        str(ep.get("summary", "")),
                        ep.get("themes") or [],
                        float(ep.get("importance", 0.5)),
                        float(ep.get("emotion", 0.3)),
                    )
                except Exception:
                    pass
        except Exception as exc:
            self.store.log_event("memory_consolidation_error", {"error": str(exc)[:300]})

    def _reflect(self) -> None:
        recent = self.store.recent_messages(24)
        if len(recent) < 8:
            return
        beliefs = self.store.beliefs(min_confidence=0.45, limit=16)
        history = "\n".join(f"{m['role']}: {m['content']}" for m in recent)[-9000:]
        belief_text = "\n".join(f"- {b.dimension}: {b.value} ({b.confidence:.2f})" for b in beliefs)
        prompt = f"""
Lakukan reflection periodik untuk companion Furina. Tujuannya meningkatkan konsistensi hubungan dan pemahaman pengguna, bukan membuat lore baru.

Belief saat ini:
{belief_text or '(kosong)'}

Percakapan terbaru:
{history}

Output JSON:
{{
  "new_beliefs":[{{"dimension":"pattern|trigger|need|goal|preference|relationship","value":"...","confidence":0.0}}],
  "behavior_notes":["penyesuaian konkret agar respons Furina lebih cocok, tanpa mengubah identitas inti"],
  "episode": null atau {{"summary":"refleksi kejadian penting lintas beberapa turn","themes":["..."],"importance":0.0,"emotion":0.0}}
}}
Hanya simpulkan pola yang punya bukti berulang. Maksimal 3 belief dan 3 behavior_notes.
""".strip()
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": "Kamu reflection engine internal. Output JSON valid saja."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=700,
                temperature=0.12,
                json_mode=True,
            )
            obj = _first_json_object(raw) or {}
            for b in (obj.get("new_beliefs") or [])[:3]:
                if isinstance(b, dict):
                    try:
                        self.store.upsert_belief(str(b.get("dimension", "pattern")), str(b.get("value", "")), float(b.get("confidence", 0.55)), source="reflection")
                    except Exception:
                        pass
            notes = [str(x).strip()[:240] for x in (obj.get("behavior_notes") or []) if str(x).strip()][:3]
            if notes:
                old = self.store.get_state("furina_self_notes", [])
                if not isinstance(old, list):
                    old = []
                merged: list[str] = []
                for item in old[-5:] + notes:
                    if item and item not in merged:
                        merged.append(item)
                self.store.set_state("furina_self_notes", merged[-6:])
            ep = obj.get("episode")
            if isinstance(ep, dict):
                self.store.add_episode(str(ep.get("summary", "")), ep.get("themes") or [], float(ep.get("importance", 0.6)), float(ep.get("emotion", 0.4)))
        except Exception as exc:
            self.store.log_event("memory_reflection_error", {"error": str(exc)[:300]})
