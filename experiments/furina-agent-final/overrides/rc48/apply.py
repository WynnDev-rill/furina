#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC48 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def replace_function(text: str, name: str, next_name: str, replacement: str) -> str:
    start_marker = f"    def {name}("
    end_marker = f"    def {next_name}("
    start = text.find(start_marker)
    end = text.find(end_marker, start + 1)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"RC48 function boundary mismatch: {name} -> {next_name}")
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    hub_path = core / "hub.py"
    version_path = core / "version.py"
    for path in (hub_path, version_path):
        if not path.is_file():
            raise SystemExit(f"RC48 source hilang: {path}")

    version = version_path.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc48"' in version:
        print("FurinaHub Core RC48 already applied")
        return
    if 'VERSION = "1.0.0-rc47"' not in version:
        raise SystemExit("RC48 hanya dapat diterapkan dari Core RC47")

    hub = hub_path.read_text(encoding="utf-8")

    # RC45/RC46 already added runtime diagnostics. Keep them, but stop the
    # automatic wake loop from restarting every few seconds while the UI polls.
    hub = replace_once(
        hub,
        '        if now - self._connector_wake_at < 8:\n',
        '        if now - self._connector_wake_at < 60:\n',
        "connector wake throttle",
    )

    status_block = '''    def connector_status(self) -> dict:
        config = load_hub_settings().get("connectors") or {}
        configured = CONNECTOR_TOKEN_PATH.exists()
        out = {
            "enabled": True,
            "base_url": config.get("base_url") or "http://127.0.0.1:3000",
            "token_configured": configured,
            "online": False,
            "state": "starting",
            "message": "Menyiapkan Plugin",
            "repairable": False,
        }
        try:
            # OpenConnector documents /v1/health as its lightweight readiness endpoint.
            self._connector_request("GET", "/v1/health")
            out.update(online=True, state="ready", message="Plugin siap digunakan", repairable=False)
        except Exception as exc:
            launcher = shutil.which("furina-openconnector")
            if not launcher:
                out.update(
                    state="missing",
                    repairable=True,
                    message="Komponen Plugin belum terpasang. Jalankan furina update.",
                )
                return out

            now = time.monotonic()
            never_woken = self._connector_wake_at <= 0
            waking = self._wake_connector_runtime() if never_woken or now - self._connector_wake_at >= 60 else False
            elapsed = time.monotonic() - self._connector_wake_at
            if waking or elapsed < 8:
                out.update(state="starting", message="Menyalakan layanan Plugin…", repairable=False)
            else:
                detail = self._connector_runtime_error()
                fallback = str(exc).strip()[:220]
                out.update(
                    state="error",
                    repairable=True,
                    message=(detail or fallback or "Plugin gagal start. Jalankan furina update untuk memperbaiki runtime."),
                )
        return out'''
    hub = replace_function(hub, "connector_status", "connector_actions", status_block)

    old_provider = '''            auth = provider.get("auth") if isinstance(provider.get("auth"), list) else []
            logo = provider.get("logoUrl") or provider.get("logo") or provider.get("iconUrl") or provider.get("icon") or PLUGIN_LOGOS.get(service, "")
            if not (str(logo).startswith("https://") or str(logo).startswith("data:image/")):
                logo = ""
            result.append({
                "id": service,
                "name": str(provider.get("name") or provider.get("displayName") or service.replace("_", " ").title()),
                "description": str(provider.get("description") or provider.get("summary") or "")[:240],
                "category": str(provider.get("category") or provider.get("group") or "Lainnya"),
                "logo": logo,
                "connected": service in connected,
                "action_count": counts.get(service, 0),
                "auth_types": [str(item.get("type") or item.get("authType") or "") for item in auth if isinstance(item, dict)],
            })
'''
    new_provider = '''            auth = provider.get("auth") if isinstance(provider.get("auth"), list) else []
            declared_auth = provider.get("authTypes") if isinstance(provider.get("authTypes"), list) else []
            auth_types = [str(x).strip().lower() for x in declared_auth if str(x).strip()]
            if not auth_types:
                auth_types = [str(item.get("type") or item.get("authType") or "").strip().lower() for item in auth if isinstance(item, dict)]
            categories = provider.get("categories") if isinstance(provider.get("categories"), list) else []
            category = str((categories[0] if categories else None) or provider.get("category") or provider.get("group") or "Lainnya")
            logo = provider.get("logoUrl") or provider.get("logo") or provider.get("iconUrl") or provider.get("icon") or PLUGIN_LOGOS.get(service, "")
            if not (str(logo).startswith("https://") or str(logo).startswith("data:image/")):
                logo = ""
            result.append({
                "id": service,
                "name": str(provider.get("name") or provider.get("displayName") or service.replace("_", " ").title()),
                "description": str(provider.get("description") or provider.get("summary") or "")[:240],
                "category": category,
                "logo": logo,
                "connected": service in connected or "no_auth" in auth_types,
                "action_count": counts.get(service, 0),
                "auth_types": auth_types,
            })
'''
    hub = replace_once(hub, old_provider, new_provider, "provider auth metadata")

    hub_path.write_text(hub, encoding="utf-8")
    version_path.write_text(version.replace('VERSION = "1.0.0-rc47"', 'VERSION = "1.0.0-rc48"', 1), encoding="utf-8")

    for path in (hub_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    combined = hub_path.read_text(encoding="utf-8") + "\n" + version_path.read_text(encoding="utf-8")
    required = (
        'VERSION = "1.0.0-rc48"',
        'self._connector_request("GET", "/v1/health")',
        'now - self._connector_wake_at < 60',
        'elapsed < 8',
        'provider.get("authTypes")',
        '"connected": service in connected or "no_auth" in auth_types',
        'repairable=True',
    )
    missing = [marker for marker in required if marker not in combined]
    if missing:
        raise SystemExit(f"RC48 marker hilang: {missing}")
    print("FURINAHUB_CORE_RC48_PLUGIN_OK")


if __name__ == "__main__":
    main()
