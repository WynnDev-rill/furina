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


def replace_block(path: pathlib.Path, start: str, end: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if new.strip() in text:
            return
        raise SystemExit(f"{label}: block markers not found")
    path.write_text(text[:a] + new.rstrip() + "\n\n" + text[b:], encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-bridge-rc7.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    service = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    activity = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
    manifest = root / "bridge/app/src/main/AndroidManifest.xml"
    gradle = root / "bridge/app/build.gradle"
    for path in (service, activity, manifest, gradle):
        if not path.is_file():
            raise SystemExit(f"missing RC7 Bridge source: {path}")

    replace_block(
        service,
        "    private boolean textMatches(AccessibilityNodeInfo n, String text) {\n",
        "    private boolean longPress(JSONObject action) {\n",
        '''    private String nodeText(AccessibilityNodeInfo n) {
        if (n == null || n.getText() == null) return "";
        return n.getText().toString();
    }

    private boolean textMatches(AccessibilityNodeInfo n, String text) {
        return nodeText(n).equals(text == null ? "" : text);
    }

    private AccessibilityNodeInfo refreshEditable(JSONObject action, AccessibilityNodeInfo fallback) {
        AccessibilityNodeInfo refreshed = editableNode(resolveNode(action));
        return refreshed != null ? refreshed : fallback;
    }

    private boolean waitForExactText(JSONObject action, AccessibilityNodeInfo fallback, String text, long timeoutMs) {
        long deadline = System.currentTimeMillis() + Math.max(100L, timeoutMs);
        while (System.currentTimeMillis() < deadline) {
            AccessibilityNodeInfo current = refreshEditable(action, fallback);
            if (textMatches(current, text)) return true;
            try { Thread.sleep(55); } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        return textMatches(refreshEditable(action, fallback), text);
    }

    private boolean setText(JSONObject action, String text) {
        AccessibilityNodeInfo n = editableNode(resolveNode(action));
        if (n == null) return false;
        if (textMatches(n, text)) return true;

        String before = nodeText(n);
        if (!n.isFocused()) n.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        Bundle b = new Bundle();
        b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        boolean accepted = n.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, b);
        if (accepted && waitForExactText(action, n, text, 650L)) return true;

        AccessibilityNodeInfo current = refreshEditable(action, n);
        String afterSet = nodeText(current);
        if (!afterSet.equals(before)) return false;

        try {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            if (clipboard == null) return false;
            clipboard.setPrimaryClip(ClipData.newPlainText("Furina", text));
            current = refreshEditable(action, n);
            if (!current.isFocused()) current.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            boolean pasted = current.performAction(AccessibilityNodeInfo.ACTION_PASTE);
            return pasted && waitForExactText(action, current, text, 750L);
        } catch (Throwable ignored) {
            return false;
        }
    }''',
        "idempotent exact text",
    )

    replace_once(activity, "import android.view.ViewGroup;\n", "import android.view.ViewGroup;\nimport android.view.WindowInsets;\n", "window insets import")
    replace_once(activity, '''        BridgeForegroundService.start(this);
        requestNotificationsIfNeeded();
        setContentView(buildUi());
''', '''        BridgeForegroundService.start(this);
        requestNotificationsIfNeeded();
        configureSystemBars();
        setContentView(buildUi());
''', "configure system bars")
    replace_once(activity, "        root.setPadding(pad, dp(28), pad, dp(36));\n", '''        final int baseTop = dp(28);
        final int baseBottom = dp(36);
        root.setPadding(pad, baseTop, pad, baseBottom);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            int top = 0;
            int bottom = 0;
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(
                        WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars() | WindowInsets.Type.displayCutout());
                top = bars.top;
                bottom = bars.bottom;
            } else {
                top = insets.getSystemWindowInsetTop();
                bottom = insets.getSystemWindowInsetBottom();
            }
            v.setPadding(pad, baseTop + top, pad, baseBottom + bottom);
            return insets;
        });
''', "root runtime insets")
    replace_once(activity, "    private void requestNotificationsIfNeeded() {\n", '''    private void configureSystemBars() {
        if (Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
        } else if (Build.VERSION.SDK_INT >= 21) {
            getWindow().getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        }
        if (Build.VERSION.SDK_INT >= 21) {
            getWindow().setStatusBarColor(Color.TRANSPARENT);
            getWindow().setNavigationBarColor(Color.TRANSPARENT);
        }
        if (Build.VERSION.SDK_INT >= 29) {
            getWindow().setNavigationBarContrastEnforced(false);
            getWindow().setStatusBarContrastEnforced(false);
        }
    }

    private void requestNotificationsIfNeeded() {
''', "system bars method")

    res = root / "bridge/app/src/main/res"
    (res / "drawable").mkdir(parents=True, exist_ok=True)
    (res / "mipmap-anydpi").mkdir(parents=True, exist_ok=True)
    (res / "mipmap-anydpi-v26").mkdir(parents=True, exist_ok=True)
    (res / "values").mkdir(parents=True, exist_ok=True)

    foreground = '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp"
    android:viewportWidth="108" android:viewportHeight="108">
    <path android:fillColor="#E9F7FF" android:pathData="M54,18 L68,31 L82,27 L77,45 L88,57 L72,62 L67,82 L54,72 L41,82 L36,62 L20,57 L31,45 L26,27 L40,31 Z"/>
    <path android:fillColor="#38BDF8" android:pathData="M54,28 C45,39 37,48 37,60 C37,70 44,78 54,78 C64,78 71,70 71,60 C71,48 63,39 54,28 Z"/>
    <path android:fillColor="#07101B" android:pathData="M47,55 C50,51 58,51 61,55 C58,58 50,58 47,55 Z"/>
</vector>
'''
    launcher = '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="48dp" android:height="48dp"
    android:viewportWidth="108" android:viewportHeight="108">
    <path android:fillColor="#07101B" android:pathData="M0,0 H108 V108 H0 Z"/>
    <path android:fillColor="#E9F7FF" android:pathData="M54,18 L68,31 L82,27 L77,45 L88,57 L72,62 L67,82 L54,72 L41,82 L36,62 L20,57 L31,45 L26,27 L40,31 Z"/>
    <path android:fillColor="#38BDF8" android:pathData="M54,28 C45,39 37,48 37,60 C37,70 44,78 54,78 C64,78 71,70 71,60 C71,48 63,39 54,28 Z"/>
</vector>
'''
    adaptive = '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/furina_icon_background"/>
    <foreground android:drawable="@drawable/ic_furina_foreground"/>
    <monochrome android:drawable="@drawable/ic_furina_foreground"/>
</adaptive-icon>
'''
    colors = '''<?xml version="1.0" encoding="utf-8"?>
<resources><color name="furina_icon_background">#07101B</color></resources>
'''
    (res / "drawable/ic_furina_foreground.xml").write_text(foreground, encoding="utf-8")
    (res / "mipmap-anydpi/ic_launcher.xml").write_text(launcher, encoding="utf-8")
    (res / "mipmap-anydpi/ic_launcher_round.xml").write_text(launcher, encoding="utf-8")
    (res / "mipmap-anydpi-v26/ic_launcher.xml").write_text(adaptive, encoding="utf-8")
    (res / "mipmap-anydpi-v26/ic_launcher_round.xml").write_text(adaptive, encoding="utf-8")
    (res / "values/furina_icon_colors.xml").write_text(colors, encoding="utf-8")

    replace_once(manifest, '''    <application
        android:allowBackup="false"
        android:label="Furina Bridge"
''', '''    <application
        android:allowBackup="false"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:label="Furina Bridge"
''', "launcher icon manifest")

    replace_once(gradle, "        versionCode 10006", "        versionCode 10007", "Bridge RC7 versionCode")
    replace_once(gradle, "        versionName '1.0.0-rc6'", "        versionName '1.0.0-rc7'", "Bridge RC7 versionName")

    required = [
        ("exact text", "waitForExactText" in service.read_text(encoding="utf-8")),
        ("no contains", "actual.contains(expected)" not in service.read_text(encoding="utf-8")),
        ("insets", "setOnApplyWindowInsetsListener" in activity.read_text(encoding="utf-8")),
        ("edge to edge", "setDecorFitsSystemWindows(false)" in activity.read_text(encoding="utf-8")),
        ("icon", 'android:icon="@mipmap/ic_launcher"' in manifest.read_text(encoding="utf-8")),
        ("rc7 code", "versionCode 10007" in gradle.read_text(encoding="utf-8")),
        ("rc7 name", "versionName '1.0.0-rc7'" in gradle.read_text(encoding="utf-8")),
    ]
    failed = [name for name, ok in required if not ok]
    if failed:
        raise SystemExit("Bridge RC7 transform incomplete: " + ", ".join(failed))
    print("Furina Bridge RC7 idempotent input + adaptive UI transform: OK")


if __name__ == "__main__":
    main()
