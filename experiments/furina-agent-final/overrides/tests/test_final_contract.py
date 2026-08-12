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
        self.assertIn("sinis", prompt.lower())
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

    def test_memory_beliefs_episodes_relationship_and_reranking(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            store.add_memory("Wynn suka teh dingin", "preference", 0.8, confidence=0.9)
            store.add_memory("Wynn ingin menyelesaikan proyek Furina", "goal", 0.9, confidence=0.85)
            results = store.search("Furina proyek", 3)
            self.assertTrue(any("Furina" in m.text for m in results))

            store.upsert_belief("preference", "lebih suka jawaban ringkas", 0.72)
            store.upsert_belief("preference", "lebih suka jawaban ringkas", 0.82)
            beliefs = store.beliefs("preference", 0.5)
            self.assertEqual(len(beliefs), 1)
            self.assertGreaterEqual(beliefs[0].evidence, 2)
            self.assertGreater(beliefs[0].confidence, 0.7)
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
            llm = JsonLLM([
                '{"done":true,"confidence":0.96,"result":"Pencarian selesai.","reason":"hasil target terlihat"}'
            ])
            agent = AndroidAgent(Config(), store, llm, DummyBridge())
            status = agent._verify_goal(
                "buka app lalu cari Wynn",
                TaskContract("cari Wynn", ["hasil pencarian Wynn tampil"], False),
                {"package": "example.app", "nodes": [{"text": "Wynn", "clickable": True}]},
                [{"action": {"type": "ime_action", "node": 2}, "result": {"ok": True}, "state_changed": True}],
            )
            self.assertTrue(status.done)
            self.assertGreater(status.confidence, 0.9)

    def test_agent_supports_universal_actions_and_stable_targets(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "mind.db")
            agent = AndroidAgent(Config(), store, JsonLLM([]), DummyBridge())
            screen = {"nodes": [{"id": 7, "view_id": "composer", "text": "Message", "class": "EditText", "editable": True, "focusable": True, "bounds": [1, 2, 300, 90]}]}
            payload = agent._enrich_action(screen, {"type": "set_text", "node": 7, "text": "halo"})
            self.assertEqual(payload["target"]["view_id"], "composer")
            self.assertTrue(payload["target"]["editable"])
            self.assertIn("long_press", __import__("furina_agent.agent", fromlist=["ALLOWED"]).ALLOWED)
            self.assertIn("scroll_node", __import__("furina_agent.agent", fromlist=["ALLOWED"]).ALLOWED)

    def test_bridge_rc5_has_generic_controls(self):
        root = Path(__file__).resolve().parents[1]
        service = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java").read_text()
        gradle = (root / "bridge/app/build.gradle").read_text()
        self.assertIn('case "long_press"', service)
        self.assertIn('case "scroll_node"', service)
        self.assertIn("ACTION_PASTE", service)
        self.assertIn('j.put("actions", actions)', service)
        self.assertIn('out.put("window_title"', service)
        self.assertIn("selectorScore", service)
        self.assertIn("ACTION_IME_ENTER", service)
        self.assertIn("versionCode 10005", gradle)
        self.assertIn("versionName '1.0.0-rc5'", gradle)

    def test_vision_fallback_is_present(self):
        root = Path(__file__).resolve().parents[1]
        routing = (root / "core/furina_agent/routing.py").read_text()
        vision = (root / "core/furina_agent/vision.py").read_text()
        agent = (root / "core/furina_agent/agent.py").read_text()
        self.assertIn("OnlineVision", routing)
        self.assertIn("image_url", vision)
        self.assertIn("_with_vision", agent)
        self.assertIn("vision_elements", agent)


if __name__ == "__main__":
    unittest.main()
