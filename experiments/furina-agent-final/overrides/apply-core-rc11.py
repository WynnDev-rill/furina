#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source marker, got {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc11.py <termux-root>")

    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    tui = core / "tui.py"
    agent = core / "agent.py"
    version = core / "version.py"
    chat_surface = core / "chat_surface.py"
    tool_runtime = core / "tool_runtime.py"

    for path in (tui, agent, version, chat_surface, tool_runtime):
        if not path.is_file():
            raise SystemExit(f"missing RC11 source: {path}")

    atext = agent.read_text(encoding="utf-8")

    if "from .tool_runtime import AgentToolRuntime\n" not in atext:
        marker = "from .memory import MemoryStore\n"
        if marker not in atext:
            raise SystemExit("RC11 tool runtime import anchor missing")
        atext = atext.replace(marker, marker + "from .tool_runtime import AgentToolRuntime\n", 1)

    if "self.tools = AgentToolRuntime(bridge, store)" not in atext:
        marker = "        self.bridge = bridge\n"
        if marker not in atext:
            raise SystemExit("RC11 tool runtime init anchor missing")
        atext = atext.replace(marker, marker + "        self.tools = AgentToolRuntime(bridge, store)\n", 1)

    old_exec = "self.bridge.action(payload)"
    new_exec = "self.tools.execute(payload)"
    if old_exec in atext:
        atext = atext.replace(old_exec, new_exec)
    if new_exec not in atext:
        raise SystemExit("RC11 agent execution boundary was not installed")

    if "RC11: relevance-ranked compact screen" not in atext:
        start_marker = "    @staticmethod\n    def _compact_screen(screen: dict) -> dict:\n"
        end_marker = "    @staticmethod\n    def _actionable_count(screen: dict) -> int:\n"
        start = atext.find(start_marker)
        end = atext.find(end_marker, start + 1)
        if start < 0 or end < 0:
            raise SystemExit("RC11 compact-screen anchors missing")
        compact = '''    @staticmethod
    def _compact_screen(screen: dict) -> dict:
        # RC11: relevance-ranked compact screen for lower planner latency.
        # Node ids are preserved; exact duplicates are removed and actionable
        # semantic nodes are prioritized before planner context is built.
        compact = {
            "ok": screen.get("ok"),
            "package": screen.get("package"),
            "window_title": screen.get("window_title"),
        }
        raw_nodes = [n for n in (screen.get("nodes") or []) if isinstance(n, dict)]

        def score(node: dict) -> int:
            value = 0
            if node.get("editable"):
                value += 9
            if node.get("clickable"):
                value += 7
            if node.get("scrollable"):
                value += 5
            if node.get("focusable"):
                value += 3
            if str(node.get("text") or node.get("desc") or "").strip():
                value += 4
            if str(node.get("view_id") or "").strip():
                value += 2
            if node.get("selected") or node.get("checked"):
                value += 1
            return value

        nodes = []
        seen = set()
        for node in sorted(raw_nodes, key=score, reverse=True):
            useful = any(
                node.get(k) not in (None, "", False)
                for k in ("text", "desc", "view_id", "clickable", "editable", "scrollable", "focusable")
            )
            if not useful:
                continue
            key = (
                node.get("view_id"),
                node.get("text"),
                node.get("desc"),
                node.get("class"),
                node.get("bounds"),
                bool(node.get("clickable")),
                bool(node.get("editable")),
            )
            try:
                hash(key)
            except TypeError:
                key = repr(key)
            if key in seen:
                continue
            seen.add(key)
            nodes.append(node)
            if len(nodes) >= 120:
                break

        compact["nodes"] = nodes
        if screen.get("vision_elements"):
            compact["vision_elements"] = screen.get("vision_elements")[:30]
        return compact

'''
        atext = atext[:start] + compact + atext[end:]

    agent.write_text(atext, encoding="utf-8")

    ttext = tui.read_text(encoding="utf-8")
    import_line = "from .chat_surface import run_chat_surface\n"
    if import_line not in ttext:
        marker = "from .bridge import AndroidBridge\n"
        if marker not in ttext:
            raise SystemExit("RC11 TUI import anchor missing")
        ttext = ttext.replace(marker, marker + import_line, 1)

    if "def _chat_legacy(console):" not in ttext:
        ttext = _replace_once(
            ttext,
            "def _chat(console):\n",
            "def _chat_legacy(console):\n",
            "RC11 legacy chat rename",
        )

    if "def _chat(console):\n    try:\n        run_chat_surface()" not in ttext:
        anchor = "\ndef _memory_list(console):\n"
        if anchor not in ttext:
            raise SystemExit("RC11 chat wrapper anchor missing")
        wrapper = r'''
def _chat(console):
    try:
        run_chat_surface()
        return
    except Exception as exc:
        try:
            log_dir = Path.home() / ".furina-agent/logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with (log_dir / "tui.log").open("a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} chat_surface: {exc}\n")
        except Exception:
            pass
        _chat_legacy(console)

'''
        ttext = ttext.replace(anchor, "\n" + wrapper + "def _memory_list(console):\n", 1)

    tui.write_text(ttext, encoding="utf-8")

    vtext = version.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc11"' not in vtext:
        vtext = _replace_once(
            vtext,
            'VERSION = "1.0.0-rc10"',
            'VERSION = "1.0.0-rc11"',
            "RC11 version",
        )
        version.write_text(vtext, encoding="utf-8")

    final_agent = agent.read_text(encoding="utf-8")
    final_tui = tui.read_text(encoding="utf-8")
    required_agent = [
        "AgentToolRuntime",
        "self.tools.execute(payload)",
        "RC11: relevance-ranked compact screen",
        "len(nodes) >= 120",
    ]
    required_tui = [
        "run_chat_surface",
        "def _chat_legacy(console):",
        "def _chat(console):",
        "tui.log",
    ]
    missing = [x for x in required_agent if x not in final_agent]
    missing += [x for x in required_tui if x not in final_tui]
    if missing:
        raise SystemExit("RC11 contract incomplete: " + ", ".join(missing))
    if 'VERSION = "1.0.0-rc11"' not in version.read_text(encoding="utf-8"):
        raise SystemExit("RC11 version bump failed")

    print("Furina RC11 chat + agent foundation transform: OK")


if __name__ == "__main__":
    main()
