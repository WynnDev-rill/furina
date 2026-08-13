import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core" / "furina_agent"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


mind_mod = load_module("rc17_mind_v2", CORE / "mind_v2.py")
cog_mod = load_module("rc17_cognition", CORE / "cognition.py")


class FakeStore:
    def __init__(self):
        self.state = {}
        self.events = []

    def get_state(self, key, default=None):
        return self.state.get(key, default)

    def set_state(self, key, value):
        self.state[key] = value

    def log_event(self, typ, payload):
        self.events.append((typ, payload))


class FakeLLM:
    def __init__(self, online=True):
        self.online = online
        self.calls = []

    def configured_online(self):
        return ["openrouter"] if self.online else []

    def cognitive_chat(self, messages, *, max_tokens, temperature, json_mode, prefer_online):
        self.calls.append(prefer_online)
        return '{"ok":true}'


class RC17CompanionMindTests(unittest.TestCase):
    def test_agent_capability_does_not_become_identity(self):
        store = FakeStore()
        mind = mind_mod.FurinaMind(store)
        mind.record(
            [
                {
                    "kind": "opinion",
                    "text": "Aku lebih suka jawaban yang tidak berpura-pura yakin.",
                    "confidence": 0.75,
                }
            ],
            source="conversation_reflection",
        )
        mind.record_agent_outcome("android_bridge", False, ms=90)

        ctx = mind.context()
        self.assertIn("tidak berpura-pura yakin", ctx)
        self.assertNotIn("android_bridge", ctx)
        self.assertIn("android_bridge", store.state["furina_agent_capabilities"])

    def test_mind_reinforces_repeated_self_evidence(self):
        store = FakeStore()
        mind = mind_mod.FurinaMind(store)
        item = {
            "kind": "lesson",
            "text": "Aku perlu mengakui ketidakpastian sebelum membuat kesimpulan.",
            "confidence": 0.7,
        }
        mind.record([item])
        mind.record([item])
        rows = store.state["furina_mind_v2"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["evidence"], 2)

    def test_online_cognition_is_preferred_and_budgeted(self):
        store = FakeStore()
        cfg = SimpleNamespace(
            cognition_online_preferred=True,
            cognition_daily_online_calls=1,
            cognition_daily_estimated_tokens=10000,
        )
        llm = FakeLLM(online=True)
        router = cog_mod.CognitionRouter(cfg, store, llm)
        messages = [{"role": "user", "content": "reflect"}]

        first = router.run(
            messages,
            max_tokens=200,
            temperature=0.1,
            purpose="mind_reflection",
        )
        second = router.run(
            messages,
            max_tokens=200,
            temperature=0.1,
            purpose="memory_consolidation",
        )

        self.assertTrue(first)
        self.assertEqual(second, "")
        self.assertEqual(llm.calls, [True])
        self.assertTrue(any(t == "cognition_deferred" for t, _ in store.events))

    def test_local_is_used_only_when_online_is_not_configured(self):
        store = FakeStore()
        cfg = SimpleNamespace(
            cognition_online_preferred=True,
            cognition_daily_online_calls=12,
            cognition_daily_estimated_tokens=24000,
        )
        llm = FakeLLM(online=False)
        router = cog_mod.CognitionRouter(cfg, store, llm)

        result = router.run(
            [{"role": "user", "content": "reflect"}],
            max_tokens=200,
            temperature=0.1,
            purpose="mind_reflection",
        )
        self.assertTrue(result)
        self.assertEqual(llm.calls, [False])

    def test_event_queue_is_bounded_and_deduplicated(self):
        store = FakeStore()
        event = {
            "type": "window",
            "package": "com.example",
            "text": "same",
            "at": 1.0,
        }
        for i in range(10):
            event["at"] = float(i + 1)
            cog_mod.enqueue_event(store, event)
        rows = store.state["cognition_event_batch"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["repeat"], 10)


if __name__ == "__main__":
    unittest.main()
