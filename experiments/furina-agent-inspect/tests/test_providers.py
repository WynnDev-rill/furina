import tempfile
import unittest
from pathlib import Path

from furina_agent.config import Config
from furina_agent.providers import ModelInfo, OpenAICompatibleProvider, ProviderSecrets


class ProviderTests(unittest.TestCase):
    def test_openrouter_free_only_filters_paid(self):
        cfg = Config(provider_prefer_free=True)
        p = OpenAICompatibleProvider("openrouter", "dummy", cfg)
        models = [
            ModelInfo("vendor/paid", {"id": "vendor/paid"}, free=False),
            ModelInfo("vendor/fast:free", {"id": "vendor/fast:free"}, free=True),
        ]
        ranked = p._rank_models(models)
        self.assertEqual([m.id for m in ranked], ["vendor/fast:free"])

    def test_secrets_are_separate_and_masked(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "providers.json"
            s = ProviderSecrets(path)
            s.set("groq", "gsk_1234567890abcdef")
            self.assertEqual(s.get("groq"), "gsk_1234567890abcdef")
            self.assertNotIn("1234567890", s.masked("groq"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
