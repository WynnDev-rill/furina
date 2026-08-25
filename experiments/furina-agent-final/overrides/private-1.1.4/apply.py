#!/usr/bin/env python3
"""Private final repair: one authoritative Core/APK bundle state."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"

version = CORE / "version.py"
text = version.read_text(encoding="utf-8")
if 'VERSION = "1.1.12"' not in text:
    raise SystemExit("expected Core 1.1.12")
version.write_text(text.replace('VERSION = "1.1.12"', 'VERSION = "1.1.13"', 1), encoding="utf-8")

hub = CORE / "hub.py"
text = hub.read_text(encoding="utf-8")
if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r62"' not in text:
    raise SystemExit("expected dependency revision r62")
text = text.replace('EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r62"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r63"', 1)
text = text.replace('furina-2026.08.25-private-1.1.12', 'furina-2026.08.25-private-1.1.13')
with hub.open("w", encoding="utf-8") as out:
    out.write(text)
    out.write(r'''

# FURINA_FINAL_114_AUTHORITATIVE_BUNDLE_STATE
_furina_114_system_snapshot = Runtime.system_snapshot
def _furina_114_authoritative_system_snapshot(self):
    snapshot = _furina_114_system_snapshot(self)
    installed = {}
    try:
        loaded = json.loads((HOME / "data" / "installed_bundle.json").read_text(encoding="utf-8"))
        installed = loaded if isinstance(loaded, dict) else {}
    except Exception:
        installed = {}
    bundle = str(installed.get("bundle_id") or "")
    revision = str(installed.get("core_revision") or "")
    core = str(installed.get("core_version") or VERSION)
    expected_bundle = "furina-2026.08.25-private-1.1.13"
    expected_revision = "2026.08.25-r63"
    if bundle:
        snapshot["bundle_id"] = bundle
        snapshot["dependency_revision"] = revision or snapshot.get("dependency_revision", "")
        snapshot["core_version"] = core
    snapshot["bundle_synced"] = bool(
        core == VERSION
        and bundle == expected_bundle
        and revision == expected_revision
    )
    snapshot["bridge_target"] = "1.1.13"
    snapshot["bundle_state_source"] = "installed_bundle.json" if bundle else "legacy-marker"
    return snapshot
Runtime.system_snapshot = _furina_114_authoritative_system_snapshot
''')

print("FURINA_FINAL_114_CORE_OK")
