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
    tui = root / "core/furina_agent/tui.py"
    bridge = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    gradle = root / "bridge/app/build.gradle"
    for path in (agent, tui, bridge, gradle):
        if not path.is_file():
            raise SystemExit(f"missing source: {path}")

    # Core compatibility transforms. Newer override sources already contain
    # these forms; replace_once is intentionally idempotent for that case.
    replace_once(agent, 'WRITE = {"set_text"}', 'WRITE = {"set_text", "ime_action"}', "agent write actions")
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

    # One Termux approval now covers the exact requested device task, including
    # Send/Kirim if it is explicitly part of that task.
    replace_once(
        tui,
        'Perintah ini membutuhkan kontrol layar. Izinkan Furina menavigasi/mengetik? Send/aksi eksternal tetap dikonfirmasi tepat sebelum dilakukan',
        'Izinkan Furina menyelesaikan tugas ini di layar? Jika disetujui, seluruh navigasi, pengetikan, pencarian, dan Send/Kirim/Post/Share yang memang diminta dalam tugas ini akan dilakukan otomatis tanpa konfirmasi kedua',
        "single task approval text",
    )
    replace_once(tui, '[dim]AI ROUTER[/]', '[dim]MODEL ROUTER[/]', "router label")
    replace_once(tui, '"AI Provider / API key"', '"Provider / API key"', "provider menu label")
    replace_once(tui, 'title="AI PROVIDERS"', 'title="MODEL PROVIDERS"', "provider panel label")
    replace_once(tui, 'table.add_row("Nama AI", cfg.persona_name)', 'table.add_row("Nama persona", cfg.persona_name)', "persona setting label")
    replace_once(tui, '"[dim]1 Nama panggilan  2 Nama AI  3 Toggle auto-start  b Back[/]"', '"[dim]1 Nama panggilan  2 Nama persona  3 Toggle auto-start  b Back[/]"', "persona setting menu")
    replace_once(tui, 'console.print(f"[dim]AI: {llm.last.backend} / {llm.last.model}[/]")', 'console.print(f"[dim]Model: {llm.last.backend} / {llm.last.model}[/]")', "backend status label")

    # Bridge RC3 resolves node actions by a stable target selector captured from
    # the same screen snapshot. Numeric node IDs remain only a fallback.
    replace_once(
        bridge,
        '            case "tap_node":\n                ok = tapNode(a.optInt("node", -1));\n                break;',
        '            case "tap_node":\n                ok = tapNode(a);\n                break;',
        "Bridge selector tap switch",
    )
    replace_once(
        bridge,
        '            case "set_text":\n                ok = setText(a.optInt("node", -1), a.optString("text", ""));\n                break;\n            case "back":',
        '            case "set_text":\n                ok = setText(a, a.optString("text", ""));\n                break;\n            case "ime_action":\n                ok = imeAction(a);\n                break;\n            case "back":',
        "Bridge selector text and IME switch",
    )
    replace_once(
        bridge,
        '        if (n.isScrollable()) j.put("scrollable", true);\n        if (n.isCheckable()) j.put("checkable", true).put("checked", n.isChecked());',
        '        if (n.isScrollable()) j.put("scrollable", true);\n        if (n.isFocused()) j.put("focused", true);\n        if (n.isEnabled()) j.put("enabled", true);\n        if (n.isCheckable()) j.put("checkable", true).put("checked", n.isChecked());',
        "Bridge richer node state",
    )

    selector_helpers = r'''    private int selectorScore(AccessibilityNodeInfo n, JSONObject target) {
        int score = 0;
        String expectedView = target.optString("view_id", "");
        String actualView = n.getViewIdResourceName();
        if (!expectedView.isEmpty() && expectedView.equals(actualView)) score += 12;

        String expectedText = target.optString("text", "");
        CharSequence actualTextCs = n.getText();
        String actualText = actualTextCs == null ? "" : actualTextCs.toString().trim();
        if (!expectedText.isEmpty() && expectedText.equals(actualText)) score += 8;

        String expectedDesc = target.optString("desc", "");
        CharSequence actualDescCs = n.getContentDescription();
        String actualDesc = actualDescCs == null ? "" : actualDescCs.toString().trim();
        if (!expectedDesc.isEmpty() && expectedDesc.equals(actualDesc)) score += 8;

        String expectedClass = target.optString("class", "");
        CharSequence cls = n.getClassName();
        if (!expectedClass.isEmpty() && cls != null && expectedClass.equals(shortClass(cls.toString()))) score += 3;

        if (target.optBoolean("editable", false) && n.isEditable()) score += 4;
        if (target.optBoolean("clickable", false) && n.isClickable()) score += 2;
        if (target.optBoolean("scrollable", false) && n.isScrollable()) score += 2;

        JSONArray expectedBounds = target.optJSONArray("bounds");
        if (expectedBounds != null && expectedBounds.length() >= 4) {
            Rect r = new Rect();
            n.getBoundsInScreen(r);
            int delta = Math.abs(r.left - expectedBounds.optInt(0))
                    + Math.abs(r.top - expectedBounds.optInt(1))
                    + Math.abs(r.right - expectedBounds.optInt(2))
                    + Math.abs(r.bottom - expectedBounds.optInt(3));
            if (delta <= 24) score += 4;
            else if (delta <= 96) score += 2;
        }
        return score;
    }

    private AccessibilityNodeInfo resolveNode(JSONObject action) {
        JSONObject target = action.optJSONObject("target");
        int fallbackId = action.optInt("node", -1);
        if (target == null) return nodeByIndex(fallbackId);

        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return null;
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(root);
        AccessibilityNodeInfo best = null;
        int bestScore = -1;
        int seen = 0;
        while (!q.isEmpty() && seen++ < 350) {
            AccessibilityNodeInfo n = q.remove();
            int score = selectorScore(n, target);
            if (score > bestScore) {
                best = n;
                bestScore = score;
            }
            for (int c = 0; c < n.getChildCount(); c++) {
                AccessibilityNodeInfo child = n.getChild(c);
                if (child != null) q.add(child);
            }
        }
        boolean strongIdentity = !target.optString("view_id", "").isEmpty()
                || !target.optString("text", "").isEmpty()
                || !target.optString("desc", "").isEmpty();
        int threshold = strongIdentity ? 6 : 5;
        if (best != null && bestScore >= threshold) return best;
        return nodeByIndex(fallbackId);
    }

'''
    replace_once(
        bridge,
        '    private boolean tapNode(int id) {\n        AccessibilityNodeInfo n = nodeByIndex(id);',
        selector_helpers + '    private boolean tapNode(JSONObject action) {\n        AccessibilityNodeInfo n = resolveNode(action);',
        "Bridge stable selector resolver",
    )
    replace_once(
        bridge,
        '    private boolean setText(int id, String text) {\n        AccessibilityNodeInfo n = nodeByIndex(id);',
        '    private boolean setText(JSONObject action, String text) {\n        AccessibilityNodeInfo n = resolveNode(action);',
        "Bridge stable set_text",
    )
    replace_once(
        bridge,
        '    private boolean tap(int x, int y) {',
        '    private boolean imeAction(JSONObject action) {\n        AccessibilityNodeInfo n = resolveNode(action);\n        if (n == null || !n.isEditable() || Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return false;\n        if (!n.isFocused()) n.performAction(AccessibilityNodeInfo.ACTION_FOCUS);\n        return n.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.getId());\n    }\n\n    private boolean tap(int x, int y) {',
        "Bridge stable IME implementation",
    )

    replace_once(gradle, "        versionCode 10001", "        versionCode 10003", "Bridge versionCode")
    replace_once(gradle, "        versionName '1.0.0-rc1'", "        versionName '1.0.0-rc3'", "Bridge versionName")

    agent_text = agent.read_text(encoding="utf-8")
    tui_text = tui.read_text(encoding="utf-8")
    bridge_text = bridge.read_text(encoding="utf-8")
    gradle_text = gradle.read_text(encoding="utf-8")
    required = [
        ("agent ime_action", "ime_action" in agent_text),
        ("agent stable target", 'payload["target"] = selector' in agent_text),
        ("agent task approval", 'needs_approval = (not task_authorized)' in agent_text),
        ("agent checks Bridge result", "_result_ok" in agent_text),
        ("single task approval text", "tanpa konfirmasi kedua" in tui_text),
        ("bridge ACTION_IME_ENTER", "ACTION_IME_ENTER" in bridge_text),
        ("bridge stable selector", "selectorScore" in bridge_text and "resolveNode" in bridge_text),
        ("bridge rc3 code", "versionCode 10003" in gradle_text),
        ("bridge rc3 name", "versionName '1.0.0-rc3'" in gradle_text),
    ]
    failed = [name for name, ok in required if not ok]
    if failed:
        raise SystemExit("companion-v2 transform incomplete: " + ", ".join(failed))
    print("companion-v2 RC3 stable UI transform: OK")


if __name__ == "__main__":
    main()
