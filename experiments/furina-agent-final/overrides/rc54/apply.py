#!/usr/bin/env python3
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
import sys

TARGET_VERSION = "1.0.0-rc54"
SUPPORTED_PREVIOUS = {"1.0.0-rc52", "1.0.0-rc53", TARGET_VERSION}


def read_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'VERSION\s*=\s*["\']([^"\']+)', text)
    return match.group(1) if match else ""


def method_node(text: str, class_name: str, method_name: str) -> ast.FunctionDef:
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return item
    raise RuntimeError(f"method not found: {class_name}.{method_name}")


def insert_before_line(text: str, line_no: int, block: str) -> str:
    lines = text.splitlines(keepends=True)
    idx = max(0, min(len(lines), line_no - 1))
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


def ensure_init_wiring(text: str) -> str:
    needed = []
    if "self.companion_state = CompanionStateV2(store)" not in text:
        needed.append("        self.companion_state = CompanionStateV2(store)")
    if "self.mind = FurinaMind(store)" not in text:
        needed.append("        self.mind = FurinaMind(store)")
    if not needed:
        return text
    node = method_node(text, "FurinaChat", "__init__")
    lines = text.splitlines(keepends=True)
    preferred = None
    for n in range(node.lineno, node.end_lineno + 1):
        if "self.llm = llm" in lines[n - 1]:
            preferred = n + 1
            break
    return insert_before_line(text, preferred or node.end_lineno + 1, "\n".join(needed))


def ensure_message_context(text: str) -> str:
    if "LIVING COMPANION STATE:" in text and "LEARNED SELF / EXPERIENCE:" in text:
        return text
    node = method_node(text, "FurinaChat", "_messages")
    lines = text.splitlines(keepends=True)
    target = None
    for n in range(node.lineno, node.end_lineno + 1):
        line = lines[n - 1]
        if "messages =" in line and '"role"' in line and '"system"' in line:
            target = n
            break
    if target is None:
        for n in range(node.lineno, node.end_lineno + 1):
            if lines[n - 1].lstrip().startswith("return "):
                target = n
                break
    if target is None:
        raise RuntimeError("unable to locate _messages system boundary")
    block = (
        '        system += "\\n\\nLIVING COMPANION STATE:\\n" + self.companion_state.context()\n'
        '        system += "\\n\\nLEARNED SELF / EXPERIENCE:\\n" + self.mind.current_context() + "\\n" + self.mind.context(8)\n'
    )
    return insert_before_line(text, target, block.rstrip("\n"))


def ensure_before_user(text: str) -> str:
    wanted = []
    if "self.companion_state.before_user(user_text)" not in text:
        wanted.append("        self.companion_state.before_user(user_text)")
    if "self.mind.observe_user_feedback(user_text)" not in text:
        wanted.append("        self.mind.observe_user_feedback(user_text)")
    if not wanted:
        return text
    node = method_node(text, "FurinaChat", "respond")
    lines = text.splitlines(keepends=True)
    target = None
    for n in range(node.lineno, node.end_lineno + 1):
        if "profile = choose_profile(" in lines[n - 1]:
            target = n
            break
    if target is None:
        for n in range(node.lineno, node.end_lineno + 1):
            if "messages = self._messages(" in lines[n - 1]:
                target = n
                break
    if target is None:
        raise RuntimeError("unable to locate respond pre-model boundary")
    return insert_before_line(text, target, "\n".join(wanted))


def ensure_after_turn(text: str) -> str:
    if "self.companion_state.after_turn(user_text, answer)" in text:
        return text
    node = method_node(text, "FurinaChat", "respond")
    lines = text.splitlines(keepends=True)
    target = None
    for n in range(node.lineno, node.end_lineno + 1):
        if 'self.store.add_message("assistant", answer)' in lines[n - 1] or "self.store.add_message('assistant', answer)" in lines[n - 1]:
            target = n + 1
            break
    if target is None:
        for n in range(node.lineno, node.end_lineno + 1):
            if "turn = self.store.increment_state(" in lines[n - 1]:
                target = n
                break
    if target is None:
        raise RuntimeError("unable to locate respond post-model boundary")
    return insert_before_line(text, target, "        self.companion_state.after_turn(user_text, answer)")


def ensure_maintenance(text: str) -> str:
    if "self.companion_state.maintenance()" in text:
        return text
    node = method_node(text, "FurinaChat", "_background")
    lines = text.splitlines(keepends=True)
    target = None
    for n in range(node.lineno, node.end_lineno + 1):
        if "self._consolidate(" in lines[n - 1]:
            target = n
            break
    if target is None:
        raise RuntimeError("unable to locate background maintenance boundary")
    return insert_before_line(text, target, "            self.companion_state.maintenance()")


