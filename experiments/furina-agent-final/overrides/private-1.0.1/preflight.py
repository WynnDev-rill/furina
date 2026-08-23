#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
path = root / "core/furina_agent/tui.py"
text = path.read_text(encoding="utf-8")
tree = ast.parse(text, filename=str(path))
lines = text.splitlines(keepends=True)

nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run_tui"]
if not nodes:
    raise SystemExit("active run_tui missing")
if len(nodes) > 1:
    # Historical patch transforms accumulated top-level definitions. Python only
    # executes the last one, so delete the shadowed entrypoints before applying
    # the private-final simplification. This reduces dead startup surface rather
    # than adding another override on top.
    spans = []
    for node in nodes[:-1]:
        start = sum(len(line) for line in lines[: node.lineno - 1])
        end = sum(len(line) for line in lines[: node.end_lineno])
        spans.append((start, end))
    for start, end in reversed(spans):
        text = text[:start] + text[end:]
    path.write_text(text, encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    remaining = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run_tui"]
    if len(remaining) != 1:
        raise SystemExit(f"run_tui cleanup failed: {len(remaining)} definitions remain")
print("FURINA_PRIVATE_1_0_1_TUI_PREFLIGHT_OK")
