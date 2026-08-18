#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

TARGET_VERSION = "1.0.0-rc59"
SUPPORTED = {"1.0.0-rc58", TARGET_VERSION}


def read_version(path: Path) -> str:
    m = re.search(r'VERSION\s*=\s*["\']([^"\']+)', path.read_text(encoding="utf-8"))
    return m.group(1) if m else ""


def atomic(path: Path, content: str | bytes) -> None:
    temp = path.with_name(path.name + ".rc59.new")
    if isinstance(content, bytes):
        temp.write_bytes(content)
    else:
        temp.write_text(content, encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, path)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <termux-root>")

    root = Path(sys.argv[1]).resolve()
    core = root / "core" / "furina_agent"
    chat_path = core / "chat.py"
    version_path = core / "version.py"
    bridge_path = core / "upstream_bridge.py"
    runtime = core / "upstream_runtime"
    here = Path(__file__).resolve().parent

    for path in (chat_path, version_path, here / "upstream_bridge.py"):
        if not path.is_file():
            raise SystemExit(f"RC59 required source missing: {path}")

    current = read_version(version_path)
    if current not in SUPPORTED:
        raise SystemExit(f"RC59 requires RC58 foundation, found {current or 'unknown'}")

    chat = chat_path.read_text(encoding="utf-8")
    old_context = (
        '        system += "\\n\\nUPSTREAM COMPANION LAYERS:\\n" '
        '+ self.upstream_bridge.context(user_text)\n'
    )
    new_context = (
        '        upstream_context = self.upstream_bridge.context(user_text)\n'
        '        if upstream_context:\n'
        '            system += "\\n\\nUPSTREAM COMPANION LAYERS:\\n" + upstream_context\n'
    )
    if old_context in chat:
        chat = chat.replace(old_context, new_context, 1)
    elif new_context not in chat:
        raise SystemExit("RC59 upstream prompt boundary mismatch")

    version = version_path.read_text(encoding="utf-8")
    version = re.sub(
        r'VERSION\s*=\s*(["\'])([^"\']+)\1',
        f'VERSION = "{TARGET_VERSION}"',
        version,
        count=1,
    )
    bridge = (here / "upstream_bridge.py").read_text(encoding="utf-8")

    for label, text in (
        (str(chat_path), chat),
        (str(version_path), version),
        (str(bridge_path), bridge),
    ):
        compile(text, label, "exec")

    required_chat = (
        "upstream_context = self.upstream_bridge.context(user_text)",
        "if upstream_context:",
        "self.upstream_bridge.after_turn(user_text, answer)",
    )
    missing = [item for item in required_chat if item not in chat]
    if missing:
        raise SystemExit("RC59 chat integration incomplete: " + ", ".join(missing))

    required_bridge = (
        "queue.Queue",
        "_turn_worker_loop",
        "_soul_worker_loop",
        "worker deadline exceeded",
        "timeout=2.4",
        'if not pieces:\n            return ""',
    )
    missing = [item for item in required_bridge if item not in bridge]
    if missing:
        raise SystemExit("RC59 bridge hardening incomplete: " + ", ".join(missing))

    atomic(bridge_path, bridge)
    atomic(chat_path, chat)
    atomic(version_path, version)

    obsolete = [
        runtime / "utsuwa_worker.mjs",
        core / "upstream_bridge.py.rc57.new",
        core / "upstream_bridge.py.rc58.new",
        core / "chat.py.rc57.new",
        core / "chat.py.rc58.new",
        core / "version.py.rc57.new",
        core / "version.py.rc58.new",
    ]
    for path in obsolete:
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass

    for path in (chat_path, version_path, bridge_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    if read_version(version_path) != TARGET_VERSION:
        raise SystemExit("RC59 version commit failed")

    print("FURINA_RC59_SYSTEM_HARDENING_OK")


if __name__ == "__main__":
    main()
