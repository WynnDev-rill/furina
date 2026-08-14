#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"Bridge RC16 marker mismatch {label}: {n}")
    return text.replace(old, new, 1)


def block(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if replacement.strip() in text:
            return text
        raise SystemExit(f"Bridge RC16 block marker missing {label}: start={a} end={b}")
    return text[:a] + replacement.rstrip() + "\n\n" + text[b:]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-universal-ui-bridge-rc16.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    service = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    gradle = root / "bridge/app/build.gradle"
    if not service.is_file() or not gradle.is_file():
        raise SystemExit("missing Bridge RC16 source")

    s = service.read_text(encoding="utf-8")

    generic_text = r'''    private boolean selectAllForReplace(AccessibilityNodeInfo node) {
        if (node == null) return false;
        String current = nodeText(node);
        Bundle selection = new Bundle();
        selection.putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, 0);
        selection.putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, current.length());
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, selection);
    }

    private boolean setText(JSONObject action, String text) {
        AccessibilityNodeInfo n = editableNode(resolveNode(action));
        if (n == null) return false;
        if (textMatches(n, text)) return true;
        if (!n.isFocused()) n.performAction(AccessibilityNodeInfo.ACTION_FOCUS);

        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        if (n.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
                && waitForExactText(action, n, text, 650L)) return true;

        AccessibilityNodeInfo current = refreshEditable(action, n);
        if (textMatches(current, text)) return true;
        if (current == null) return false;

        if (!nodeText(current).isEmpty() && !selectAllForReplace(current)) return false;
        try {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            if (clipboard == null) return false;
            clipboard.setPrimaryClip(ClipData.newPlainText("Furina", text));
            current = refreshEditable(action, current);
            if (current == null) return false;
            if (!current.isFocused()) current.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            boolean pasted = current.performAction(AccessibilityNodeInfo.ACTION_PASTE);
            return pasted && waitForExactText(action, current, text, 800L);
        } catch (Throwable ignored) {
            return false;
        }
    }
'''
    s = block(
        s,
        "    private boolean setText(JSONObject action, String text) {\n",
        "    private boolean longPress(JSONObject action) {\n",
        generic_text,
        "idempotent generic text replacement",
    )

    result_find = r'''    private int fastActionScore(AccessibilityNodeInfo node, String wanted, JSONObject action, String stablePackage) {
        int score = fastScore(node, wanted);
        if (score < 0) return score;
        if (!action.optBoolean("result_mode", false)) return score;

        if (node == null || node.isEditable()) return -1;
        try {
            String nodePackage = node.getPackageName() == null ? "" : node.getPackageName().toString();
            if (transientWindowPackage(nodePackage)) return -1;
            if (stablePackage != null && !stablePackage.isEmpty()
                    && nodePackage != null && !nodePackage.isEmpty()
                    && !stablePackage.equals(nodePackage)) return -1;
        } catch (Throwable ignored) {}

        String meta = fastEditableMeta(node);
        if (meta.contains("search") || meta.contains("query") || meta.contains("inputmethod") || meta.contains("keyboard")) {
            score -= 90;
        }
        try { if (node.isFocused()) score -= 30; } catch (Throwable ignored) {}

        AccessibilityNodeInfo current = node;
        boolean clickable = false;
        for (int depth = 0; depth < 6 && current != null; depth++) {
            try {
                if (current.isEnabled() && current.isClickable()) {
                    score += Math.max(12, 44 - depth * 5);
                    clickable = true;
                    break;
                }
            } catch (Throwable ignored) {}
            current = current.getParent();
        }
        if (!clickable) {
            Rect rect = new Rect();
            try { node.getBoundsInScreen(rect); } catch (Throwable ignored) {}
            if (rect.isEmpty()) return -1;
            score += 4;
        }
        return score;
    }

    private AccessibilityNodeInfo fastFind(JSONObject action) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return null;
        java.util.ArrayList<String> wantedValues = new java.util.ArrayList<>();
        JSONArray targets = action.optJSONArray("targets");
        if (targets != null) for (int i = 0; i < targets.length(); i++) {
            String value = targets.optString(i, "").trim();
            if (!value.isEmpty()) wantedValues.add(value);
        }
        String target = action.optString("target", "").trim();
        if (!target.isEmpty()) wantedValues.add(target);
        for (String alias : fastRoleAliases(action.optString("role", ""))) wantedValues.add(alias);
        if (wantedValues.isEmpty()) return null;

        String stablePackage = activeRootPackage();
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(root);
        AccessibilityNodeInfo best = null;
        int bestScore = -1;
        int seen = 0;
        while (!q.isEmpty() && seen++ < 560) {
            AccessibilityNodeInfo node = q.remove();
            for (String wanted : wantedValues) {
                int score = fastActionScore(node, wanted, action, stablePackage);
                if (score > bestScore) {
                    best = node;
                    bestScore = score;
                }
            }
            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) q.add(child);
            }
        }
        int threshold = action.optBoolean("result_mode", false) ? 70 : 58;
        return bestScore >= threshold ? best : null;
    }
'''
    s = block(
        s,
        "    private AccessibilityNodeInfo fastFind(JSONObject action) {\n",
        "    private boolean tapTextFast(JSONObject action) {\n",
        result_find,
        "result-aware candidate finder",
    )

    fast_text = r'''    private boolean setTextFast(JSONObject action) {
        if (isTermuxPackageFast(activeRootPackage())) return false;
        String text = action.optString("text", "");
        if (text.length() > 4000) return false;
        AccessibilityNodeInfo node = fastEditable(action);
        if (node == null) return false;
        if (textMatches(node, text)) return true;
        if (!node.isFocused()) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);

        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        if (node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) {
            long deadline = System.currentTimeMillis() + 520L;
            while (System.currentTimeMillis() < deadline) {
                AccessibilityNodeInfo current = fastEditable(action);
                if (textMatches(current != null ? current : node, text)) return true;
                waitFastEvent(currentEventSeq(), 45L);
            }
        }

        AccessibilityNodeInfo current = fastEditable(action);
        if (textMatches(current, text)) return true;
        if (current == null) return false;
        if (!nodeText(current).isEmpty() && !selectAllForReplace(current)) return false;
        try {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            if (clipboard == null) return false;
            clipboard.setPrimaryClip(ClipData.newPlainText("Furina", text));
            current = fastEditable(action);
            if (current == null) return false;
            if (!current.isFocused()) current.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            if (!current.performAction(AccessibilityNodeInfo.ACTION_PASTE)) return false;
            long deadline = System.currentTimeMillis() + 800L;
            while (System.currentTimeMillis() < deadline) {
                AccessibilityNodeInfo check = fastEditable(action);
                if (textMatches(check != null ? check : current, text)) return true;
                waitFastEvent(currentEventSeq(), 55L);
            }
            return textMatches(fastEditable(action), text);
        } catch (Throwable ignored) {
            return false;
        }
    }
'''
    s = block(
        s,
        "    private boolean setTextFast(JSONObject action) {\n",
        "    private boolean imeFast(JSONObject action) {\n",
        fast_text,
        "idempotent role-aware text replacement",
    )

    ime = r'''    private boolean imeFast(JSONObject action) {
        if (isTermuxPackageFast(activeRootPackage())) return false;
        configureAgentAccessibility();

        String optionalTarget = action == null ? "" : action.optString("optional_if_target_visible", "").trim();
        if (!optionalTarget.isEmpty()) {
            try {
                JSONObject resultProbe = new JSONObject()
                        .put("target", optionalTarget)
                        .put("result_mode", true);
                long sequence = currentEventSeq();
                long deadline = System.currentTimeMillis() + 850L;
                while (System.currentTimeMillis() < deadline) {
                    if (fastFind(resultProbe) != null) return true;
                    waitFastEvent(sequence, Math.min(100L, Math.max(1L, deadline - System.currentTimeMillis())));
                    sequence = currentEventSeq();
                }
            } catch (Throwable ignored) {}
        }

        AccessibilityNodeInfo node = fastEditable(action);
        if (node != null) {
            if (!node.isFocused()) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R
                    && node.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.getId())) return true;
        }
        try {
            String role = action == null ? "" : action.optString("role", "");
            if ("search".equals(fastNorm(role))) {
                return tapTextFast(new JSONObject().put("role", "search").put("max_scrolls", 0));
            }
        } catch (Throwable ignored) {}
        return false;
    }
'''
    s = block(
        s,
        "    private boolean imeFast(JSONObject action) {\n",
        "    private boolean scrollBestFast(JSONObject action) {\n",
        ime,
        "live-search aware submit",
    )

    service.write_text(s, encoding="utf-8")

    g = gradle.read_text(encoding="utf-8")
    g = rep(g, "        versionCode 10015", "        versionCode 10016", "Bridge versionCode")
    g = rep(g, "        versionName '1.0.0-rc15'", "        versionName '1.0.0-rc16'", "Bridge versionName")
    gradle.write_text(g, encoding="utf-8")

    final = service.read_text(encoding="utf-8")
    required = (
        "selectAllForReplace",
        "ACTION_SET_SELECTION",
        'action.optBoolean("result_mode", false)',
        "fastActionScore",
        "transientWindowPackage(nodePackage)",
        "optional_if_target_visible",
        "fastEditable(action)",
    )
    missing = [needle for needle in required if needle not in final]
    if missing:
        raise SystemExit("Bridge RC16 incomplete: " + ", ".join(missing))
    if "versionCode 10016" not in g or "versionName '1.0.0-rc16'" not in g:
        raise SystemExit("Bridge RC16 version missing")
    print("Furina Bridge RC16 idempotent input + universal result selection: OK")


if __name__ == "__main__":
    main()
