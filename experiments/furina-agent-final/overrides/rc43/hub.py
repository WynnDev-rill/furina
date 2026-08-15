from __future__ import annotations

import json
import base64
import hashlib
import os
import re
import secrets
import shutil
import subprocess
import threading
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .companion import CompanionSession
from .config import HOME, MODELS_DIR, load_config, save_config
from .hub_settings import (
    PRESETS,
    SKILL_META,
    TRAIT_LABELS,
    apply_preset,
    effective_device_mode,
    load_hub_settings,
    normalize,
    save_hub_settings,
)
from .memory import MemoryStore
from .providers import PROVIDER_LABELS, OpenAICompatibleProvider, ProviderSecrets
from .routing import RoutingLLM
from .version import VERSION
from .hub_web import HTML

HUB_HOST = "127.0.0.1"
HUB_PORT = 8787
PID_PATH = HOME / "run" / "furinahub.pid"
TOKEN_PATH = HOME / "run" / "furinahub.token"
UPDATE_STATUS_PATH = HOME / "run" / "furinahub-update.json"
CONNECTOR_TOKEN_PATH = HOME / "data" / "openconnector.token"
CHAT_MEDIA_DIR = HOME / "data" / "chat-images"
MODEL_HOSTS = {"huggingface.co"}
MODEL_CATALOG = (
    {
        "id": "qwen3.5-4b-q4km",
        "name": "Qwen3.5 4B Q4_K_M",
        "file": "Qwen_Qwen3.5-4B-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF/resolve/main/Qwen_Qwen3.5-4B-Q4_K_M.gguf",
        "size_label": "sekitar 2,5 GB",
        "category": "chat",
        "description": "Pilihan seimbang untuk percakapan lokal di ponsel.",
    },
    {
        "id": "qwen3-4b-q4km",
        "name": "Qwen3 4B Q4_K_M",
        "file": "Qwen_Qwen3-4B-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/Qwen_Qwen3-4B-GGUF/resolve/main/Qwen_Qwen3-4B-Q4_K_M.gguf",
        "size_label": "sekitar 2,5 GB",
        "category": "chat",
        "description": "Model stabil dan multibahasa untuk perangkat menengah.",
    },
    {
        "id": "qwen2.5-0.5b-q4km",
        "name": "Qwen2.5 0.5B Q4_K_M",
        "file": "Qwen2.5-0.5B-Instruct-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf",
        "size_label": "sekitar 0,4 GB",
        "category": "chat",
        "description": "Ringan untuk perangkat dengan ruang dan RAM terbatas.",
    },
)
PLUGIN_LOGOS = {
    "github": "https://cdn.simpleicons.org/github",
    "gmail": "https://cdn.simpleicons.org/gmail",
    "google_drive": "https://cdn.simpleicons.org/googledrive",
    "googledrive": "https://cdn.simpleicons.org/googledrive",
    "slack": "https://cdn.simpleicons.org/slack",
    "notion": "https://cdn.simpleicons.org/notion",
    "airtable": "https://cdn.simpleicons.org/airtable",
    "dropbox": "https://cdn.simpleicons.org/dropbox",
    "discord": "https://cdn.simpleicons.org/discord",
    "spotify": "https://cdn.simpleicons.org/spotify",
    "youtube": "https://cdn.simpleicons.org/youtube",
    "google_calendar": "https://cdn.simpleicons.org/googlecalendar",
}
UI_PRESET_KEYS = ("adaptive", "tsundere", "gentle", "playful", "cool", "custom")
UI_TRAIT_KEYS = ("warmth", "directness", "playfulness", "teasing", "expressiveness")
UI_TRAIT_LABELS = {
    "warmth": "Kelembutan",
    "directness": "Ketegasan",
    "playfulness": "Keceriaan",
    "teasing": "Kejahilan",
    "expressiveness": "Ekspresif",
}


