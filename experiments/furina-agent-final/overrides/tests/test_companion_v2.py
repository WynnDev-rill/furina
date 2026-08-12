import unittest

from furina_agent.agent import AndroidAgent
from furina_agent.companion import _obvious_device_intent
from furina_agent.config import Config
from furina_agent.providers import OpenAICompatibleProvider


class DummyStore:
    def log_event(self, *args, **kwargs):
        pass


class PlannerLLM:
    def __init__(self):
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(kwargs)
        return '{"summary":"ketuk pencarian","action":{"type":"tap_node","node":7}}'


class DummyBridge:
    pass


class CapturingProvider(OpenAICompatibleProvider):
    def __init__(self, name, cfg):
        super().__init__(name, "test-key", cfg)
        self.payloads = []

    def _json(self, method, url, payload=None, timeout=30):
        if method == "POST":
            self.payloads.append(payload)
            return {"choices": [{"message": {"content": '{"mode":"chat"}'}, "finish_reason": "stop"}]}
        return {"data": []}


class CompanionV2Tests(unittest.TestCase):
    def test_obvious_youtube_command_bypasses_llm_router(self):
        self.assertTrue(_obvious_device_intent("buka youtube dan cari channel mr beast"))
        self.assertTrue(_obvious_device_intent("open whatsapp lalu kirim pesan"))
        self.assertFalse(_obvious_device_intent("cara buka youtube di hp"))

    def test_planner_requests_json_mode(self):
        llm = PlannerLLM()
        agent = AndroidAgent(Config(), DummyStore(), llm, DummyBridge())
        step = agent._plan(
            "buka youtube dan cari mr beast",
            {"nodes": [{"id": 7, "text": "Search", "clickable": True}]},
            [],
            [{"label": "YouTube", "package": "com.google.android.youtube"}],
        )
        self.assertEqual(step.action["type"], "tap_node")
        self.assertTrue(llm.calls[-1]["json_mode"])
        self.assertEqual(llm.calls[-1]["temperature"], 0.0)

    def test_youtube_finish_cannot_happen_after_only_opening_app(self):
        agent = AndroidAgent(Config(), DummyStore(), PlannerLLM(), DummyBridge())
        ready, _ = agent._finish_ready(
            "buka youtube dan cari mr beast",
            {"nodes": [{"text": "YouTube"}]},
            [{"action": {"type": "open_app", "package": "com.google.android.youtube"}, "result": {"ok": True}}],
        )
        self.assertFalse(ready)

    def test_youtube_finish_accepts_visible_results_after_query(self):
        agent = AndroidAgent(Config(), DummyStore(), PlannerLLM(), DummyBridge())
        history = [
            {"action": {"type": "open_app", "package": "com.google.android.youtube"}, "result": {"ok": True}},
            {"action": {"type": "tap_node", "node": 3}, "result": {"ok": True}},
            {"action": {"type": "set_text", "node": 8, "text": "mr beast"}, "result": {"ok": True}},
            {"action": {"type": "tap_node", "node": 10}, "result": {"ok": True}},
        ]
        ready, _ = agent._finish_ready(
            "buka youtube dan cari mr beast",
            {"nodes": [{"text": "MrBeast"}, {"text": "Subscribers"}]},
            history,
        )
        self.assertTrue(ready)

    def test_openrouter_excludes_reasoning(self):
        provider = CapturingProvider("openrouter", Config())
        out = provider.chat_model(
            "some-model:free",
            [{"role": "user", "content": "hi"}],
            max_tokens=100,
            temperature=0.0,
            json_mode=True,
        )
        self.assertEqual(out, '{"mode":"chat"}')
        payload = provider.payloads[-1]
        self.assertEqual(payload["reasoning"], {"exclude": True})
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    def test_groq_qwen36_disables_and_hides_reasoning(self):
        provider = CapturingProvider("groq", Config())
        provider.chat_model(
            "qwen/qwen3.6-27b",
            [{"role": "user", "content": "hi"}],
            max_tokens=100,
            temperature=0.0,
            json_mode=True,
        )
        payload = provider.payloads[-1]
        self.assertEqual(payload["reasoning_format"], "hidden")
        self.assertEqual(payload["reasoning_effort"], "none")


if __name__ == "__main__":
    unittest.main()
