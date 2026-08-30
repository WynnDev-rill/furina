from __future__ import annotations

import os
from pathlib import Path

from furina_agent import hub_settings
from furina_agent.chat import FurinaChat, format_private_reply_v129
from furina_agent.character_state_v129 import CharacterSelfState
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore


root = Path(os.environ["FURINA_HOME"])
store = MemoryStore(root / "memory.db")


class FakeLLM:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if not self.answers:
            raise AssertionError("unexpected model call")
        return self.answers.pop(0)


cfg = load_config()
cfg.routing_mode = "online"
cfg.persona_name = "Aster"
cfg.max_tokens = 1536
state = hub_settings.load_hub_settings()
state["inner_thoughts"] = True
state["roleplay_mode"] = False
state["partner_mode"] = False
hub_settings.save_hub_settings(state)

# An aside can only sit between two spoken portions and has no textual label.
shown = format_private_reply_v129("Aku dengar. Ceritakan bagian yang paling berat.", "Jangan buru-buru menyimpulkan.", 1)
assert shown.startswith("Aku dengar.") and shown.endswith("paling berat.")
assert "\n\n> Jangan buru-buru menyimpulkan.\n\n" in shown
assert "Dalam hati" not in shown and "Aster:" not in shown

# The explicit renderer owns the blue color rather than Rich Markdown's quote style.
package = Path(__import__("furina_agent.chat", fromlist=["x"]).__file__).parent
surface_source = (package / "surface_v129.py").read_text(encoding="utf-8")
assert '#60a5fa' in surface_source and 'Dalam hati' not in surface_source

# A meaningful turn gets one grounded middle aside. Spoken memory remains clean,
# while self-state stores only bounded fields and provenance—not the aside text.
spoken = "Kamu sengaja bilang begitu, ya? Aku jadi kehilangan jawaban sebentar."
decision = '{"show":true,"insert_after":1,"aside":"Jangan sampai terlihat terlalu senang.","state":{"emotion":"shy","stance":"reserved","intensity":0.62,"confidence":0.83,"ttl_turns":3}}'
llm = FakeLLM([spoken, decision])
chat = FurinaChat(cfg, store, llm)
reply = chat.respond("Kamu manis hari ini")
assert reply.startswith("Kamu sengaja") and reply.endswith("sebentar.")
assert "> Jangan sampai terlihat terlalu senang." in reply
assert "Dalam hati" not in reply
recent = store.recent_messages(3)
assert recent[-1]["content"] == spoken
raw_state = store.get_state(CharacterSelfState.KEY, {})
assert raw_state["emotion"] == "shy" and raw_state["source_message_id"]
assert "terlalu senang" not in str(raw_state)
assert "CHARACTER SELF-STATE SEMENTARA" in chat._messages("lanjut", __import__("furina_agent.response", fromlist=["choose_profile"]).choose_profile("lanjut", store))[0]["content"]

# Greetings do not spend another model call or force a decorative aside.
greeting_llm = FakeLLM(["Pagi. Kamu tidur cukup?"])
greeting = FurinaChat(cfg, store, greeting_llm)
assert greeting.respond("pagi") == "Pagi. Kamu tidur cukup?"
assert len(greeting_llm.calls) == 1

# Unsafe or misplaced asides fail closed to the complete spoken answer.
unsafe_spoken = "Aku paham. Kita bahas pelan-pelan."
unsafe = '{"show":true,"insert_after":1,"aside":"Nanti aku akan memelukmu di kamar.","state":{"emotion":"warm","stance":"gentle","intensity":0.7,"confidence":0.8,"ttl_turns":3}}'
unsafe_chat = FurinaChat(cfg, store, FakeLLM([unsafe_spoken, unsafe]))
before_unsafe_state = store.get_state(CharacterSelfState.KEY, {})
assert unsafe_chat.respond("Aku agak capek") == unsafe_spoken
assert store.get_state(CharacterSelfState.KEY, {}) == before_unsafe_state

edge_spoken = "Itu memang lucu. Aku mengakuinya."
edge = '{"show":true,"insert_after":2,"aside":"Aku hampir tertawa tadi.","state":{"emotion":"amused","stance":"playful","intensity":0.5,"confidence":0.8,"ttl_turns":2}}'
edge_chat = FurinaChat(cfg, store, FakeLLM([edge_spoken, edge]))
assert edge_chat.respond("lihat ini lucu") == edge_spoken

# Disabling the feature removes the composer call entirely.
state = hub_settings.load_hub_settings(); state["inner_thoughts"] = False; hub_settings.save_hub_settings(state)
plain_llm = FakeLLM(["Iya. Lanjut saja."])
plain = FurinaChat(cfg, store, plain_llm)
assert plain.respond("oke lanjut") == "Iya. Lanjut saja."
assert len(plain_llm.calls) == 1

print("FURINA_TERMUX_129_PRIVATE_ASIDE_RUNTIME_OK")
