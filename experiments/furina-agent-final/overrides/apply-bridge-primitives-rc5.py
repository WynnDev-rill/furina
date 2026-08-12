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
        raise SystemExit("usage: apply-bridge-primitives-rc5.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    bridge = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    gradle = root / "bridge/app/build.gradle"
    if not bridge.is_file() or not gradle.is_file():
        raise SystemExit("missing Bridge primitive source")

    replace_once(
        bridge,
        '            case "tap_node":\n                ok = tapNode(a.optInt("node", -1));\n                break;',
        '            case "tap_node":\n                ok = tapNode(a);\n                break;',
        "selector tap switch",
    )
    replace_once(
        bridge,
        '            case "set_text":\n                ok = setText(a.optInt("node", -1), a.optString("text", ""));\n                break;\n            case "back":',
        '            case "set_text":\n                ok = setText(a, a.optString("text", ""));\n                break;\n            case "ime_action":\n                ok = imeAction(a);\n                break;\n            case "back":',
        "selector text and IME switch",
    )
    replace_once(
        bridge,
        '        if (n.isScrollable()) j.put("scrollable", true);\n        if (n.isCheckable()) j.put("checkable", true).put("checked", n.isChecked());',
        '        if (n.isScrollable()) j.put("scrollable", true);\n        if (n.isFocused()) j.put("focused", true);\n        if (n.isEnabled()) j.put("enabled", true);\n        if (n.isCheckable()) j.put("checkable", true).put("checked", n.isChecked());',
        "richer node state",
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
        "stable selector resolver",
    )
    replace_once(
        bridge,
        '    private boolean setText(int id, String text) {\n        AccessibilityNodeInfo n = nodeByIndex(id);',
        '    private boolean setText(JSONObject action, String text) {\n        AccessibilityNodeInfo n = resolveNode(action);',
        "stable set_text",
    )
    replace_once(
        bridge,
        '    private boolean tap(int x, int y) {',
        '    private boolean imeAction(JSONObject action) {\n        AccessibilityNodeInfo n = resolveNode(action);\n        if (n == null || !n.isEditable() || Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return false;\n        if (!n.isFocused()) n.performAction(AccessibilityNodeInfo.ACTION_FOCUS);\n        return n.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.getId());\n    }\n\n    private boolean tap(int x, int y) {',
        "IME implementation",
    )

    replace_once(gradle, "        versionCode 10001", "        versionCode 10003", "primitive versionCode")
    replace_once(gradle, "        versionName '1.0.0-rc1'", "        versionName '1.0.0-rc3'", "primitive versionName")

    bridge_text = bridge.read_text(encoding="utf-8")
    gradle_text = gradle.read_text(encoding="utf-8")
    required = [
        ("selector", "selectorScore" in bridge_text and "resolveNode" in bridge_text),
        ("IME", "ACTION_IME_ENTER" in bridge_text),
        ("rc3 code", "versionCode 10003" in gradle_text),
        ("rc3 name", "versionName '1.0.0-rc3'" in gradle_text),
    ]
    failed = [name for name, ok in required if not ok]
    if failed:
        raise SystemExit("Bridge primitives incomplete: " + ", ".join(failed))
    print("Bridge stable selector + IME primitives: OK")


if __name__ == "__main__":
    main()
