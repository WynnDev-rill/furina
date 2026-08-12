import tempfile
import unittest
from pathlib import Path

from furina_agent.chat import FurinaChat
from furina_agent.config import Config
from furina_agent.memory import MemoryStore


class DummyLLM:
    def chat(self, messages, **kwargs):
        self.messages = messages
        return "ok"


class ChatMessageTests(unittest.TestCase):
    def test_single_leading_system_and_no_duplicate_current_user(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "db.sqlite")
            store.add_message("user", "sebelumnya")
            store.add_message("assistant", "jawaban lama")
            llm = DummyLLM()
            cfg = Config()
            chat = FurinaChat(cfg, store, llm)
            chat.respond("halo baru")
            messages = llm.messages
            self.assertEqual(messages[0]["role"], "system")
            self.assertEqual(sum(m["role"] == "system" for m in messages), 1)
            self.assertEqual(sum(m.get("content") == "halo baru" for m in messages), 1)
            self.assertEqual(messages[-1], {"role": "user", "content": "halo baru"})


if __name__ == "__main__":
    unittest.main()
