from __future__ import annotations

import os
from pathlib import Path

from furina_agent import hub_settings
from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore, _furina_120_claims
from furina_agent.output_v126 import visible_answer
from furina_agent.personality import TRAIT_IDS, compile_contextual_personality
from furina_agent.providers import OpenAICompatibleProvider
from furina_agent.response_v126 import support_strategy


root = Path(os.environ["FURINA_HOME"])

# New settings default safely and persist without the old schema dropping them.
state = hub_settings.load_hub_settings()
assert state["roleplay_mode"] is False and state["custom_personality_traits"] == []
state["roleplay_mode"] = True
state["custom_personality_traits"] = [
    {"id": "curious", "label": "Penasaran", "description": "Suka memahami alasan sebelum menyimpulkan.", "active": True},
    {"id": "quiet", "label": "Tenang", "description": "Bereaksi tanpa heboh.", "active": False},
]
hub_settings.save_hub_settings(state)
loaded = hub_settings.load_hub_settings()
assert loaded["roleplay_mode"] is True and len(loaded["custom_personality_traits"]) == 2

# Every built-in trait contributes its original action card to one stable
# personality. Custom traits coexist rather than replacing the built-ins.
context = {"partner_mode": False, "roleplay_mode": False, "custom_traits": loaded["custom_personality_traits"]}
contract = compile_contextual_personality(TRAIT_IDS, "Aku sedang bingung karena masalah kerja.", context)
for trait_id in TRAIT_IDS:
    from furina_agent.personality import TRAIT_BY_ID
    assert TRAIT_BY_ID[trait_id].label in contract
assert "Penasaran" in contract and "Tenang" not in contract
assert "RolePlay nonaktif" in contract and "semua sifat" in contract
many_custom = [{"id": f"c{i}", "label": f"Sifat {i}", "description": f"Kecenderungan unik nomor {i} yang tetap kontekstual.", "active": True} for i in range(500)]
bounded = compile_contextual_personality(TRAIT_IDS, "Obrolan biasa hari ini.", {"custom_traits": many_custom})
assert len(bounded) < 7000 and "494 sifat kustom lain" in bounded

# Emotional support begins with exploration when context is missing, then
# moves to comfort/action when the user supplies detail or asks for advice.
assert support_strategy("Aku kecewa dan capek.") == "explore"
assert support_strategy("Aku kecewa karena proyek yang kukerjakan gagal setelah berbulan-bulan.") == "comfort"
assert support_strategy("Aku kecewa. Apa yang harus kulakukan?") == "action"

# Structured explicit facts work independently of the raw full-history opt-in
# and can be injected across a new conversation through a bounded capsule.
hub_settings.save_hub_settings({**loaded, "full_local_memory": False})
store = MemoryStore(root / "memory.db")
message_id = store.add_message("user", "Aku bekerja sebagai desainer produk.")
assert message_id and _furina_120_claims("Aku bekerja sebagai desainer produk.")
claims = store.continuity_capsule()
assert any("desainer produk" in row["value"] for row in claims)

class FakeLLM:
    def chat(self, messages, **kwargs): return "ok"

cfg = load_config(); cfg.routing_mode = "online"; cfg.persona_name = "Aster"
chat = FurinaChat(cfg, store, FakeLLM())
store.create_conversation("Percakapan baru")
profile = __import__("furina_agent.response", fromlist=["choose_profile"]).choose_profile("Menurutmu ini cocok untuk pekerjaanku?", store)
messages = chat._messages("Menurutmu ini cocok untuk pekerjaanku?", profile)
system = messages[0]["content"]
assert "desainer produk" in system and "ROLEPLAY=ON" in system
assert "FINAL BEHAVIOR KERNEL V3" in system and "PERSONALITY STATE V3" in system

# Thinking is never streamed before it is sanitized. Tagged reasoning is
# removed; a naked reasoning-only response is rejected rather than exposed.
assert visible_answer("<think>rahasia</think>Jawaban bersih") == "Jawaban bersih"
assert visible_answer("Analysis: rahasia\nFinal answer: Jawaban aman") == "Jawaban aman"
assert visible_answer("Reasoning: rahasia tanpa hasil") == ""

provider = OpenAICompatibleProvider("openrouter", "test-key", cfg)
captured_payload = {}
def fake_json(method, url, payload=None, timeout=30):
    captured_payload.update(payload or {})
    return {"choices": [{"message": {"content": "Analysis: rahasia\nFinal answer: Jawaban aman"}, "finish_reason": "stop"}]}
provider._json = fake_json
visible_chunks = []
answer, finish = provider._chat_once("reasoning-model", [{"role": "user", "content": "Hai"}], max_tokens=100, temperature=.5, json_mode=False, on_token=visible_chunks.append)
assert answer == "Jawaban aman" and visible_chunks == ["Jawaban aman"] and finish == "stop"
assert captured_payload["stream"] is False and captured_payload["reasoning"] == {"exclude": True}

# Source-level UI and release contracts.
package = Path(__import__("furina_agent.personality", fromlist=["x"]).__file__).parent
tui = (package / "tui_v126.py").read_text(encoding="utf-8")
providers = (package / "output_v126.py").read_text(encoding="utf-8")
training = (package / "training_v125.py").read_text(encoding="utf-8")
assert "RolePlay ·" in tui and "Sifat kustom" in tui and 'ns["_settings"] = settings' in tui
assert "on_token=None" in providers and "on_token(cleaned)" in providers
assert "training_personality" in training and "roleplay_mode" in training

print("FURINA_TERMUX_126_BEHAVIOR_CONTINUITY_RUNTIME_OK")
