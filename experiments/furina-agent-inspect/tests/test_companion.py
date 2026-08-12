import unittest

from furina_agent.companion import CompanionSession
from furina_agent.config import Config


class DummyLLM:
    def chat(self, messages, **kwargs):
        return '{"mode":"device","goal":"buka YouTube dan cari video yang diminta","confidence":0.94}'


class DummyStore: pass


class CompanionTests(unittest.TestCase):
    def test_natural_router_can_map_typo_to_device(self):
        c = CompanionSession(Config(), DummyStore(), DummyLLM())
        intent = c.classify("bka yutub cri vidio kucing")
        self.assertEqual(intent.mode, "device")
        self.assertIn("YouTube", intent.goal)


if __name__ == "__main__":
    unittest.main()