class Runtime:
    def __init__(self):
        self.lock = threading.RLock()
        self.session = None
        self.cfg = None
        self.store = None
        self.jobs: dict[str, dict] = {}
        self.job_lock = threading.RLock()
        self.update_lock = threading.RLock()
        self.update_status = {"state": "idle", "message": "Belum ada pemeriksaan update.", "restart_required": False}
        self.model_status = {"state": "idle", "message": "Belum ada unduhan model.", "percent": 0}
        self._connector_wake_at = 0.0
        self._rebuild()

    def _rebuild(self):
        with self.lock:
            self.cfg = load_config()
            hub = load_hub_settings()
            changed = False
            if hub.get("assistant_name") != self.cfg.persona_name:
                hub["assistant_name"] = self.cfg.persona_name
                changed = True
            if hub.get("user_nickname") != self.cfg.user_nickname:
                hub["user_nickname"] = self.cfg.user_nickname
                changed = True
            cfg_mode = str(getattr(self.cfg, "device_control_mode", hub.get("device_control_mode", "normal")) or "normal").strip().lower()
            if cfg_mode in {"normal", "shizuku", "root"} and hub.get("device_control_mode") != cfg_mode:
                hub["device_control_mode"] = cfg_mode
                changed = True
            if changed:
                save_hub_settings(hub)
            self.store = MemoryStore()
            self.session = CompanionSession(self.cfg, self.store, RoutingLLM(self.cfg))

    def rebuild(self):
        self._rebuild()

    def public_settings(self) -> dict:
        cfg = load_config()
        settings = load_hub_settings()
        # Config is also changed by the Termux TUI. Reconcile it on every read
        # so the APK never presents a stale, separate identity.
        cfg_mode = str(getattr(cfg, "device_control_mode", "normal") or "normal").strip().lower()
        if (
            settings.get("assistant_name") != cfg.persona_name
            or settings.get("user_nickname") != cfg.user_nickname
            or (cfg_mode in {"normal", "shizuku", "root"} and settings.get("device_control_mode") != cfg_mode)
        ):
            settings["assistant_name"] = cfg.persona_name
            settings["user_nickname"] = cfg.user_nickname
            if cfg_mode in {"normal", "shizuku", "root"}:
                settings["device_control_mode"] = cfg_mode
            settings = save_hub_settings(settings)
        secrets_store = ProviderSecrets()
        models = []
        for path in sorted(MODELS_DIR.glob("*.gguf")):
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            lower = path.name.lower()
            is_qwen = "qwen" in lower and "mmproj" not in lower
            if "mmproj" in lower:
                category, purpose = "vision_projector", "Penghubung model vision"
            elif "smolvlm" in lower:
                category, purpose = "vision", "Pemahaman gambar"
            elif "embedding" in lower:
                category, purpose = "embedding", "Pencarian memori"
            elif is_qwen:
                category, purpose = "chat", "Percakapan lokal"
            else:
                category, purpose = "support", "Komponen pendukung"
            models.append({
                "path": str(path),
                "name": path.name,
                "size_bytes": size,
                "active": bool(cfg.model_path and Path(cfg.model_path) == path),
                "category": category,
                "purpose": purpose,
                "primary": is_qwen,
            })
        providers = [
            {
                "id": key,
                "label": label,
                "configured": key in secrets_store.configured(),
                "masked": secrets_store.masked(key),
            }
            for key, label in PROVIDER_LABELS.items()
        ]
        return {
            "hub": settings,
            "core": {
                "persona_name": cfg.persona_name,
                "user_nickname": cfg.user_nickname,
                "routing_mode": cfg.routing_mode,
                "model_path": cfg.model_path,
                "threads": cfg.threads,
                "context_size": cfg.context_size,
                "max_tokens": cfg.max_tokens,
                "temperature": cfg.temperature,
                "top_p": cfg.top_p,
                "device_control_mode": str(getattr(cfg, "device_control_mode", settings["device_control_mode"])),
            },
            "models": models,
            "model_catalog": [
                {
                    **{k: v for k, v in item.items() if k != "url"},
                    "installed": any(model["name"] == item["file"] for model in models),
                    "path": str(MODELS_DIR / item["file"]),
                    "active": bool(cfg.model_path and Path(cfg.model_path).name == item["file"]),
                }
                for item in MODEL_CATALOG
            ],
            "providers": providers,
            "presets": {key: PRESETS[key] for key in UI_PRESET_KEYS if key in PRESETS},
            "trait_labels": {key: UI_TRAIT_LABELS[key] for key in UI_TRAIT_KEYS},
            "skill_meta": SKILL_META,
            "model_status": dict(self.model_status),
        }

    def save_settings(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("payload settings tidak valid")
        cfg = load_config()
        hub = load_hub_settings()

        if isinstance(payload.get("hub"), dict):
            incoming = dict(hub)
            incoming.update(payload["hub"])
            if isinstance(payload["hub"].get("characteristics"), dict):
                traits = dict(hub.get("characteristics") or {})
                traits.update(payload["hub"]["characteristics"])
                incoming["characteristics"] = traits
            if isinstance(payload["hub"].get("agent_skills"), dict):
                skills = dict(hub.get("agent_skills") or {})
                skills.update(payload["hub"]["agent_skills"])
                incoming["agent_skills"] = skills
            hub = save_hub_settings(incoming)

        if payload.get("preset"):
            hub = apply_preset(hub, str(payload["preset"]))

        core = payload.get("core") if isinstance(payload.get("core"), dict) else {}
        if "persona_name" in core or "assistant_name" in (payload.get("hub") or {}):
            value = str(core.get("persona_name") or hub.get("assistant_name") or "Furina").strip()[:48]
            cfg.persona_name = value or "Furina"
            hub["assistant_name"] = cfg.persona_name
        if "user_nickname" in core or "user_nickname" in (payload.get("hub") or {}):
            value = str(core.get("user_nickname") or hub.get("user_nickname") or "").strip()[:48]
            cfg.user_nickname = value
            hub["user_nickname"] = value

        if "routing_mode" in core:
            mode = str(core["routing_mode"]).strip().lower()
            if mode not in {"local", "auto", "online"}:
                raise ValueError("routing_mode tidak valid")
            cfg.routing_mode = mode

        if "model_path" in core:
            selected = str(core.get("model_path") or "").strip()
            if selected:
                path = Path(selected).resolve()
                models_root = MODELS_DIR.resolve()
                if path.parent != models_root or path.suffix.lower() != ".gguf" or not path.exists():
                    raise ValueError("model lokal tidak valid")
                cfg.model_path = str(path)

        if "device_control_mode" in core or "device_control_mode" in (payload.get("hub") or {}):
            mode = str(core.get("device_control_mode") or hub.get("device_control_mode") or "normal").strip().lower()
            if mode not in {"normal", "shizuku", "root"}:
                raise ValueError("mode kontrol tidak valid")
            if hasattr(cfg, "device_control_mode"):
                cfg.device_control_mode = mode
            hub["device_control_mode"] = mode

        if "threads" in core:
            cfg.threads = max(1, min(12, int(core["threads"])))
        if "context_size" in core:
            cfg.context_size = max(2048, min(16384, int(core["context_size"])))
        if "max_tokens" in core:
            cfg.max_tokens = max(128, min(8192, int(core["max_tokens"])))
        if "temperature" in core:
            cfg.temperature = max(0.0, min(2.0, float(core["temperature"])))
        if "top_p" in core:
            cfg.top_p = max(0.05, min(1.0, float(core["top_p"])))

        save_config(cfg)
        save_hub_settings(hub)
        self.rebuild()
        return self.public_settings()

    def set_provider(self, payload: dict) -> dict:
        provider = str(payload.get("provider") or "").strip().lower()
        if provider not in PROVIDER_LABELS:
            raise ValueError("provider tidak dikenal")
        secret_store = ProviderSecrets()
        if payload.get("remove"):
            secret_store.remove(provider)
        else:
            secret_store.set(provider, str(payload.get("key") or ""))
        self.rebuild()
        return self.public_settings()

    def test_provider(self, payload: dict) -> dict:
        provider = str(payload.get("provider") or "").strip().lower()
        if provider not in PROVIDER_LABELS:
            raise ValueError("provider tidak dikenal")
        key = ProviderSecrets().get(provider)
        if not key:
            raise ValueError("API key provider belum diatur")
        ok, message = OpenAICompatibleProvider(provider, key, load_config()).test()
        return {"provider": provider, "ok": bool(ok), "message": str(message)[:300]}

    def bootstrap(self) -> dict:
        cfg = load_config()
        active_id = self.store.active_conversation_id()
        rows = self.store._conn().execute(
            "SELECT id,role,content,created_at,attachment_json FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 40",
            (active_id,),
        ).fetchall()
        history = []
        for row in reversed(rows):
            item = dict(row)
            raw_attachment = item.pop("attachment_json", "")
            try:
                item["attachment"] = json.loads(raw_attachment) if raw_attachment else None
            except Exception:
                item["attachment"] = None
            history.append(item)
        return {
            "app": "FurinaHub",
            "core_version": VERSION,
            "bridge_target": "1.0.0-rc27",
            "assistant_name": cfg.persona_name,
            "user_nickname": cfg.user_nickname,
            "routing_mode": cfg.routing_mode,
            "history": history,
            "active_conversation_id": active_id,
            "conversations": self.store.list_conversations(),
            "settings": load_hub_settings(),
        }

    def memory_snapshot(self) -> dict:
        conn = self.store._conn()
        rows = conn.execute(
            """SELECT id,text,kind,importance,confidence,source,created_at
               FROM memories ORDER BY importance DESC,last_used_at DESC LIMIT 24"""
        ).fetchall()
        beliefs = conn.execute(
            """SELECT dimension,value,confidence,evidence,source,updated_at
               FROM beliefs WHERE contradicted=0
               ORDER BY confidence DESC,evidence DESC LIMIT 16"""
        ).fetchall()
        psyche = self.store.get_state("furina_psyche_v1", {})
        mid = psyche.get("mid", {}) if isinstance(psyche, dict) else {}
        return {
            "memories": [dict(r) for r in rows],
            "beliefs": [dict(r) for r in beliefs],
            "preferences": {
                "language": "Indonesia",
                "assistant_name": load_config().persona_name,
                "user_nickname": load_config().user_nickname,
            },
            "open_loops": list(mid.get("goals") or [])[:8] + list(mid.get("concerns") or [])[:8],
        }

    def change_memory(self, payload: dict) -> dict:
        action = str(payload.get("action") or "").strip().lower()
        if action == "add":
            text = str(payload.get("text") or "").strip()
            if len(text) < 4 or len(text) > 600:
                raise ValueError("memori harus 4–600 karakter")
            self.store.add_memory(text, kind="user_note", importance=0.72, confidence=0.92, source="furinahub")
        elif action == "delete":
            memory_id = int(payload.get("id") or 0)
            cur = self.store._conn().execute("DELETE FROM memories WHERE id=?", (memory_id,))
            self.store._conn().commit()
            if not cur.rowcount:
                raise ValueError("memori tidak ditemukan")
        else:
            raise ValueError("aksi memori tidak valid")
        return self.memory_snapshot()

    def system_snapshot(self) -> dict:
        cfg = load_config()
        hub = load_hub_settings()
        bridge = {}
        bridge_error = ""
        control_status = {}
        try:
            bridge = self.session.bridge.health() or {}
            control_status = self.session.bridge.control_status() or {}
        except Exception as exc:
            bridge_error = str(exc)
        revision_path = HOME / "data" / "dependency_revision"
        try:
            dependency_revision = revision_path.read_text(encoding="utf-8").strip()
        except Exception:
            dependency_revision = "belum diperiksa"
        requested = str(hub.get("device_control_mode", "normal"))
        access = hub.get("device_access") if isinstance(hub.get("device_access"), dict) else {}
        effective = effective_device_mode(hub)
        if effective == "shizuku" and not bool(control_status.get("shizuku_ready")):
            effective = "normal"
        elif effective == "root" and not bool(control_status.get("root_ready")):
            effective = "normal"
        return {
            "core_version": VERSION,
            "bridge_target": "1.0.0-rc27",
            "dependency_revision": dependency_revision,
            "bridge": bridge,
            "bridge_error": bridge_error,
            "routing_mode": cfg.routing_mode,
            "model_path": cfg.model_path,
            "device_control_mode": hub.get("device_control_mode", "normal"),
            "device": {
                "requested_mode": requested,
                "effective_mode": effective,
                "normal": {
                    "available": bool(bridge),
                    "verified": bool(bridge.get("foreground") or bridge.get("accessibility")),
                    "hint": "Aktifkan Accessibility FurinaHub untuk kontrol biasa.",
                    "detail": (access.get("normal") or {}).get("detail", ""),
                },
                "shizuku": {
                    "available": bool(control_status.get("shizuku_available")),
                    "verified": bool(control_status.get("shizuku_ready")),
                    "checked_at": (access.get("shizuku") or {}).get("checked_at", 0),
                    "hint": "Mulai Shizuku, izinkan FurinaHub, lalu periksa akses. rish di Termux tidak diperlukan.",
                    "detail": (access.get("shizuku") or {}).get("detail", ""),
                },
                "root": {
                    "available": bool(bridge),
                    "verified": bool(control_status.get("root_ready")),
                    "checked_at": (access.get("root") or {}).get("checked_at", 0),
                    "hint": "Perangkat harus root dan aplikasi superuser harus mengizinkan Termux.",
                    "detail": (access.get("root") or {}).get("detail", ""),
                },
            },
            "skills": hub.get("agent_skills", {}),
            "connector": self.connector_status(),
            "update": self.get_update_status(),
        }

    def probe_device_mode(self, payload: dict) -> dict:
        mode = str(payload.get("mode") or "normal").strip().lower()
        if mode not in {"normal", "shizuku", "root"}:
            raise ValueError("mode kontrol tidak valid")
        ok = False
        detail = ""
        if mode == "normal":
            try:
                health = self.session.bridge.health() or {}
                ok = bool(health.get("foreground") or health.get("accessibility"))
                detail = "Bridge siap." if ok else "Bridge atau Accessibility belum aktif."
            except Exception as exc:
                detail = str(exc)[:220]
        else:
            # Shizuku/root execution lives in the Android Bridge. Checking
            # rish/su inside Termux verifies a different runtime and kept the
            # APK selection stuck on Normal even when Bridge access was ready.
            try:
                result = self.session.bridge.control({"type": "prepare_" + mode, "mode": mode}) or {}
                ok = bool(result.get("ok"))
                detail = str(result.get("message") or result.get("error") or "Akses belum siap.")[:220]
            except Exception as exc:
                detail = str(exc)[:220]
        hub = load_hub_settings()
        access = dict(hub.get("device_access") or {})
        access[mode] = {"verified": bool(ok), "checked_at": time.time(), "detail": detail}
        hub["device_access"] = access
        if ok and mode != "normal":
            skills = dict(hub.get("agent_skills") or {})
            skills["privileged_controls"] = True
            hub["agent_skills"] = skills
        save_hub_settings(hub)
        self.rebuild()
        return self.system_snapshot()

    def clear_messages(self) -> dict:
        active = self.store.active_conversation_id()
        self.store._conn().execute("DELETE FROM messages WHERE conversation_id=?", (active,))
        self.store._conn().commit()
        return self.bootstrap()

    def change_conversation(self, payload: dict) -> dict:
        action = str(payload.get("action") or "list").strip().lower()
        if action == "create":
            self.store.create_conversation(str(payload.get("title") or "Percakapan baru"))
        elif action == "switch":
            self.store.switch_conversation(int(payload.get("id") or 0))
        elif action == "delete":
            self.store.delete_conversation(int(payload.get("id") or 0))
        elif action != "list":
            raise ValueError("aksi percakapan tidak valid")
        return self.bootstrap()

    def delete_message_branch(self, message_id: int) -> dict:
        active = self.store.active_conversation_id()
        row = self.store._conn().execute(
            "SELECT id FROM messages WHERE id=? AND conversation_id=?", (int(message_id), active)
        ).fetchone()
        if not row:
            raise ValueError("pesan tidak ditemukan")
        self.store._conn().execute(
            "DELETE FROM messages WHERE id>=? AND conversation_id=?", (int(message_id), active)
        )
        self.store._conn().commit()
        return self.bootstrap()

    @staticmethod
    def _connector_is_read_action(action_id: str) -> bool:
        verb = str(action_id).rsplit(".", 1)[-1].lower()
        return verb.startswith(("get", "list", "search", "read", "find", "query", "download", "fetch", "lookup"))

    def _connector_request(self, method: str, path: str, payload: dict | None = None) -> dict:
        settings = load_hub_settings().get("connectors") or {}
        base = str(settings.get("base_url") or "http://127.0.0.1:3000").rstrip("/")
        parsed = urllib.parse.urlparse(base)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            base = "http://127.0.0.1:3000"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        try:
            token = CONNECTOR_TOKEN_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            token = ""
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                raw = response.read(2_000_000).decode("utf-8", errors="replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read(1200).decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenConnector HTTP {exc.code}: {raw[:500]}") from exc

    def _wake_connector_runtime(self) -> bool:
        """Ask the managed Termux launcher to start without blocking the UI."""
        now = time.monotonic()
        if now - self._connector_wake_at < 8:
            return False
        self._connector_wake_at = now
        launcher = shutil.which("furina-openconnector")
        if not launcher:
            return False
        try:
            subprocess.Popen(
                [launcher, "start"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception:
            return False

    def set_connector_token(self, payload: dict) -> dict:
        token = str(payload.get("token") or "").strip()
        CONNECTOR_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        if payload.get("remove") or not token:
            try:
                CONNECTOR_TOKEN_PATH.unlink()
            except FileNotFoundError:
                pass
        else:
            if len(token) > 4000:
                raise ValueError("runtime token terlalu panjang")
            CONNECTOR_TOKEN_PATH.write_text(token, encoding="utf-8")
            os.chmod(CONNECTOR_TOKEN_PATH, 0o600)
        return self.connector_status()

    @staticmethod
    def _connector_action_items(response: dict) -> list:
        value = response.get("data", response) if isinstance(response, dict) else response
        if isinstance(value, dict):
            value = value.get("actions") or value.get("items") or value.get("data") or []
        return value if isinstance(value, list) else []

    def connector_status(self) -> dict:
        config = load_hub_settings().get("connectors") or {}
        configured = CONNECTOR_TOKEN_PATH.exists()
        # The runtime is managed by FurinaHub. Discovery is always available;
        # individual plugins remain opt-in when the user connects credentials.
        out = {"enabled": True, "base_url": config.get("base_url") or "http://127.0.0.1:3000", "token_configured": configured, "online": False, "state": "starting", "message": "Menyiapkan Plugin"}
        try:
            data = self._connector_request("GET", "/v1/actions")
            items = self._connector_action_items(data)
            out.update(online=True, state="ready", message="Plugin siap digunakan", action_count=len(items) if isinstance(items, list) else None)
        except Exception:
            waking = self._wake_connector_runtime()
            installed = bool(shutil.which("furina-openconnector"))
            out.update(
                state="starting" if waking or installed else "missing",
                message=(
                    "Menyalakan layanan Plugin…"
                    if waking or installed
                    else "Komponen Plugin belum terpasang. Jalankan update Core & dependency."
                ),
            )
        return out

    def connector_actions(self, query: str = "") -> dict:
        data = self._connector_request("GET", "/v1/actions")
        items = self._connector_action_items(data)
        needle = str(query or "").strip().lower()
        if needle:
            items = [x for x in items if needle in json.dumps(x, ensure_ascii=False).lower()]
        return {"actions": items[:60], "count": len(items)}

    @staticmethod
    def _connector_items(response: dict, keys: tuple[str, ...]) -> list:
        value = response.get("data", response) if isinstance(response, dict) else response
        if isinstance(value, dict):
            for key in keys:
                if isinstance(value.get(key), list):
                    return value[key]
        return value if isinstance(value, list) else []

    def connector_plugins(self, query: str = "") -> dict:
        """Return provider-level catalog data suitable for a plugin picker."""
        status = self.connector_status()
        if not status.get("online"):
            return {
                "plugins": [],
                "count": 0,
                "online": False,
                "state": status.get("state", "offline"),
                "message": status.get("message", "Layanan Plugin belum siap."),
            }
        providers = self._connector_items(self._connector_request("GET", "/v1/providers"), ("providers", "items", "apps"))
        actions = self._connector_action_items(self._connector_request("GET", "/v1/actions"))
        try:
            connections = self._connector_items(self._connector_request("GET", "/api/connections"), ("connections", "items"))
        except Exception:
            try:
                connections = self._connector_items(self._connector_request("GET", "/v1/apps/authenticated"), ("apps", "providers", "items"))
            except Exception:
                connections = []
        connected = {
            str(item.get("service") or item.get("provider") or item.get("id") or "").lower()
            for item in connections if isinstance(item, dict)
        }
        counts: dict[str, int] = {}
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_id = str(action.get("id") or action.get("actionId") or action.get("name") or "")
            service = str(action.get("service") or action.get("provider") or action_id.split(".", 1)[0]).lower()
            if service:
                counts[service] = counts.get(service, 0) + 1
        result = []
        for provider in providers:
            if not isinstance(provider, dict):
                continue
            service = str(provider.get("service") or provider.get("id") or provider.get("slug") or "").strip().lower()
            if not service:
                continue
            auth = provider.get("auth") if isinstance(provider.get("auth"), list) else []
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
        needle = str(query or "").strip().casefold()
        if needle:
            result = [item for item in result if needle in json.dumps(item, ensure_ascii=False).casefold()]
        result.sort(key=lambda item: (not item["connected"], item["category"], item["name"].casefold()))
        return {"plugins": result, "count": len(result), "online": True, "state": "ready", "message": "Plugin siap digunakan"}

    def connect_plugin(self, payload: dict) -> dict:
        service = re.sub(r"[^a-z0-9_-]", "", str(payload.get("service") or "").lower())
        if not service:
            raise ValueError("plugin tidak valid")
        mode = str(payload.get("mode") or "oauth").lower()
        if mode == "api_key":
            key = str(payload.get("api_key") or "").strip()
            if not key:
                raise ValueError("API key belum diisi")
            self._connector_request("PUT", "/api/connections/" + service, {"authType": "api_key", "values": {"apiKey": key}})
            return {"ok": True, "connected": True, "message": "Plugin terhubung."}
        response = self._connector_request("POST", "/api/oauth/authorizations", {"service": service})
        value = response.get("data", response) if isinstance(response, dict) else {}
        url = value.get("authorizationUrl") if isinstance(value, dict) else ""
        if not str(url).startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise RuntimeError("OpenConnector belum memiliki konfigurasi OAuth untuk plugin ini")
        return {"ok": True, "authorization_url": url, "message": "Lanjutkan izin di browser."}

    @staticmethod
    def _json_object(raw: str) -> dict:
        text = str(raw or "").strip()
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise ValueError("model tidak menghasilkan rencana plugin yang valid")
        value = json.loads(match.group(0))
        if not isinstance(value, dict):
            raise ValueError("rencana plugin tidak valid")
        return value

    def _chat_with_plugins(self, text: str, plugin_ids: list[str]) -> dict:
        allowed = {re.sub(r"[^a-z0-9_-]", "", str(x).lower()) for x in plugin_ids[:4]}
        actions = [
            item for item in self.connector_actions().get("actions", [])
            if str(item.get("service") or item.get("provider") or item.get("id") or item.get("actionId") or "").split(".", 1)[0].lower() in allowed
        ][:40]
        if not actions:
            raise ValueError("plugin terpilih belum menyediakan action")
        contracts = []
        for item in actions:
            action_id = str(item.get("id") or item.get("actionId") or item.get("name") or "")
            contracts.append({"id": action_id, "description": item.get("description") or item.get("summary") or "", "input": item.get("inputSchema") or item.get("schema") or {}})
        planner = self.session.llm.chat([
            {"role": "system", "content": "Pilih tepat satu action OpenConnector untuk permintaan pengguna. Jawab JSON saja: {\"action_id\":\"...\",\"input\":{...},\"reason\":\"alasan singkat bahasa Indonesia\"}. Jangan mengarang action atau field."},
            {"role": "user", "content": json.dumps({"request": text, "actions": contracts}, ensure_ascii=False)},
        ], max_tokens=700, temperature=0.05, json_mode=True, role="connector_planner")
        plan = self._json_object(planner)
        action_id = str(plan.get("action_id") or "")
        if action_id not in {item["id"] for item in contracts}:
            raise ValueError("model memilih action di luar plugin yang diizinkan")
        action_input = plan.get("input") if isinstance(plan.get("input"), dict) else {}
        if not self._connector_is_read_action(action_id):
            return {"mode": "plugin_confirmation", "answer": str(plan.get("reason") or "Konfirmasi aksi plugin."), "plugin_action": {"action_id": action_id, "input": action_input}}
        result = self.execute_connector({"action_id": action_id, "input": action_input, "confirm": True})
        answer = self.session.llm.chat([
            {"role": "system", "content": "Jelaskan hasil tool kepada pengguna secara ringkas, akurat, dan hanya dalam bahasa Indonesia. Jangan menambah fakta yang tidak ada di hasil."},
            {"role": "user", "content": json.dumps({"request": text, "action": action_id, "result": result}, ensure_ascii=False)[:24000]},
        ], max_tokens=min(1000, int(self.cfg.max_tokens)), temperature=0.2, role="connector_result")
        self.store.add_message("user", text)
        self.store.add_message("assistant", answer)
        return {"mode": "plugin", "answer": answer, "plugin_action": action_id}

    def execute_connector(self, payload: dict) -> dict:
        action_id = str(payload.get("action_id") or "").strip()
        if not action_id or len(action_id) > 180:
            raise ValueError("action_id tidak valid")
        if not bool(payload.get("confirm")):
            raise ValueError("aksi connector memerlukan konfirmasi eksplisit")
        connector = load_hub_settings().get("connectors") or {}
        if not self._connector_is_read_action(action_id) and not connector.get("allow_write_actions"):
            raise ValueError("aksi tulis diblokir; aktifkan izin aksi tulis di pengaturan connector")
        body = {"input": payload.get("input") if isinstance(payload.get("input"), dict) else {}}
        if payload.get("connection_name"):
            body["connectionName"] = str(payload["connection_name"])[:120]
        return self._connector_request("POST", "/v1/actions/" + urllib.parse.quote(action_id, safe="._-"), body)

    def get_update_status(self) -> dict:
        with self.update_lock:
            return dict(self.update_status)

    def get_model_status(self) -> dict:
        with self.update_lock:
            return dict(self.model_status)

    def media_payload(self, media_id: str) -> dict:
        clean = re.sub(r"[^a-f0-9]", "", str(media_id).lower())
        if len(clean) != 32:
            raise ValueError("media tidak valid")
        matches = list(CHAT_MEDIA_DIR.glob(clean + ".*"))
        if len(matches) != 1 or matches[0].suffix not in {".jpg", ".png", ".webp"}:
            raise FileNotFoundError(clean)
        path = matches[0]
        mime = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[path.suffix]
        return {"id": clean, "name": path.name, "mime": mime, "base64": base64.b64encode(path.read_bytes()).decode("ascii")}

    @staticmethod
    def _safe_model_name(url: str, requested: str = "") -> str:
        parsed = urllib.parse.urlparse(str(url))
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in MODEL_HOSTS:
            raise ValueError("unduhan model hanya diizinkan dari HTTPS Hugging Face")
        name = str(requested or Path(urllib.parse.unquote(parsed.path)).name).strip()
        name = re.sub(r"[^A-Za-z0-9._+-]", "-", name)[:180]
        if not name.lower().endswith(".gguf") or name.startswith("."):
            raise ValueError("nama model harus berupa file .gguf")
        return name

    def _download_model(self, url: str, name: str) -> None:
        target = MODELS_DIR / name
        part = MODELS_DIR / (name + ".part")
        try:
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "FurinaHub/1.0"})
            with urllib.request.urlopen(req, timeout=45) as response, part.open("wb") as out:
                total = max(0, int(response.headers.get("Content-Length") or 0))
                received = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    received += len(chunk)
                    percent = min(99, int(received * 100 / total)) if total else 0
                    with self.update_lock:
                        self.model_status = {"state": "running", "message": f"Mengunduh {name}", "percent": percent, "received": received, "total": total, "name": name}
            if received < 1024:
                raise RuntimeError("file unduhan kosong atau tidak valid")
            os.replace(part, target)
            os.chmod(target, 0o600)
            with self.update_lock:
                self.model_status = {"state": "done", "message": f"{name} siap digunakan.", "percent": 100, "name": name}
        except Exception as exc:
            try:
                part.unlink()
            except FileNotFoundError:
                pass
            with self.update_lock:
                self.model_status = {"state": "error", "message": f"Unduhan gagal: {str(exc)[:240]}", "percent": 0, "name": name}

    def change_model(self, payload: dict) -> dict:
        action = str(payload.get("action") or "").strip().lower()
        if action == "download":
            with self.update_lock:
                if self.model_status.get("state") == "running":
                    raise ValueError("unduhan model lain masih berjalan")
            catalog_id = str(payload.get("catalog_id") or "").strip()
            item = next((entry for entry in MODEL_CATALOG if entry["id"] == catalog_id), None)
            if not item:
                raise ValueError("pilih model dari katalog FurinaHub")
            url = item["url"]
            name = self._safe_model_name(url, item["file"])
            with self.update_lock:
                self.model_status = {"state": "starting", "message": f"Menyiapkan {name}", "percent": 0, "name": name}
            threading.Thread(target=self._download_model, args=(url, name), daemon=True).start()
            return self.get_model_status()
        if action == "delete":
            path = Path(str(payload.get("path") or "")).resolve()
            if path.parent != MODELS_DIR.resolve() or path.suffix.lower() != ".gguf" or not path.exists():
                raise ValueError("model tidak valid")
            cfg = load_config()
            if cfg.model_path and Path(cfg.model_path).resolve() == path:
                cfg.model_path = ""
                if cfg.routing_mode == "local":
                    cfg.routing_mode = "auto"
                save_config(cfg)
            path.unlink()
            self.rebuild()
            return {"state": "done", "message": f"{path.name} dihapus dari Termux."}
        raise ValueError("aksi model tidak valid")

    def _set_update_status(self, **values) -> None:
        with self.update_lock:
            self.update_status.update(values)
            self.update_status["updated_at"] = time.time()
        try:
            UPDATE_STATUS_PATH.write_text(json.dumps(self.update_status, ensure_ascii=False), encoding="utf-8")
            os.chmod(UPDATE_STATUS_PATH, 0o600)
        except Exception:
            pass

    @staticmethod
    def _update_failure_detail(log_path: Path) -> str:
        """Return the useful end of the installer log, safe for one-line UI."""
        try:
            raw = log_path.read_text(encoding="utf-8", errors="replace")[-16000:]
        except Exception:
            return ""
        raw = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", raw).replace("\r", "\n")
        ignored = ("FurinaHub  By Wynn", "Core RC", "Log lengkap:")
        lines = []
        for item in raw.splitlines():
            line = " ".join(item.strip().split())
            if not line or line.startswith(ignored):
                continue
            if line not in lines:
                lines.append(line)
        return " · ".join(lines[-3:])[:420]

    def _run_core_update(self) -> None:
        log_path = HOME / "logs" / "furinahub-inapp-update.log"
        try:
            command = shutil.which("furina")
            if not command:
                raise RuntimeError("launcher furina tidak ditemukan")
            self._set_update_status(state="running", message="Memeriksa Core dan dependency terkelola…", percent=1, restart_required=False)
            with log_path.open("w", encoding="utf-8") as log:
                update_env = dict(os.environ)
                update_env["FURINAHUB_MACHINE_PROGRESS"] = "1"
                proc = subprocess.Popen([command, "update"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=update_env)
                started = time.time()
                assert proc.stdout is not None
                for line in proc.stdout:
                    log.write(line); log.flush()
                    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line).strip()
                    match = re.search(r"(?:PROGRESS\s+|^|\s)(\d{1,3})%?\s+(.+)", clean)
                    if match:
                        percent = max(1, min(99, int(match.group(1))))
                        self._set_update_status(state="running", percent=percent, message=match.group(2)[:180], elapsed_seconds=int(time.time()-started), restart_required=False)
                proc.wait(timeout=900)
            if proc.returncode != 0:
                detail = self._update_failure_detail(log_path)
                suffix = f": {detail}" if detail else f". Buka log {log_path}"
                raise RuntimeError(f"updater berhenti (kode {proc.returncode}){suffix}")
            self._set_update_status(
                state="done",
                message="Pemeriksaan Core & dependency selesai. Muat ulang FurinaHub untuk memakai Core terbaru.",
                percent=100,
                restart_required=True,
            )
        except Exception as exc:
            self._set_update_status(
                state="error",
                message=f"Update gagal: {str(exc)[:260]}",
                percent=int(self.get_update_status().get("percent") or 0),
                restart_required=False,
            )

    def start_core_update(self) -> dict:
        with self.update_lock:
            if self.update_status.get("state") == "running":
                return dict(self.update_status)
            self.update_status = {
                "state": "starting",
                "message": "Menyiapkan pemeriksaan Core & dependency…",
                "percent": 0,
                "restart_required": False,
                "updated_at": time.time(),
            }
        threading.Thread(target=self._run_core_update, name="furinahub-core-update", daemon=True).start()
        return self.get_update_status()

    def chat(self, text: str, image: dict | None = None, plugins: list | None = None) -> dict:
        text = str(text or "").strip()
        if not text and not image:
            raise ValueError("pesan kosong")
        if len(text) > 12000:
            raise ValueError("pesan terlalu panjang")
        with self.lock:
            plugin_ids = [str(item) for item in (plugins or []) if str(item).strip()]
            if plugin_ids and not image:
                return self._chat_with_plugins(text, plugin_ids)
            if isinstance(image, dict):
                mime = str(image.get("mime") or "").lower()
                encoded = str(image.get("base64") or "")
                name = str(image.get("name") or "gambar")[:120]
                if mime not in {"image/jpeg", "image/png", "image/webp"}:
                    raise ValueError("format gambar harus JPEG, PNG, atau WebP")
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except Exception as exc:
                    raise ValueError("data gambar tidak valid") from exc
                if not raw or len(raw) > 6_000_000:
                    raise ValueError("gambar maksimal 6 MB")
                prompt = text or "Jelaskan isi gambar ini secara ringkas dan akurat."
                vision_prompt = (
                    "TUGAS: pahami gambar secara teliti dan jawab pertanyaan pengguna. "
                    "Jangan menebak nama gim, tempat, tombol, atau tulisan yang tidak benar-benar terlihat. "
                    "Jika teks kecil tidak terbaca, katakan tidak terbaca. "
                    "Jawaban WAJIB dalam bahasa Indonesia kecuali pengguna meminta bahasa lain.\n\n"
                    f"Pertanyaan pengguna: {prompt}"
                )
                answer = self.session.llm.vision(vision_prompt, encoded, mime=mime, max_tokens=min(1200, int(self.cfg.max_tokens)), json_mode=False)
                common_en = len(re.findall(r"\b(the|this|image|shows|with|and|appears|screen|game)\b", answer.lower()))
                common_id = len(re.findall(r"\b(gambar|ini|dengan|dan|terlihat|menampilkan|layar)\b", answer.lower()))
                if common_en >= 3 and common_en > common_id:
                    answer = self.session.llm.chat([
                        {"role": "system", "content": "Terjemahkan jawaban analisis gambar berikut ke bahasa Indonesia yang alami. Pertahankan ketidakpastian dan jangan menambah fakta. Jawab hanya hasil terjemahan."},
                        {"role": "user", "content": answer},
                    ], max_tokens=min(1200, int(self.cfg.max_tokens)), temperature=0.1, role="vision_translation")
                ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime]
                media_id = secrets.token_hex(16)
                CHAT_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                target = CHAT_MEDIA_DIR / (media_id + ext)
                temp = CHAT_MEDIA_DIR / (media_id + ext + ".part")
                temp.write_bytes(raw)
                os.chmod(temp, 0o600)
                os.replace(temp, target)
                attachment = {"kind": "image", "id": media_id, "name": name, "mime": mime, "size": len(raw)}
                self.store.add_message("user", prompt, attachment=attachment)
                self.store.add_message("assistant", answer)
                return {"mode": "chat", "answer": answer}
            intent = self.session.classify(text)
            if intent.mode == "chat":
                answer = self.session.chat.respond(text)
                return {"mode": "chat", "answer": answer}
            job_id = secrets.token_hex(8)
            with self.job_lock:
                self.jobs[job_id] = {
                    "id": job_id,
                    "goal": intent.goal,
                    "original": text,
                    "status": "task_approval_required",
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "pending": {
                        "risk": "task",
                        "summary": "FurinaHub perlu mengontrol layar untuk menjalankan permintaan ini.",
                        "detail": intent.goal,
                    },
                    "answer": "",
                    "error": "",
                    "_event": threading.Event(),
                    "_decision": None,
                    "_started": False,
                }
            return {"mode": "device", "job": self.public_job(job_id)}

    def public_job(self, job_id: str) -> dict:
        with self.job_lock:
            job = self.jobs.get(job_id)
            if not job:
                raise KeyError(job_id)
            return {k: v for k, v in job.items() if not k.startswith("_")}

    def _approval_callback(self, job_id: str):
        def approve(summary, action, risk, detail):
            with self.job_lock:
                job = self.jobs.get(job_id)
                if not job:
                    return False
                event = job["_event"]
                event.clear()
                job["_decision"] = None
                job["status"] = "action_approval_required"
                job["pending"] = {
                    "risk": str(risk),
                    "summary": str(summary or "Konfirmasi aksi"),
                    "detail": str(detail or ""),
                    "action": action if isinstance(action, dict) else {},
                }
                job["updated_at"] = time.time()
            if not event.wait(300):
                return False
            with self.job_lock:
                job = self.jobs.get(job_id)
                if not job:
                    return False
                decision = bool(job.get("_decision"))
                job["_decision"] = None
                job["pending"] = None
                job["status"] = "running"
                job["updated_at"] = time.time()
            return decision
        return approve

    def _run_agent(self, job_id: str):
        try:
            with self.job_lock:
                job = self.jobs[job_id]
                goal = str(job["goal"])
                job["status"] = "running"
                job["pending"] = None
                job["updated_at"] = time.time()
            result = self.session.agent.run(
                goal,
                self._approval_callback(job_id),
                task_authorized=True,
            )
            with self.job_lock:
                job = self.jobs[job_id]
                job["answer"] = str(result or "")
                job["status"] = "done"
                job["updated_at"] = time.time()
        except Exception as exc:
            with self.job_lock:
                job = self.jobs.get(job_id)
                if job:
                    job["error"] = str(exc)[:500]
                    job["status"] = "error"
                    job["updated_at"] = time.time()

    def decide_job(self, job_id: str, allow: bool) -> dict:
        with self.job_lock:
            job = self.jobs.get(job_id)
            if not job:
                raise KeyError(job_id)
            status = job["status"]
            if status == "task_approval_required":
                if not allow:
                    job["status"] = "cancelled"
                    job["pending"] = None
                    job["updated_at"] = time.time()
                    return self.public_job(job_id)
                if not job.get("_started"):
                    job["_started"] = True
                    job["status"] = "starting"
                    job["pending"] = None
                    t = threading.Thread(target=self._run_agent, args=(job_id,), daemon=True)
                    t.start()
                return self.public_job(job_id)
            if status == "action_approval_required":
                job["_decision"] = bool(allow)
                job["_event"].set()
                job["updated_at"] = time.time()
                return self.public_job(job_id)
            return self.public_job(job_id)


