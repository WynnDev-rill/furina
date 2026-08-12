import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from furina_agent import config as config_mod
from furina_agent.config import Config


class FinalReleaseContractTests(unittest.TestCase):
    def test_legacy_320_token_cap_migrates_to_1024(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            cfg_path = home / 'config.json'
            data = home / 'data'; logs = home / 'logs'; run = home / 'run'; models = home / 'models'
            for p in (data, logs, run, models): p.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(json.dumps({'max_tokens': 320, 'user_nickname': 'Wynn'}), encoding='utf-8')
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
            self.assertEqual(cfg.max_tokens, 1024)
            self.assertEqual(cfg.user_nickname, 'Wynn')

    def test_non_thinking_sampler_defaults_match_fast_companion_mode(self):
        cfg = Config()
        self.assertFalse(cfg.local_reasoning)
        self.assertAlmostEqual(cfg.temperature, 0.70)
        self.assertAlmostEqual(cfg.top_p, 0.80)
        self.assertEqual(cfg.top_k, 20)

    def test_installer_is_storage_free_and_pinned(self):
        root = Path(__file__).resolve().parents[1]
        installer = (root / 'install.sh').read_text(encoding='utf-8')
        self.assertNotIn('storage/shared', installer)
        self.assertNotIn('/storage/emulated', installer)
        self.assertIn('[[ -f "$ROOT/config.json" ]] && MODE="update"', installer)
        self.assertIn('LLAMA_REV="f785fc9ea485e6cfdda129978310aa52939c3619"', installer)
        self.assertIn('MODEL_REV="e9cf779"', installer)
        self.assertIn('dda8f686b793f189a84c854832bb8b4db59c381a60275a567513d5ebb4d92906', installer)
        self.assertIn('source_chunks', installer)
        self.assertIn('-DGGML_CPU_KLEIDIAI=ON', installer)
        self.assertIn('fallback ke CPU native stabil', installer)

    def test_tui_exposes_nickname_and_zero_code_setup(self):
        root = Path(__file__).resolve().parents[1]
        tui = (root / 'core/furina_agent/tui.py').read_text(encoding='utf-8')
        self.assertIn('Nama panggilan', tui)
        self.assertIn('Tidak perlu memindahkan ZIP', tui)
        self.assertIn('Tidak ada kode pairing', tui)
        self.assertIn('By Wynn', tui)

    def test_server_runtime_can_disable_reasoning_and_apply_tuned_affinity(self):
        root = Path(__file__).resolve().parents[1]
        cli = (root / 'core/furina_agent/cli.py').read_text(encoding='utf-8')
        self.assertIn('["--reasoning", "off"]', cli)
        self.assertIn('["--reasoning-budget", "0"]', cli)
        self.assertIn('cfg.cpu_mask', cli)
        self.assertIn('"--cpu-strict"', cli)

    def test_provider_gemini_does_not_send_temperature(self):
        root = Path(__file__).resolve().parents[1]
        providers = (root / 'core/furina_agent/providers.py').read_text(encoding='utf-8')
        self.assertIn('if self.name != "gemini"', providers)
        self.assertIn('payload["temperature"] = temperature', providers)


if __name__ == '__main__':
    unittest.main()
