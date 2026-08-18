#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

TARGET_VERSION = "1.0.0-rc58"
SUPPORTED = {"1.0.0-rc57", TARGET_VERSION}


def read_version(path: Path) -> str:
    m = re.search(r'VERSION\s*=\s*["\']([^"\']+)', path.read_text(encoding="utf-8"))
    return m.group(1) if m else ""


def atomic(path: Path, content: str | bytes) -> None:
    temp = path.with_name(path.name + ".rc58.new")
    if isinstance(content, bytes): temp.write_bytes(content)
    else: temp.write_text(content, encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, path)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    chat_path = core / "chat.py"
    version_path = core / "version.py"
    bridge_path = core / "upstream_bridge.py"
    runtime = core / "upstream_runtime"
    here = Path(__file__).resolve().parent

    required = (
        chat_path, version_path, here / "upstream_bridge.py", here / "lumimuse_worker.cjs",
        here / "zerochat_worker.py", here / "utsuwa_worker.cjs", here / "soul_worker.py",
    )
    for path in required:
        if not path.is_file(): raise SystemExit(f"RC58 required source missing: {path}")

    current = read_version(version_path)
    if current not in SUPPORTED:
        raise SystemExit(f"RC58 requires RC57 foundation, found {current or 'unknown'}")

    chat = chat_path.read_text(encoding="utf-8")
    if "self.upstream_bridge.context(user_text)" not in chat:
        count = chat.count("self.upstream_bridge.context()")
        if count != 1:
            raise SystemExit(f"RC58 upstream context boundary mismatch: {count}")
        chat = chat.replace("self.upstream_bridge.context()", "self.upstream_bridge.context(user_text)", 1)

    version = version_path.read_text(encoding="utf-8")
    version = re.sub(r'VERSION\s*=\s*(["\'])([^"\']+)\1', f'VERSION = "{TARGET_VERSION}"', version, count=1)
    bridge = (here / "upstream_bridge.py").read_text(encoding="utf-8")

    for label, text in ((str(chat_path), chat), (str(version_path), version), (str(bridge_path), bridge)):
        compile(text, label, "exec")
    for py in ("zerochat_worker.py", "soul_worker.py"):
        compile((here / py).read_text(encoding="utf-8"), str(here / py), "exec")

    checks = (
        "self.upstream_bridge.context(user_text)",
        "self.upstream_bridge.after_turn(user_text, answer)",
        "answer = naturalize(",
    )
    missing = [item for item in checks if item not in chat]
    if missing: raise SystemExit("RC58 chat integration incomplete: " + ", ".join(missing))
    bridge_checks = ("_lumimuse_context", "_run_zerochat", "utsuwa_worker.cjs", "zerochat_worker.py")
    missing = [item for item in bridge_checks if item not in bridge]
    if missing: raise SystemExit("RC58 bridge integration incomplete: " + ", ".join(missing))

    runtime.mkdir(parents=True, exist_ok=True)
    atomic(bridge_path, bridge)
    for name in ("lumimuse_worker.cjs", "zerochat_worker.py", "utsuwa_worker.cjs", "soul_worker.py"):
        atomic(runtime / name, (here / name).read_bytes())
    old_utsuwa = runtime / "utsuwa_worker.mjs"
    if old_utsuwa.exists():
        try: old_utsuwa.unlink()
        except OSError: pass
    atomic(chat_path, chat)
    atomic(version_path, version)

    for path in (chat_path, version_path, bridge_path, runtime / "zerochat_worker.py", runtime / "soul_worker.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    if read_version(version_path) != TARGET_VERSION:
        raise SystemExit("RC58 version commit failed")
    print("FURINA_RC58_ALL_UPSTREAM_RUNTIME_OK")


if __name__ == "__main__":
    main()
