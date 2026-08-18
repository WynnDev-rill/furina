#!/usr/bin/env python3
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

TARGET_VERSION = "1.0.0-rc56"
SUPPORTED_PREVIOUS = {"1.0.0-rc55", TARGET_VERSION}


def read_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(r'VERSION\s*=\s*["\']([^"\']+)', text)
    return m.group(1) if m else ""


def method_node(text: str, class_name: str, method_name: str):
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return item
    return None


def insert_after_line(text: str, line_no: int, block: str) -> str:
    lines = text.splitlines(keepends=True)
    idx = max(0, min(len(lines), line_no))
    payload = block if block.endswith("\n") else block + "\n"
    lines.insert(idx, payload)
    return "".join(lines)


def ensure_import(text: str, statement: str) -> str:
    if statement in text:
        return text
    lines = text.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("from __future__ import") or stripped.startswith("import ") or stripped.startswith("from "):
            insert_at = i + 1
            continue
        if stripped == "":
            continue
        if insert_at:
            break
    lines.insert(insert_at, statement + "\n")
    return "".join(lines)


def ensure_naturalize_hook(text: str) -> str:
    if "answer = naturalize(" in text:
        return text
    node = method_node(text, "FurinaChat", "respond")
    if node is None:
        raise RuntimeError("unable to locate FurinaChat.respond")
    tree = ast.parse(text)
    respond_node = None
    for top in tree.body:
        if isinstance(top, ast.ClassDef) and top.name == "FurinaChat":
            for item in top.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "respond":
                    respond_node = item
                    break
    if respond_node is None:
        raise RuntimeError("respond AST missing")

    answer_assign = None
    for stmt in respond_node.body:
        if isinstance(stmt, ast.Assign):
            names = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            if "answer" not in names:
                continue
            if isinstance(stmt.value, ast.Call):
                func = stmt.value.func
                if isinstance(func, ast.Attribute) and func.attr == "chat":
                    answer_assign = stmt
                    break
    if answer_assign is None:
        raise RuntimeError("unable to locate answer LLM assignment")

    block = (
        "        answer = naturalize(\n"
        "            answer,\n"
        "            technical=(profile.name == \"SHARP\"),\n"
        "            profile=profile.name,\n"
        "            user_text=user_text,\n"
        "        )"
    )
    return insert_after_line(text, answer_assign.end_lineno, block)


def set_target_version(text: str) -> str:
    m = re.search(r'VERSION\s*=\s*(["\'])([^"\']+)\1', text)
    if not m:
        raise RuntimeError("version marker missing")
    current = m.group(2)
    if current not in SUPPORTED_PREVIOUS:
        raise RuntimeError(f"unsupported Core version for RC56 patch: {current}")
    return text[:m.start()] + f'VERSION = "{TARGET_VERSION}"' + text[m.end():]


def write_atomic(path: Path, content: str | bytes) -> None:
    temp = path.with_name(path.name + ".rc56.new")
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
    core = root / "core/furina_agent"
    chat_path = core / "chat.py"
    version_path = core / "version.py"
    response_path = core / "response.py"
    persona_path = core / "persona.py"
    natural_path = core / "naturalness.py"

    here = Path(__file__).resolve().parent
    response_source = here / "response.py"
    persona_source = here / "persona.py"
    natural_source = here / "naturalness.py"

    for path in (chat_path, version_path, response_source, persona_source, natural_source):
        if not path.is_file():
            raise SystemExit(f"RC56 required source missing: {path}")

    current = read_version(version_path)
    if current not in SUPPORTED_PREVIOUS:
        raise SystemExit(f"RC56 requires Core RC55 foundation, found {current or 'unknown'}")

    chat = chat_path.read_text(encoding="utf-8")
    ast.parse(chat)
    chat = ensure_import(chat, "from .naturalness import naturalize")
    chat = ensure_naturalize_hook(chat)

    response = response_source.read_text(encoding="utf-8")
    persona = persona_source.read_text(encoding="utf-8")
    natural = natural_source.read_text(encoding="utf-8")
    version = set_target_version(version_path.read_text(encoding="utf-8"))

    # Validate all candidates before touching the installed Core.
    for label, text in (
        (str(chat_path), chat),
        (str(response_path), response),
        (str(persona_path), persona),
        (str(natural_path), natural),
        (str(version_path), version),
    ):
        compile(text, label, "exec")

    required_chat = (
        "from .naturalness import naturalize",
        "answer = naturalize(",
        'profile=profile.name',
        "self.companion_state.before_user(user_text)",
        "self.companion_state.after_turn(user_text, answer)",
    )
    missing = [item for item in required_chat if item not in chat]
    if missing:
        raise SystemExit("RC56 chat integration incomplete: " + ", ".join(missing))

    for item in ('name = "IDENTITY"', "max_tokens = 80", "max_tokens = 360"):
        if item not in response:
            raise SystemExit("RC56 response policy incomplete: " + item)
    for item in ("ANTI-CHATBOT", "kalau berubah pikiran beri tahu", "tidak ada dasar untuk mengklaim kesadaran subjektif"):
        if item not in persona:
            raise SystemExit("RC56 persona policy incomplete: " + item)
    for item in ("_GENERIC_TAILS", "_CANNED_DECLINE", "profile == \"IDENTITY\""):
        if item not in natural:
            raise SystemExit("RC56 naturalness guard incomplete: " + item)

    # Replace version last so interruptions remain retryable.
    write_atomic(response_path, response)
    write_atomic(persona_path, persona)
    write_atomic(natural_path, natural)
    write_atomic(chat_path, chat)
    write_atomic(version_path, version)

    for path in (response_path, persona_path, natural_path, chat_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    if read_version(version_path) != TARGET_VERSION:
        raise SystemExit("RC56 version commit failed")

    print("FURINA_RC56_ANTI_CHATBOT_POLICY_OK")


if __name__ == "__main__":
    main()
