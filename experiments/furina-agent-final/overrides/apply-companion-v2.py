#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(path: pathlib.Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-companion-v2.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    agent = root / "core/furina_agent/agent.py"
    bridge = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    gradle = root / "bridge/app/build.gradle"
    for path in (agent, bridge, gradle):
        if not path.is_file():
            raise SystemExit(f"missing source: {path}")

    replace_once(
        agent,
        'WRITE = {"set_text"}',
        'WRITE = {"set_text", "ime_action"}',
        "agent write actions",
    )
    replace_once(
        agent,
        '- Buka YouTube dari package yang benar, observasi layar, temukan Search/Cari melalui accessibility tree, aktifkan kontrol itu, isi query dengan set_text, lalu benar-benar submit pencarian dengan tombol/search suggestion/keyboard action yang terlihat.\n- Setelah submit, observasi lagi. Finish hanya setelah layar memperlihatkan hasil pencarian atau channel/video yang cocok dengan query pengguna.\n- Jika set_text tidak mengubah layar, cari tombol Search/Cari/Enter yang terlihat dan tekan. Jangan diam setelah mengetik.',
        '- Buka YouTube dari package yang benar, observasi layar, temukan Search/Cari melalui accessibility tree, aktifkan kontrol itu, isi query dengan set_text, lalu submit dengan ime_action pada field yang sama bila tersedia. Jika itu gagal, gunakan tombol/search suggestion yang terlihat.\n- Setelah submit, observasi lagi. Finish hanya setelah layar memperlihatkan hasil pencarian atau channel/video yang cocok dengan query pengguna.\n- Jangan berhenti setelah mengetik query. Setelah set_text selalu lanjutkan ke ime_action atau kontrol Search/Cari yang terlihat lalu verifikasi hasil.',
        "YouTube skill",
    )
    replace_once(
        agent,
        '"action": {{"type": "observe|wait|tap_node|tap|swipe|set_text|back|home|recents|open_app|finish", ...}}',
        '"action": {{"type": "observe|wait|tap_node|tap|swipe|set_text|ime_action|back|home|recents|open_app|finish", ...}}',
        "planner action schema",
    )
    replace_once(
        agent,
        '- set_text: {{"type":"set_text","node":12,"text":"..."}}\n- open_app:',
        '- set_text: {{"type":"set_text","node":12,"text":"..."}}\n- ime_action: {{"type":"ime_action","node":12}} ; submit Search/Enter/Go dari field editable yang sedang fokus\n- open_app:',
        "planner ime format",
    )
    replace_once(
        agent,
        '2. Setelah open_app/tap/set_text/swipe selalu gunakan state berikutnya untuk menentukan langkah baru.',
        '2. Setelah open_app/tap/set_text/ime_action/swipe selalu gunakan state berikutnya untuk menentukan langkah baru.',
        "planner state rule",
    )
    replace_once(
        agent,
        '        if typ == "set_text":\n            return "write", "mengisi teks lokal"',
        '        if typ in WRITE:\n            return "write", "mengisi/men-submit teks lokal"',
        "ime risk",
    )
    replace_once(
        agent,
        'submitted_after = any(a.get("type") in {"tap", "tap_node"} for a in actions[last_set + 1 :])',
        'submitted_after = any(a.get("type") in {"tap", "tap_node", "ime_action"} for a in actions[last_set + 1 :])',
        "YouTube completion verification",
    )

    replace_once(
        bridge,
        '            case "set_text":\n                ok = setText(a.optInt("node", -1), a.optString("text", ""));\n                break;\n            case "back":',
        '            case "set_text":\n                ok = setText(a.optInt("node", -1), a.optString("text", ""));\n                break;\n            case "ime_action":\n                ok = imeAction(a.optInt("node", -1));\n                break;\n            case "back":',
        "Bridge ime switch",
    )
    replace_once(
        bridge,
        '    private boolean tap(int x, int y) {',
        '    private boolean imeAction(int id) {\n        AccessibilityNodeInfo n = nodeByIndex(id);\n        if (n == null || !n.isEditable() || Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return false;\n        if (!n.isFocused()) {\n            n.performAction(AccessibilityNodeInfo.ACTION_FOCUS);\n            n = nodeByIndex(id);\n            if (n == null) return false;\n        }\n        return n.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.getId());\n    }\n\n    private boolean tap(int x, int y) {',
        "Bridge ime implementation",
    )

    replace_once(gradle, "        versionCode 10001", "        versionCode 10002", "Bridge versionCode")
    replace_once(gradle, "        versionName '1.0.0-rc1'", "        versionName '1.0.0-rc2'", "Bridge versionName")

    # Final contract checks. Fail closed if any expected behavior is absent.
    agent_text = agent.read_text(encoding="utf-8")
    bridge_text = bridge.read_text(encoding="utf-8")
    gradle_text = gradle.read_text(encoding="utf-8")
    required = [
        ("agent ime_action", "ime_action" in agent_text),
        ("agent structured JSON", "json_mode=True" in agent_text),
        ("bridge ACTION_IME_ENTER", "ACTION_IME_ENTER" in bridge_text),
        ("bridge rc2 code", "versionCode 10002" in gradle_text),
        ("bridge rc2 name", "versionName '1.0.0-rc2'" in gradle_text),
    ]
    failed = [name for name, ok in required if not ok]
    if failed:
        raise SystemExit("companion-v2 transform incomplete: " + ", ".join(failed))
    print("companion-v2 IME transform: OK")


if __name__ == "__main__":
    main()
