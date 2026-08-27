from __future__ import annotations

import ast
import json
import os
from pathlib import Path

from furina_agent import hub_settings
from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.neutral_corpus import load_neutral_corpus, prompt_fingerprint
from furina_agent.training_room import (
    CATEGORIES,
    generate_live_training_pair,
    LiveTrainingPair,
    TrainingSession,
    load_training_state,
    record_live_training_choice,
    record_live_training_skip,
    should_offer_live_training,
)


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict], dict]] = []

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if kwargs.get("role") == "training_prompt":
            return json.dumps({"context": "Obrolan netral berlanjut.", "prompt": "Aku belum yakin harus mulai dari bagian mana."})
        return json.dumps({"a": "Jawaban pertama yang layak.", "b": "Jawaban kedua yang juga layak."})


root = Path(os.environ["FURINA_HOME"])
corpus = load_neutral_corpus()
assert len(corpus) >= 90
assert len(CATEGORIES) == 9
for row in corpus:
    text = (row["context"] + " " + row["prompt"]).casefold()
    assert not any(word in text for word in ("furina", "genshin", "fontaine", "archon", "teyvat"))

# The single Advanced toggle is a first-class settings field. It survives the
# normalize/save/load round trip instead of being discarded by the old schema.
fresh_settings = hub_settings.load_hub_settings()
assert fresh_settings["training_suggestions"] is False
fresh_settings["training_suggestions"] = True
hub_settings.save_hub_settings(fresh_settings)
assert hub_settings.load_hub_settings()["training_suggestions"] is True

# An answered legacy prompt becomes globally retired without losing counts.
legacy_path = root / "legacy.json"
legacy_text = corpus[0]["prompt"]
legacy_path.write_text(json.dumps({
    "schema": 1,
    "counts": {"natural": {"directness": {"langsung dan spontan": 29}}},
    "decisions": [{"category": "natural", "simulated_user": legacy_text}],
    "updated_at": 1,
}), encoding="utf-8")
legacy = load_training_state(legacy_path)
assert "fp:" + prompt_fingerprint(legacy_text) in legacy["retired_prompt_ids"]
assert legacy["counts"]["natural"]["directness"]["langsung dan spontan"] == 29

# Skip permanently retires the prompt, records no vote, and the same prompt
# cannot reappear even if another category can draw it.
skip_path = root / "skip.json"
first = TrainingSession("natural", FakeLLM(), state_path=skip_path, seed="same-seed")
first_pair = first.generate()
first_id = first.prompt_125["id"]
first_text = first_pair.user_text
first.skip()
skipped = load_training_state(skip_path)
assert first_id in skipped["retired_prompt_ids"]
assert skipped["skipped_prompts"] == 1 and not skipped["decisions"]
for category in CATEGORIES:
    session = TrainingSession(category, FakeLLM(), state_path=skip_path, seed="same-seed")
    pair = session.generate()
    assert pair.user_text != first_text

# A/B choice also retires its prompt and increments only the abstract count.
choice_path = root / "choice.json"
chosen = TrainingSession("emotional", FakeLLM(), state_path=choice_path, seed="choice")
pair = chosen.generate()
prompt_id = chosen.prompt_125["id"]
chosen.choose("a")
state = load_training_state(choice_path)
assert prompt_id in state["retired_prompt_ids"]
assert sum(sum(v.values()) for v in state["counts"]["emotional"].values()) == 1

# R keeps the same prompt while persisting only its rejection reason.
reroll_path = root / "reroll.json"
rerolled = TrainingSession("language", FakeLLM(), state_path=reroll_path, seed="reroll")
original = rerolled.generate()
original_id = rerolled.prompt_125["id"]
rerolled.reject_pair("generic")
again = rerolled.generate()
assert rerolled.prompt_125["id"] == original_id and again.user_text == original.user_text
assert original_id not in load_training_state(reroll_path)["retired_prompt_ids"]

# Every category is backed by a neutral prompt. Persona/relationship terms are
# introduced only into the response-generation call, never into the corpus.
for category in CATEGORIES:
    llm = FakeLLM()
    session = TrainingSession(category, llm, state_path=root / f"{category}.json", seed=category)
    pair = session.generate()
    assert pair.response_a != pair.response_b
    response_prompt = llm.calls[-1][0][1]["content"]
    assert pair.user_text in response_prompt and "Preferensi lama" in response_prompt

