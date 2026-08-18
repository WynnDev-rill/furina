#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Android RC41 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    gradle_path = app / "build.gradle"
    hub_path = root / "core/furina_agent/hub.py"
    updater_path = app / "src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"
    for path in (gradle_path, hub_path, updater_path):
        if not path.is_file():
            raise SystemExit(f"Android RC41 source missing: {path}")

    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = replace_once(gradle, "versionCode 10040", "versionCode 10041", "versionCode")
    gradle = replace_once(gradle, "versionName '1.0.0-rc40'", "versionName '1.0.0-rc41'", "versionName")
    gradle_path.write_text(gradle, encoding="utf-8")

    hub = hub_path.read_text(encoding="utf-8")
    hub = hub.replace('"bridge_target": "1.0.0-rc40"', '"bridge_target": "1.0.0-rc41"')
    if '"bridge_target": "1.0.0-rc41"' not in hub:
        raise SystemExit("Android RC41 bridge target missing")
    hub_path.write_text(hub, encoding="utf-8")

    updater = updater_path.read_text(encoding="utf-8")
    old_urls = '''    private static final String[] MANIFEST_URLS = new String[]{
            "https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/manifest.json",
            "https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final/manifest.json",
            "https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final/manifest.json?ref=experiment/furina-agent-termux",
            "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json",
            "https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json"
    };'''
    new_urls = '''    private static final String[] MANIFEST_URLS = new String[]{
            "https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final/manifest.json?ref=experiment/furina-agent-termux",
            "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json",
            "https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/manifest.json",
            "https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json",
            "https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final/manifest.json"
    };'''
    updater = replace_once(updater, old_urls, new_urls, "live manifest precedence")
    updater = replace_once(updater, "FurinaHub-Updater/6", "FurinaHub-Updater/7", "updater agent")
    updater_path.write_text(updater, encoding="utf-8")

    combined = gradle + "\n" + hub + "\n" + updater
    checks = (
        "versionCode 10041",
        "versionName '1.0.0-rc41'",
        '"bridge_target": "1.0.0-rc41"',
        "FurinaHub-Updater/7",
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"Android RC41 marker hilang: {missing}")

    api = updater.index("api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final/manifest.json")
    raw = updater.index("raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json")
    stable = updater.index("releases/download/furina-update-stable/manifest.json")
    bootstrap = updater.index("furina-bootstrap-v1.0.0/experiments/furina-agent-final/manifest.json")
    if not (api < raw < stable < bootstrap):
        raise SystemExit("Android RC41 manifest precedence tidak aman")
    print("FURINAHUB_ANDROID_RC41_UPDATE_RECOVERY_OK")


if __name__ == "__main__":
    main()
