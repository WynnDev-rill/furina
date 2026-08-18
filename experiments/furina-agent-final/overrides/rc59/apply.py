#!/usr/bin/env python3
from __future__ import annotations

import ast
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


def node_for(text: str, cls: str, method: str):
    tree = ast.parse(text)
    for top in tree.body:
        if isinstance(top, ast.ClassDef) and top.name == cls:
            for item in top.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method:
                    return item
    return None


def replace_method(text: str, cls: str, method: str, replacement: str) -> str:
    node = node_for(text, cls, method)
    if not node:
        raise SystemExit(f"RC59 method missing: {cls}.{method}")
    lines = text.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = [replacement.rstrip() + "\n"]
    return "".join(lines)


def insert_before_method(text: str, cls: str, method: str, block: str) -> str:
    node = node_for(text, cls, method)
    if not node:
        raise SystemExit(f"RC59 insertion boundary missing: {cls}.{method}")
    lines = text.splitlines(keepends=True)
    lines.insert(node.lineno - 1, block.rstrip() + "\n\n")
    return "".join(lines)


def harden_local_background(chat: str) -> str:
    if "import queue\n" not in chat:
        marker = "import json\n"
        if marker not in chat:
            raise SystemExit("RC59 chat import boundary missing")
        chat = chat.replace(marker, marker + "import queue\n", 1)

    new_init = (
        "        self._background_queue = queue.Queue()\n"
        "        self._background_thread = threading.Thread(\n"
        "            target=self._background_worker_loop, name=\"furina-memory-worker\", daemon=True\n"
        "        )\n"
        "        self._background_thread.start()"
    )
    if "self._background_queue = queue.Queue()" not in chat:
        old = "        self._background_lock = threading.Lock()"
        if chat.count(old) != 1:
            raise SystemExit(f"RC59 background init boundary mismatch: {chat.count(old)}")
        chat = chat.replace(old, new_init, 1)

    schedule = '''    def _schedule_background(self, user_text: str, answer: str, turn: int) -> None:
        # Preserve every turn in one ordered worker instead of spawning a thread
        # per message and dropping work when a nonblocking lock is busy.
        self._background_queue.put((user_text, answer, turn))'''
    chat = replace_method(chat, "FurinaChat", "_schedule_background", schedule)

    background = '''    def _background(self, user_text: str, answer: str, turn: int) -> None:
        self._consolidate(user_text, answer)
        if turn % 8 == 0:
            self._reflect()
        if turn % 16 == 0:
            self.store.decay_memories()'''
    chat = replace_method(chat, "FurinaChat", "_background", background)

    if "def _background_worker_loop(self)" not in chat:
        worker = '''    def _background_worker_loop(self) -> None:
        while True:
            user_text, answer, turn = self._background_queue.get()
            try:
                # Small debounce keeps foreground chat responsive while still
                # guaranteeing that every queued turn is eventually processed.
                time.sleep(4.0)
                self._background(user_text, answer, turn)
            except Exception as exc:
                self.store.log_event("background_worker_error", {"error": str(exc)[:300]})
            finally:
                self._background_queue.task_done()'''
        chat = insert_before_method(chat, "FurinaChat", "_background", worker)

    return chat


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
    ast.parse(chat)
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

    chat = harden_local_background(chat)

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
        "self._background_queue = queue.Queue()",
        "def _background_worker_loop(self)",
        "self._background_queue.put((user_text, answer, turn))",
    )
    missing = [item for item in required_chat if item not in chat]
    if missing:
        raise SystemExit("RC59 chat integration incomplete: " + ", ".join(missing))
    if "_background_lock" in chat or "acquire(blocking=False)" in chat:
        raise SystemExit("RC59 obsolete lossy background lock remains in chat")

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
