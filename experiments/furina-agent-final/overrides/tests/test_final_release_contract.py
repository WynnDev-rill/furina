import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from furina_agent import config as config_mod
from furina_agent.config import Config


class FinalReleaseContractTests(unittest.TestCase):
    def test_legacy_config_migrates_to_rc7_companion(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            cfg_path = home / "config.json"
            data = home / "data"; logs = home / "logs"; run = home / "run"; models = home / "models"
            for p in (data, logs, run, models):
                p.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(json.dumps({
                "config_revision": 4,
                "context_size": 4096,
                "max_tokens": 2048,
                "response_continuations": 4,
                "agent_max_steps": 24,
                "memory_limit": 6,
                "local_reasoning": True,
                "user_nickname": "Wynn",
            }), encoding="utf-8")
            with patch.multiple(
                config_mod,
                HOME=home,
                CONFIG_PATH=cfg_path,
                DATA_DIR=data,
                LOG_DIR=logs,
                RUN_DIR=run,
                MODELS_DIR=models,
            ):
                cfg = config_mod.load_config()
            self.assertEqual(cfg.config_revision, 7)
            self.assertEqual(cfg.context_size, 6144)
            self.assertGreaterEqual(cfg.memory_limit, 7)
            self.assertGreaterEqual(cfg.context_budget_chars, 6000)
            self.assertGreaterEqual(cfg.agent_max_steps, 28)
            self.assertFalse(cfg.local_reasoning)
            self.assertTrue(cfg.embedding_enabled)
            self.assertTrue(cfg.local_vision_enabled)
            self.assertTrue(cfg.proactive_events_enabled)
            self.assertTrue(cfg.skill_learning_enabled)
            self.assertEqual(cfg.user_nickname, "Wynn")

    def test_default_companion_budget(self):
        cfg = Config()
        self.assertFalse(cfg.local_reasoning)
        self.assertEqual(cfg.context_size, 6144)
        self.assertEqual(cfg.memory_limit, 7)
        self.assertEqual(cfg.context_budget_chars, 12000)
        self.assertEqual(cfg.agent_max_steps, 28)
        self.assertAlmostEqual(cfg.temperature, 0.70)
        self.assertEqual(cfg.max_tokens, 2048)
        self.assertEqual(cfg.response_continuations, 4)
        self.assertEqual(cfg.embedding_port, 8081)
        self.assertEqual(cfg.vision_port, 8082)
        self.assertEqual(cfg.event_port, 8767)

    def test_installer_is_pinned_and_applies_all_rc7_layers(self):
        root = Path(__file__).resolve().parents[1]
        workspace = Path(os.environ.get("GITHUB_WORKSPACE", "")) if os.environ.get("GITHUB_WORKSPACE") else None
        release_installer = workspace / "experiments/furina-agent-final/install.sh" if workspace else None
        installer_path = release_installer if release_installer and release_installer.is_file() else root / "install.sh"
        installer = installer_path.read_text(encoding="utf-8")
        self.assertNotIn("storage/shared", installer)
        self.assertNotIn("/storage/emulated", installer)
        self.assertIn('VERSION="1.0.0-rc7"', installer)
        self.assertIn('[[ -f "$ROOT/config.json" ]] && MODE="update"', installer)
        self.assertIn('LLAMA_REV="f785fc9ea485e6cfdda129978310aa52939c3619"', installer)
        self.assertIn('MODEL_REV="e9cf779"', installer)
        self.assertIn("dda8f686b793f189a84c854832bb8b4db59c381a60275a567513d5ebb4d92906", installer)
        self.assertIn("50d28e22432a148f6f8a86eab3700f92add5d1f54baf7790675a2a4dadbccf26", installer)
        self.assertIn("6f67b8036b2469fcd71728702720c6b51aebd759b78137a8120733b4d66438bc", installer)
        self.assertIn("921dc7e259f308e5b027111fa185efcbf33db13f6e35749ddf7f5cdb60ef520b", installer)
        self.assertIn("source_chunks", installer)
        self.assertIn("companion-v4", installer)
        self.assertIn("apply-bridge-primitives-rc5.py", installer)
        self.assertIn("apply-bridge-rc4.py", installer)
        self.assertIn("apply-universal-agent-rc5.py", installer)
        self.assertIn("apply-core-rc6.py", installer)
        self.assertIn("apply-bridge-rc6.py", installer)
        self.assertIn("apply-core-rc7.py", installer)
        self.assertIn("apply-bridge-rc7.py", installer)
        self.assertIn("llama-embedding", installer)
        self.assertIn("-DGGML_CPU_KLEIDIAI=ON", installer)
        self.assertIn("termux-open-url", installer)

    def test_core_has_hybrid_memory_skills_events_and_rc7_continuity(self):
        root = Path(__file__).resolve().parents[1]
        memory = (root / "core/furina_agent/memory.py").read_text(encoding="utf-8")
        chat = (root / "core/furina_agent/chat.py").read_text(encoding="utf-8")
        response = (root / "core/furina_agent/response.py").read_text(encoding="utf-8")
        persona = (root / "core/furina_agent/persona.py").read_text(encoding="utf-8")
        agent = (root / "core/furina_agent/agent.py").read_text(encoding="utf-8")
        routing = (root / "core/furina_agent/routing.py").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS beliefs", memory)
        self.assertIn("CREATE TABLE IF NOT EXISTS episodes", memory)
        self.assertIn("CREATE TABLE IF NOT EXISTS memory_vectors", memory)
        self.assertIn("CREATE TABLE IF NOT EXISTS learned_skills", memory)
        self.assertIn("query_vec = self._embed_text(query)", memory)
        self.assertIn("relationship_state", memory)
        self.assertIn("backfill_vectors", chat)
        self.assertIn("DEVICE CONTEXT", chat)
        self.assertIn("_temporal_context", chat)
        self.assertIn("_internal_chat", chat)
        self.assertIn("_reflect", chat)
        self.assertIn("contradictions", chat)
        self.assertIn("choose_profile", response)
        self.assertIn("Sinisme hanya bumbu situasional", persona)
        self.assertIn("_deterministic_gate", agent)
        self.assertIn("agent_cancelled_user_return", agent)
        self.assertIn("watch_user_return", agent)
        self.assertIn("duplicate_suppressed", agent)
        self.assertIn("LEARNED SKILL HINTS", agent)
        self.assertIn("LocalVision", routing)

    def test_tui_is_one_companion_surface(self):
        root = Path(__file__).resolve().parents[1]
        tui = (root / "core/furina_agent/tui.py").read_text(encoding="utf-8")
        self.assertIn("Percakapan + tindakan Android", tui)
        self.assertNotIn('table.add_row("2", "Android Agent langsung")', tui)
        self.assertIn("hybrid semantic", tui)
        self.assertIn("skill-learning", tui)
        self.assertIn("tanpa konfirmasi kedua", tui)
        self.assertIn("MODEL ROUTER", tui)
        self.assertIn("Provider / API key", tui)
        self.assertIn("FURINA MIND", tui)

    def test_provider_reasoning_is_hidden(self):
        root = Path(__file__).resolve().parents[1]
        providers = (root / "core/furina_agent/providers.py").read_text(encoding="utf-8")
        self.assertIn('payload["reasoning"] = {"exclude": True}', providers)
        self.assertIn('payload["reasoning_format"] = "hidden"', providers)
        self.assertIn('payload["reasoning_effort"] = "none"', providers)

    def test_bridge_self_updater_and_adaptive_ui_survive_rc7(self):
        root = Path(__file__).resolve().parents[1]
        manifest = (root / "bridge/app/src/main/AndroidManifest.xml").read_text()
        updater = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java").read_text()
        main = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java").read_text()
        service = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java").read_text()
        self.assertIn("REQUEST_INSTALL_PACKAGES", manifest)
        self.assertIn("UpdateFileProvider", manifest)
        self.assertIn('android:icon="@mipmap/ic_launcher"', manifest)
        self.assertIn("verifyArchive", updater)
        self.assertIn("BridgeUpdater", main)
        self.assertIn("setOnApplyWindowInsetsListener", main)
        self.assertIn("dispatchGestureAwait", service)
        self.assertIn("waitForExactText", service)
        self.assertIn("recent_events", service)


if __name__ == "__main__":
    unittest.main()
