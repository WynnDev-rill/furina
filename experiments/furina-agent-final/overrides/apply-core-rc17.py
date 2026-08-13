#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC17 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc17.py <termux-root>")

    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    config = core / "config.py"
    routing = core / "routing.py"
    chat = core / "chat.py"
    events = core / "events.py"
    tool_runtime = core / "tool_runtime.py"
    mind_v2 = core / "mind_v2.py"
    cognition = core / "cognition.py"
    version = core / "version.py"
    for path in (config, routing, chat, events, tool_runtime, mind_v2, cognition, version):
        if not path.is_file():
            raise SystemExit(f"missing RC17 source: {path}")

    c = config.read_text(encoding="utf-8")
    c = replace_once(c, "    config_revision: int = 10", "    config_revision: int = 11", "config revision")
    c = replace_once(
        c,
        '    direct_control_enabled: bool = True\n',
        '''    direct_control_enabled: bool = True

    # RC17 companion cognition: no background heartbeat. Internal reasoning is
    # online-first only when an API is configured, with a hard daily budget;
    # otherwise the already-running local Qwen backend is the fallback.
    cognition_online_preferred: bool = True
    cognition_daily_online_calls: int = 12
    cognition_daily_estimated_tokens: int = 24000
    memory_consolidation_interval_turns: int = 6
    mind_reflection_interval_turns: int = 12
    mind_user_weight: float = 0.30
''',
        "cognition config",
    )
    c = replace_once(
        c,
        '    defaults["lexicon_auto_min_seen"] = max(2, min(int(defaults["lexicon_auto_min_seen"]), 12))\n',
        '''    defaults["lexicon_auto_min_seen"] = max(2, min(int(defaults["lexicon_auto_min_seen"]), 12))
    defaults["cognition_daily_online_calls"] = max(0, min(int(defaults["cognition_daily_online_calls"]), 48))
    defaults["cognition_daily_estimated_tokens"] = max(2000, min(int(defaults["cognition_daily_estimated_tokens"]), 250000))
    defaults["memory_consolidation_interval_turns"] = max(2, min(int(defaults["memory_consolidation_interval_turns"]), 24))
    defaults["mind_reflection_interval_turns"] = max(4, min(int(defaults["mind_reflection_interval_turns"]), 48))
    defaults["mind_user_weight"] = max(0.10, min(float(defaults["mind_user_weight"]), 0.45))
''',
        "cognition clamps",
    )
    config.write_text(c, encoding="utf-8")

    r = routing.read_text(encoding="utf-8")
    marker = '''    def chat(
        self,
        messages: list[dict],
'''
    insertion = '''    def cognitive_chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 700,
        temperature: float = 0.1,
        json_mode: bool = True,
        prefer_online: bool = True,
    ) -> str:
        """High-quality internal cognition without changing foreground routing."""
        if prefer_online and self.configured_online():
            try:
                return self._online_chat(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    json_mode=json_mode,
                )
            except LLMError:
                pass
        if self._ensure_local():
            answer = self.local.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                json_mode=json_mode,
            )
            self.last = RouteResult("local", "GGUF")
            return answer
        raise LLMError("Internal cognition tidak memiliki backend yang tersedia.")

'''
    if insertion.strip() not in r:
        if marker not in r:
            raise SystemExit("RC17 routing marker missing")
        r = r.replace(marker, insertion + marker, 1)
    routing.write_text(r, encoding="utf-8")

    e = events.read_text(encoding="utf-8")
    e = replace_once(
        e,
        "from .memory import MemoryStore\n",
        "from .memory import MemoryStore\nfrom .cognition import enqueue_event\n",
        "event cognition import",
    )
    e = replace_once(
        e,
        "        self._recent.append(compact)\n",
        '''        self._recent.append(compact)
        # Cheap local queue only. If Termux/Core is closed there is no Python
        # model heartbeat; Bridge history is seeded into this queue on next start.
        try:
            enqueue_event(self.store, compact)
        except Exception:
            pass
''',
        "event batching",
    )
    events.write_text(e, encoding="utf-8")

    ch = chat.read_text(encoding="utf-8")
    ch = replace_once(
        ch,
        "from .response import choose_profile\n",
        "from .response import choose_profile\nfrom .mind_v2 import FurinaMind\nfrom .cognition import CognitionRouter\n",
        "chat mind imports",
    )
    ch = replace_once(
        ch,
        "        self.lexicon = PersonalLexicon(store)\n",
        '''        self.lexicon = PersonalLexicon(store)
        self.mind = FurinaMind(store)
        self.cognition = CognitionRouter(cfg, store, llm)
''',
        "chat mind init",
    )
    ch = replace_once(
        ch,
        '            + self._relationship_context()\n',
        '''            + self._relationship_context()
            + "\\n\\nFURINA LEARNED SELF (jangan ubah persona inti berdasarkan data ini):\\n"
            + self.mind.context(10)
            + "\\n\\nCURRENT INTERNAL STATE:\\n"
            + self.mind.current_context()
''',
        "mind context injection",
    )
    ch = replace_once(
        ch,
        '        profile = choose_profile(user_text, self.store)\n',
        '        self.mind.observe_user_feedback(user_text)\n        profile = choose_profile(user_text, self.store)\n',
        "mind feedback",
    )

    start = ch.find("    def _internal_chat(self, messages: list[dict], *, max_tokens: int, temperature: float, json_mode: bool = True) -> str:\n")
    end = ch.find("    def _consolidate(self, user_text: str, answer: str) -> None:\n", start)
    if start < 0 or end < 0:
        raise SystemExit("RC17 internal cognition block markers missing")
    internal = '''    def _internal_chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        json_mode: bool = True,
        purpose: str = "memory_consolidation",
    ) -> str:
        return self.cognition.run(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            purpose=purpose,
            json_mode=json_mode,
        )

'''
    ch = ch[:start] + internal + ch[end:]

    old_bg = '''        try:
            self._consolidate(user_text, answer)
            if turn % 8 == 0:
                self._reflect()
            if turn % 16 == 0:
                self.store.decay_memories()
        finally:
'''
    new_bg = '''        try:
            consolidate_every = max(2, int(getattr(self.cfg, "memory_consolidation_interval_turns", 6)))
            reflect_every = max(4, int(getattr(self.cfg, "mind_reflection_interval_turns", 12)))
            if turn % consolidate_every == 0:
                self._consolidate(user_text, answer)
            if turn % reflect_every == 0:
                self._reflect()
            if turn % max(16, reflect_every * 2) == 0:
                self.store.decay_memories()
        finally:
'''
    ch = replace_once(ch, old_bg, new_bg, "background cadence")

    ch = replace_once(
        ch,
        '    def _consolidate(self, user_text: str, answer: str) -> None:\n        prompt = f"""\n',
        '''    def _consolidate(self, user_text: str, answer: str) -> None:
        recent = self.store.recent_messages(12)
        batch = "\\n".join(f"{m['role']}: {m['content']}" for m in recent)[-7000:]
        prompt = f"""
''',
        "batched consolidation",
    )
    ch = replace_once(
        ch,
        '''User:
{user_text[:3000]}

Furina:
{answer[:3000]}
''',
        '''Batch percakapan terbaru:
{batch}
''',
        "consolidation batch prompt",
    )
    ch = replace_once(
        ch,
        '''                max_tokens=650,
                temperature=0.08,
                json_mode=True,
            )
''',
        '''                max_tokens=650,
                temperature=0.08,
                json_mode=True,
                purpose="memory_consolidation",
            )
''',
        "consolidation purpose",
    )

    reflect_idx = ch.find("    def _reflect(self) -> None:\n")
    if reflect_idx < 0:
        raise SystemExit("RC17 reflection marker missing")
    reflection = '''    def _reflect(self) -> None:
        recent = self.store.recent_messages(30)
        if len(recent) < 8:
            return
        beliefs = self.store.beliefs(min_confidence=0.48, limit=12)
        history = "\\n".join(f"{m['role']}: {m['content']}" for m in recent)[-10000:]
        belief_text = "\\n".join(f"- {b.dimension}: {b.value} ({b.confidence:.2f})" for b in beliefs)
        self_context = self.mind.context(12)
        user_weight = float(getattr(self.cfg, "mind_user_weight", 0.30))
        prompt = f"""
Lakukan reflection periodik untuk Furina sebagai COMPANION.

Prioritas:
- sekitar {round((1.0-user_weight)*100)}%: apa yang Furina pelajari tentang DIRINYA dari percakapan ini.
- sekitar {round(user_weight*100)}%: apa yang benar-benar penting dipahami tentang pengguna atau hubungan.
- Pengalaman agent/alat bukan pusat reflection ini.
- Persona inti Furina TIDAK BOLEH ditulis ulang. Self-learning hanya boleh mengubah learned preferences,
  opinions, uncertainty, expectations, lessons, goals, dan penyesuaian perilaku.

LEARNED SELF SAAT INI:
{self_context}

USER BELIEFS SAAT INI:
{belief_text or '(kosong)'}

PERCAKAPAN TERBARU:
{history}

Cari evidence nyata. Jangan menciptakan emosi/opini hanya agar terlihat hidup.
Opini atau preferensi Furina boleh terbentuk jika konsisten dengan interaksi dan persona inti,
tetapi simpan sebagai learned-self dengan confidence yang sesuai.

Output SATU JSON:
{{
  "self_updates":[
    {{"kind":"observation|lesson|preference|opinion|uncertainty|expectation|goal|behavior",
      "text":"...", "confidence":0.0}}
  ],
  "user_beliefs":[
    {{"dimension":"pattern|trigger|need|goal|preference|relationship",
      "value":"...", "confidence":0.0}}
  ],
  "behavior_notes":["perubahan konkret untuk respons berikutnya tanpa mengubah persona inti"],
  "episode": null atau {{"summary":"kejadian relasional penting","themes":["..."],"importance":0.0,"emotion":0.0}}
}}

Maksimal 6 self_updates, 2 user_beliefs, 3 behavior_notes.
Jika tidak ada evidence yang cukup, gunakan array kosong.
""".strip()
        try:
            raw = self._internal_chat(
                [
                    {"role": "system", "content": "Kamu reflection engine internal companion-first. Output JSON valid saja."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=900,
                temperature=0.16,
                json_mode=True,
                purpose="mind_reflection",
            )
            if not raw:
                return
            obj = _first_json_object(raw) or {}
            self_updates = [x for x in (obj.get("self_updates") or []) if isinstance(x, dict)][:6]
            self.mind.record(self_updates, source="conversation_reflection")

            for b in (obj.get("user_beliefs") or [])[:2]:
                if not isinstance(b, dict):
                    continue
                try:
                    self.store.upsert_belief(
                        str(b.get("dimension", "pattern")),
                        str(b.get("value", "")),
                        float(b.get("confidence", 0.55)),
                        source="reflection",
                    )
                except Exception:
                    pass

            notes = [str(x).strip()[:260] for x in (obj.get("behavior_notes") or []) if str(x).strip()][:3]
            if notes:
                self.mind.record(
                    [{"kind": "behavior", "text": x, "confidence": 0.68} for x in notes],
                    source="behavior_reflection",
                )
                old = self.store.get_state("furina_self_notes", [])
                if not isinstance(old, list):
                    old = []
                merged: list[str] = []
                for item in old[-4:] + notes:
                    if item and item not in merged:
                        merged.append(item)
                self.store.set_state("furina_self_notes", merged[-6:])

            ep = obj.get("episode")
            if isinstance(ep, dict):
                self.store.add_episode(
                    str(ep.get("summary", "")),
                    ep.get("themes") or [],
                    float(ep.get("importance", 0.6)),
                    float(ep.get("emotion", 0.4)),
                )
        except Exception as exc:
            self.store.log_event("mind_v2_reflection_error", {"error": str(exc)[:300]})
'''
    ch = ch[:reflect_idx] + reflection + "\n"
    chat.write_text(ch, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = replace_once(v, 'VERSION = "1.0.0-rc16"', 'VERSION = "1.0.0-rc17"', "core version")
    version.write_text(v, encoding="utf-8")

    for path in (mind_v2, cognition, config, routing, chat, events, tool_runtime, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    checks = [
        (mind_v2, "class FurinaMind"),
        (mind_v2, "Conversation is the primary source"),
        (cognition, "class CognitionRouter"),
        (cognition, "No timer lives here"),
        (config, "cognition_online_preferred: bool = True"),
        (config, "mind_user_weight: float = 0.30"),
        (routing, "def cognitive_chat("),
        (chat, "FURINA LEARNED SELF"),
        (chat, 'purpose="mind_reflection"'),
        (chat, "Maksimal 6 self_updates, 2 user_beliefs"),
        (events, "enqueue_event(self.store, compact)"),
        (tool_runtime, "def capabilities(self)"),
        (tool_runtime, "suppressed_duplicate_failure"),
        (version, 'VERSION = "1.0.0-rc17"'),
    ]
    missing = [needle for path, needle in checks if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC17 companion architecture incomplete: " + ", ".join(missing))

    print("Furina RC17 companion-first Mind v2 + bounded cognition + capability registry: OK")


if __name__ == "__main__":
    main()
