import tempfile
import time
import unittest
from pathlib import Path

from furina_agent.agent import AndroidAgent, TaskContract
from furina_agent.companion import _obvious_device_intent
from furina_agent.config import Config
from furina_agent.fastpath import choose_fast_skill, compile_fast_contract
from furina_agent.lexicon import PersonalLexicon
from furina_agent.llm import LocalLLM, sanitize
from furina_agent.memory import MemoryStore
from furina_agent.naturalness import naturalize
from furina_agent.persona import build_system_prompt
from furina_agent.prospective import extract_prospectives
from furina_agent.response import choose_profile


class FakeLocal(LocalLLM):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.calls = 0

    def _request_once(self, messages, *, max_tokens, temperature, on_token, json_mode=False):
        self.calls += 1
        if self.calls == 1:
            if on_token:
                on_token("Kalimat pertama belum ")
            return "Kalimat pertama belum", "length"
        if on_token:
            on_token("selesai.")
        return "selesai.", "stop"


class JsonLLM:
    def __init__(self, outputs):
        self.outputs = list(outputs)

    def chat(self, *args, **kwargs):
        if not self.outputs:
            raise AssertionError("no JSON output left")
        return self.outputs.pop(0)


class DummyBridge:
    pass


class FinalContractTests(unittest.TestCase):
    def test_persona_is_balanced_contextual_and_human_sounding(self):
        prompt = build_system_prompt("Furina", "Wynn")
        self.assertIn("Nama panggilan pengguna adalah Wynn", prompt)
        self.assertIn("CONTOH RITME DAN KARAKTER", prompt)
        self.assertIn("Jangan menyebut atau menganggap dirimu AI", prompt)
        self.assertIn("tsundere", prompt.lower())
        self.assertIn("Sinis dan sarkas adalah bagian dirimu, tetapi bukan nada default", prompt)
        self.assertIn("Hindari kebiasaan bahasa AI", prompt)
        self.assertIn("aku sedih", prompt)
        self.assertIn("sok tau", prompt)
        self.assertIn("Jangan gunakan emoji", prompt)
        self.assertIn("chain-of-thought", prompt)

    def test_naturalness_guard_is_conservative_and_preserves_code(self):
        text = "Tentu saja, perlu dicatat bahwa dalam konteks ini hal tersebut penting. Jika kamu mau, aku bisa bantu menjelaskannya."
        out = naturalize(text)
        self.assertNotIn("Tentu saja", out)
        self.assertNotIn("perlu dicatat", out.lower())
        self.assertNotIn("dalam konteks ini", out.lower())
        self.assertNotIn("aku bisa bantu", out.lower())
        code = "```python\nprint('dengan demikian')\n```"
        self.assertIn(code, naturalize("Dengan demikian, coba ini:\n" + code))

    def test_personal_lexicon_deduplicates_and_requires_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            lex = PersonalLexicon(store)
            lex.observe('pakai kata "yaudah"', "CASUAL")
            lex.observe('gunakan kata "Yaudah"', "CASUAL")
            rows = store._conn().execute("SELECT * FROM personal_lexicon WHERE canonical='yaudah'").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(int(rows[0]["explicit_count"]), 2)
            self.assertGreaterEqual(int(rows[0]["seen_count"]), 2)
            self.assertIn("Yaudah", lex.prompt_context("oke", "CASUAL"))

            # Automatic forms need repetition before they can influence a prompt.
            lex.observe("kayaknya hasilnya masuk akal", "CASUAL")
            first = lex.prompt_context("menurutmu gimana", "CASUAL", auto_min_seen=2)
            lex.observe("kayaknya ini lebih enak", "CASUAL")
            second = lex.prompt_context("menurutmu gimana", "CASUAL", auto_min_seen=2)
            self.assertNotEqual(first, second)
            self.assertIn("kayaknya", second.lower())

            before = lex.count()
            lex.observe("password abc123 token rahasia", "CASUAL")
            self.assertEqual(before, lex.count())

    def test_fast_contract_and_skill_selection_skip_planner_when_safe(self):
        apps = [{"label": "YouTube", "package": "com.google.android.youtube"}]
        contract = compile_fast_contract("buka YouTube lalu cari kucing", apps)
        self.assertIsNotNone(contract)
        self.assertEqual(contract["target_package"], "com.google.android.youtube")
        self.assertEqual(contract["required_write_text"], "kucing")
        self.assertIn("cari", contract["fast_tags"])
        self.assertIsNone(compile_fast_contract("buka YouTube lalu kirim komentar", apps))

        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            history = [
                {"executed": {"type": "open_app", "package": "com.google.android.youtube"}, "result": {"ok": True}},
                {"executed": {"type": "set_text", "text": "lama", "target": {"view_id": "search", "class": "EditText", "editable": True}}, "result": {"ok": True, "verified_text": True}},
                {"executed": {"type": "ime_action", "target": {"view_id": "search", "class": "EditText", "editable": True}}, "result": {"ok": True}},
            ]
            store.learn_skill("buka YouTube lalu cari lama", history, "com.google.android.youtube")
            store.learn_skill("buka YouTube lalu cari baru", history, "com.google.android.youtube")
            skill = choose_fast_skill(store, "buka YouTube lalu cari kucing", "com.google.android.youtube", 2)
            self.assertIsNotNone(skill)
            self.assertGreaterEqual(skill.success_count, 2)
            self.assertGreater(skill.score, 0.72)

    def test_explicit_prospective_memory_parser_and_store(self):
        now = 1_700_000_000.0
        parsed = extract_prospectives("ingatkan aku minum air dalam 10 menit", now=now)
        self.assertEqual(len(parsed), 1)
        self.assertAlmostEqual(parsed[0][1] - now, 600, delta=1)
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            rid = store.add_prospective("ingatkan tes", time.time() - 1)
            self.assertGreater(rid, 0)
            due = store.due_prospectives(time.time(), 4)
            self.assertTrue(any(int(x["id"]) == rid for x in due))
            store.mark_prospective_fired(rid)
            self.assertFalse(any(int(x["id"]) == rid for x in store.due_prospectives(time.time(), 4)))

    def test_sanitizer_removes_reasoning_and_emoji(self):
        self.assertEqual(sanitize("<think>rahasia</think>Hai 😛"), "Hai")
        self.assertEqual(sanitize("<analysis>belum selesai"), "")

    def test_local_length_finish_auto_continues(self):
        cfg = Config(max_tokens=64, response_continuations=4)
        llm = FakeLocal(cfg)
        chunks = []
        text = llm.chat([{"role": "user", "content": "tes"}], on_token=chunks.append)
        self.assertEqual(llm.calls, 2)
        self.assertIn("selesai.", text)
        self.assertEqual("".join(chunks), "Kalimat pertama belum selesai.")

    def test_arbitrary_app_commands_route_to_device(self):
        self.assertTrue(_obvious_device_intent("buka Tokopedia lalu cari laptop"))
        self.assertTrue(_obvious_device_intent("buka Discord dan cari Wynn lalu kirim pesan"))
        self.assertTrue(_obvious_device_intent("buka aplikasi aneh-yang-baru"))
        self.assertFalse(_obvious_device_intent("bagaimana cara buka Tokopedia"))

    def test_memory_beliefs_episodes_relationship_and_rc8_schema(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            store.add_memory("Wynn suka teh dingin", "preference", 0.8, confidence=0.9)
            store.add_memory("Wynn ingin menyelesaikan proyek Furina", "goal", 0.9, confidence=0.85)
            results = store.search("Furina proyek", 3)
            self.assertTrue(any("Furina" in m.text for m in results))
            tables = {r[0] for r in store._conn().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            self.assertIn("memory_vectors", tables)
            self.assertIn("memory_vector_lsh", tables)
            self.assertIn("prospective_memories", tables)
            self.assertIn("learned_skills", tables)
            self.assertEqual(store.vector_coverage(), (0, 2))
            b1, b2 = store._lsh_buckets([1.0, -1.0] * 16)
            self.assertIn(b1, store._lsh_neighbors(b1))
            self.assertIsInstance(b2, int)

            store.upsert_belief("preference", "lebih suka jawaban ringkas", 0.72)
            store.upsert_belief("preference", "lebih suka jawaban ringkas", 0.82)
            beliefs = store.beliefs("preference", 0.5)
            self.assertEqual(len(beliefs), 1)
            self.assertGreaterEqual(beliefs[0].evidence, 2)
            store.contradict_belief("preference", "ringkas", "lebih suka jawaban detail", 0.75)
            active = store.beliefs("preference", 0.5)
            self.assertTrue(any("detail" in b.value for b in active))
            self.assertFalse(any("ringkas" in b.value for b in active))

            store.add_episode("Hari ini Furina berhasil mengendalikan YouTube dan mencari channel.", ["android", "milestone"], 0.8, 0.6)
            self.assertTrue(store.search_episodes("YouTube", 2))
            before = store.relationship_state()
            after = store.update_relationship("jujur aku percaya padamu, makasih")
            self.assertGreater(after["closeness"], before["closeness"])
            self.assertGreater(after["trust"], before["trust"])

    def test_skill_learning_never_persists_literal_goal_or_screen_pii(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            history = [
                {"action": {"type": "open_app", "package": "example.notes"}, "executed": {"type": "open_app", "package": "example.notes"}, "result": {"ok": True}},
                {"action": {"type": "set_text", "node": 7, "text": "password abc123"}, "executed": {"type": "set_text", "node": 7, "text": "password abc123", "target": {"view_id": "editor", "text": "Wynn private note", "desc": "personal editor", "class": "EditText", "editable": True}}, "result": {"ok": True, "verified_text": True}},
            ]
            sid = store.learn_skill('buka catatan lalu tulis "password abc123"', history, "example.notes")
            self.assertIsNotNone(sid)
            row = store._conn().execute("SELECT goal_text,steps_json FROM learned_skills WHERE id=?", (sid,)).fetchone()
            goal_text, steps_json = row[0], row[1]
            for secret in ("password abc123", "Wynn private note", "personal editor"):
                self.assertNotIn(secret, goal_text)
                self.assertNotIn(secret, steps_json)
            self.assertIn("from_current_goal", steps_json)
            self.assertIn("intent=", goal_text)

    def test_response_router_is_contextual(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            self.assertEqual(choose_profile("hi", store).name, "REFLEX")
            self.assertEqual(choose_profile("ada bug python di api json", store).name, "SHARP")
            close = choose_profile("aku merasa capek dan kecewa hari ini", store)
            self.assertEqual(close.name, "CLOSE")
            self.assertIn("perhatian", close.instruction)
            playful = choose_profile("wkwk kamu nyebelin", store)
            self.assertIn("banter", playful.instruction.lower())

    def test_generic_goal_verifier_stops_after_success(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            llm = JsonLLM(['{"done":true,"confidence":0.96,"result":"Pencarian selesai.","reason":"hasil target terlihat"}'])
            agent = AndroidAgent(Config(), store, llm, DummyBridge())
            status = agent._verify_goal("buka app lalu cari Wynn", TaskContract("cari Wynn", ["hasil pencarian Wynn tampil"], False), {"package": "example.app", "nodes": [{"text": "Wynn", "clickable": True}]}, [{"action": {"type": "ime_action", "node": 2}, "result": {"ok": True}, "state_changed": True}])
            self.assertTrue(status.done)

    def test_hard_evidence_gate_blocks_fake_write_and_missing_scrolls(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            agent = AndroidAgent(Config(), store, JsonLLM([]), DummyBridge())
            contract = TaskContract("tulis", ["teks ada"], False, 0, "furina", "example.notes")
            ok, reason = agent._deterministic_gate(contract, {"package": "example.notes", "nodes": []}, [])
            self.assertFalse(ok)
            self.assertIn("belum terbukti", reason)
            ok, _ = agent._deterministic_gate(contract, {"package": "example.notes", "nodes": []}, [{"action": {"type": "set_text", "text": "furina"}, "result": {"ok": True, "verified_text": True}}])
            self.assertTrue(ok)

    def test_rc7_control_reliability_is_preserved_under_rc9(self):
        root = Path(__file__).resolve().parents[1]
        service = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java").read_text()
        activity = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java").read_text()
        gradle = (root / "bridge/app/build.gradle").read_text()
        agent = (root / "core/furina_agent/agent.py").read_text()
        config = (root / "core/furina_agent/config.py").read_text()
        chat = (root / "core/furina_agent/chat.py").read_text()
        self.assertIn("waitForExactText", service)
        self.assertNotIn("actual.contains(expected)", service)
        self.assertIn("duplicate_suppressed", agent)
        self.assertIn("watch_user_return", agent)
        self.assertIn("if not (screen.get(\"nodes\") or []) or stalls >= 2", agent)
        self.assertIn("_try_fast_skill", agent)
        self.assertIn("_wait_after_action", agent)
        self.assertNotIn('time.sleep(0.9 if typ == "open_app" else 0.48)', agent)
        self.assertIn("config_revision: int = 9", config)
        self.assertIn("PERSONAL LEXICON", chat)
        self.assertIn("setOnApplyWindowInsetsListener", activity)
        self.assertIn("versionCode 10007", gradle)
        self.assertIn("versionName '1.0.0-rc7'", gradle)


if __name__ == "__main__":
    unittest.main()
