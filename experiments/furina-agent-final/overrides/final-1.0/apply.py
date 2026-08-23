#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


def replace_function(text: str, name: str, replacement: str) -> str:
    tree = ast.parse(text)
    matches = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(matches) != 1:
        raise SystemExit(f"final function boundary mismatch: {name}={len(matches)}")
    node = matches[0]
    lines = text.splitlines(keepends=True)
    return "".join(lines[:node.lineno-1]) + replacement.rstrip() + "\n\n" + "".join(lines[node.end_lineno:])


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"final Core marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <furina-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    version_path = core / "version.py"
    cli_path = core / "cli.py"
    chat_path = core / "chat.py"
    relation_path = core / "relationship_v4.py"
    for path in (version_path, cli_path, chat_path, relation_path):
        if not path.is_file():
            raise SystemExit(f"final Core source missing: {path}")

    version = once(version_path.read_text(encoding="utf-8"), 'VERSION = "1.0.0-rc69"', 'VERSION = "1.0.0"', "version")

    # TUI and CLI must share the same local updater. Network bootstrap is only
    # recovery when the local client is genuinely missing.
    cli = cli_path.read_text(encoding="utf-8")
    cli = replace_function(cli, "cmd_update", r'''def cmd_update(_args):
    import shutil

    command = shutil.which("furina-update")
    if command:
        raise SystemExit(subprocess.run([command], check=False).returncode)
    print("Updater lokal belum tersedia; menjalankan recovery satu kali…")
    cmd_recover(_args)''')

    # One ordered memory worker remains lossless, but its backlog is now bounded.
    # At an extreme 64-turn backlog, put() applies backpressure instead of allowing
    # memory growth without limit. Normal single-user chat never approaches it.
    chat = chat_path.read_text(encoding="utf-8")
    chat = once(chat, "self._background_queue = queue.Queue()", "self._background_queue = queue.Queue(maxsize=64)", "bounded background queue")

    relationship = relation_path.read_text(encoding="utf-8")
    relationship = relationship.replace(
        '"description": "Kalian memulai sebagai pasangan; kedekatan tumbuh dari percakapan nyata, bukan mode pertemanan.",',
        '"description": "Kalian memulai sebagai pasangan; kedekatan tumbuh dari percakapan nyata.",',
    ).replace(
        '"Ini identitas hubungan, bukan pilihan mode. Jangan menyebut fase pertemanan.\\n"',
        '"Ini identitas hubungan, bukan pilihan mode. Jangan mengubah hubungan menjadi mode lain.\\n"',
    )

    version_path.write_text(version, encoding="utf-8")
    cli_path.write_text(cli, encoding="utf-8")
    chat_path.write_text(chat, encoding="utf-8")
    relation_path.write_text(relationship, encoding="utf-8")

    for path in (version_path, cli_path, chat_path, relation_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    combined = "\n".join((version, cli, chat, relationship))
    required = (
        'VERSION = "1.0.0"', 'shutil.which("furina-update")',
        "queue.Queue(maxsize=64)", "Jangan mengubah hubungan menjadi mode lain",
    )
    missing = [item for item in required if item not in combined]
    if missing:
        raise SystemExit(f"final Core integration incomplete: {missing}")
    if "bukan mode pertemanan" in relationship or "fase pertemanan" in relationship:
        raise SystemExit("final relationship copy still exposes friendship-mode wording")
    print("FURINA_PRIVATE_FINAL_CORE_OK")


if __name__ == "__main__":
    main()
