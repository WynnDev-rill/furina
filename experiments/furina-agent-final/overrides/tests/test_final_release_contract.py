import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from furina_agent import config as config_mod
from furina_agent.config import Config


class FinalReleaseContractTests(unittest.TestCase):
    def test_legacy_config_migrates_to_rc9_cognition_under_rc10_ui(self):
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
            self.assertEqual(cfg.config_revision, 9)
            self.assertEqual(cfg.context_size, 6144)
            self.assertGreaterEqual(cfg.memory_limit, 7)
            self.assertGreaterEqual(cfg.context_budget_chars, 6000)
            self.assertGreaterEqual(cfg.agent_max_steps, 28)
            self.assertFalse(cfg.local_reasoning)
            self.assertTrue(cfg.embedding_enabled)
            self.assertTrue(cfg.local_vision_enabled)
            self.assertTrue(cfg.proactive_events_enabled)
            self.assertTrue(cfg.skill_learning_enabled)
            self.assertTrue(cfg.fast_path_enabled)
            self.assertTrue(cfg.lexicon_enabled)
            self.assertEqual(cfg.user_nickname, "Wynn")

    def test_default_companion_budget(self):
        cfg = Config()
        self.assertFalse(cfg.local_reasoning)
        self.assertEqual(cfg.context_size, 6144)
        self.assertEqual(cfg.memory_limit, 7)
        self.assertEqual(cfg.context_budget_chars, 12000)
        self.assertEqual(cfg.agent_max_steps, 28)
        self.assertEqual(cfg.embedding_port, 8081)
        self.assertEqual(cfg.vision_port, 8082)
        self.assertEqual(cfg.event_port, 8767)
        self.assertEqual(cfg.fast_path_min_successes, 2)
        self.assertLessEqual(cfg.fast_path_ui_timeout_ms, 500)
        self.assertEqual(cfg.lexicon_prompt_limit, 8)
        self.assertEqual(cfg.lexicon_auto_min_seen, 2)

    def test_installer_is_pinned_and_applies_rc10_ui_on_rc7_bridge(self):
        root = Path(__file__).resolve().parents[1]
        workspace = Path(os.environ.get("GITHUB_WORKSPACE", "")) if os.environ.get("GITHUB_WORKSPACE") else None
        release_installer = workspace / "experiments/furina-agent-final/install.sh" if workspace else None
        installer_path = release_installer if release_installer and release_installer.is_file() else root / "install.sh"
        installer = installer_path.read_text(encoding="utf-8")
        self.assertNotIn("storage/shared", installer)
        self.assertNotIn("/storage/emulated", installer)
        self.assertIn('VERSION="1.0.0-rc10"', installer)
        self.assertIn("companion-v7", installer)
        self.assertIn("apply-ui-rc10.py", installer)
        self.assertIn("apply-ui-rc10-hotfix.py", installer)
        self.assertIn("apply-core-rc9.py", installer)
        self.assertIn("apply-core-rc8.py", installer)
        self.assertIn("apply-core-rc7.py", installer)
        self.assertIn("apply-bridge-rc7.py", installer)
        self.assertIn("fastpath.py", installer)
        self.assertIn("lexicon.py", installer)
        self.assertIn("llama-embedding", installer)
        self.assertIn("-DGGML_CPU_KLEIDIAI=ON", installer)
        self.assertIn("pkg install -y python python-pip git cmake ninja clang make curl ccache util-linux termux-tools patch gum", installer)
        self.assertIn('if [[ "$MODE" == "install" ]]; then', installer)
        self.assertIn('run_quiet "Memasang Furina Core RC10"', installer)
        self.assertIn('LOG="$ROOT/logs/setup.log"', installer)
        self.assertIn("ui_progress", installer)
        self.assertIn("Furina siap", installer)

    def test_core_has_rc9_fastpath_lexicon_and_rc8_memory_context(self):
        root = Path(__file__).resolve().parents[1]
        memory = (root / "core/furina_agent/memory.py").read_text(encoding="utf-8")
        chat = (root / "core/furina_agent/chat.py").read_text(encoding="utf-8")
        response = (root / "core/furina_agent/response.py").read_text(encoding="utf-8")
        persona = (root / "core/furina_agent/persona.py").read_text(encoding="utf-8")
        companion = (root / "core/furina_agent/companion.py").read_text(encoding="utf-8")
        agent = (root / "core/furina_agent/agent.py").read_text(encoding="utf-8")
        routing = (root / "core/furina_agent/routing.py").read_text(encoding="utf-8")
        fastpath = (root / "core/furina_agent/fastpath.py").read_text(encoding="utf-8")
        lexicon = (root / "core/furina_agent/lexicon.py").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS memory_vectors", memory)
        self.assertIn("CREATE TABLE IF NOT EXISTS memory_vector_lsh", memory)
        self.assertIn("CREATE TABLE IF NOT EXISTS prospective_memories", memory)
        self.assertIn("CREATE TABLE IF NOT EXISTS learned_skills", memory)
        self.assertIn("intent_tags", memory)
        self.assertIn("backfill_vector_index", memory)
        self.assertIn("relationship_state", memory)
        self.assertIn("_temporal_context", chat)
        self.assertIn("_internal_chat", chat)
        self.assertIn("naturalize(answer", chat)
        self.assertIn("PERSONAL LEXICON", chat)
        self.assertIn("PersonalLexicon", chat)
        self.assertIn("DEVICE STATE", chat)
        self.assertIn("PROSPECTIVE MEMORY", chat)
        self.assertIn("choose_profile", response)
        self.assertIn("Sinis dan sarkas adalah bagian dirimu, tetapi bukan nada default", persona)
        self.assertIn("ReminderDaemon", companion)
        self.assertIn("_deterministic_gate", agent)
        self.assertIn("compile_fast_contract", agent)
        self.assertIn("_try_fast_skill", agent)
        self.assertIn("_wait_after_action", agent)
        self.assertNotIn('time.sleep(0.9 if typ == "open_app" else 0.48)', agent)
        self.assertIn("watch_user_return", agent)
        self.assertIn("duplicate_suppressed", agent)
        self.assertIn("LocalVision", routing)
        self.assertIn("choose_fast_skill", fastpath)
        self.assertIn("wait_for_event", fastpath)
        self.assertIn("CREATE TABLE IF NOT EXISTS personal_lexicon", lexicon)
        self.assertIn("canonical TEXT NOT NULL UNIQUE", lexicon)

    def test_rc10_tui_is_compact_gum_visible_and_preserves_task_approval(self):
        root = Path(__file__).resolve().parents[1]
        tui = (root / "core/furina_agent/tui.py").read_text(encoding="utf-8")
        version = (root / "core/furina_agent/version.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "1.0.0-rc10"', version)
        self.assertIn("def _gum() -> str | None:", tui)
        self.assertIn('["Chat", "Memory", "Provider", "Settings", "System", "Update", "Exit"]', tui)
        self.assertIn('"--cursor", "› "', tui)
        self.assertNotIn("--cursor-prefix", tui)
        self.assertIn("stdout=subprocess.PIPE", tui)
        self.assertIn("stderr=None", tui)
        self.assertNotIn("capture_output=True", tui)
        self.assertIn("def _display_name() -> str:", tui)
        self.assertIn("By Wynn", tui)
        self.assertIn('[dim]Mode[/]', tui)
        self.assertIn("due_prospectives", tui)
        self.assertIn("Furina perlu memakai layar untuk tugas ini", tui)
        self.assertIn("termasuk Send/Kirim/Post/Share yang memang eksplisit", tui)
        self.assertIn("task_authorized=True", tui)
        self.assertNotIn('title="SYSTEM"', tui)
        self.assertNotIn('title="ACTIONS"', tui)
        self.assertNotIn("Percakapan + tindakan Android", tui)
        self.assertNotIn("AI ROUTER", tui)
        self.assertNotIn("MEMORY / RESPONSE", tui)

    def test_bridge_rc7_is_preserved_unchanged_for_core_rc10(self):
        root = Path(__file__).resolve().parents[1]
        manifest = (root / "bridge/app/src/main/AndroidManifest.xml").read_text()
        updater = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java").read_text()
        main = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java").read_text()
        service = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java").read_text()
        gradle = (root / "bridge/app/build.gradle").read_text()
        self.assertIn("REQUEST_INSTALL_PACKAGES", manifest)
        self.assertIn('android:icon="@mipmap/ic_launcher"', manifest)
        self.assertIn("verifyArchive", updater)
        self.assertIn("setOnApplyWindowInsetsListener", main)
        self.assertIn("dispatchGestureAwait", service)
        self.assertIn("waitForExactText", service)
        self.assertIn("versionCode 10007", gradle)
        self.assertIn("versionName '1.0.0-rc7'", gradle)


if __name__ == "__main__":
    unittest.main()