def ensure_reflection_learning(text: str) -> str:
    if 'source="reflection_behavior"' in text or "source='reflection_behavior'" in text:
        return text
    try:
        node = method_node(text, "FurinaChat", "_reflect")
    except RuntimeError:
        return text
    lines = text.splitlines(keepends=True)
    notes_line = None
    if_line = None
    for n in range(node.lineno, node.end_lineno + 1):
        stripped = lines[n - 1].strip()
        if stripped.startswith("notes ="):
            notes_line = n
        elif notes_line and stripped == "if notes:":
            if_line = n
            break
    if not notes_line or not if_line:
        return text
    block = (
        "                try:\n"
        "                    self.mind.record(\n"
        "                        [{\"kind\": \"behavior\", \"text\": note, \"confidence\": 0.68} for note in notes],\n"
        "                        source=\"reflection_behavior\",\n"
        "                    )\n"
        "                except Exception:\n"
        "                    pass\n"
    )
    return insert_before_line(text, if_line + 1, block.rstrip("\n"))


def set_target_version(text: str) -> str:
    match = re.search(r'VERSION\s*=\s*(["\'])([^"\']+)\1', text)
    if not match:
        raise RuntimeError("version marker missing")
    current = match.group(2)
    if current not in SUPPORTED_PREVIOUS:
        raise RuntimeError(f"unsupported Core version for RC54 patch: {current}")
    return text[:match.start()] + f'VERSION = "{TARGET_VERSION}"' + text[match.end():]


def write_atomic(path: Path, content: str | bytes) -> None:
    temp = path.with_name(path.name + ".rc54.new")
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
    state_path = core / "companion_state_v2.py"
    mind_path = core / "mind_v2.py"
    state_source = Path(__file__).with_name("companion_state_v2.py")
    mind_source = Path(__file__).with_name("mind_v2.py")

    for path in (chat_path, version_path, state_source, mind_source):
        if not path.is_file():
            raise SystemExit(f"RC54 required source missing: {path}")

    current = read_version(version_path)
    if current not in SUPPORTED_PREVIOUS:
        raise SystemExit(f"RC54 cannot patch Core {current or 'unknown'}")

    chat = chat_path.read_text(encoding="utf-8")
    ast.parse(chat)
    chat = ensure_import(chat, "from .companion_state_v2 import CompanionStateV2")
    chat = ensure_import(chat, "from .mind_v2 import FurinaMind")
    chat = ensure_init_wiring(chat)
    chat = ensure_message_context(chat)
    chat = ensure_before_user(chat)
    chat = ensure_after_turn(chat)
    chat = ensure_maintenance(chat)
    chat = ensure_reflection_learning(chat)

    version = set_target_version(version_path.read_text(encoding="utf-8"))
    state_bytes = state_source.read_bytes()
    mind_bytes = mind_source.read_bytes()

    # Validate every candidate before mutating the installed Core.
    compile(chat, str(chat_path), "exec")
    compile(state_bytes.decode("utf-8"), str(state_path), "exec")
    compile(mind_bytes.decode("utf-8"), str(mind_path), "exec")
    compile(version, str(version_path), "exec")

    required = (
        "CompanionStateV2",
        "FurinaMind",
        "LIVING COMPANION STATE:",
        "LEARNED SELF / EXPERIENCE:",
        "self.companion_state.before_user(user_text)",
        "self.mind.observe_user_feedback(user_text)",
        "self.companion_state.after_turn(user_text, answer)",
        "self.companion_state.maintenance()",
    )
    missing = [item for item in required if item not in chat]
    if missing:
        raise SystemExit("RC54 integration incomplete: " + ", ".join(missing))

    # Replace version last. If the process is interrupted, the updater sees the
    # previous version and safely retries instead of accepting a partial patch.
    write_atomic(state_path, state_bytes)
    write_atomic(mind_path, mind_bytes)
    write_atomic(chat_path, chat)
    write_atomic(version_path, version)

    # Final on-disk verification.
    for path in (state_path, mind_path, chat_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    if read_version(version_path) != TARGET_VERSION:
        raise SystemExit("RC54 version commit failed")

    print("FURINA_RC54_TRANSACTIONAL_COMPANION_RECOVERY_OK")


if __name__ == "__main__":
    main()
