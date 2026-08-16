#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_function(text: str, name: str, next_name: str, replacement: str) -> str:
    start_marker = f"    def {name}("
    end_marker = f"    def {next_name}("
    start = text.find(start_marker)
    end = text.find(end_marker, start + 1)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"RC49 function boundary mismatch: {name} -> {next_name}")
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
            raise SystemExit(f"RC49 source hilang: {path}")

    version = version_path.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc49"' in version:
        print("FurinaHub Core RC49 already applied")
        return
    if 'VERSION = "1.0.0-rc48"' not in version:
        raise SystemExit("RC49 hanya dapat diterapkan dari Core RC48")

    hub = hub_path.read_text(encoding="utf-8")

    helpers_and_plugins = r'''    @staticmethod
    def _connector_provider_object(response: dict) -> dict:
        value = response.get("data", response) if isinstance(response, dict) else response
        if isinstance(value, dict) and isinstance(value.get("provider"), dict):
            value = value["provider"]
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _connector_category(value) -> str:
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, dict):
            value = value.get("displayName") or value.get("display_name") or value.get("name") or value.get("id")
        text = " ".join(str(value or "Lainnya").replace("_", " ").split()).strip()
        return text or "Lainnya"

    @staticmethod
    def _connector_field(raw, default_key: str = "", default_label: str = "", *, secret: bool = False, required: bool = True) -> dict:
        meta = raw if isinstance(raw, dict) else {}
        key = str(
            (raw if isinstance(raw, str) else None)
            or meta.get("key") or meta.get("name") or meta.get("id") or default_key
        ).strip()
        key = re.sub(r"[^A-Za-z0-9_.-]", "", key)[:100]
        label = str(meta.get("label") or meta.get("displayName") or meta.get("display_name") or default_label or key).strip()
        hint = str(meta.get("description") or meta.get("help") or meta.get("placeholder") or "").strip()[:240]
        lowered = key.casefold()
        sensitive = bool(meta.get("secret") or meta.get("sensitive") or secret or any(word in lowered for word in ("secret", "password", "token", "apikey", "api_key", "private")))
        needed = bool(meta.get("required", required))
        return {"key": key, "label": label or key, "hint": hint, "secret": sensitive, "required": needed}

    @classmethod
    def _connector_auth_specs(cls, provider: dict) -> list[dict]:
        specs: list[dict] = []
        auth = provider.get("auth") if isinstance(provider.get("auth"), list) else []
        for raw in auth:
            if not isinstance(raw, dict):
                continue
            kind = str(raw.get("type") or raw.get("authType") or "").strip().lower()
            if kind not in {"no_auth", "api_key", "custom_credential", "oauth2"}:
                continue
            fields: list[dict] = []
            if kind == "api_key":
                fields.append(cls._connector_field({}, "apiKey", "API key", secret=True))
                for item in raw.get("extraFields") or []:
                    field = cls._connector_field(item)
                    if field["key"] and field["key"] != "apiKey":
                        fields.append(field)
            elif kind == "custom_credential":
                for item in raw.get("fields") or []:
                    field = cls._connector_field(item)
                    if field["key"]:
                        fields.append(field)
            elif kind == "oauth2":
                fields.append(cls._connector_field({}, "clientId", "Client ID", secret=False))
                fields.append(cls._connector_field({}, "clientSecret", "Client secret", secret=True))
                for item in raw.get("clientConfigFields") or []:
                    field = cls._connector_field(item)
                    if field["key"] not in {"clientId", "clientSecret"} and field["key"]:
                        fields.append(field)
            specs.append({"type": kind, "fields": fields})

        declared = provider.get("authTypes") if isinstance(provider.get("authTypes"), list) else []
        known = {item["type"] for item in specs}
        for item in declared:
            kind = str(item or "").strip().lower()
            if kind in known or kind not in {"no_auth", "api_key", "custom_credential", "oauth2"}:
                continue
            if kind == "api_key":
                fields = [cls._connector_field({}, "apiKey", "API key", secret=True)]
            elif kind == "oauth2":
                fields = [
                    cls._connector_field({}, "clientId", "Client ID"),
                    cls._connector_field({}, "clientSecret", "Client secret", secret=True),
                ]
            else:
                fields = []
            specs.append({"type": kind, "fields": fields})
        return specs

    def _connector_provider_detail(self, service: str) -> dict:
        try:
            return self._connector_provider_object(
                self._connector_request("GET", "/api/providers/" + urllib.parse.quote(service, safe="_-"))
            )
        except Exception:
            providers = self._connector_items(self._connector_request("GET", "/v1/providers"), ("providers", "items", "apps"))
            for item in providers:
                if not isinstance(item, dict):
                    continue
                candidate = str(item.get("service") or item.get("id") or item.get("slug") or "").strip().lower()
                if candidate == service:
                    return item
        raise ValueError("metadata plugin tidak tersedia")

    @staticmethod
    def _connector_connection_service(item: dict) -> str:
        return str(item.get("service") or item.get("provider") or item.get("id") or "").strip().lower()

    def _connector_connections(self) -> dict[str, dict]:
        try:
            items = self._connector_items(self._connector_request("GET", "/api/connections"), ("connections", "items"))
        except Exception:
            items = []
        result: dict[str, dict] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            service = self._connector_connection_service(item)
            auth_type = str(item.get("authType") or item.get("auth_type") or "").strip().lower()
            if service and auth_type != "no_auth":
                result[service] = item
        return result

    def _connector_oauth_meta(self, service: str) -> dict:
        try:
            items = self._connector_items(self._connector_request("GET", "/api/oauth/configs"), ("configs", "items", "providers"))
        except Exception:
            return {}
        for item in items:
            if not isinstance(item, dict):
                continue
            candidate = str(item.get("service") or item.get("provider") or item.get("id") or "").strip().lower()
            if candidate != service:
                continue
            configured = any(bool(item.get(key)) for key in ("configured", "clientConfigured", "client_configured", "hasConfig", "hasClientId"))
            redirect = str(item.get("expectedRedirectUri") or item.get("redirectUri") or item.get("redirect_uri") or "").strip()
            return {"configured": configured, "expected_redirect_uri": redirect}
        return {}

    @staticmethod
    def _connector_validate_values(spec: dict, values) -> dict:
        if not isinstance(values, dict):
            values = {}
        allowed = {field.get("key") for field in spec.get("fields") or [] if field.get("key")}
        clean: dict[str, str] = {}
        for key in allowed:
            value = str(values.get(key) or "").strip()
            if len(value) > 12000:
                raise ValueError("credential terlalu panjang")
            if value:
                clean[key] = value
        for field in spec.get("fields") or []:
            if field.get("required") and field.get("key") not in clean:
                raise ValueError(f"{field.get('label') or field.get('key')} belum diisi")
        return clean

    def connector_plugins(self, query: str = "") -> dict:
        """Return a safe provider catalog. no_auth means ready, not connected."""
        status = self.connector_status()
        if not status.get("online"):
            return {
                "plugins": [],
                "count": 0,
                "total_count": 0,
                "online": False,
                "state": status.get("state", "offline"),
                "message": status.get("message", "Layanan Plugin belum siap."),
                "repairable": bool(status.get("repairable") or status.get("state") in {"missing", "error"}),
            }
        providers = self._connector_items(self._connector_request("GET", "/v1/providers"), ("providers", "items", "apps"))
        actions = self._connector_action_items(self._connector_request("GET", "/v1/actions"))
        connections = self._connector_connections()
        counts: dict[str, int] = {}
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_id = str(action.get("id") or action.get("actionId") or action.get("name") or "")
            service = str(action.get("service") or action.get("provider") or action_id.split(".", 1)[0]).strip().lower()
            if service:
                counts[service] = counts.get(service, 0) + 1

        preferred = {
            name: index for index, name in enumerate((
                "github", "gmail", "google_drive", "google_calendar", "notion", "slack",
                "dropbox", "gitlab", "discord", "linear", "jira", "trello", "airtable",
                "supabase", "hackernews", "arxiv", "crossref",
            ))
        }
        result = []
        for provider in providers:
            if not isinstance(provider, dict):
                continue
            service = str(provider.get("service") or provider.get("id") or provider.get("slug") or "").strip().lower()
            if not service:
                continue
            specs = self._connector_auth_specs(provider)
            auth_types = [item["type"] for item in specs]
            connected = service in connections
            no_auth = "no_auth" in auth_types
            ready = connected or no_auth
            conn = connections.get(service) or {}
            profile = conn.get("profile") if isinstance(conn.get("profile"), dict) else {}
            label = str(profile.get("displayName") or conn.get("displayName") or conn.get("connectionName") or "").strip()
            categories = provider.get("categories") if isinstance(provider.get("categories"), list) else []
            category_source = (categories[0] if categories else None) or provider.get("category") or provider.get("group")
            logo = provider.get("logoUrl") or provider.get("logo") or provider.get("iconUrl") or provider.get("icon") or PLUGIN_LOGOS.get(service, "")
            if not (str(logo).startswith("https://") or str(logo).startswith("data:image/")):
                logo = ""
            supported = bool(set(auth_types) & {"no_auth", "api_key", "custom_credential", "oauth2"})
            result.append({
                "id": service,
                "name": str(provider.get("name") or provider.get("displayName") or service.replace("_", " ").title()),
                "description": str(provider.get("description") or provider.get("summary") or "")[:240],
                "category": self._connector_category(category_source),
                "logo": logo,
                "connected": connected,
                "ready": ready,
                "no_auth": no_auth,
                "supported": supported,
                "connection_label": label[:120],
                "action_count": counts.get(service, 0),
                "auth_types": auth_types,
                "priority": preferred.get(service, 9999),
            })
        needle = str(query or "").strip().casefold()
        if needle:
            result = [item for item in result if needle in json.dumps(item, ensure_ascii=False).casefold()]
        result.sort(key=lambda item: (
            not item["connected"],
            item["priority"],
            not item["ready"],
            item["category"].casefold(),
            item["name"].casefold(),
        ))
        return {
            "plugins": result,
            "count": len(result),
            "total_count": len(providers),
            "online": True,
            "state": "ready",
            "message": "Plugin siap digunakan",
        }
'''
    hub = replace_function(hub, "connector_plugins", "connect_plugin", helpers_and_plugins)

    connect_block = r'''    def connect_plugin(self, payload: dict) -> dict:
        service = re.sub(r"[^a-z0-9_-]", "", str(payload.get("service") or "").lower())
        if not service:
            raise ValueError("plugin tidak valid")
        provider = self._connector_provider_detail(service)
        specs = self._connector_auth_specs(provider)
        by_type = {item["type"]: item for item in specs}
        connections = self._connector_connections()
        if service in connections:
            return {"ok": True, "connected": True, "flow": "connected", "message": "Plugin sudah terhubung."}
        if "no_auth" in by_type:
            return {"ok": True, "connected": False, "ready": True, "flow": "no_auth", "message": "Plugin siap digunakan tanpa login."}
        if not by_type:
            return {"ok": False, "flow": "unsupported", "message": "Metode autentikasi plugin ini belum didukung oleh runtime lokal."}

        mode = str(payload.get("mode") or "auto").strip().lower()
        oauth_meta = self._connector_oauth_meta(service) if "oauth2" in by_type else {}

        if mode == "auto":
            # Prefer one-click OAuth only when a client app was already configured.
            if "oauth2" in by_type and oauth_meta.get("configured"):
                mode = "oauth2"
            elif "api_key" in by_type:
                spec = by_type["api_key"]
                return {"ok": True, "flow": "credential", "mode": "api_key", "fields": spec["fields"], "auth_options": list(by_type), "message": "Masukkan credential yang diminta layanan ini."}
            elif "custom_credential" in by_type:
                spec = by_type["custom_credential"]
                return {"ok": True, "flow": "credential", "mode": "custom_credential", "fields": spec["fields"], "auth_options": list(by_type), "message": "Masukkan credential yang diminta layanan ini."}
            elif "oauth2" in by_type:
                spec = by_type["oauth2"]
                return {
                    "ok": True,
                    "flow": "oauth_setup",
                    "mode": "oauth2",
                    "fields": spec["fields"],
                    "auth_options": list(by_type),
                    "expected_redirect_uri": oauth_meta.get("expected_redirect_uri", ""),
                    "message": "OAuth lokal memerlukan Client ID aplikasi satu kali. Setelah tersimpan, koneksi berikutnya cukup lewat browser.",
                }
            return {"ok": False, "flow": "unsupported", "message": "Metode autentikasi plugin ini belum didukung."}

        if mode in {"api_key", "custom_credential"}:
            spec = by_type.get(mode)
            if not spec:
                raise ValueError("metode autentikasi tidak tersedia untuk plugin ini")
            values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            if mode == "api_key" and payload.get("api_key") and "apiKey" not in values:
                values = dict(values)
                values["apiKey"] = payload.get("api_key")
            clean = self._connector_validate_values(spec, values)
            self._connector_request(
                "PUT",
                "/api/connections/" + urllib.parse.quote(service, safe="_-"),
                {"authType": mode, "values": clean},
            )
            return {"ok": True, "connected": True, "flow": "connected", "message": "Plugin terhubung."}

        if mode == "oauth2":
            spec = by_type.get("oauth2")
            if not spec:
                raise ValueError("OAuth tidak tersedia untuk plugin ini")
            submitted = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            if submitted:
                clean = self._connector_validate_values(spec, submitted)
                config = {
                    "clientId": clean.pop("clientId"),
                    "clientSecret": clean.pop("clientSecret", ""),
                }
                if clean:
                    config["extra"] = clean
                self._connector_request(
                    "PUT",
                    "/api/oauth/configs/" + urllib.parse.quote(service, safe="_-"),
                    config,
                )
            try:
                response = self._connector_request("POST", "/api/oauth/authorizations", {"service": service})
            except Exception as exc:
                meta = self._connector_oauth_meta(service)
                return {
                    "ok": True,
                    "flow": "oauth_setup",
                    "mode": "oauth2",
                    "fields": spec["fields"],
                    "expected_redirect_uri": meta.get("expected_redirect_uri", ""),
                    "message": "OAuth belum dikonfigurasi untuk layanan ini. Masukkan Client ID aplikasi terlebih dahulu.",
                    "detail": str(exc)[:240],
                }
            value = response.get("data", response) if isinstance(response, dict) else {}
            url = value.get("authorizationUrl") if isinstance(value, dict) else ""
            if not str(url).startswith(("https://", "http://127.0.0.1", "http://localhost")):
                raise RuntimeError("OpenConnector tidak mengembalikan URL otorisasi yang aman")
            return {"ok": True, "flow": "oauth_browser", "authorization_url": url, "message": "Selesaikan izin di browser."}

        raise ValueError("metode autentikasi tidak valid")
'''
    hub = replace_function(hub, "connect_plugin", "_json_object", connect_block)

    # Keep Core diagnostics aligned with the Android shell that owns the UI.
    hub = hub.replace('"bridge_target": "1.0.0-rc30"', '"bridge_target": "1.0.0-rc32"')
    hub_path.write_text(hub, encoding="utf-8")
    version_path.write_text(version.replace('VERSION = "1.0.0-rc48"', 'VERSION = "1.0.0-rc49"', 1), encoding="utf-8")

    for path in (hub_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    combined = hub_path.read_text(encoding="utf-8") + "\n" + version_path.read_text(encoding="utf-8")
    required = (
        'VERSION = "1.0.0-rc49"',
        '"bridge_target": "1.0.0-rc32"',
        'def _connector_auth_specs(',
        'def _connector_category(',
        '"no_auth": no_auth',
        '"ready": ready',
        '"flow": "oauth_setup"',
        '"flow": "credential"',
        '"flow": "oauth_browser"',
        '"authType": mode',
    )
    missing = [item for item in required if item not in combined]
    if missing:
        raise SystemExit(f"RC49 marker hilang: {missing}")
    print("FURINAHUB_CORE_RC49_PLUGIN_AUTH_OK")


if __name__ == "__main__":
    main()
