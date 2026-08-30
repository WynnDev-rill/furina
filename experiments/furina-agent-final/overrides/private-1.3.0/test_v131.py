from __future__ import annotations

import os
from pathlib import Path

from furina_agent import hub_settings
from furina_agent.chat import FurinaChat
from furina_agent.chat_v130 import _valid_aside, continuation_policy, romantic_turn_policy
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.response import choose_profile
from furina_agent.training_room import generate_live_training_pair


root = Path(os.environ["FURINA_HOME"])
store = MemoryStore(root / "memory-v131.db")
cfg = load_config(); cfg.routing_mode = "online"; cfg.persona_name = "Aster"; cfg.max_tokens = 1536
settings = hub_settings.load_hub_settings()
settings.update({"inner_thoughts": True, "roleplay_mode": False, "partner_mode": True, "user_nickname": "Wynn"})
hub_settings.save_hub_settings(settings)


class FakeLLM:
    def __init__(self, answers): self.answers, self.calls = list(answers), []
    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if not self.answers: raise AssertionError("unexpected model call")
        return self.answers.pop(0)


# Display identity is not silently converted into a mandatory romantic address.
chat = FurinaChat(cfg, store, FakeLLM([]))
system = chat._messages("halo", choose_profile("halo", store))[0]["content"]
assert "Panggilan yang user ajarkan adalah Wynn" not in system

# Explicit address stays optional and repetition pressure suppresses it.
store.set_state("partner_address_v130", {"value": "Sayang", "source": "explicit_user"})
store.add_message("assistant", "Baik, Sayang.")
store.add_message("assistant", "Tentu saja, Sayang.")
policy = romantic_turn_policy("lanjut", partner_mode=True, roleplay_mode=False, nickname="Sayang", address_recent=2)
assert "hindari pada giliran ini" in policy and "bukan pengganti nama" in policy

# Acknowledgements preserve conversational momentum rather than forcing a support-agent closure.
ack = continuation_policy("oke", [{"role": "assistant", "content": "Kau memang sengaja menggodaku, ya?"}])
assert "bukan otomatis tanda percakapan selesai" in ack and "kalau ada lagi" in ack

# A silent utterance is private wording, not a body-state caption.
assert _valid_aside("Jangan sampai dia tahu aku senang.", partner_mode=True)
assert not _valid_aside("Dadaku berdebar karena dia.", partner_mode=True)

# Live A/B uses full history and two independently generated, runtime-quality candidates.
store.add_message("user", "Aku masih ragu dengan keputusan kemarin.")
store.add_message("assistant", "Bagian mana yang paling membuatmu ragu?")
llm = FakeLLM([
    "Yang paling berat itu risikonya, atau kemungkinan kamu menyesal?",
    "Aku belum mau menyimpulkan. Ceritakan dulu bagian yang paling mengganjal.",
])
live_chat = FurinaChat(cfg, store, llm)
pair = generate_live_training_pair(live_chat, "Aku takut salah memilih, tapi juga lega akhirnya punya pilihan.")
assert pair.response_a and pair.response_b and pair.response_a != pair.response_b
assert len(llm.calls) == 2
for messages, kwargs in llm.calls:
    joined = "\n".join(str(row.get("content") or "") for row in messages)
    assert "Bagian mana yang paling membuatmu ragu?" in joined
    assert kwargs.get("role") == "live_training_candidate"

print("FURINA_TERMUX_131_ADAPTIVE_VOICE_RUNTIME_OK")
