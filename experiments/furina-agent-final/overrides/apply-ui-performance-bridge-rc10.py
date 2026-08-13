#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Bridge RC10 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def before(text: str, marker: str, block: str, label: str) -> str:
    if block.strip() in text:
        return text
    count = text.count(marker)
    if count != 1:
        raise SystemExit(f"Bridge RC10 insertion mismatch {label}: {count}")
    return text.replace(marker, block.rstrip() + "\n\n" + marker, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-ui-performance-bridge-rc10.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    service = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    gradle = root / "bridge/app/build.gradle"
    if not service.is_file() or not gradle.is_file():
        raise SystemExit("missing Bridge RC10 source")

    s = service.read_text(encoding="utf-8")
    s = rep(
        s,
        '''            case "scroll_global":
                ok = scrollGlobal(a);
                break;
            case "set_text":''',
        '''            case "scroll_global":
                ok = scrollGlobal(a);
                break;
            case "tap_text":
                ok = tapTextFast(a);
                break;
            case "scroll_best":
                ok = scrollBestFast(a);
                break;
            case "run_ui_sequence":
                return runUiSequence(a);
            case "set_text":''',
        "action switch",
    )

    methods = r'''    private static String fastNorm(String value) {
        if (value == null) return "";
        return value.trim().toLowerCase(java.util.Locale.ROOT).replaceAll("\\s+", " ");
    }

    private int fastScore(AccessibilityNodeInfo n, String wanted) {
        if (n == null || !n.isEnabled()) return -1;
        String w = fastNorm(wanted);
        if (w.isEmpty()) return -1;
        String text = fastNorm(n.getText() == null ? "" : n.getText().toString());
        String desc = fastNorm(n.getContentDescription() == null ? "" : n.getContentDescription().toString());
        String view = fastNorm(n.getViewIdResourceName());
        int score = -1;
        if (text.equals(w)) score = 120;
        else if (desc.equals(w)) score = 112;
        else if (!text.isEmpty() && text.contains(w)) score = 84;
        else if (!desc.isEmpty() && desc.contains(w)) score = 78;
        else if (!view.isEmpty() && view.contains(w.replace(" ", "_"))) score = 58;
        if (score >= 0 && n.isClickable()) score += 18;
        return score;
    }

    private AccessibilityNodeInfo fastFind(String wanted) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return null;
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(root);
        AccessibilityNodeInfo best = null;
        int bestScore = -1;
        int seen = 0;
        while (!q.isEmpty() && seen++ < 420) {
            AccessibilityNodeInfo n = q.remove();
            int score = fastScore(n, wanted);
            if (score > bestScore) {
                best = n;
                bestScore = score;
            }
            for (int i = 0; i < n.getChildCount(); i++) {
                AccessibilityNodeInfo child = n.getChild(i);
                if (child != null) q.add(child);
            }
        }
        return bestScore >= 58 ? best : null;
    }

    private AccessibilityNodeInfo fastFind(JSONObject action) {
        JSONArray targets = action.optJSONArray("targets");
        if (targets != null) {
            AccessibilityNodeInfo best = null;
            int bestScore = -1;
            for (int i = 0; i < targets.length(); i++) {
                String wanted = targets.optString(i, "");
                AccessibilityNodeInfo node = fastFind(wanted);
                int score = fastScore(node, wanted);
                if (score > bestScore) {
                    best = node;
                    bestScore = score;
                }
            }
            if (best != null) return best;
        }
        return fastFind(action.optString("target", ""));
    }

    private boolean tapTextFast(JSONObject action) {
        AccessibilityNodeInfo node = fastFind(action);
        if (node == null) return false;
        AccessibilityNodeInfo current = node;
        for (int i = 0; i < 6 && current != null; i++) {
            if (current.isEnabled() && current.isClickable()
                    && current.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true;
            current = current.getParent();
        }
        Rect rect = new Rect();
        node.getBoundsInScreen(rect);
        return !rect.isEmpty() && tap(rect.centerX(), rect.centerY());
    }

    private AccessibilityNodeInfo fastEditable() {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return null;
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(root);
        AccessibilityNodeInfo only = null;
        int count = 0;
        int seen = 0;
        while (!q.isEmpty() && seen++ < 420) {
            AccessibilityNodeInfo node = q.remove();
            if (node.isEditable() && node.isEnabled()) {
                if (node.isFocused()) return node;
                if (only == null) only = node;
                count++;
            }
            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) q.add(child);
            }
        }
        return count == 1 ? only : null;
    }

    private boolean setTextFast(JSONObject action) {
        String text = action.optString("text", "");
        if (text.length() > 4000) return false;
        AccessibilityNodeInfo node = fastEditable();
        if (node == null) return false;
        if (textMatches(node, text)) return true;
        if (!node.isFocused()) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        if (!node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) return false;
        long deadline = System.currentTimeMillis() + 360L;
        while (System.currentTimeMillis() < deadline) {
            AccessibilityNodeInfo current = fastEditable();
            if (textMatches(current != null ? current : node, text)) return true;
            waitFastEvent(currentEventSeq(), 45L);
        }
        return textMatches(fastEditable(), text);
    }

    private boolean imeFast() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return false;
        AccessibilityNodeInfo node = fastEditable();
        if (node == null) return false;
        if (!node.isFocused()) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        return node.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.getId());
    }

    private boolean scrollBestFast(JSONObject action) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return false;
        boolean backward = "backward".equalsIgnoreCase(action.optString("direction", "forward"));
        int semantic = backward ? AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD : AccessibilityNodeInfo.ACTION_SCROLL_FORWARD;
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(root);
        AccessibilityNodeInfo best = null;
        long bestArea = -1L;
        int seen = 0;
        while (!q.isEmpty() && seen++ < 420) {
            AccessibilityNodeInfo node = q.remove();
            if (node.isScrollable() && node.isEnabled()) {
                Rect rect = new Rect();
                node.getBoundsInScreen(rect);
                long area = Math.max(0, rect.width()) * (long) Math.max(0, rect.height());
                if (area > bestArea) {
                    best = node;
                    bestArea = area;
                }
            }
            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) q.add(child);
            }
        }
        if (best != null && best.performAction(semantic)) return true;
        return scrollGlobal(action);
    }

    private boolean waitFastEvent(long afterSequence, long timeoutMs) {
        long deadline = System.currentTimeMillis() + Math.max(1L, timeoutMs);
        synchronized (EVENT_LOCK) {
            while (EVENT_SEQ <= afterSequence) {
                long remaining = deadline - System.currentTimeMillis();
                if (remaining <= 0L) return false;
                try {
                    EVENT_LOCK.wait(Math.min(remaining, 120L));
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return false;
                }
            }
            return true;
        }
    }

    private boolean waitFastPackage(String packageName, long timeoutMs) {
        if (packageName == null || packageName.isEmpty()) return false;
        long deadline = System.currentTimeMillis() + Math.max(80L, timeoutMs);
        long sequence = currentEventSeq();
        while (System.currentTimeMillis() < deadline) {
            if (packageName.equals(activeRootPackage())) return true;
            waitFastEvent(sequence, Math.min(120L, Math.max(1L, deadline - System.currentTimeMillis())));
            sequence = currentEventSeq();
        }
        return packageName.equals(activeRootPackage());
    }

    private boolean waitFastText(JSONObject action, long timeoutMs) {
        long deadline = System.currentTimeMillis() + Math.max(80L, timeoutMs);
        long sequence = currentEventSeq();
        while (System.currentTimeMillis() < deadline) {
            if (fastFind(action) != null) return true;
            waitFastEvent(sequence, Math.min(120L, Math.max(1L, deadline - System.currentTimeMillis())));
            sequence = currentEventSeq();
        }
        return fastFind(action) != null;
    }

    private boolean nextFastReady(JSONObject step) {
        String type = step.optString("type", "");
        if ("tap_text".equals(type) || "wait_text".equals(type)) return fastFind(step) != null;
        if ("set_text_best".equals(type) || "ime_best".equals(type)) return fastEditable() != null;
        if ("wait_package".equals(type)) return step.optString("package", "").equals(activeRootPackage());
        return false;
    }

    private void awaitFastNext(JSONArray steps, int nextIndex, long afterSequence, long timeoutMs) {
        if (nextIndex >= steps.length()) return;
        JSONObject next = steps.optJSONObject(nextIndex);
        if (next == null || nextFastReady(next)) return;
        long deadline = System.currentTimeMillis() + Math.max(40L, timeoutMs);
        long sequence = afterSequence;
        while (System.currentTimeMillis() < deadline) {
            waitFastEvent(sequence, Math.min(120L, Math.max(1L, deadline - System.currentTimeMillis())));
            sequence = currentEventSeq();
            if (nextFastReady(next)) return;
        }
    }

    private JSONObject runUiSequence(JSONObject action) throws JSONException {
        JSONArray steps = action.optJSONArray("steps");
        JSONObject out = new JSONObject().put("type", "run_ui_sequence").put("ok", false).put("completed_steps", 0);
        if (steps == null || steps.length() == 0 || steps.length() > 10) return out.put("error", "invalid_sequence");
        long started = System.currentTimeMillis();
        for (int i = 0; i < steps.length(); i++) {
            JSONObject step = steps.optJSONObject(i);
            if (step == null) return out.put("failed_step", i).put("error", "invalid_step");
            String type = step.optString("type", "");
            long sequence = currentEventSeq();
            boolean ok;
            if ("open_app".equals(type)) {
                ok = openApp(step) && waitFastPackage(step.optString("package", ""), step.optLong("timeout_ms", 1300L));
            } else if ("tap_text".equals(type)) {
                ok = tapTextFast(step);
            } else if ("set_text_best".equals(type)) {
                ok = setTextFast(step);
            } else if ("ime_best".equals(type)) {
                ok = imeFast();
            } else if ("scroll_best".equals(type)) {
                ok = scrollBestFast(step);
            } else if ("wait_text".equals(type)) {
                ok = waitFastText(step, step.optLong("timeout_ms", 1100L));
            } else if ("wait_package".equals(type)) {
                ok = waitFastPackage(step.optString("package", ""), step.optLong("timeout_ms", 1300L));
            } else if ("back".equals(type)) {
                ok = performGlobalAction(GLOBAL_ACTION_BACK);
            } else if ("home".equals(type)) {
                ok = performGlobalAction(GLOBAL_ACTION_HOME);
            } else if ("recents".equals(type)) {
                ok = performGlobalAction(GLOBAL_ACTION_RECENTS);
            } else {
                return out.put("failed_step", i).put("error", "unsupported_step");
            }
            if (!ok) return out.put("failed_step", i).put("error", "step_failed").put("elapsed_ms", System.currentTimeMillis() - started);
            out.put("completed_steps", i + 1);
            if (i + 1 < steps.length() && !"wait_text".equals(type) && !"wait_package".equals(type)) {
                awaitFastNext(steps, i + 1, sequence, "open_app".equals(type) ? 900L : 420L);
            }
        }
        return out.put("ok", true).put("elapsed_ms", System.currentTimeMillis() - started).put("package", activeRootPackage());
    }
'''
    s = before(s, "    private boolean scrollGlobal(JSONObject action) {\n", methods, "fast methods")

    s = rep(
        s,
        '''        if (type == AccessibilityEvent.TYPE_WINDOWS_CHANGED) return "windows";
        return "other";''',
        '''        if (type == AccessibilityEvent.TYPE_WINDOWS_CHANGED) return "windows";
        if (type == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED) return "content";
        return "other";''',
        "content event name",
    )
    s = rep(
        s,
        '''                || type == AccessibilityEvent.TYPE_VIEW_CLICKED
                || type == AccessibilityEvent.TYPE_WINDOWS_CHANGED;''',
        '''                || type == AccessibilityEvent.TYPE_VIEW_CLICKED
                || type == AccessibilityEvent.TYPE_WINDOWS_CHANGED
                || type == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED;''',
        "content event capture",
    )
    s = rep(
        s,
        '''            synchronized (EVENT_LOCK) {
                RECENT_EVENTS.addLast(j);
                while (RECENT_EVENTS.size() > 32) RECENT_EVENTS.removeFirst();
            }''',
        '''            synchronized (EVENT_LOCK) {
                RECENT_EVENTS.addLast(j);
                while (RECENT_EVENTS.size() > 32) RECENT_EVENTS.removeFirst();
                EVENT_LOCK.notifyAll();
            }''',
        "event wake",
    )
    service.write_text(s, encoding="utf-8")

    g = gradle.read_text(encoding="utf-8")
    g = rep(g, "        versionCode 10009", "        versionCode 10010", "versionCode")
    g = rep(g, "        versionName '1.0.0-rc9'", "        versionName '1.0.0-rc10'", "versionName")
    gradle.write_text(g, encoding="utf-8")

    service_text = service.read_text(encoding="utf-8")
    gradle_text = gradle.read_text(encoding="utf-8")
    checks = [
        ("sequence", "runUiSequence(JSONObject action)" in service_text),
        ("semantic tap", 'case "tap_text"' in service_text),
        ("semantic scroll", 'case "scroll_best"' in service_text and "ACTION_SCROLL_FORWARD" in service_text),
        ("event wake", "EVENT_LOCK.notifyAll()" in service_text),
        ("content events", "TYPE_WINDOW_CONTENT_CHANGED" in service_text),
        ("code", "versionCode 10010" in gradle_text),
        ("name", "versionName '1.0.0-rc10'" in gradle_text),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        raise SystemExit("Bridge RC10 incomplete: " + ", ".join(failed))
    print("Furina Bridge RC10 event-driven UI sequence: OK")


if __name__ == "__main__":
    main()
