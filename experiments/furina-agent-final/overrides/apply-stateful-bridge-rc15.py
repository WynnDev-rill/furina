#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"Bridge RC15 marker mismatch {label}: {n}")
    return text.replace(old, new, 1)


def before(text: str, marker: str, insertion: str, label: str) -> str:
    if insertion.strip() in text:
        return text
    n = text.count(marker)
    if n != 1:
        raise SystemExit(f"Bridge RC15 insertion mismatch {label}: {n}")
    return text.replace(marker, insertion.rstrip() + "\n\n" + marker, 1)


def block(text: str, start: str, end: str, new: str, label: str) -> str:
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if new.strip() in text:
            return text
        raise SystemExit(f"Bridge RC15 block marker missing {label}")
    return text[:a] + new.rstrip() + "\n\n" + text[b:]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-stateful-bridge-rc15.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    service = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    gradle = root / "bridge/app/build.gradle"
    if not service.is_file() or not gradle.is_file():
        raise SystemExit("missing Bridge RC15 source")

    s = service.read_text(encoding="utf-8")
    s = before(
        s,
        "    private android.content.SharedPreferences sessionPrefs() {\n",
        '    private static volatile String LAST_STABLE_PACKAGE = "";\n',
        "stable package cache",
    )

    active = '''    private String activeRootPackage() {
        try {
            AccessibilityNodeInfo root = getRootInActiveWindow();
            if (root != null && root.getPackageName() != null) {
                String candidate = root.getPackageName().toString();
                if (!transientWindowPackage(candidate)) {
                    LAST_STABLE_PACKAGE = candidate;
                    return candidate;
                }
            }
        } catch (Throwable ignored) {}
        if (LAST_STABLE_PACKAGE != null && !LAST_STABLE_PACKAGE.isEmpty()) return LAST_STABLE_PACKAGE;
        try {
            String persisted = sessionPrefs().getString(KEY_STABLE_FOREGROUND, "");
            if (persisted != null && !persisted.isEmpty()) {
                LAST_STABLE_PACKAGE = persisted;
                return persisted;
            }
        } catch (Throwable ignored) {}
        return "";
    }
'''
    s = block(s, "    private String activeRootPackage() {\n", "    private String stableForegroundPackage(AccessibilityEvent event) {\n", active, "active package fallback")

    session = '''    private void updateTermuxSession(AccessibilityEvent event, double eventAtSeconds) {
        if (event == null) return;
        int type = event.getEventType();
        if (type != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
                && type != AccessibilityEvent.TYPE_WINDOWS_CHANGED
                && type != AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED) return;

        String current = "";
        if (type == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            current = stableForegroundPackage(event);
        } else if (type == AccessibilityEvent.TYPE_WINDOWS_CHANGED) {
            String rootPackage = activeRootPackage();
            current = transientWindowPackage(rootPackage) ? stableForegroundPackage(event) : rootPackage;
        } else {
            try {
                AccessibilityNodeInfo root = getRootInActiveWindow();
                if (root != null && root.getPackageName() != null) {
                    String rootPackage = root.getPackageName().toString();
                    if (!transientWindowPackage(rootPackage)) current = rootPackage;
                }
            } catch (Throwable ignored) {}
        }
        if (current == null || current.isEmpty() || transientWindowPackage(current)) return;
        LAST_STABLE_PACKAGE = current;

        android.content.SharedPreferences prefs = sessionPrefs();
        String previous = prefs.getString(KEY_STABLE_FOREGROUND, "");
        long nowMs = Math.max(1L, Math.round(eventAtSeconds * 1000.0));
        if (previous.isEmpty()) {
            prefs.edit().putString(KEY_STABLE_FOREGROUND, current).apply();
            return;
        }
        if (current.equals(previous)) return;

        android.content.SharedPreferences.Editor edit = prefs.edit().putString(KEY_STABLE_FOREGROUND, current);
        if (isTermuxPackageFast(previous) && !isTermuxPackageFast(current)) {
            edit.putLong(KEY_ACTIVE_LEFT_MS, nowMs);
            edit.putString(KEY_LAST_OUTSIDE_PACKAGE, current);
            edit.apply();
            return;
        }
        if (!isTermuxPackageFast(previous) && isTermuxPackageFast(current)) {
            long leftMs = prefs.getLong(KEY_ACTIVE_LEFT_MS, 0L);
            String outside = prefs.getString(KEY_LAST_OUTSIDE_PACKAGE, previous);
            if (leftMs > 0L && nowMs >= leftMs) {
                long durationMs = nowMs - leftMs;
                edit.putLong(KEY_LAST_LEFT_MS, leftMs);
                edit.putLong(KEY_LAST_RETURNED_MS, nowMs);
                edit.putLong(KEY_LAST_DURATION_MS, durationMs);
                edit.remove(KEY_ACTIVE_LEFT_MS);
                edit.apply();
                appendAbsenceHistory(prefs, leftMs, nowMs, outside);
                return;
            }
        }
        edit.apply();
    }
'''
    s = block(s, "    private void updateTermuxSession(AccessibilityEvent event, double eventAtSeconds) {\n", "    private JSONObject termuxSessionJson() {\n", session, "multi-event session tracking")

    s = rep(
        s,
        '''            if (type == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
                updateTermuxSession(event, eventAt);
                j.put("termux_session", termuxSessionJson());
            }
''',
        '''            if (type == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
                    || type == AccessibilityEvent.TYPE_WINDOWS_CHANGED
                    || type == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED) {
                updateTermuxSession(event, eventAt);
                j.put("termux_session", termuxSessionJson());
            }
''',
        "event session refresh",
    )

    s = rep(
        s,
        '''        if ("notes".equals(r)) return new String[]{"notes", "catatan"};
        return new String[0];
''',
        '''        if ("notes".equals(r)) return new String[]{"notes", "catatan"};
        if ("send".equals(r)) return new String[]{"send", "send message", "kirim", "kirim pesan", "submit"};
        if ("message".equals(r)) return new String[]{"message", "pesan", "type a message", "ketik pesan", "tulis pesan", "compose", "reply", "balas", "comment", "komentar", "chat"};
        if ("input".equals(r)) return new String[]{"input", "type", "enter", "ketik", "tulis"};
        return new String[0];
''',
        "semantic action roles",
    )

    editable = r'''    private String fastEditableMeta(AccessibilityNodeInfo node) {
        if (node == null) return "";
        StringBuilder b = new StringBuilder();
        try { if (node.getText() != null) b.append(' ').append(node.getText()); } catch (Throwable ignored) {}
        try { if (node.getContentDescription() != null) b.append(' ').append(node.getContentDescription()); } catch (Throwable ignored) {}
        try { if (node.getViewIdResourceName() != null) b.append(' ').append(node.getViewIdResourceName()); } catch (Throwable ignored) {}
        try { if (node.getClassName() != null) b.append(' ').append(node.getClassName()); } catch (Throwable ignored) {}
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            try { if (node.getHintText() != null) b.append(' ').append(node.getHintText()); } catch (Throwable ignored) {}
        }
        return fastNorm(b.toString());
    }

    private boolean fastContainsAny(String value, String[] needles) {
        if (value == null || value.isEmpty()) return false;
        for (String needle : needles) if (value.contains(fastNorm(needle))) return true;
        return false;
    }

    private int fastEditableRoleScore(AccessibilityNodeInfo node, String role) {
        if (node == null || !node.isEditable() || !node.isEnabled()) return -10000;
        String r = fastNorm(role);
        String meta = fastEditableMeta(node);
        int score = node.isFocused() ? 24 : 0;
        if (r.isEmpty() || "input".equals(r)) {
            if (fastContainsAny(meta, fastRoleAliases("input"))) score += 45;
            return score;
        }
        boolean searchMeta = fastContainsAny(meta, fastRoleAliases("search"));
        boolean messageMeta = fastContainsAny(meta, fastRoleAliases("message"));
        if ("search".equals(r)) {
            if (searchMeta) score += 130;
            if (messageMeta) score -= 90;
            return score;
        }
        if ("message".equals(r)) {
            if (searchMeta) score -= 240;
            if (messageMeta) score += 150;
            String view = "";
            try { view = fastNorm(node.getViewIdResourceName()); } catch (Throwable ignored) {}
            if (view.contains("entry") || view.contains("compose") || view.contains("message") || view.contains("input")) score += 70;
            return score;
        }
        return score;
    }

    private AccessibilityNodeInfo fastEditable(JSONObject action) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return null;
        String role = action == null ? "" : action.optString("role", action.optString("field_role", ""));
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(root);
        AccessibilityNodeInfo best = null;
        int bestScore = -10000;
        int count = 0;
        int seen = 0;
        while (!q.isEmpty() && seen++ < 520) {
            AccessibilityNodeInfo node = q.remove();
            if (node.isEditable() && node.isEnabled()) {
                count++;
                int score = fastEditableRoleScore(node, role);
                if (score > bestScore) { best = node; bestScore = score; }
            }
            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) q.add(child);
            }
        }
        String normalizedRole = fastNorm(role);
        if ("message".equals(normalizedRole) && bestScore < 0) return null;
        if ("search".equals(normalizedRole) && bestScore < 40) return null;
        if (normalizedRole.isEmpty() && count != 1 && (best == null || !best.isFocused())) return null;
        return best;
    }

    private AccessibilityNodeInfo fastEditable() {
        return fastEditable(new JSONObject());
    }
'''
    s = block(s, "    private AccessibilityNodeInfo fastEditable() {\n", "    private boolean setTextFast(JSONObject action) {\n", editable, "role-aware editable")

    set_text = '''    private boolean setTextFast(JSONObject action) {
        if (isTermuxPackageFast(activeRootPackage())) return false;
        String text = action.optString("text", "");
        if (text.length() > 4000) return false;
        AccessibilityNodeInfo node = fastEditable(action);
        if (node == null) return false;
        if (textMatches(node, text)) return true;
        if (!node.isFocused()) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        if (!node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) return false;
        long deadline = System.currentTimeMillis() + 420L;
        while (System.currentTimeMillis() < deadline) {
            AccessibilityNodeInfo current = fastEditable(action);
            if (textMatches(current != null ? current : node, text)) return true;
            waitFastEvent(currentEventSeq(), 45L);
        }
        return textMatches(fastEditable(action), text);
    }
'''
    s = block(s, "    private boolean setTextFast(JSONObject action) {\n", "    private boolean imeFast() {\n", set_text, "role-aware set text")

    ime = '''    private boolean imeFast(JSONObject action) {
        if (isTermuxPackageFast(activeRootPackage())) return false;
        configureAgentAccessibility();
        AccessibilityNodeInfo node = fastEditable(action);
        if (node != null) {
            if (!node.isFocused()) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && node.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.getId())) return true;
        }
        try {
            String role = action == null ? "" : action.optString("role", "");
            if ("search".equals(fastNorm(role))) return tapTextFast(new JSONObject().put("role", "search").put("max_scrolls", 0));
        } catch (Throwable ignored) {}
        return false;
    }
'''
    s = block(s, "    private boolean imeFast() {\n", "    private boolean scrollBestFast(JSONObject action) {\n", ime, "role-aware ime")

    s = rep(
        s,
        '        if ("set_text_best".equals(type) || "ime_best".equals(type)) return fastEditable() != null;\n',
        '        if ("set_text_best".equals(type) || "ime_best".equals(type)) return fastEditable(step) != null;\n',
        "next role readiness",
    )
    s = rep(s, '                ok = imeFast();\n', '                ok = imeFast(step);\n', "sequence role ime")

    transition = r'''    private long fastUiSignature() {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return 0L;
        long hash = 1125899906842597L;
        try { hash = hash * 31L + fastNorm(String.valueOf(root.getPackageName())).hashCode(); } catch (Throwable ignored) {}
        try { hash = hash * 31L + root.getWindowId(); } catch (Throwable ignored) {}
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(root);
        int seen = 0;
        while (!q.isEmpty() && seen++ < 180) {
            AccessibilityNodeInfo node = q.remove();
            String meta = fastEditableMeta(node);
            hash = hash * 31L + meta.hashCode();
            try { hash = hash * 31L + (node.isEditable() ? 7 : 3) + (node.isClickable() ? 11 : 0); } catch (Throwable ignored) {}
            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) q.add(child);
            }
        }
        return hash;
    }

    private boolean waitFastUiChange(long beforeSignature, long afterSequence, long timeoutMs) {
        long deadline = System.currentTimeMillis() + Math.max(120L, Math.min(timeoutMs, 5000L));
        long sequence = afterSequence;
        while (System.currentTimeMillis() < deadline) {
            if (isTermuxPackageFast(activeRootPackage())) return false;
            long current = fastUiSignature();
            if (current != 0L && current != beforeSignature) return true;
            waitFastEvent(sequence, Math.min(100L, Math.max(1L, deadline - System.currentTimeMillis())));
            sequence = currentEventSeq();
        }
        long current = fastUiSignature();
        return current != 0L && current != beforeSignature;
    }
'''
    s = before(s, "    private JSONObject runUiSequence(JSONObject action) throws JSONException {\n", transition, "UI transition helpers")

    s = rep(
        s,
        '''            String type = step.optString("type", "");
            long sequence = currentEventSeq();
            boolean ok;
''',
        '''            String type = step.optString("type", "");
            long sequence = currentEventSeq();
            long uiSignatureBefore = fastUiSignature();
            boolean ok;
''',
        "sequence transition baseline",
    )
    s = rep(
        s,
        '''            if (!ok) return out.put("failed_step", i).put("failed_type", type).put("error", "step_failed").put("package", activeRootPackage()).put("event_seq", currentEventSeq()).put("elapsed_ms", System.currentTimeMillis() - started);
            out.put("completed_steps", i + 1);
''',
        '''            if (!ok) return out.put("failed_step", i).put("failed_type", type).put("error", "step_failed").put("package", activeRootPackage()).put("event_seq", currentEventSeq()).put("elapsed_ms", System.currentTimeMillis() - started);
            if (step.optBoolean("require_change", false)
                    && !waitFastUiChange(uiSignatureBefore, sequence, step.optLong("transition_timeout_ms", 2200L))) {
                return out.put("failed_step", i).put("failed_type", type).put("error", "transition_not_observed").put("package", activeRootPackage()).put("event_seq", currentEventSeq()).put("elapsed_ms", System.currentTimeMillis() - started);
            }
            out.put("completed_steps", i + 1);
''',
        "selection transition guard",
    )

    service.write_text(s, encoding="utf-8")
    g = gradle.read_text(encoding="utf-8")
    g = rep(g, "        versionCode 10014", "        versionCode 10015", "version code")
    g = rep(g, "        versionName '1.0.0-rc14'", "        versionName '1.0.0-rc15'", "version name")
    gradle.write_text(g, encoding="utf-8")

    checks = [
        (service, 'LAST_STABLE_PACKAGE'),
        (service, 'TYPE_WINDOWS_CHANGED'),
        (service, 'TYPE_WINDOW_CONTENT_CHANGED'),
        (service, 'fastEditableRoleScore'),
        (service, '"message".equals(normalizedRole) && bestScore < 0'),
        (service, 'waitFastUiChange'),
        (service, 'transition_not_observed'),
        (service, '"send".equals(r)'),
        (gradle, 'versionCode 10015'),
        (gradle, "versionName '1.0.0-rc15'"),
    ]
    missing = [needle for path, needle in checks if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("Bridge RC15 incomplete: " + ", ".join(missing))
    print("Furina Bridge RC15 state-aware fields + foreground tracking: OK")


if __name__ == "__main__":
    main()
