#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Bridge RC9 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def insert_once(text: str, marker: str, insertion: str, label: str) -> str:
    if insertion.strip() in text:
        return text
    count = text.count(marker)
    if count != 1:
        raise SystemExit(f"Bridge RC9 marker mismatch {label}: {count}")
    return text.replace(marker, marker + insertion, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-bridge-rc9.py <termux-root>")

    root = pathlib.Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    service = app / "src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    gradle = app / "build.gradle"
    if not service.is_file() or not gradle.is_file():
        raise SystemExit("missing Bridge RC9 source")

    g = gradle.read_text(encoding="utf-8")
    g = replace_once(g, "        versionCode 10008", "        versionCode 10009", "versionCode")
    g = replace_once(g, "        versionName '1.0.0-rc8'", "        versionName '1.0.0-rc9'", "versionName")
    gradle.write_text(g, encoding="utf-8")

    s = service.read_text(encoding="utf-8")
    s = insert_once(
        s,
        "    private static long EVENT_SEQ = 0L;\n",
        '''    private static final String TERMUX_PACKAGE = "com.termux";
    private static final String SESSION_PREFS = "furina_termux_session_v1";
    private static final String KEY_STABLE_FOREGROUND = "stable_foreground";
    private static final String KEY_ACTIVE_LEFT_MS = "active_left_ms";
    private static final String KEY_LAST_LEFT_MS = "last_left_ms";
    private static final String KEY_LAST_RETURNED_MS = "last_returned_ms";
    private static final String KEY_LAST_DURATION_MS = "last_duration_ms";
    private static final String KEY_LAST_OUTSIDE_PACKAGE = "last_outside_package";
    private static final String KEY_HISTORY = "history_json";
''',
        "session constants",
    )

    methods = r'''    private android.content.SharedPreferences sessionPrefs() {
        return getSharedPreferences(SESSION_PREFS, MODE_PRIVATE);
    }

    private boolean transientWindowPackage(String pkg) {
        if (pkg == null || pkg.isEmpty()) return true;
        String p = pkg.toLowerCase(java.util.Locale.ROOT);
        if (p.equals(getPackageName().toLowerCase(java.util.Locale.ROOT))) return true;
        if (p.equals("com.android.systemui")) return true;
        return p.contains("inputmethod")
                || p.contains("keyboard")
                || p.contains("swiftkey")
                || p.contains("gboard")
                || p.equals("com.google.android.inputmethod.latin")
                || p.equals("com.touchtype.swiftkey");
    }

    private String activeRootPackage() {
        try {
            AccessibilityNodeInfo root = getRootInActiveWindow();
            if (root != null && root.getPackageName() != null) {
                return root.getPackageName().toString();
            }
        } catch (Throwable ignored) {}
        return "";
    }

    private String stableForegroundPackage(AccessibilityEvent event) {
        String eventPackage = "";
        try {
            if (event != null && event.getPackageName() != null) {
                eventPackage = event.getPackageName().toString();
            }
        } catch (Throwable ignored) {}
        if (!transientWindowPackage(eventPackage)) return eventPackage;
        String rootPackage = activeRootPackage();
        return transientWindowPackage(rootPackage) ? "" : rootPackage;
    }

    private void appendAbsenceHistory(android.content.SharedPreferences prefs, long leftMs, long returnedMs, String outsidePackage) {
        try {
            JSONArray previous;
            try {
                previous = new JSONArray(prefs.getString(KEY_HISTORY, "[]"));
            } catch (Throwable ignored) {
                previous = new JSONArray();
            }
            JSONObject item = new JSONObject();
            item.put("left_at", leftMs / 1000.0);
            item.put("returned_at", returnedMs / 1000.0);
            item.put("duration_seconds", Math.max(0L, returnedMs - leftMs) / 1000.0);
            if (outsidePackage != null && !outsidePackage.isEmpty()) item.put("outside_package", outsidePackage);
            previous.put(item);
            JSONArray trimmed = new JSONArray();
            int start = Math.max(0, previous.length() - 8);
            for (int i = start; i < previous.length(); i++) trimmed.put(previous.get(i));
            prefs.edit().putString(KEY_HISTORY, trimmed.toString()).apply();
        } catch (Throwable ignored) {}
    }

    private void updateTermuxSession(AccessibilityEvent event, double eventAtSeconds) {
        if (event == null || event.getEventType() != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return;
        String current = stableForegroundPackage(event);
        if (current.isEmpty()) return;

        android.content.SharedPreferences prefs = sessionPrefs();
        String previous = prefs.getString(KEY_STABLE_FOREGROUND, "");
        long nowMs = Math.max(1L, Math.round(eventAtSeconds * 1000.0));
        if (previous.isEmpty()) {
            prefs.edit().putString(KEY_STABLE_FOREGROUND, current).apply();
            return;
        }
        if (current.equals(previous)) return;

        android.content.SharedPreferences.Editor edit = prefs.edit().putString(KEY_STABLE_FOREGROUND, current);
        if (TERMUX_PACKAGE.equals(previous) && !TERMUX_PACKAGE.equals(current)) {
            edit.putLong(KEY_ACTIVE_LEFT_MS, nowMs);
            edit.putString(KEY_LAST_OUTSIDE_PACKAGE, current);
            edit.apply();
            return;
        }
        if (!TERMUX_PACKAGE.equals(previous) && TERMUX_PACKAGE.equals(current)) {
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

    private JSONObject termuxSessionJson() {
        JSONObject out = new JSONObject();
        try {
            android.content.SharedPreferences prefs = sessionPrefs();
            String foreground = prefs.getString(KEY_STABLE_FOREGROUND, "");
            long activeLeftMs = prefs.getLong(KEY_ACTIVE_LEFT_MS, 0L);
            long lastLeftMs = prefs.getLong(KEY_LAST_LEFT_MS, 0L);
            long lastReturnedMs = prefs.getLong(KEY_LAST_RETURNED_MS, 0L);
            long lastDurationMs = prefs.getLong(KEY_LAST_DURATION_MS, 0L);
            out.put("source", "bridge_window_state_v1");
            out.put("authoritative", true);
            out.put("foreground_package", foreground);
            out.put("currently_away", activeLeftMs > 0L && !TERMUX_PACKAGE.equals(foreground));
            if (activeLeftMs > 0L) out.put("active_left_at", activeLeftMs / 1000.0);
            if (lastLeftMs > 0L) out.put("last_left_at", lastLeftMs / 1000.0);
            if (lastReturnedMs > 0L) out.put("last_returned_at", lastReturnedMs / 1000.0);
            if (lastDurationMs >= 0L && lastReturnedMs > 0L) out.put("last_absence_seconds", lastDurationMs / 1000.0);
            String outside = prefs.getString(KEY_LAST_OUTSIDE_PACKAGE, "");
            if (!outside.isEmpty()) out.put("last_outside_package", outside);
            try { out.put("history", new JSONArray(prefs.getString(KEY_HISTORY, "[]"))); }
            catch (Throwable ignored) { out.put("history", new JSONArray()); }
        } catch (Throwable ignored) {}
        return out;
    }

'''
    if methods.strip() not in s:
        marker = "    private long currentEventSeq() {\n"
        if marker not in s:
            raise SystemExit("Bridge RC9 session-method insertion marker missing")
        s = s.replace(marker, methods + marker, 1)

    s = replace_once(
        s,
        '        out.put("recent_events", recentEventsJson());\n',
        '        out.put("recent_events", recentEventsJson());\n        out.put("termux_session", termuxSessionJson());\n',
        "screen session payload",
    )
    s = replace_once(
        s,
        '            j.put("at", System.currentTimeMillis() / 1000.0);\n',
        '''            double eventAt = System.currentTimeMillis() / 1000.0;
            j.put("at", eventAt);
            if (type == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
                updateTermuxSession(event, eventAt);
                j.put("termux_session", termuxSessionJson());
            }
''',
        "window session update",
    )
    service.write_text(s, encoding="utf-8")

    service_text = service.read_text(encoding="utf-8")
    gradle_text = gradle.read_text(encoding="utf-8")
    required = [
        ("persistent session prefs", "furina_termux_session_v1" in service_text),
        ("window-only session tracking", "TYPE_WINDOW_STATE_CHANGED" in service_text and "updateTermuxSession(event, eventAt)" in service_text),
        ("screen session payload", 'out.put("termux_session", termuxSessionJson())' in service_text),
        ("bounded history", "previous.length() - 8" in service_text),
        ("rc9 code", "versionCode 10009" in gradle_text),
        ("rc9 name", "versionName '1.0.0-rc9'" in gradle_text),
    ]
    failed = [name for name, ok in required if not ok]
    if failed:
        raise SystemExit("Bridge RC9 transform incomplete: " + ", ".join(failed))
    print("Furina Bridge RC9 persistent Termux session tracking: OK")


if __name__ == "__main__":
    main()
