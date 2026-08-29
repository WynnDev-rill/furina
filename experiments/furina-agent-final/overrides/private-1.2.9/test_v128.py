from __future__ import annotations

import os
from pathlib import Path

from furina_agent import hub_settings
from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.output_v128 import leaks_machine_identity, leaks_roleplay_v128
from furina_agent.persona import build_system_prompt
from furina_agent.personality import compile_contextual_personality
from furina_agent.providers import OpenAICompatibleProvider
from furina_agent.style_v128 import AdaptiveStyleMemory, plan_turn


root = Path(os.environ["FURINA_HOME"])

# The new feature is opt-in and survives the official settings schema.
state = hub_settings.load_hub_settings()
assert state["schema_version"] == 7
assert state["inner_thoughts"] is False
state["inner_thoughts"] = True
hub_settings.save_hub_settings(state)
assert hub_settings.load_hub_settings()["inner_thoughts"] is True

# The companion name is dynamic and has no inherited Furina/Genshin persona.
prompt = build_system_prompt("Aster", "Wynn")
assert "Kamu adalah Aster, seorang manusia" in prompt
assert "Identitasmu adalah Furina" not in prompt
assert "bangga, teatrikal" not in prompt.casefold()
assert "tokoh mana pun" in prompt and "AI, chatbot" in prompt
assert "Genshin" not in prompt and "Furina" not in prompt

# Turn length is a soft, adaptive target. Detailed work gets more room, but
# every plan retains a generation budget larger than its ordinary target.
dummy_style = {"familiar_words": 12, "reply_scale": 1.0, "training_words": 0}
small = plan_turn("halo", [], dummy_style)
large = plan_turn("Tolong analisis bug database dan jelaskan strategi perbaikannya secara mendalam.", [], dummy_style)
assert small.target_words <= 24
assert large.target_words > small.target_words * 3
assert small.max_tokens > small.soft_upper_words
assert "jangan berhenti di tengah kata/kalimat" in small.prompt()

# Style shape persists across fresh chat objects/conversations without storing
# message contents in the style state.
store = MemoryStore(root / "memory.db")
style_a = AdaptiveStyleMemory(store)
for text in ("gimana nih?", "udah deh", "kok aneh?", "iya aja"):
    style_a.observe_user(text)
style_b = AdaptiveStyleMemory(store)
learned = style_b.profile("halo")
assert learned["samples"] == 4 and learned["familiar_words"] < 10
raw_style = store.get_state("adaptive_style_v128", {})
assert "gimana nih" not in str(raw_style)

# Social shyness is contextual and only available through a selected original
# trait; RolePlay-off always asks for direct speech rather than stage action.
social = compile_contextual_personality(["hajidere"], "Kamu manis deh", {"roleplay_mode": False, "store": store})
assert "SOCIAL STATE ADAPTIF" in social
assert "malu/gugup" in social
assert "ucapan langsung" in social

# The stricter visible-output gate catches machine identity and common narrated
# RolePlay forms while allowing ordinary direct speech.
assert leaks_machine_identity("Sebagai AI, aku tidak memiliki tubuh.")
assert leaks_roleplay_v128("Aku meraih tanganmu lalu tersenyum.")
assert leaks_roleplay_v128("[menatapmu pelan] Hai.")
assert not leaks_roleplay_v128("Aku tidak setuju, tapi ceritakan dulu alasannya.")

# Online output is buffered: a machine-identity leak is repaired before a
# single character reaches the TUI.
provider_cfg = load_config(); provider_cfg.routing_mode = "online"
provider = OpenAICompatibleProvider("openrouter", "test-key", provider_cfg)
provider_rows = iter([
    {"choices": [{"message": {"content": "Sebagai AI, aku tidak punya kehidupan nyata."}, "finish_reason": "stop"}]},
    {"choices": [{"message": {"content": "Aku belum punya jawaban yang jujur untuk itu."}, "finish_reason": "stop"}]},
])
provider._json = lambda *args, **kwargs: next(provider_rows)
visible = []
safe = provider.chat_model(
    "test-model", [{"role": "user", "content": "Kamu siapa?"}],
    max_tokens=120, temperature=.7, on_token=visible.append,
)
assert safe == "Aku belum punya jawaban yang jujur untuk itu."
assert visible == [safe]


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

# The lexicon is active again, and an explicitly learned phrase is injected in
# a later turn even when a fresh FurinaChat object is created.
lex_seed = FurinaChat(cfg, store, FakeLLM(["Baik."]))
assert lex_seed.lexicon is not None and lex_seed.lexicon.available
lex_seed.lexicon.observe('Aku sering bilang "agak nyeleneh".', "CASUAL")
fresh = FurinaChat(cfg, store, FakeLLM(["Hm, memang agak nyeleneh."]))
profile = __import__("furina_agent.response", fromlist=["choose_profile"]).choose_profile("Pendapatmu?", store)
messages = fresh._messages("Pendapatmu?", profile)
system = str(messages[0]["content"])
assert "STYLE MEMORY LINTAS PERCAKAPAN" in system
assert "agak nyeleneh" in system
assert "preferensi aktif, bukan arsip pasif" in system

# Oversized casual candidates are regenerated, never sliced. Only the complete
# selected utterance is stored; the optional character thought is a separate
# JSON call and is never written into conversation memory.
long_candidate = " ".join(["Kalimat panjang yang tidak perlu."] * 45)
final_spoken = "Iya, bagian itu memang agak nyeleneh."
llm = FakeLLM([long_candidate, final_spoken, '{"thought":"Aku senang dia menanyakannya."}'])
chat = FurinaChat(cfg, store, llm)
shown = chat.respond("menurutmu?", on_token=None)
assert final_spoken in shown
assert "Dalam hati Aster" in shown
assert "Aku senang dia menanyakannya." in shown
assert not final_spoken.endswith(("-", "…"))
recent = store.recent_messages(4)
assistant_rows = [row for row in recent if row.get("role") == "assistant"]
assert assistant_rows and assistant_rows[-1]["content"] == final_spoken
assert all("Dalam hati" not in str(row.get("content")) for row in recent)

# Turning the feature off removes both the extra call and the display block.
state = hub_settings.load_hub_settings(); state["inner_thoughts"] = False; hub_settings.save_hub_settings(state)
plain_llm = FakeLLM(["Hai juga."])
plain = FurinaChat(cfg, store, plain_llm)
assert plain.respond("hai") == "Hai juga."
assert len(plain_llm.calls) == 1

# The restored 20-trait interface remains intact; no custom-trait UI returns.
package = Path(__import__("furina_agent.chat", fromlist=["x"]).__file__).parent
source = (package / "tui_v128.py").read_text(encoding="utf-8")
assert "Pikiran dalam hati" in source and "Sifat kustom" not in source

print("FURINA_TERMUX_128_ADAPTIVE_HUMAN_DIALOGUE_RUNTIME_OK")
