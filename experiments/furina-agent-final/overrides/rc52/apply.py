#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC52 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def replace_between(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"RC52 boundary mismatch: {label}")
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    routing_path = root / "core/furina_agent/routing.py"
    version_path = root / "core/furina_agent/version.py"
    hub_path = root / "core/furina_agent/hub.py"
    for path in (routing_path, version_path, hub_path):
        if not path.is_file():
            raise SystemExit(f"RC52 source missing: {path}")

    routing = routing_path.read_text(encoding="utf-8")
    if "import time\n" not in routing:
        if routing.count("import subprocess\n") != 1:
            raise SystemExit("RC52 import anchor missing")
        routing = routing.replace("import subprocess\n", "import subprocess\nimport time\n", 1)

    new_ensure = '''    def _ensure_local(self) -> bool:
        # Fast path: keep a healthy llama.cpp process warm instead of reloading
        # the GGUF for every local conversation turn.
        if self.local.health():
            return True
        if not self.cfg.model_path or not Path(self.cfg.model_path).exists():
            return False
        launcher = HOME / "bin" / "furina"
        if not launcher.exists():
            return False
        try:
            subprocess.run(
                [str(launcher), "start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=135,
                check=False,
            )
        except subprocess.TimeoutExpired:
            # A slow cold load may outlive the launcher timeout. Do not kill a
            # server that is becoming ready; the bounded health poll below is
            # authoritative.
            pass
        except Exception:
            return False

        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            if self.local.health():
                return True
            time.sleep(0.25)
        return self.local.health()
'''
    routing = replace_between(
        routing,
        "    def _ensure_local(self) -> bool:",
        "    def chat(",
        new_ensure,
        "local startup readiness",
    )

    chat_start = routing.find("    def chat(")
    local_start = routing.find('        if self.cfg.routing_mode == "local":', chat_start)
    online_start = routing.find('        if self.cfg.routing_mode in {"auto", "online"}:', local_start)
    if local_start < 0 or online_start < 0:
        raise SystemExit("RC52 explicit local routing boundary missing")
    new_local = '''        if self.cfg.routing_mode == "local":
            # Explicit Local must have the same self-start behavior as Auto
            # fallback. Previously this branch skipped _ensure_local(), so the
            # first local chat failed whenever llama.cpp was not already up.
            if not self._ensure_local():
                raise LLMError(
                    "Model lokal belum aktif. Pastikan model GGUF sudah dipilih dan file model masih tersedia."
                )
            answer = self.local.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                on_token=on_token,
                json_mode=json_mode,
            )
            self._record("local", "GGUF", role)
            return answer
'''
    routing = routing[:local_start] + new_local.rstrip() + "\n\n" + routing[online_start:]
    routing_path.write_text(routing, encoding="utf-8")

    version = version_path.read_text(encoding="utf-8")
    version = replace_once(version, 'VERSION = "1.0.0-rc51"', 'VERSION = "1.0.0-rc52"', "Core version")
    version_path.write_text(version, encoding="utf-8")

    hub = hub_path.read_text(encoding="utf-8")
    old_target = '"bridge_target": "1.0.0-rc39"'
    if old_target in hub:
        hub = hub.replace(old_target, '"bridge_target": "1.0.0-rc40"')
    elif '"bridge_target": "1.0.0-rc40"' not in hub:
        raise SystemExit("RC52 bridge target marker missing")
    hub_path.write_text(hub, encoding="utf-8")

    combined = routing + "\n" + version + "\n" + hub
    checks = (
        'VERSION = "1.0.0-rc52"',
        '"bridge_target": "1.0.0-rc40"',
        "if not self._ensure_local():",
        "deadline = time.monotonic() + 12.0",
        "time.sleep(0.25)",
        'self._record("local", "GGUF", role)',
        'if self.cfg.routing_mode in {"auto", "online"}:',
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"RC52 marker hilang: {missing}")
    print("FURINAHUB_CORE_RC52_LOCAL_READY_OK")


if __name__ == "__main__":
    main()