RUNTIME = Runtime()


def _token(explicit: str = "") -> str:
    HOME.joinpath("run").mkdir(parents=True, exist_ok=True)
    value = str(explicit or "").strip()
    if len(value) < 24:
        value = secrets.token_urlsafe(32)
    TOKEN_PATH.write_text(value, encoding="utf-8")
    os.chmod(TOKEN_PATH, 0o600)
    return value


SESSION_TOKEN = ""


class Handler(BaseHTTPRequestHandler):
    server_version = "FurinaHub/1.0"

    def log_message(self, fmt, *args):
        return

    def _json(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            length = 0
        if length < 0 or length > 9_000_000:
            raise ValueError("request terlalu besar")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _authorized(self) -> bool:
        token = self.headers.get("X-FurinaHub-Token", "")
        return bool(SESSION_TOKEN) and secrets.compare_digest(token, SESSION_TOKEN)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/":
            access = urllib.parse.parse_qs(parsed.query).get("access", [""])[0]
            if not SESSION_TOKEN or not secrets.compare_digest(str(access), SESSION_TOKEN):
                self._json({"error": "FurinaHub access token diperlukan"}, 403)
                return
            html = HTML.replace("__FURINAHUB_TOKEN__", SESSION_TOKEN)
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/health":
            access = urllib.parse.parse_qs(parsed.query).get("access", [""])[0]
            if not SESSION_TOKEN or not secrets.compare_digest(str(access), SESSION_TOKEN):
                self._json({"ok": False}, 403)
                return
            self._json({"ok": True, "app": "FurinaHub", "version": VERSION})
            return
        if path.startswith("/api/") and not self._authorized():
            self._json({"error": "unauthorized"}, 403)
            return
        try:
            if path == "/api/bootstrap":
                self._json(RUNTIME.bootstrap()); return
            if path == "/api/settings":
                self._json(RUNTIME.public_settings()); return
            if path == "/api/memory":
                self._json(RUNTIME.memory_snapshot()); return
            if path == "/api/system":
                self._json(RUNTIME.system_snapshot()); return
            if path == "/api/connectors/actions":
                query = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
                self._json(RUNTIME.connector_actions(query)); return
            if path == "/api/connectors/plugins":
                query = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
                self._json(RUNTIME.connector_plugins(query)); return
            if path == "/api/update/status":
                self._json(RUNTIME.get_update_status()); return
            if path == "/api/models/status":
                self._json(RUNTIME.get_model_status()); return
            if path.startswith("/api/media/"):
                self._json(RUNTIME.media_payload(path.rsplit("/", 1)[-1])); return
            if path.startswith("/api/agent/jobs/"):
                self._json(RUNTIME.public_job(path.rsplit("/", 1)[-1])); return
        except KeyError:
            self._json({"error": "job tidak ditemukan"}, 404); return
        except Exception as exc:
            self._json({"error": str(exc)}, 500); return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._authorized():
            self._json({"error": "unauthorized"}, 403)
            return
        path = urllib.parse.urlparse(self.path).path
        try:
            body = self._body()
            if path == "/api/chat":
                self._json(RUNTIME.chat(body.get("message", ""), body.get("image"), body.get("plugins"))); return
            if path == "/api/settings":
                self._json(RUNTIME.save_settings(body)); return
            if path == "/api/provider":
                self._json(RUNTIME.set_provider(body)); return
            if path == "/api/provider/test":
                self._json(RUNTIME.test_provider(body)); return
            if path == "/api/models":
                self._json(RUNTIME.change_model(body)); return
            if path == "/api/memory":
                self._json(RUNTIME.change_memory(body)); return
            if path == "/api/device/probe":
                self._json(RUNTIME.probe_device_mode(body)); return
            if path == "/api/messages/clear":
                self._json(RUNTIME.clear_messages()); return
            if path == "/api/conversations":
                self._json(RUNTIME.change_conversation(body)); return
            if path.startswith("/api/messages/") and path.endswith("/branch"):
                message_id = int(path.split("/")[-2])
                self._json(RUNTIME.delete_message_branch(message_id)); return
            if path == "/api/connectors/token":
                self._json(RUNTIME.set_connector_token(body)); return
            if path == "/api/connectors/execute":
                self._json(RUNTIME.execute_connector(body)); return
            if path == "/api/connectors/connect":
                self._json(RUNTIME.connect_plugin(body)); return
            if path == "/api/update/core":
                self._json(RUNTIME.start_core_update()); return
            if path.startswith("/api/agent/jobs/") and path.endswith("/decision"):
                job_id = path.split("/")[-2]
                self._json(RUNTIME.decide_job(job_id, bool(body.get("allow")))); return
        except KeyError:
            self._json({"error": "job tidak ditemukan"}, 404); return
        except ValueError as exc:
            self._json({"error": str(exc)}, 400); return
        except Exception as exc:
            self._json({"error": str(exc)}, 500); return
        self._json({"error": "not found"}, 404)


def main():
    global SESSION_TOKEN
    explicit = ""
    args = list(sys.argv[1:])
    if "--token" in args:
        idx = args.index("--token")
        if idx + 1 < len(args):
            explicit = args[idx + 1]
    SESSION_TOKEN = _token(explicit)
    HOME.joinpath("run").mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    if not explicit:
        print(f"FurinaHub: http://{HUB_HOST}:{HUB_PORT}/?access={SESSION_TOKEN}", flush=True)
    try:
        server = ThreadingHTTPServer((HUB_HOST, HUB_PORT), Handler)
        server.daemon_threads = True
        server.serve_forever(poll_interval=0.4)
    finally:
        try:
            PID_PATH.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
