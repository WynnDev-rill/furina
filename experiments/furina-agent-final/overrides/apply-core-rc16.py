#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC16 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc16.py <termux-root>")

    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    paste_input = core / "paste_input.py"
    chat_surface = core / "chat_surface.py"
    version = core / "version.py"
    for path in (paste_input, chat_surface, version):
        if not path.is_file():
            raise SystemExit(f"missing RC16 source: {path}")

    # Textual dispatches subclass handlers first and then base-class default
    # handlers unless prevent_default() is set. RC15 only called stop(), which
    # stops bubbling to parent widgets but does not suppress Input._on_paste.
    # Result: Furina inserted the complete payload, then Textual Input inserted
    # its first line again. Suppress that base default before mutating value.
    p = paste_input.read_text(encoding="utf-8")
    p = replace_once(
        p,
        '''    def _on_paste(self, event: events.Paste) -> None:\n        text = self._normalize_paste(event.text)\n        if text:\n''',
        '''    def _on_paste(self, event: events.Paste) -> None:\n        event.prevent_default()  # RC16: do not also run Input._on_paste\n        text = str(event.text or "")\n        if text:\n''',
        "prevent base paste handler",
    )
    # Keep source line endings exactly as supplied by the terminal/clipboard.
    # Display conversion already makes CR/LF safe in the single-row composer.
    p = replace_once(
        p,
        '''    @staticmethod\n    def _normalize_paste(text: str) -> str:\n        return str(text or "").replace("\\r\\n", "\\n").replace("\\r", "\\n")\n\n''',
        '''    @staticmethod\n    def _normalize_paste(text: str) -> str:\n        # Kept for compatibility with RC15 imports/tests; RC16 paste handling\n        # preserves the source payload byte-for-character at the Python string\n        # level instead of normalizing line endings.\n        return str(text or "")\n\n''',
        "preserve paste line endings",
    )
    paste_input.write_text(p, encoding="utf-8")

    # RC15 removed the composer length cap, but submission still used strip(),
    # which silently removed leading/trailing whitespace and newlines. Commands
    # use a stripped view; actual chat content now keeps the exact composer value.
    s = chat_surface.read_text(encoding="utf-8")
    s = replace_once(
        s,
        '''            text = event.value.strip()\n            event.input.value = ""\n            self._history_index = -1\n            self._history_draft = ""\n            if not text:\n                return\n            if text.casefold() in {"/back", "/exit", "/quit"}:\n                self.exit()\n                return\n            if text.casefold() == "/clear":\n''',
        '''            text = event.value\n            event.input.value = ""\n            self._history_index = -1\n            self._history_draft = ""\n            command = text.strip().casefold()\n            if not command:\n                return\n            if command in {"/back", "/exit", "/quit"}:\n                self.exit()\n                return\n            if command == "/clear":\n''',
        "preserve submitted paste payload",
    )
    s = replace_once(
        s,
        '''            yield FullPasteInput(placeholder="Tulis pesan…", id="composer", max_length=0)  # RC15: full multiline paste\n''',
        '''            yield FullPasteInput(placeholder="Tulis pesan…", id="composer", max_length=0, select_on_focus=False)  # RC16: full paste exactly once\n''',
        "chat composer focus behavior",
    )
    chat_surface.write_text(s, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = replace_once(v, 'VERSION = "1.0.0-rc15"', 'VERSION = "1.0.0-rc16"', "core version")
    version.write_text(v, encoding="utf-8")

    for path in (paste_input, chat_surface, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    required = [
        (paste_input, "event.prevent_default()"),
        (paste_input, 'text = str(event.text or "")'),
        (chat_surface, "command = text.strip().casefold()"),
        (chat_surface, "select_on_focus=False"),
        (version, 'VERSION = "1.0.0-rc16"'),
    ]
    missing = [needle for path, needle in required if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC16 paste-once contract incomplete: " + ", ".join(missing))

    print("Furina RC16 paste exactly-once + exact payload preservation: OK")


if __name__ == "__main__":
    main()
