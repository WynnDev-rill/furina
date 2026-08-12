import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from furina_agent.config import Config
from furina_agent.llm import LocalLLM
from furina_agent.persona import build_system_prompt


class FakeLocal(LocalLLM):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.calls = 0
    def _request_once(self, messages, *, max_tokens, temperature, on_token):
        self.calls += 1
        if self.calls == 1:
            if on_token: on_token("Kalimat pertama belum ")
            return "Kalimat pertama belum", "length"
        if on_token: on_token("selesai.")
        return "selesai.", "stop"


class FinalContractTests(unittest.TestCase):
    def test_nickname_is_in_persona_but_not_forced_every_turn(self):
        prompt = build_system_prompt("Furina", "Wynn")
        self.assertIn("Nama panggilan pengguna adalah Wynn", prompt)
        self.assertIn("bukan di setiap respons", prompt)

    def test_local_length_finish_auto_continues(self):
        cfg = Config(max_tokens=64, response_continuations=1)
        llm = FakeLocal(cfg)
        chunks = []
        text = llm.chat([{"role":"user","content":"tes"}], on_token=chunks.append)
        self.assertEqual(llm.calls, 2)
        self.assertIn("selesai.", text)
        self.assertEqual("".join(chunks), "Kalimat pertama belum selesai.")

    def test_bridge_source_uses_zero_code_bootstrap(self):
        root = Path(__file__).resolve().parents[1]
        server = (root / 'bridge/app/src/main/java/com/wynndev/furinaagentbridge/LocalBridgeServer.java').read_text()
        prefs = (root / 'bridge/app/src/main/java/com/wynndev/furinaagentbridge/BridgePrefs.java').read_text()
        self.assertIn('"/bootstrap"', server)
        self.assertIn('consumeBootstrapWindow', server)
        self.assertIn('openBootstrapWindow', prefs)

    def test_release_bridge_has_stable_signing_hook(self):
        root = Path(__file__).resolve().parents[1]
        gradle = (root / 'bridge/app/build.gradle').read_text()
        self.assertIn('FURINA_AGENT_KEYSTORE_PATH', gradle)
        self.assertIn("versionCode 10001", gradle)


if __name__ == '__main__':
    unittest.main()