# Live suggestions are opt-in, delayed, bounded, and excluded for technical or
# crisis turns. Skip extends the cooldown and never writes a preference vote.
hub_settings.load_hub_settings = lambda: {"training_suggestions": False}
live_path = root / "live.json"
assert not should_offer_live_training("Aku bingung harus memilih yang mana sekarang.", path=live_path)
hub_settings.load_hub_settings = lambda: {"training_suggestions": True}
for _ in range(7):
    assert not should_offer_live_training("Aku bingung harus memilih yang mana sekarang.", path=live_path)
assert should_offer_live_training("Aku bingung harus memilih yang mana sekarang.", path=live_path)
assert not should_offer_live_training("Tolong perbaiki error kode Python ini sekarang.", path=live_path)
assert not should_offer_live_training("Aku ingin bunuh diri dan ini darurat.", path=live_path)
assert not should_offer_live_training("Aku bingung harus memilih yang mana sekarang.", session_offers=2, path=live_path)
before = len(load_training_state(live_path)["decisions"])
record_live_training_skip(live_path)
assert len(load_training_state(live_path)["decisions"]) == before
for _ in range(11):
    assert not should_offer_live_training("Aku kecewa tetapi juga sedikit lega hari ini.", path=live_path)

# An explicit live A/B choice stores only a hash and abstract poles in the
# training store—not a duplicate of the real message or generated answers.
private_text = "Pesan pribadi yang tidak boleh disalin ke data latihan"
live_pair = LiveTrainingPair("natural", "directness", "langsung dan spontan", "lebih bertahap dan reflektif", "Pilih aku A", "Pilih aku B", prompt_fingerprint(private_text))
assert record_live_training_choice(live_pair, "b", live_path) == "Pilih aku B"
raw = live_path.read_text(encoding="utf-8")
assert private_text not in raw and "Pilih aku A" not in raw and "Pilih aku B" not in raw
assert prompt_fingerprint(private_text) in raw

# Live candidate generation reuses the real chat composer, so current persona,
# partner state, memory and learned preference contract reach both candidates.
store = MemoryStore(root / "live-chat.db")
cfg = load_config()
cfg.persona_name = "Aster"
live_llm = FakeLLM()
chat = FurinaChat(cfg, store, live_llm)
hub_settings.load_hub_settings = lambda: {"training_suggestions": True, "partner_mode": True, "personality_traits": []}
generated = generate_live_training_pair(chat, "Aku kecewa tetapi juga lega karena akhirnya selesai.")
assert generated.response_a != generated.response_b
live_system = live_llm.calls[-1][0][0]["content"]
assert "Aster" in live_system and "LIVE PREFERENCE CHOICE" in live_system

# Choosing A/B commits one real user turn and only the selected answer. The
# rejected candidate is never written to normal conversation history.
before_messages = len(store.recent_messages(50))
chat.commit_preferred_response("Pesan chat untuk pilihan langsung.", "Respons yang dipilih langsung.")
recent = store.recent_messages(50)
new_messages = recent[before_messages:]
assert [row["role"] for row in new_messages] == ["user", "assistant"]
assert [row["content"] for row in new_messages] == ["Pesan chat untuk pilihan langsung.", "Respons yang dipilih langsung."]

# UI contract: horizontal carousel and one Advanced toggle, with no frequency
# selector. The sandbox remains structurally isolated from real-chat memory.
package = Path(__import__("furina_agent.training_room").training_room.__file__).parent
surface = (package / "chat_surface.py").read_text(encoding="utf-8")
tui = (package / "tui_v125.py").read_text(encoding="utf-8")
training = (package / "training_v125.py").read_text(encoding="utf-8")
assert "class LiveChoiceScreen" in surface and '("a", "b", "skip")' in surface
assert "Respons A[/]" in surface and "Respons B[/]" in surface
assert "← → pilih  ·  Enter konfirmasi  ·  Esc lewati" not in surface and 'self._live_offers = 0' in surface
assert "Saran latihan di chat" in tui and "Frekuensi" not in tui
assert 'actions = ("Respons A", "Respons B", "Lewati"' in tui and "← → pilih  ·  Enter konfirmasi  ·  Esc selesai" not in tui
imports = "\n".join(ast.get_source_segment(training, node) or "" for node in ast.walk(ast.parse(training)) if isinstance(node, (ast.Import, ast.ImportFrom)))
assert "MemoryStore" not in imports and "FurinaChat" not in imports

print("FURINA_TERMUX_125_NEUTRAL_LIVE_TRAINING_RUNTIME_OK")
