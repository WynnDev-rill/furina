import unittest
from pathlib import Path

from furina_agent.config import Config
from furina_agent.llm import LocalLLM, sanitize
from furina_agent.persona import build_system_prompt


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


class FinalContractTests(unittest.TestCase):
    def test_nickname_is_in_persona_but_not_forced_every_turn(self):
        prompt = build_system_prompt("Furina", "Wynn")
        self.assertIn("Nama panggilan pengguna adalah Wynn", prompt)
        self.assertIn("bukan di setiap respons", prompt)

    def test_persona_hides_reasoning_forbids_emoji_and_lore_by_default(self):
        prompt = build_system_prompt("Furina", "Wynn")
        self.assertIn("Jangan gunakan emoji", prompt)
        self.assertIn("Jangan menampilkan chain-of-thought", prompt)
        self.assertIn("Jangan membawa lore", prompt)
        self.assertIn("tsundere", prompt.lower())
        self.assertIn("sinis", prompt.lower())

    def test_sanitizer_removes_reasoning_and_emoji(self):
        text = sanitize("<think>rahasia</think>Hai 😛")
        self.assertEqual(text, "Hai")
        self.assertEqual(sanitize("<analysis>belum selesai"), "")

    def test_local_length_finish_auto_continues(self):
        cfg = Config(max_tokens=64, response_continuations=4)
        llm = FakeLocal(cfg)
        chunks = []
        text = llm.chat([{"role": "user", "content": "tes"}], on_token=chunks.append)
        self.assertEqual(llm.calls, 2)
        self.assertIn("selesai.", text)
        self.assertEqual("".join(chunks), "Kalimat pertama belum selesai.")

    def test_bridge_source_uses_zero_code_bootstrap(self):
        root = Path(__file__).resolve().parents[1]
        server = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/LocalBridgeServer.java").read_text()
        prefs = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/BridgePrefs.java").read_text()
        self.assertIn('"/bootstrap"', server)
        self.assertIn("consumeBootstrapWindow", server)
        self.assertIn("openBootstrapWindow", prefs)

    def test_release_bridge_has_stable_signing_hook_and_rc2_identity(self):
        root = Path(__file__).resolve().parents[1]
        gradle = (root / "bridge/app/build.gradle").read_text()
        self.assertIn("FURINA_AGENT_KEYSTORE_PATH", gradle)
        self.assertIn("versionCode 10002", gradle)
        self.assertIn("versionName '1.0.0-rc2'", gradle)


if __name__ == "__main__":
    unittest.main()
