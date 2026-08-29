from __future__ import annotations

import os
from pathlib import Path

from furina_agent import hub_settings
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.output_v127 import leaks_reasoning, leaks_roleplay
from furina_agent.personality import TRAIT_IDS, compile_contextual_personality
from furina_agent.providers import OpenAICompatibleProvider, ProviderError


root = Path(os.environ["FURINA_HOME"])

# Migration removes both the custom-trait UI and its hidden saved behavior.
state = hub_settings.load_hub_settings()
state["custom_personality_traits"] = [{"id": "x", "label": "X", "description": "Tidak boleh bertahan"}]
state["roleplay_mode"] = False
hub_settings.save_hub_settings(state)
loaded = hub_settings.load_hub_settings()
assert loaded["schema_version"] == 6
assert "custom_personality_traits" not in loaded
assert loaded["roleplay_mode"] is False

# The improved coexistence logic remains, but only the original 20 traits can
# participate and the prompt has no custom-trait concept.
contract = compile_contextual_personality(TRAIT_IDS, "Aku capek karena masalah kerja.", {"roleplay_mode": False})
assert "20 sifat bawaan" in contract and "RolePlay nonaktif" in contract
assert "sifat kustom" not in contract.casefold()
for trait_id in TRAIT_IDS:
    from furina_agent.personality import TRAIT_BY_ID
    assert TRAIT_BY_ID[trait_id].label in contract

# The former two-column 20-trait selector is restored rather than replaced by
# the temporary built-in/custom submenu.
package = Path(__import__("furina_agent.personality", fromlist=["x"]).__file__).parent
source = (package / "tui_v127.py").read_text(encoding="utf-8")
assert "Sifat kustom" not in source and "/20 sifat aktif" in source
from furina_agent.tui_v127 import install_tui_v127
original_selector = object()
fake_ns = {
    "_private_personalization_116": original_selector,
    "_clear": lambda: None,
    "_header": lambda *args: None,
    "_choose": lambda *args, **kwargs: "Kembali",
}
install_tui_v127(fake_ns)
assert fake_ns["_private_personalization_117"] is original_selector
assert fake_ns["_private_personalization_110"] is original_selector

# Screenshot-shaped naked reasoning is recognized even without think tags.
leak = 'Okay, the user just said "halo" again. Let me check the history.\nLooking back at the conversation:'
assert leaks_reasoning(leak)
assert leaks_reasoning("We need to answer the user directly.")
assert not leaks_reasoning("Halo. Lagi santai atau ada yang ingin kamu ceritakan?")
assert leaks_roleplay("*tersenyum lalu mendekat* Hai.")
assert leaks_roleplay("Aku perlahan memelukmu. Tenang saja.")
assert leaks_roleplay("Aku baru saja selesai ngopi, jadi kamu mau ikutan?")
assert not leaks_roleplay("Bagian *penting* ini perlu diperiksa.")

# Unsafe online output is never emitted. One corrected retry is allowed; a
# second unsafe result fails closed so routing can try another model.
cfg = load_config(); cfg.routing_mode = "online"
provider = OpenAICompatibleProvider("openrouter", "test-key", cfg)
responses = iter([
    {"choices": [{"message": {"content": leak}, "finish_reason": "stop"}]},
    {"choices": [{"message": {"content": "Halo. Ada apa?"}, "finish_reason": "stop"}]},
])
calls = []
def fake_json(method, url, payload=None, timeout=30):
    calls.append(payload)
    return next(responses)
provider._json = fake_json
visible = []
answer = provider.chat_model("reasoning-model", [{"role": "user", "content": "halo"}], max_tokens=120, temperature=.7, on_token=visible.append)
assert answer == "Halo. Ada apa?" and visible == ["Halo. Ada apa?"] and len(calls) == 2
assert "OUTPUT SAFETY CORRECTION" in calls[1]["messages"][0]["content"]

provider2 = OpenAICompatibleProvider("openrouter", "test-key", cfg)
responses2 = iter([
    {"choices": [{"message": {"content": "*tersenyum dan mendekat* Hai."}, "finish_reason": "stop"}]},
    {"choices": [{"message": {"content": "Aku memelukmu. Hai."}, "finish_reason": "stop"}]},
])
provider2._json = lambda *args, **kwargs: next(responses2)
try:
    provider2.chat_model("roleplay-model", [{"role": "user", "content": "hai"}], max_tokens=120, temperature=.7)
except ProviderError:
    pass
else:
    raise AssertionError("RolePlay leak must fail closed after retry")

# Old leaked assistant turns are quarantined from future online context without
# deleting the user's database.
from furina_agent.chat import FurinaChat
class FakeLLM:
    def chat(self, messages, **kwargs): return "ok"
store = MemoryStore(root / "memory.db")
store.create_conversation("Uji")
store.add_message("user", "halo")
store.add_message("assistant", leak)
chat = FurinaChat(cfg, store, FakeLLM())
profile = __import__("furina_agent.response", fromlist=["choose_profile"]).choose_profile("halo lagi", store)
messages = chat._messages("halo lagi", profile)
assert all(leak not in str(row.get("content")) for row in messages)

print("FURINA_TERMUX_127_OUTPUT_PERSONALITY_RUNTIME_OK")
