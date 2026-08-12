import unittest
from unittest.mock import patch

from furina_agent.config import Config
from furina_agent.providers import ModelInfo, ProviderError
from furina_agent.routing import RoutingLLM


class FakeSecrets:
    def configured(self):
        return ["groq"]
    def get(self, name):
        return "dummy"


class FakeProvider:
    calls = []
    def __init__(self, name, key, cfg):
        self.name = name
    def candidate_models(self):
        return [ModelInfo("m1", {}), ModelInfo("m2", {})]
    def chat_model(self, model, messages, **kwargs):
        self.__class__.calls.append(model)
        if model == "m1":
            raise ProviderError("groq", "rate", status=429)
        return "ok-from-m2"


class RoutingTests(unittest.TestCase):
    def test_model_failover_on_rate_limit(self):
        FakeProvider.calls = []
        cfg = Config(routing_mode="online", provider_order=["groq"])
        router = RoutingLLM(cfg)
        router.secrets = FakeSecrets()
        with patch("furina_agent.routing.OpenAICompatibleProvider", FakeProvider):
            out = router.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(out, "ok-from-m2")
        self.assertEqual(FakeProvider.calls, ["m1", "m2"])
        self.assertEqual(router.last.model, "m2")


if __name__ == "__main__":
    unittest.main()
