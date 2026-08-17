#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC36 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    updater_path = app / "src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"
    gradle_path = app / "build.gradle"
    hub_path = root / "core/furina_agent/hub.py"
    for path in (updater_path, gradle_path, hub_path):
        if not path.is_file():
            raise SystemExit(f"RC36 source missing: {path}")

    updater = updater_path.read_text(encoding="utf-8")
    old_manifest = '    private static final String MANIFEST_URL = "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json";'
    new_manifest = '''    private static final String[] MANIFEST_URLS = new String[]{
            "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json",
            "https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json",
            "https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json"
    };'''
    updater = replace_once(updater, old_manifest, new_manifest, "manifest mirrors")
    updater = replace_once(
        updater,
        '                JSONObject manifest = new JSONObject(readText(MANIFEST_URL, 256 * 1024));',
        '                JSONObject manifest = new JSONObject(readTextAny(MANIFEST_URLS, 256 * 1024));',
        "manifest fallback binding",
    )
    helper = '''    private static String readTextAny(String[] urls, int limit) throws Exception {
        Throwable last = null;
        for (String url : urls) {
            try {
                return readText(url, limit);
            } catch (Throwable error) {
                last = error;
            }
        }
        if (last instanceof Exception) throw (Exception) last;
        throw new IllegalStateException(last == null ? "tidak ada jalur update" : String.valueOf(last));
    }

'''
    marker = '    private static String readText(String url, int limit) throws Exception {'
    if helper not in updater:
        if marker not in updater:
            raise SystemExit("RC36 readText marker missing")
        updater = updater.replace(marker, helper + marker, 1)
    updater = replace_once(
        updater,
        'conn.setRequestProperty("User-Agent", "FurinaBridge-Updater/1");',
        'conn.setRequestProperty("User-Agent", "FurinaHub-Updater/2");',
        "updater user agent",
    )
    updater_path.write_text(updater, encoding="utf-8")

    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = replace_once(gradle, "versionCode 10035", "versionCode 10036", "versionCode")
    gradle = replace_once(gradle, "versionName '1.0.0-rc35'", "versionName '1.0.0-rc36'", "versionName")
    gradle_path.write_text(gradle, encoding="utf-8")

    hub = hub_path.read_text(encoding="utf-8")
    hub = replace_once(
        hub,
        '"bridge_target": "1.0.0-rc35"',
        '"bridge_target": "1.0.0-rc36"',
        "Core bridge target",
    )
    hub_path.write_text(hub, encoding="utf-8")

    combined = updater + "\n" + gradle + "\n" + hub
    checks = (
        "MANIFEST_URLS",
        "cdn.jsdelivr.net/gh/WynnDev-rill/furina@experiment/furina-agent-termux",
        "readTextAny(MANIFEST_URLS",
        "FurinaHub-Updater/2",
        "versionCode 10036",
        "versionName '1.0.0-rc36'",
        '"bridge_target": "1.0.0-rc36"',
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"RC36 marker hilang: {missing}")
    print("FURINAHUB_ANDROID_RC36_UPDATE_TRANSPORT_OK")


if __name__ == "__main__":
    main()
