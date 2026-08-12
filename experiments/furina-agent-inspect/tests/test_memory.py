import tempfile
import unittest
from pathlib import Path

from furina_agent.memory import MemoryStore, extract_explicit_memories


class MemoryTests(unittest.TestCase):
    def test_memory_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            s = MemoryStore(Path(td) / "db.sqlite")
            s.add_memory("Aku suka kopi tanpa gula", "preference", 0.8)
            got = s.search("kopi", 3)
            self.assertTrue(got)
            self.assertIn("kopi", got[0].text.lower())

    def test_explicit_extraction(self):
        out = list(extract_explicit_memories("Aku suka UI modern dan sederhana."))
        self.assertTrue(out)
        self.assertEqual(out[0][1], "preference")


if __name__ == "__main__":
    unittest.main()
