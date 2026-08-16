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
    hub = replace_once(
        hub,
        'CONNECTOR_TOKEN_PATH = HOME / "data" / "openconnector.token"\n',
        'CONNECTOR_TOKEN_PATH = HOME / "data" / "openconnector.token"\nCONNECTOR_LOG_PATH = HOME / "logs" / "openconnector.log"\n',
        "connector log path",
    )

    old_status = '''    def connector_status(self) -> dict:\n        config = load_hub_settings().get("connectors") or {}\n        configured = CONNECTOR_TOKEN_PATH.exists()\n        # The runtime is managed by FurinaHub. Discovery is always available;\n        # individual plugins remain opt-in when the user connects credentials.\n        out = {"enabled": True, "base_url": config.get("base_url") or "http://127.0.0.1:3000", "token_configured": configured, "online": False, "state": "starting", "message": "Menyiapkan Plugin"}\n        try:\n            data = self._connector_request("GET", "/v1/actions")\n            items = self._connector_action_items(data)\n            out.update(online=True, state="ready", message="Plugin siap digunakan", action_count=len(items) if isinstance(items, list) else None)\n        except Exception:\n            waking = self._wake_connector_runtime()\n            installed = bool(shutil.which("furina-openconnector"))\n            out.update(\n                state="starting" if waking or installed else "missing",\n                message=(\n                    "Menyalakan layanan Plugin…"\n                    if waking or installed\n                    else "Komponen Plugin belum terpasang. Jalankan update Core & dependency."\n                ),\n            )\n        return out\n'''
    new_status = '''    @staticmethod\n    def _connector_log_detail() -> str:\n        try:\n            raw = CONNECTOR_LOG_PATH.read_text(encoding="utf-8", errors="replace")[-12000:]\n        except Exception:\n            return ""\n        lines = []\n        for item in raw.replace("\\r", "\\n").splitlines():\n            line = " ".join(item.strip().split())\n            if not line or line.startswith(("> ", "npm notice", "ExperimentalWarning")):\n                continue\n            if line not in lines:\n                lines.append(line)\n        return " · ".join(lines[-2:])[:300]\n\n    def connector_status(self) -> dict:\n        config = load_hub_settings().get("connectors") or {}\n        configured = CONNECTOR_TOKEN_PATH.exists()\n        out = {"enabled": True, "base_url": config.get("base_url") or "http://127.0.0.1:3000", "token_configured": configured, "online": False, "state": "starting", "message": "Menyiapkan Plugin"}\n        try:\n            # OpenConnector documents /v1/health as the cheap readiness probe.\n            self._connector_request("GET", "/v1/health")\n            out.update(online=True, state="ready", message="Plugin siap digunakan")\n        except Exception:\n            waking = self._wake_connector_runtime()\n            installed = bool(shutil.which("furina-openconnector"))\n            detail = self._connector_log_detail() if installed and not waking else ""\n            if detail:\n                out.update(state="error", message="Plugin gagal start: " + detail)\n            elif waking or installed:\n                out.update(state="starting", message="Menyalakan layanan Plugin…")\n            else:\n                out.update(state="missing", message="Komponen Plugin belum terpasang. Jalankan furina update.")\n        return out\n'''
    hub = replace_once(hub, old_status, new_status, "connector readiness")

    old_provider = '''            auth = provider.get("auth") if isinstance(provider.get("auth"), list) else []\n            logo = provider.get("logoUrl") or provider.get("logo") or provider.get("iconUrl") or provider.get("icon") or PLUGIN_LOGOS.get(service, "")\n            if not (str(logo).startswith("https://") or str(logo).startswith("data:image/")):\n                logo = ""\n            result.append({\n                "id": service,\n                "name": str(provider.get("name") or provider.get("displayName") or service.replace("_", " ").title()),\n                "description": str(provider.get("description") or provider.get("summary") or "")[:240],\n                "category": str(provider.get("category") or provider.get("group") or "Lainnya"),\n                "logo": logo,\n                "connected": service in connected,\n                "action_count": counts.get(service, 0),\n                "auth_types": [str(item.get("type") or item.get("authType") or "") for item in auth if isinstance(item, dict)],\n            })\n'''
    new_provider = '''            auth = provider.get("auth") if isinstance(provider.get("auth"), list) else []\n            declared_auth = provider.get("authTypes") if isinstance(provider.get("authTypes"), list) else []\n            auth_types = [str(x).strip().lower() for x in declared_auth if str(x).strip()]\n            if not auth_types:\n                auth_types = [str(item.get("type") or item.get("authType") or "").strip().lower() for item in auth if isinstance(item, dict)]\n            categories = provider.get("categories") if isinstance(provider.get("categories"), list) else []\n            category = str((categories[0] if categories else None) or provider.get("category") or provider.get("group") or "Lainnya")\n            logo = provider.get("logoUrl") or provider.get("logo") or provider.get("iconUrl") or provider.get("icon") or PLUGIN_LOGOS.get(service, "")\n            if not (str(logo).startswith("https://") or str(logo).startswith("data:image/")):\n                logo = ""\n            result.append({\n                "id": service,\n                "name": str(provider.get("name") or provider.get("displayName") or service.replace("_", " ").title()),\n                "description": str(provider.get("description") or provider.get("summary") or "")[:240],\n                "category": category,\n                "logo": logo,\n                # no_auth providers are immediately usable and need no credential row.\n                "connected": service in connected or "no_auth" in auth_types,\n                "action_count": counts.get(service, 0),\n                "auth_types": auth_types,\n            })\n'''
    hub = replace_once(hub, old_provider, new_provider, "provider auth metadata")

    hub_path.write_text(hub, encoding="utf-8")
    version_path.write_text(version.replace('VERSION = "1.0.0-rc47"', 'VERSION = "1.0.0-rc48"', 1), encoding="utf-8")

    for path in (hub_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    combined = hub_path.read_text(encoding="utf-8") + "\n" + version_path.read_text(encoding="utf-8")
    required = (
        'VERSION = "1.0.0-rc48"',
        'CONNECTOR_LOG_PATH = HOME / "logs" / "openconnector.log"',
        'self._connector_request("GET", "/v1/health")',
        'provider.get("authTypes")',
        '"connected": service in connected or "no_auth" in auth_types',
    )
    missing = [marker for marker in required if marker not in combined]
    if missing:
        raise SystemExit(f"RC48 marker hilang: {missing}")
    print("FURINAHUB_CORE_RC48_PLUGIN_OK")


if __name__ == "__main__":
    main()
