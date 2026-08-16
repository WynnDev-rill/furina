#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC49 hardening marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: harden.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    hub_path = root / "core/furina_agent/hub.py"
    version_path = root / "core/furina_agent/version.py"
    if not hub_path.is_file() or not version_path.is_file():
        raise SystemExit("RC49 hardening source tidak lengkap")
    version = version_path.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc49"' not in version:
        raise SystemExit("RC49 hardening memerlukan Core RC49")

    hub = hub_path.read_text(encoding="utf-8")
    old = '''    @staticmethod
    def _connector_category(value) -> str:
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, dict):
            value = value.get("displayName") or value.get("display_name") or value.get("name") or value.get("id")
        text = " ".join(str(value or "Lainnya").replace("_", " ").split()).strip()
        return text or "Lainnya"
'''
    new = '''    @staticmethod
    def _connector_category(value) -> str:
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, dict):
            lowered = {str(key).casefold(): item for key, item in value.items()}
            value = lowered.get("displayname") or lowered.get("display_name") or lowered.get("name") or lowered.get("id")
        text = " ".join(str(value or "Lainnya").replace("_", " ").split()).strip()
        return text or "Lainnya"
'''
    hub = replace_once(hub, old, new, "case-insensitive category")

    old_secret = 'cls._connector_field({}, "clientSecret", "Client secret", secret=True)'
    new_secret = 'cls._connector_field({}, "clientSecret", "Client secret", secret=True, required=False)'
    old_count = hub.count(old_secret)
    new_count = hub.count(new_secret)
    if old_count == 2 and new_count == 0:
        hub = hub.replace(old_secret, new_secret)
    elif not (old_count == 0 and new_count == 2):
        raise SystemExit(f"RC49 OAuth clientSecret marker mismatch: old={old_count} new={new_count}")

    old_oauth = '''            configured = any(bool(item.get(key)) for key in ("configured", "clientConfigured", "client_configured", "hasConfig", "hasClientId"))
'''
    new_oauth = '''            configured = any(bool(item.get(key)) for key in ("configured", "clientConfigured", "client_configured", "hasConfig", "hasClientId", "clientId", "client_id"))
'''
    hub = replace_once(hub, old_oauth, new_oauth, "OAuth configured detection")

    old_connection = '''            auth_types = [item["type"] for item in specs]
            connected = service in connections
            no_auth = "no_auth" in auth_types
            ready = connected or no_auth
'''
    new_connection = '''            auth_types = [item["type"] for item in specs]
            no_auth = "no_auth" in auth_types
            # no_auth is a virtual ready connection, never an authenticated account.
            connected = service in connections and not no_auth
            ready = connected or no_auth
'''
    hub = replace_once(hub, old_connection, new_connection, "no-auth connection semantics")

    hub_path.write_text(hub, encoding="utf-8")
    compile(hub, str(hub_path), "exec")
    assert 'lowered.get("displayname")' in hub
    assert hub.count('"Client secret", secret=True, required=False') == 2
    assert '"clientId", "client_id"' in hub
    assert 'connected = service in connections and not no_auth' in hub
    print("FURINAHUB_CORE_RC49_HARDENED")


if __name__ == "__main__":
    main()
