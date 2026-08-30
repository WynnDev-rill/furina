from __future__ import annotations

import os
from pathlib import Path

from furina_agent import hub_settings
from furina_agent.chat import FurinaChat, format_private_reply_v130, likely_ungrounded_scene_v130, romantic_turn_policy_v130
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore


root = Path(os.environ["FURINA_HOME"])
store = MemoryStore(root / "memory-v130.db")


class FakeLLM:
    def __init__(self, answers): self.answers, self.calls = list(answers), []
    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if not self.answers: raise AssertionError("unexpected model call")
        return self.answers.pop(0)


cfg = load_config(); cfg.routing_mode = "online"; cfg.persona_name = "Aster"; cfg.max_tokens = 1536
state = hub_settings.load_hub_settings()
state.update({"inner_thoughts": True, "roleplay_mode": False, "partner_mode": True, "user_nickname": "Sayang"})
hub_settings.save_hub_settings(state)

policy = romantic_turn_policy_v130("Aku capek hari ini", partner_mode=True, roleplay_mode=False, nickname="Sayang")
assert "responsiveness" in policy and "Panggilan yang user ajarkan adalah Sayang" in policy
assert "romantis lewat ucapan langsung" in policy and "kalian berpacaran" in policy
assert likely_ungrounded_scene_v130("Cuaca cerah. Ayo kita jogging di taman dekat sini.", "hari ini bagaimana?", roleplay_mode=False)
assert not likely_ungrounded_scene_v130("Aku senang kamu mengabariku, Sayang.", "halo", roleplay_mode=False)
assert not likely_ungrounded_scene_v130("*Aku memelukmu.*", "peluk aku", roleplay_mode=True)

# A term of address explicitly taught in chat is retained separately from the display name.
address_chat = FurinaChat(cfg, store, FakeLLM(["Baik, Sayang. Aku ingat."]))
address_chat.respond("Mulai sekarang panggil aku Sayang")
assert store.get_state("partner_address_v130", {})["value"] == "Sayang"
assert "Panggilan yang user ajarkan adalah Sayang" in address_chat._messages("lanjut", __import__("furina_agent.response", fromlist=["choose_profile"]).choose_profile("lanjut", store))[0]["content"]

shown = format_private_reply_v130("Jangan senyum begitu. Aku jadi sulit mempertahankan gengsiku.", "Sial, aku memang senang.", 1)
assert shown == "Jangan senyum begitu.\n\n> Sial, aku memang senang.\n\nAku jadi sulit mempertahankan gengsiku."

# A salient romantic turn reliably asks the private-aside director and keeps the aside out of stored dialogue.
spoken = "Jangan memujiku mendadak begitu. Aku bisa salah tingkah, tahu."
aside = '{"show":true,"insert_after":1,"aside":"Padahal aku senang sekali.","state":{"emotion":"shy","stance":"reserved","intensity":0.62,"confidence":0.86,"ttl_turns":3}}'
chat = FurinaChat(cfg, store, FakeLLM([spoken, aside]))
reply = chat.respond("Kamu manis hari ini, Sayang")
assert "> Padahal aku senang sekali." in reply
assert "Padahal aku senang sekali." not in str(store.recent_messages(4))
assert store.recent_messages(2)[-1]["content"] == spoken
assert store.get_state("private_aside_director_v130", {})["last_shown_turn"] >= 1

# A trivial greeting stays short and does not force a decorative inner thought.
greeting_llm = FakeLLM(["Pagi, Sayang. Tidurmu cukup?"])
greeting = FurinaChat(cfg, store, greeting_llm)
assert greeting.respond("pagi") == "Pagi, Sayang. Tidurmu cukup?"
assert len(greeting_llm.calls) == 1

# Ungrounded physical romance is regenerated but keeps partner warmth.
bad = "Selamat pagi, Sayang. Aku sudah menunggumu di taman dekat sini."
fixed = "Pagi, Sayang. Aku senang kamu muncul sepagi ini."
repair_llm = FakeLLM([bad, fixed])
repaired = FurinaChat(cfg, store, repair_llm).respond("pagi lagi")
assert repaired == fixed and len(repair_llm.calls) == 2

surface = (Path(__import__("furina_agent.chat", fromlist=["x"]).__file__).parent / "surface_v130.py").read_text(encoding="utf-8")
assert '"bold #5de4c7" if assistant else "bold #e8b86d"' in surface and "bright_magenta" not in surface and "#60a5fa" in surface

print("FURINA_TERMUX_130_ADAPTIVE_ROMANCE_RUNTIME_OK")
