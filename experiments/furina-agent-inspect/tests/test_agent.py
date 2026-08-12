import unittest

from furina_agent.agent import AndroidAgent
from furina_agent.config import Config


class Dummy: pass


class AgentRiskTests(unittest.TestCase):
    def setUp(self):
        self.agent = AndroidAgent(Config(), Dummy(), Dummy(), Dummy())

    def test_send_button_requires_external_confirmation(self):
        screen = {"nodes": [{"id": 9, "text": "Send", "clickable": True}]}
        risk, _ = self.agent.risk(screen, {"type": "tap_node", "node": 9})
        self.assertEqual(risk, "external")

    def test_delete_is_blocked(self):
        screen = {"nodes": [{"id": 4, "text": "Hapus", "clickable": True}]}
        risk, _ = self.agent.risk(screen, {"type": "tap_node", "node": 4})
        self.assertEqual(risk, "blocked")

    def test_open_app_is_navigation(self):
        risk, _ = self.agent.risk({}, {"type": "open_app", "package": "com.google.android.youtube"})
        self.assertEqual(risk, "navigate")


if __name__ == "__main__":
    unittest.main()
