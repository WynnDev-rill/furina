import unittest

from furina_agent.llm import normalize_messages


class MessageNormalizationTests(unittest.TestCase):
    def test_merges_system_messages_at_front(self):
        got = normalize_messages([
            {"role": "user", "content": "old"},
            {"role": "system", "content": "persona"},
            {"role": "assistant", "content": "reply"},
            {"role": "system", "content": "memory"},
            {"role": "user", "content": "new"},
        ])
        self.assertEqual(got[0]["role"], "system")
        self.assertEqual(sum(m["role"] == "system" for m in got), 1)
        self.assertIn("persona", got[0]["content"])
        self.assertIn("memory", got[0]["content"])
        self.assertEqual([m["role"] for m in got[1:]], ["user", "assistant", "user"])


if __name__ == "__main__":
    unittest.main()
