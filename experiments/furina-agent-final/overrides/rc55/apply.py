#!/usr/bin/env python3
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

TARGET_VERSION = "1.0.0-rc55"
SUPPORTED_PREVIOUS = {"1.0.0-rc52", "1.0.0-rc53", "1.0.0-rc54", TARGET_VERSION}


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
    if node is None:
        raise RuntimeError("unable to locate FurinaChat.__init__")
    lines = text.splitlines(keepends=True)
    target = node.end_lineno + 1
    for n in range(node.lineno, node.end_lineno + 1):
        if "self.llm = llm" in lines[n - 1]:
            target = n + 1
            break
    return insert_before_line(text, target, "\n".join(needed))


def ensure_message_context(text: str) -> str:
    missing = []
    if "LIVING COMPANION STATE:" not in text:
        missing.append('        system += "\\n\\nLIVING COMPANION STATE:\\n" + self.companion_state.context()')
    if "LEARNED SELF / EXPERIENCE:" not in text:
        missing.append('        system += "\\n\\nLEARNED SELF / EXPERIENCE:\\n" + self.mind.current_context() + "\\n" + self.mind.context(8)')
    if not missing:
        return text
    node = method_node(text, "FurinaChat", "_messages")
    if node is None:
        raise RuntimeError("unable to locate FurinaChat._messages")
    lines = text.splitlines(keepends=True)
    target = None
    for n in range(node.lineno, node.end_lineno + 1):
        line = lines[n - 1]
        if "messages =" in line and '"system"' in line:
            target = n
            break
    if target is None:
        for n in range(node.lineno, node.end_lineno + 1):
            if lines[n - 1].lstrip().startswith("return "):
                target = n
                break
    if target is None:
        raise RuntimeError("unable to locate _messages system boundary")
    return insert_before_line(text, target, "\n".join(missing))


def ensure_before_user(text: str) -> str:
    wanted = []
    if "self.companion_state.before_user(user_text)" not in text:
        wanted.append("        self.companion_state.before_user(user_text)")
    if "self.mind.observe_user_feedback(user_text)" not in text:
        wanted.append("        self.mind.observe_user_feedback(user_text)")
    if not wanted:
        return text
    node = method_node(text, "FurinaChat", "respond")
    if node is None:
        raise RuntimeError("unable to locate FurinaChat.respond")
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
    if node is None:
        raise RuntimeError("unable to locate FurinaChat.respond")
    lines = text.splitlines(keepends=True)
    target = None
    for n in range(node.lineno, node.end_lineno + 1):
        line = lines[n - 1]
        if 'self.store.add_message("assistant", answer)' in line or "self.store.add_message('assistant', answer)" in line:
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


def ensure_optional_background_maintenance(text: str) -> str:
    """Maintenance is an optimization, not a required compatibility boundary.

    Some deployed RC52 builds do not expose FurinaChat._background. Companion
    state already decays lazily in before_user()/context(), so absence of this
    hook must never block installation.
    """
    if "self.companion_state.maintenance()" in text:
        return text
    node = method_node(text, "FurinaChat", "_background")
    if node is None:
        return text
    lines = text.splitlines(keepends=True)
    for n in range(node.lineno, node.end_lineno + 1):
        if "self._consolidate(" in lines[n - 1]:
            return insert_before_line(text, n, "            self.companion_state.maintenance()")
    return text


def ensure_optional_reflection_learning(text: str) -> str:
    if 'source="reflection_behavior"' in text or "source='reflection_behavior'" in text:
        return text
    node = method_node(text, "FurinaChat", "_reflect")
    if node is None:
        return text
    lines = text.splitlines(keepends=True)
    seen_notes = False
    for n in range(node.lineno, node.end_lineno + 1):
        stripped = lines[n - 1].strip()
        if stripped.startswith("notes ="):
            seen_notes = True
            continue
        if seen_notes and stripped == "if notes:":
            block = (
                "                try:\n"
                "                    self.mind.record(\n"
                "                        [{\"kind\": \"behavior\", \"text\": note, \"confidence\": 0.68} for note in notes],\n"
                "                        source=\"reflection_behavior\",\n"
                "                    )\n"
                "                except Exception:\n"
                "                    pass"
            )
            return insert_before_line(text, n + 1, block)
    return text


def set_target_version(text: str) -> str:
    m = re.search(r'VERSION\s*=\s*(["\'])([^"\']+)\1', text)
    if not m:
        raise RuntimeError("version marker missing")
    current = m.group(2)
    if current not in SUPPORTED_PREVIOUS:
        raise RuntimeError(f"unsupported Core version for RC55 patch: {current}")
    return text[:m.start()] + f'VERSION = "{TARGET_VERSION}"' + text[m.end():]


def write_atomic(path: Path, content: str | bytes) -> None:
    temp = path.with_name(path.name + ".rc55.new")
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
    # RC55 is the compatibility recovery patch. Reuse the canonical RC53 state
    # module and the already installed mind module instead of referring to two
    # files that were never shipped in the RC55 override directory.
    state_source = Path(__file__).resolve().parent.parent / "rc53" / "companion_state_v2.py"
    mind_source = mind_path

    for path in (chat_path, version_path, state_source, mind_source):
        if not path.is_file():
            raise SystemExit(f"RC55 required source missing: {path}")

    current = read_version(version_path)
    if current not in SUPPORTED_PREVIOUS:
        raise SystemExit(f"RC55 cannot patch Core {current or 'unknown'}")

    chat = chat_path.read_text(encoding="utf-8")
    ast.parse(chat)
    chat = ensure_import(chat, "from .companion_state_v2 import CompanionStateV2")
    chat = ensure_import(chat, "from .mind_v2 import FurinaMind")
    chat = ensure_init_wiring(chat)
    chat = ensure_message_context(chat)
    chat = ensure_before_user(chat)
    chat = ensure_after_turn(chat)
    chat = ensure_optional_background_maintenance(chat)
    chat = ensure_optional_reflection_learning(chat)

    version = set_target_version(version_path.read_text(encoding="utf-8"))
    state_bytes = state_source.read_bytes()
    mind_bytes = mind_source.read_bytes()

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
    )
    missing = [item for item in required if item not in chat]
    if missing:
        raise SystemExit("RC55 integration incomplete: " + ", ".join(missing))

    write_atomic(state_path, state_bytes)
    write_atomic(mind_path, mind_bytes)
    write_atomic(chat_path, chat)
    write_atomic(version_path, version)

    for path in (state_path, mind_path, chat_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    if read_version(version_path) != TARGET_VERSION:
        raise SystemExit("RC55 version commit failed")

    print("FURINA_RC55_COMPATIBLE_COMPANION_PATCH_OK")


if __name__ == "__main__":
    main()
