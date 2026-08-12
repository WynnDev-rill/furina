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
        raise SystemExit("usage: apply-universal-agent-rc5.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    service = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    gradle = root / "bridge/app/build.gradle"
    tui = root / "core/furina_agent/tui.py"
    if not service.is_file() or not gradle.is_file() or not tui.is_file():
        raise SystemExit("missing RC5 source")

    replace_once(
        service,
        "import android.content.Intent;\n",
        "import android.content.Intent;\nimport android.content.ClipData;\nimport android.content.ClipboardManager;\n",
        "clipboard imports",
    )
    replace_once(
        service,
        "import android.view.accessibility.AccessibilityNodeInfo;\n",
        "import android.view.accessibility.AccessibilityNodeInfo;\nimport android.view.accessibility.AccessibilityWindowInfo;\n",
        "window info import",
    )
    replace_once(
        service,
        '        out.put("package", pkg == null ? "" : pkg.toString());\n        JSONArray nodes = new JSONArray();',
        '        out.put("package", pkg == null ? "" : pkg.toString());\n        AccessibilityWindowInfo window = root.getWindow();\n        if (window != null && window.getTitle() != null) out.put("window_title", window.getTitle().toString());\n        JSONArray nodes = new JSONArray();',
        "window title",
    )
    replace_once(
        service,
        '        if (n.isScrollable()) j.put("scrollable", true);\n        if (n.isFocused()) j.put("focused", true);\n        if (n.isEnabled()) j.put("enabled", true);\n        if (n.isCheckable()) j.put("checkable", true).put("checked", n.isChecked());',
        '        if (n.isScrollable()) j.put("scrollable", true);\n        if (n.isFocusable()) j.put("focusable", true);\n        if (n.isLongClickable()) j.put("long_clickable", true);\n        if (n.isFocused()) j.put("focused", true);\n        if (n.isSelected()) j.put("selected", true);\n        if (n.isEnabled()) j.put("enabled", true);\n        if (n.isPassword()) j.put("password", true);\n        if (n.isCheckable()) j.put("checkable", true).put("checked", n.isChecked());\n        JSONArray actions = new JSONArray();\n        for (AccessibilityNodeInfo.AccessibilityAction action : n.getActionList()) {\n            int aid = action.getId();\n            if (aid == AccessibilityNodeInfo.ACTION_CLICK) actions.put("click");\n            else if (aid == AccessibilityNodeInfo.ACTION_LONG_CLICK) actions.put("long_click");\n            else if (aid == AccessibilityNodeInfo.ACTION_SET_TEXT) actions.put("set_text");\n            else if (aid == AccessibilityNodeInfo.ACTION_PASTE) actions.put("paste");\n            else if (aid == AccessibilityNodeInfo.ACTION_SCROLL_FORWARD) actions.put("scroll_forward");\n            else if (aid == AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD) actions.put("scroll_backward");\n            else if (aid == AccessibilityNodeInfo.ACTION_FOCUS) actions.put("focus");\n        }\n        if (actions.length() > 0) j.put("actions", actions);',
        "richer node actions",
    )
    replace_once(
        service,
        '            case "tap_node":\n                ok = tapNode(a);\n                break;\n            case "tap":',
        '            case "tap_node":\n                ok = tapNode(a);\n                break;\n            case "long_press":\n                ok = longPress(a);\n                break;\n            case "tap":',
        "long press switch",
    )
    replace_once(
        service,
        '            case "swipe":\n                ok = swipe(a.optInt("x1"), a.optInt("y1"), a.optInt("x2"), a.optInt("y2"), a.optInt("duration_ms", 350));\n                break;\n            case "set_text":',
        '            case "swipe":\n                ok = swipe(a.optInt("x1"), a.optInt("y1"), a.optInt("x2"), a.optInt("y2"), a.optInt("duration_ms", 350));\n                break;\n            case "scroll_node":\n                ok = scrollNode(a);\n                break;\n            case "set_text":',
        "scroll node switch",
    )

    old_set_text = '''    private boolean setText(JSONObject action, String text) {
        AccessibilityNodeInfo n = resolveNode(action);
        if (n == null || !n.isEditable()) return false;
        Bundle b = new Bundle();
        b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        return n.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, b);
    }

'''
    new_set_text = '''    private AccessibilityNodeInfo editableNode(AccessibilityNodeInfo start) {
        if (start == null) return null;
        if (start.isEditable()) return start;
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(start);
        int seen = 0;
        while (!q.isEmpty() && seen++ < 60) {
            AccessibilityNodeInfo n = q.remove();
            if (n.isEditable()) return n;
            for (int i = 0; i < n.getChildCount(); i++) {
                AccessibilityNodeInfo child = n.getChild(i);
                if (child != null) q.add(child);
            }
        }
        return null;
    }

    private boolean setText(JSONObject action, String text) {
        AccessibilityNodeInfo n = editableNode(resolveNode(action));
        if (n == null) return false;
        if (!n.isFocused()) n.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        Bundle b = new Bundle();
        b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        if (n.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, b)) return true;
        try {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            if (clipboard == null) return false;
            clipboard.setPrimaryClip(ClipData.newPlainText("Furina", text));
            return n.performAction(AccessibilityNodeInfo.ACTION_PASTE);
        } catch (Throwable ignored) {
            return false;
        }
    }

    private boolean longPress(JSONObject action) {
        AccessibilityNodeInfo n = resolveNode(action);
        if (n == null) return false;
        if (n.isLongClickable() && n.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK)) return true;
        Rect r = new Rect();
        n.getBoundsInScreen(r);
        if (r.isEmpty()) return false;
        int duration = Math.max(450, Math.min(action.optInt("duration_ms", 650), 1600));
        Path p = new Path();
        p.moveTo(r.centerX(), r.centerY());
        GestureDescription gd = new GestureDescription.Builder()
                .addStroke(new GestureDescription.StrokeDescription(p, 0, duration))
                .build();
        return dispatchGesture(gd, null, null);
    }

    private boolean scrollNode(JSONObject action) {
        AccessibilityNodeInfo n = resolveNode(action);
        if (n == null) return false;
        AccessibilityNodeInfo cur = n;
        for (int i = 0; i < 7 && cur != null; i++) {
            if (cur.isScrollable()) break;
            cur = cur.getParent();
        }
        if (cur == null) cur = n;
        String direction = action.optString("direction", "forward");
        int a = "backward".equalsIgnoreCase(direction)
                ? AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
                : AccessibilityNodeInfo.ACTION_SCROLL_FORWARD;
        if (cur.performAction(a)) return true;
        Rect r = new Rect();
        cur.getBoundsInScreen(r);
        if (r.isEmpty()) return false;
        int x = r.centerX();
        int top = r.top + Math.max(20, r.height() / 4);
        int bottom = r.bottom - Math.max(20, r.height() / 4);
        return "backward".equalsIgnoreCase(direction)
                ? swipe(x, top, x, bottom, 350)
                : swipe(x, bottom, x, top, 350);
    }

'''
    replace_once(service, old_set_text, new_set_text, "robust text and generic node actions")

    # Final TUI wording. The actual policy already uses one task-level approval;
    # keep the interface consistent with that behavior and with the Furina identity.
    replace_once(
        tui,
        'Perintah ini membutuhkan kontrol layar. Izinkan Furina menavigasi/mengetik? Send/aksi eksternal tetap dikonfirmasi tepat sebelum dilakukan',
        'Izinkan Furina menyelesaikan tugas ini di layar? Jika disetujui, navigasi, pengetikan, pencarian, dan Send/Kirim/Post/Share yang memang diminta akan dilakukan otomatis tanpa konfirmasi kedua',
        "single task approval TUI",
    )
    replace_once(tui, '[dim]AI ROUTER[/]', '[dim]MODEL ROUTER[/]', "router label")
    replace_once(tui, '"AI Provider / API key"', '"Provider / API key"', "provider menu")
    replace_once(tui, 'title="AI PROVIDERS"', 'title="MODEL PROVIDERS"', "provider panel")
    replace_once(tui, 'console.print(f"[dim]AI: {llm.last.backend} / {llm.last.model}[/]")', 'console.print(f"[dim]Model: {llm.last.backend} / {llm.last.model}[/]")', "model status")
    replace_once(tui, '[dim]MEMORY / RESPONSE[/]', '[dim]FURINA MIND / RESPONSE[/]', "mind label")

    replace_once(gradle, "        versionCode 10004", "        versionCode 10005", "Bridge RC5 versionCode")
    replace_once(gradle, "        versionName '1.0.0-rc4'", "        versionName '1.0.0-rc5'", "Bridge RC5 versionName")

    service_text = service.read_text(encoding="utf-8")
    gradle_text = gradle.read_text(encoding="utf-8")
    tui_text = tui.read_text(encoding="utf-8")
    required = [
        ("long press", 'case "long_press"' in service_text and "longPress(JSONObject action)" in service_text),
        ("scroll node", 'case "scroll_node"' in service_text and "scrollNode(JSONObject action)" in service_text),
        ("clipboard fallback", "ACTION_PASTE" in service_text and "ClipboardManager" in service_text),
        ("node actions", 'j.put("actions", actions)' in service_text),
        ("window title", 'out.put("window_title"' in service_text),
        ("single approval UI", "tanpa konfirmasi kedua" in tui_text),
        ("mind UI", "FURINA MIND" in tui_text),
        ("rc5 code", "versionCode 10005" in gradle_text),
        ("rc5 name", "versionName '1.0.0-rc5'" in gradle_text),
    ]
    failed = [name for name, ok in required if not ok]
    if failed:
        raise SystemExit("universal agent RC5 transform incomplete: " + ", ".join(failed))
    print("Universal Android Agent + Furina Mind RC5 transform: OK")


if __name__ == "__main__":
    main()
