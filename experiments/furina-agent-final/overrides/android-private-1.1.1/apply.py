#!/usr/bin/env python3
"""Repair FurinaHub's connection state rendering and settings navigation."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
APP = ROOT / "bridge/app"
BUILD = APP / "build.gradle"
MAIN = APP / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
HTML = APP / "src/main/assets/furinahub/index.html"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{label}: expected exactly one marker")
    return text.replace(old, new, 1)


build = BUILD.read_text(encoding="utf-8")
build = replace_once(build, "versionCode 10077", "versionCode 10078", "version code")
build = replace_once(build, "versionName '1.1.9'", "versionName '1.1.10'", "version name")
BUILD.write_text(build, encoding="utf-8")

main = MAIN.read_text(encoding="utf-8")
main = replace_once(main, 'EXPECTED_CORE_VERSION = "1.1.9"', 'EXPECTED_CORE_VERSION = "1.1.10"', "Core version")
main = replace_once(main, 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r59"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r60"', "dependency revision")
if "furina-2026.08.25-private-1.1.9" not in main:
    raise SystemExit("bundle id: marker missing")
main = main.replace("furina-2026.08.25-private-1.1.9", "furina-2026.08.25-private-1.1.10")

# Re-opening FurinaHub after Termux has been brought to the foreground must
# refresh the saved Core health instead of leaving a stale Offline status.
main = replace_once(
    main,
    "        BridgePrefs.openBootstrapWindow(this, 120_000L);\n        if (web != null)",
    "        BridgePrefs.openBootstrapWindow(this, 120_000L);\n        probeSavedCore();\n        if (web != null)",
    "resume health refresh",
)
MAIN.write_text(main, encoding="utf-8")

page = HTML.read_text(encoding="utf-8")

# 1.1.9 removed the updater button from Settings but left an unconditional
# reference in applyConnection(). That throws before the connection status is
# rendered, making a successful Termux handshake look permanently Offline.
old_connection = "const coreBtn=document.getElementById('coreUpdateBtn');coreBtn.disabled=!connection.termux_installed||!!connection.busy;coreBtn.textContent=connection.connected?'Update Core':'Recovery lewat Termux';"
new_connection = "const coreBtn=document.getElementById('coreUpdateBtn');if(coreBtn){coreBtn.disabled=!connection.termux_installed||!!connection.busy;coreBtn.textContent=connection.connected?'Update Core':'Recovery lewat Termux';}"
page = replace_once(page, old_connection, new_connection, "removed updater button guard")

# The prior nested-if is impossible for the Relationship view and made the
# settings/relationship route skip its intended refresh path.
old_go = "drawer(false);if(id==='settings')if(id==='relationship'){if(connection.connected)loadRelationship();else renderRelationship(null)}if(connection.connected){"
new_go = "drawer(false);if(id==='relationship'){if(connection.connected)loadRelationship();else renderRelationship(null)}if(connection.connected){"
page = replace_once(page, old_go, new_go, "settings navigation")

# Keep the connection card aligned on compact phones without creating a hidden
# or collapsed trait list. The trait grid remains an always-rendered 20-item
# matrix supplied by the shared Termux Core.
css = "#settings .settingsConnectionCard{margin-top:16px}.settingsConnectionCard .actions{align-items:stretch}.settingsConnectionCard .btn{white-space:normal;line-height:1.2}.traitGrid110{content-visibility:visible}.traitChoice110{visibility:visible}"
if "</style>" not in page:
    raise SystemExit("style marker missing")
page = page.replace("</style>", css + "</style>", 1)
HTML.write_text(page, encoding="utf-8")

print("FURINAHUB_PRIVATE_1_1_1_CONNECTION_AND_SETTINGS_REPAIR_OK")
