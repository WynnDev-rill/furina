#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC37 marker mismatch: {label} ({count})")
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
            raise SystemExit(f"RC37 source missing: {path}")

    updater = updater_path.read_text(encoding="utf-8")
    old_urls = '''    private static final String[] MANIFEST_URLS = new String[]{
            "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json",
            "https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json",
            "https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json"
    };'''
    new_urls = '''    private static final String[] MANIFEST_URLS = new String[]{
            "https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/manifest.json",
            "https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final/manifest.json?ref=experiment/furina-agent-termux",
            "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json",
            "https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json",
            "https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json"
    };'''
    updater = replace_once(updater, old_urls, new_urls, "stable manifest channel")
    updater = replace_once(
        updater,
        'conn.setRequestProperty("User-Agent", "FurinaHub-Updater/2");',
        'conn.setRequestProperty("User-Agent", "FurinaHub-Updater/3");\n        if (url.startsWith("https://api.github.com/")) conn.setRequestProperty("Accept", "application/vnd.github.raw+json");',
        "API raw header",
    )
    updater_path.write_text(updater, encoding="utf-8")

    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = replace_once(gradle, "versionCode 10036", "versionCode 10037", "versionCode")
    gradle = replace_once(gradle, "versionName '1.0.0-rc36'", "versionName '1.0.0-rc37'", "versionName")
    gradle_path.write_text(gradle, encoding="utf-8")

    hub = hub_path.read_text(encoding="utf-8")
    old_target = '"bridge_target": "1.0.0-rc36"'
    new_target = '"bridge_target": "1.0.0-rc37"'
    count = hub.count(old_target)
    if count == 0:
        if new_target not in hub:
            raise SystemExit("RC37 marker mismatch: Core bridge target (0)")
    elif count in (1, 2):
        hub = hub.replace(old_target, new_target)
    else:
        raise SystemExit(f"RC37 marker mismatch: Core bridge target ({count})")
    hub_path.write_text(hub, encoding="utf-8")

    combined = updater + "\n" + gradle + "\n" + hub
    checks = (
        "releases/download/furina-update-stable/manifest.json",
        "api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final/manifest.json",
        "application/vnd.github.raw+json",
        "FurinaHub-Updater/3",
        "versionCode 10037",
        "versionName '1.0.0-rc37'",
        '"bridge_target": "1.0.0-rc37"',
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"RC37 marker hilang: {missing}")
    print("FURINAHUB_ANDROID_RC37_STABLE_UPDATE_CHANNEL_OK")


if __name__ == "__main__":
    main()
