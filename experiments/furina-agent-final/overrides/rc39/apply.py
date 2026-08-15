#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import shutil
import sys


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root> [template-dir]")
    root = pathlib.Path(sys.argv[1]).resolve()
    templates = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else pathlib.Path(__file__).resolve().parent
    core = root / "core/furina_agent"
    version = core / "version.py"
    if not version.is_file():
        raise SystemExit(f"RC39 source missing: {version}")
    current = version.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc39"' in current:
        print("FurinaHub Core RC39 already applied")
        return
    if 'VERSION = "1.0.0-rc38"' not in current:
        raise SystemExit("RC39 hanya dapat diterapkan dari Core RC38")

    for name in ("hub.py", "direct_control.py", "memory.py", "companion.py"):
        source = templates / name
        if not source.is_file():
            raise SystemExit(f"RC39 template hilang: {source}")
        shutil.copyfile(source, core / name)

    routing = core / "routing.py"
    routing_text = routing.read_text(encoding="utf-8")
    routing_text = routing_text.replace(
        "from .vision import OnlineVision, VisionError",
        "from .vision import OnlineVision, VisionError\nfrom .local_vision import LocalVision, LocalVisionError",
        1,
    )
    routing_text = routing_text.replace(
        "        self.vision_router = OnlineVision(cfg, self.secrets)\n",
        "        self.vision_router = OnlineVision(cfg, self.secrets)\n        self.local_vision = LocalVision(cfg)\n",
        1,
    )
    old_vision = '''    def vision(self, prompt: str, png_base64: str, *, max_tokens: int = 420, json_mode: bool = True) -> str:
        if not self.secrets.configured():
            raise LLMError("Vision fallback membutuhkan provider online yang sudah dikonfigurasi.")
        try:
            return self.vision_router.analyze(prompt, png_base64, max_tokens=max_tokens, json_mode=json_mode)
        except VisionError as exc:
            raise LLMError(str(exc)) from exc
'''
    new_vision = '''    def vision(self, prompt: str, png_base64: str, *, max_tokens: int = 420, json_mode: bool = True) -> str:
        failures: list[str] = []
        if self.cfg.routing_mode != "online":
            try:
                return self.local_vision.analyze(prompt, png_base64, max_tokens=max_tokens, json_mode=json_mode)
            except LocalVisionError as exc:
                failures.append(str(exc))
        if self.cfg.routing_mode != "local" and self.secrets.configured():
            try:
                return self.vision_router.analyze(prompt, png_base64, max_tokens=max_tokens, json_mode=json_mode)
            except VisionError as exc:
                failures.append(str(exc))
        detail = "; ".join(failures[-3:])
        raise LLMError("Vision tidak tersedia" + (f": {detail}" if detail else ". Atur model vision lokal atau provider online."))
'''
    if old_vision not in routing_text:
        raise SystemExit("RC39 routing vision marker berubah")
    routing.write_text(routing_text.replace(old_vision, new_vision, 1), encoding="utf-8")

    version.write_text(current.replace('VERSION = "1.0.0-rc38"', 'VERSION = "1.0.0-rc39"', 1), encoding="utf-8")
    for cache in sorted(core.rglob("__pycache__"), reverse=True):
        shutil.rmtree(cache, ignore_errors=True)
    for path in (core / "hub_settings.py", core / "hub.py", core / "direct_control.py", core / "memory.py", core / "companion.py", routing, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    markers = {
        core / "hub.py": (
            '"bridge_target": "1.0.0-rc23"', "/api/device/probe", "/api/conversations",
            "/api/connectors/execute", "test_provider", "requested_mode", "effective_mode",
            "_update_failure_detail", "prepare_\" + mode", "rish di Termux tidak diperlukan",
        ),
        core / "hub_settings.py": (
            "SETTINGS_STATE_KEY", "SCHEMA_VERSION = 2", "device_access", "allow_write_actions",
        ),
        core / "direct_control.py": ("effective_device_mode", "load_hub_settings"),
        core / "memory.py": ("conversation_id", "list_conversations", "create_conversation"),
        core / "companion.py": ("semantic_chat_overridden_by_explicit_request", "fallback_steps"),
        core / "routing.py": ("LocalVision", "self.local_vision.analyze", "Vision tidak tersedia"),
    }
    for path, required in markers.items():
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in required if marker not in text]
        if missing:
            raise SystemExit(f"RC39 marker hilang di {path.name}: {missing}")
    print("FURINAHUB_CORE_RC39_OK")


if __name__ == "__main__":
    main()
