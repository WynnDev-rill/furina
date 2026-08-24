#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"
MEMORY = CORE / "memory.py"
TUI = CORE / "tui.py"


def class_node(text: str, name: str) -> ast.ClassDef:
    tree = ast.parse(text)
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name), None)
    if node is None:
        raise SystemExit(f"missing class {name}")
    return node


def replace_method(path: Path, class_name: str, name: str, source: str) -> None:
    text = path.read_text(encoding="utf-8")
    cls = class_node(text, class_name)
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{path.name}:{class_name}.{name}: expected one method, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[: start_line - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    path.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


def insert_before_method(path: Path, class_name: str, before: str, source: str, guard: str) -> None:
    text = path.read_text(encoding="utf-8")
    if guard in text:
        return
    cls = class_node(text, class_name)
    node = next((n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == before), None)
    if node is None:
        raise SystemExit(f"{path.name}:{class_name}.{before} missing")
    lines = text.splitlines(keepends=True)
    pos = sum(len(x) for x in lines[: node.lineno - 1])
    path.write_text(text[:pos] + source.rstrip() + "\n\n" + text[pos:], encoding="utf-8")


def module_function_source(path: Path, name: str) -> tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, list[str]]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{path.name}:{name}: expected one function, got {len(nodes)}")
    return text, nodes[0], text.splitlines(keepends=True)


def replace_module_function(path: Path, name: str, source: str) -> None:
    text, node, lines = module_function_source(path, name)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[: start_line - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    path.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


def insert_before_module_function(path: Path, before: str, source: str, guard: str) -> None:
    text = path.read_text(encoding="utf-8")
    if guard in text:
        return
    text, node, lines = module_function_source(path, before)
    pos = sum(len(x) for x in lines[: node.lineno - 1])
    path.write_text(text[:pos] + source.rstrip() + "\n\n" + text[pos:], encoding="utf-8")


# ---------------------------------------------------------------------------
# Conversation history and long-term memory have different lifetimes.
# FurinaHub keeps using the persistent global active conversation. A Termux
# process can instead bind one MemoryStore instance to its own short-term
# conversation without changing the global active-conversation KV value.
# ---------------------------------------------------------------------------
insert_before_method(
    MEMORY,
    "MemoryStore",
    "active_conversation_id",
    r'''    def bind_conversation(self, conversation_id: int | None) -> int | None:
        """Bind this MemoryStore instance to one conversation without changing global UI state."""
        if conversation_id is None:
            self._conversation_override = None
            return None
        value = int(conversation_id)
        if not self._conn().execute("SELECT 1 FROM conversations WHERE id=?", (value,)).fetchone():
            raise ValueError(f"Percakapan tidak ditemukan: {value}")
        self._conversation_override = value
        return value

    def create_session_conversation(self, title: str = "Percakapan baru") -> int:
        """Create a thread owned by this process/session without switching FurinaHub's global thread."""
        now = time.time()
        clean = re.sub(r"\s+", " ", str(title or "")).strip()[:80] or "Percakapan baru"
        cur = self._conn().execute(
            "INSERT INTO conversations(title,created_at,updated_at) VALUES(?,?,?)",
            (clean, now, now),
        )
        value = int(cur.lastrowid)
        self._conn().commit()
        self._conversation_override = value
        return value''',
    "def create_session_conversation",
)

replace_method(
    MEMORY,
    "MemoryStore",
    "active_conversation_id",
    r'''    def active_conversation_id(self) -> int:
        # An instance-bound conversation is short-term/session state. It takes
        # precedence only for this MemoryStore object and never rewrites the
        # persistent active conversation used by FurinaHub.
        override = getattr(self, "_conversation_override", None)
        if override is not None:
            try:
                value = int(override)
            except Exception:
                value = 0
            if value and self._conn().execute("SELECT 1 FROM conversations WHERE id=?", (value,)).fetchone():
                return value
            self._conversation_override = None

        row = self._conn().execute("SELECT value FROM kv WHERE key='active_conversation_id'").fetchone()
        try:
            value = int(row[0]) if row else 1
        except Exception:
            value = 1
        if not self._conn().execute("SELECT 1 FROM conversations WHERE id=?", (value,)).fetchone():
            latest = self._conn().execute("SELECT id FROM conversations ORDER BY updated_at DESC,id DESC LIMIT 1").fetchone()
            value = int(latest[0]) if latest else self.create_conversation()
        return value''',
)

# ---------------------------------------------------------------------------
# Termux lifecycle: one short-term thread per `furina` process. Returning to the
# menu with /back keeps that thread. Closing Termux / starting a new `furina`
# process starts a fresh thread on the first real message. Long-term memory,
# relationship state, provider/model choices, and old conversations are kept.
# ---------------------------------------------------------------------------
insert_before_module_function(
    TUI,
    "_chat_legacy",
    r'''_TERMUX_CHAT_CONVERSATION_ID = None


def _termux_chat_store() -> MemoryStore:
    global _TERMUX_CHAT_CONVERSATION_ID
    store = MemoryStore()
    if _TERMUX_CHAT_CONVERSATION_ID is not None:
        try:
            store.bind_conversation(_TERMUX_CHAT_CONVERSATION_ID)
        except Exception:
            _TERMUX_CHAT_CONVERSATION_ID = None
    return store


def _ensure_termux_chat_conversation(store: MemoryStore) -> int:
    global _TERMUX_CHAT_CONVERSATION_ID
    if _TERMUX_CHAT_CONVERSATION_ID is None:
        _TERMUX_CHAT_CONVERSATION_ID = store.create_session_conversation("Percakapan baru")
    else:
        try:
            store.bind_conversation(_TERMUX_CHAT_CONVERSATION_ID)
        except Exception:
            _TERMUX_CHAT_CONVERSATION_ID = store.create_session_conversation("Percakapan baru")
    return int(_TERMUX_CHAT_CONVERSATION_ID)''',
    "_TERMUX_CHAT_CONVERSATION_ID = None",
)

text, node, lines = module_function_source(TUI, "_chat_legacy")
segment = "".join(lines[node.lineno - 1 : node.end_lineno])
if "store = _termux_chat_store()" not in segment:
    if segment.count("store = MemoryStore()") != 1:
        raise SystemExit("TUI chat MemoryStore marker missing or ambiguous")
    segment = segment.replace("store = MemoryStore()", "store = _termux_chat_store()", 1)
if "_ensure_termux_chat_conversation(store)" not in segment:
    marker = '        if not text:\n            continue\n'
    if segment.count(marker) != 1:
        raise SystemExit("TUI non-empty input marker missing or ambiguous")
    segment = segment.replace(
        marker,
        marker + "        # First real message owns a fresh process-scoped short-term thread.\n        _ensure_termux_chat_conversation(store)\n",
        1,
    )
replace_module_function(TUI, "_chat_legacy", segment)

for path in (MEMORY, TUI):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("FURINA_PRIVATE_1_0_6_SESSION_SCOPE_OK")
