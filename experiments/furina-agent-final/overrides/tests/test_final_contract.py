import tempfile
import unittest
from pathlib import Path

from furina_agent.agent import AndroidAgent, TaskContract
from furina_agent.companion import _obvious_device_intent
from furina_agent.config import Config
from furina_agent.llm import LocalLLM, sanitize
from furina_agent.memory import MemoryStore
from furina_agent.persona import build_system_prompt
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
    def test_persona_uses_dialogue_anchors_and_avoids_customer_service(self):
        prompt = build_system_prompt("Furina", "Wynn")
        self.assertIn("Nama panggilan pengguna adalah Wynn", prompt)
        self.assertIn("CONTOH RITME DAN KARAKTER", prompt)
        self.assertIn("Jangan otomatis menutup", prompt)
        self.assertIn("Jangan menyebut atau menganggap dirimu AI", prompt)
        self.assertIn("tsundere", prompt.lower())
        self.assertIn("Sinisme hanya bumbu situasional", prompt)
        self.assertIn("sense of drama", prompt)
        self.assertIn("Jangan gunakan emoji", prompt)
        self.assertIn("chain-of-thought", prompt)

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

    def test_memory_beliefs_episodes_relationship_and_hybrid_schema(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            store.add_memory("Wynn suka teh dingin", "preference", 0.8, confidence=0.9)
            store.add_memory("Wynn ingin menyelesaikan proyek Furina", "goal", 0.9, confidence=0.85)
            results = store.search("Furina proyek", 3)
            self.assertTrue(any("Furina" in m.text for m in results))
            tables = {r[0] for r in store._conn().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            self.assertIn("memory_vectors", tables)
            self.assertIn("learned_skills", tables)
            self.assertEqual(store.vector_coverage(), (0, 2))

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
            self.assertIn("example.notes", goal_text)
            self.assertTrue(store.find_skills("buka catatan dan tulis teks", "example.notes", 3))
            self.assertFalse(store.find_skills("perintah tidak berhubungan", "", 3))

    def test_response_router_is_contextual(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            self.assertEqual(choose_profile("hi", store).name, "REFLEX")
            self.assertEqual(choose_profile("ada bug python di api json", store).name, "SHARP")
            self.assertEqual(choose_profile("aku merasa capek dan kecewa hari ini", store).name, "CLOSE")
            self.assertEqual(choose_profile("tolong analisis strategi ini secara menyeluruh dan bandingkan tradeoff yang ada", store).name, "DEEP")

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
            scroll_contract = TaskContract("scroll", ["3 scroll"], False, 3, "", "")
            history = [{"action": {"type": "scroll_global"}, "result": {"ok": True}, "state_changed": True} for _ in range(2)]
            ok, reason = agent._deterministic_gate(scroll_contract, {"package": "tiktok", "nodes": []}, history)
            self.assertFalse(ok)
            self.assertIn("2/3", reason)
            history.append({"action": {"type": "scroll_global"}, "result": {"ok": True}, "scroll_event": True})
            self.assertTrue(agent._deterministic_gate(scroll_contract, {"package": "tiktok", "nodes": []}, history)[0])

    def test_agent_supports_universal_actions_and_stable_targets(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            agent = AndroidAgent(Config(), store, JsonLLM([]), DummyBridge())
            screen = {"nodes": [{"id": 7, "view_id": "composer", "text": "Message", "class": "EditText", "editable": True, "focusable": True, "bounds": [1, 2, 300, 90]}]}
            payload = agent._enrich_action(screen, {"type": "set_text", "node": 7, "text": "halo"})
            self.assertEqual(payload["target"]["view_id"], "composer")
            allowed = __import__("furina_agent.agent", fromlist=["ALLOWED"]).ALLOWED
            self.assertIn("long_press", allowed)
            self.assertIn("scroll_node", allowed)
            self.assertIn("scroll_global", allowed)

    def test_rc7_reliability_temporal_and_bridge_ui_contract(self):
        root = Path(__file__).resolve().parents[1]
        service = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java").read_text()
        activity = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java").read_text()
        manifest = (root / "bridge/app/src/main/AndroidManifest.xml").read_text()
        gradle = (root / "bridge/app/build.gradle").read_text()
        agent = (root / "core/furina_agent/agent.py").read_text()
        chat = (root / "core/furina_agent/chat.py").read_text()
        events = (root / "core/furina_agent/events.py").read_text()
        config = (root / "core/furina_agent/config.py").read_text()

        self.assertIn("waitForExactText", service)
        self.assertNotIn("actual.contains(expected)", service)
        self.assertIn("duplicate_suppressed", agent)
        self.assertIn("watch_user_return", agent)
        self.assertIn("_interruptible", agent)
        self.assertIn("if not (screen.get(\"nodes\") or []) or stalls >= 2", agent)
        self.assertIn("_temporal_context", chat)
        self.assertIn("companion_last_user_at", chat)
        self.assertIn("_internal_chat", chat)
        self.assertIn("user_returned_to_termux_at", events)
        self.assertIn("config_revision: int = 7", config)
        self.assertIn("setOnApplyWindowInsetsListener", activity)
        self.assertIn("setDecorFitsSystemWindows(false)", activity)
        self.assertIn('android:icon="@mipmap/ic_launcher"', manifest)
        self.assertIn("versionCode 10007", gradle)
        self.assertIn("versionName '1.0.0-rc7'", gradle)

    def test_rc6_review_fixes_are_preserved(self):
        root = Path(__file__).resolve().parents[1]
        local_vision = (root / "core/furina_agent/local_vision.py").read_text()
        config = (root / "core/furina_agent/config.py").read_text()
        agent = (root / "core/furina_agent/agent.py").read_text()
        memory = (root / "core/furina_agent/memory.py").read_text()
        start_block = local_vision.split("    def _start(self) -> None:", 1)[1].split("    def analyze(", 1)[0]
        self.assertNotIn("_schedule_idle_stop()", start_block)
        self.assertIn("finally:", local_vision)
        self.assertIn('defaults["event_port"] = 8767', config)
        self.assertIn("contract.target_package", agent)
        self.assertIn('compact_goal = ("app="', memory)
        self.assertNotIn('compact_goal = " ".join(str(goal).split())', memory)

    def test_local_vision_and_embedding_sidecars_are_present(self):
        root = Path(__file__).resolve().parents[1]
        routing = (root / "core/furina_agent/routing.py").read_text()
        local_vision = (root / "core/furina_agent/local_vision.py").read_text()
        embeddings = (root / "core/furina_agent/embeddings.py").read_text()
        events = (root / "core/furina_agent/events.py").read_text()
        agent = (root / "core/furina_agent/agent.py").read_text()
        self.assertIn("LocalVision", routing)
        self.assertIn("--mmproj", local_vision)
        self.assertIn('"/embedding"', embeddings)
        self.assertIn("socket.SOCK_DGRAM", events)
        self.assertIn("_with_vision", agent)
        self.assertIn("agent_cancelled_user_return", agent)


if __name__ == "__main__":
    unittest.main()
