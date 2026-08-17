#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import pathlib
import sys
import tempfile
import urllib.request

ORIGINAL_URL = "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/overrides/apply-core-rc17.py"
ORIGINAL_BLOB = "ffadcffc83df3786b670894b8307bd760a5c0b4d"


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def normalize_background(chat: pathlib.Path) -> None:
    text = chat.read_text(encoding="utf-8")
    start = text.find("    def _background(self, user_text: str, answer: str, turn: int) -> None:\n")
    if start < 0:
        raise SystemExit("RC17 hotfix: _background function not found")

    next_internal = text.find("    def _internal_chat(", start)
    next_consolidate = text.find("    def _consolidate(", start)
    candidates = [x for x in (next_internal, next_consolidate) if x >= 0]
    if not candidates:
        raise SystemExit("RC17 hotfix: background end marker not found")
    end = min(candidates)

    block = text[start:end]
    try_pos = block.find("        try:\n")
    finally_pos = block.find("        finally:\n", try_pos)
    if try_pos < 0 or finally_pos < 0:
        raise SystemExit("RC17 hotfix: background try/finally markers not found")

    canonical = '''        try:
            self._consolidate(user_text, answer)
            if turn % 8 == 0:
                self._reflect()
            if turn % 16 == 0:
                self.store.decay_memories()
        finally:
'''
    block = block[:try_pos] + canonical + block[finally_pos + len("        finally:\n"):]
    chat.write_text(text[:start] + block + text[end:], encoding="utf-8")


def load_original() -> tuple[bytes, pathlib.Path | None]:
    local = pathlib.Path(__file__).resolve().with_name("apply-core-rc17.py")
    if local.is_file():
        return local.read_bytes(), local
    data = urllib.request.urlopen(ORIGINAL_URL, timeout=30).read()
    return data, None


def run_original(root: pathlib.Path) -> None:
    data, local = load_original()
    actual = git_blob_sha(data)
    if actual != ORIGINAL_BLOB:
        raise SystemExit(f"RC17 hotfix: original transform integrity mismatch: {actual}")

    temp_path: pathlib.Path | None = None
    path = local
    if path is None:
        with tempfile.NamedTemporaryFile("wb", suffix="-rc17.py", delete=False) as fh:
            fh.write(data)
            temp_path = pathlib.Path(fh.name)
        path = temp_path

    old_argv = sys.argv[:]
    try:
        sys.argv = [str(path), str(root)]
        namespace = {"__name__": "__main__", "__file__": str(path)}
        exec(compile(data, str(path), "exec"), namespace, namespace)
    finally:
        sys.argv = old_argv
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc17-hotfix.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    chat = root / "core/furina_agent/chat.py"
    if not chat.is_file():
        raise SystemExit(f"RC17 hotfix: missing staged chat source: {chat}")

    normalize_background(chat)
    run_original(root)
    print("Furina RC17 installer hotfix: background marker normalized and RC17 applied")


if __name__ == "__main__":
    main()
