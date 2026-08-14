from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import threading
import sys
import time
import urllib.parse
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
    load_hub_settings,
    normalize,
    save_hub_settings,
)
from .memory import MemoryStore
from .providers import PROVIDER_LABELS, ProviderSecrets
from .routing import RoutingLLM
from .version import VERSION
from .hub_web import HTML

HUB_HOST = "127.0.0.1"
HUB_PORT = 8787
PID_PATH = HOME / "run" / "furinahub.pid"
TOKEN_PATH = HOME / "run" / "furinahub.token"
UPDATE_STATUS_PATH = HOME / "run" / "furinahub-update.json"


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
        secrets_store = ProviderSecrets()
        models = []
        for path in sorted(MODELS_DIR.glob("*.gguf")):
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            models.append({
                "path": str(path),
                "name": path.name,
                "size_bytes": size,
                "active": bool(cfg.model_path and Path(cfg.model_path) == path),
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
            "providers": providers,
            "presets": PRESETS,
            "trait_labels": TRAIT_LABELS,
            "skill_meta": SKILL_META,
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

    def bootstrap(self) -> dict:
        cfg = load_config()
        history = self.store.recent_messages(24)
        return {
            "app": "FurinaHub",
            "core_version": VERSION,
            "bridge_target": "1.0.0-rc19",
            "assistant_name": cfg.persona_name,
            "user_nickname": cfg.user_nickname,
            "routing_mode": cfg.routing_mode,
            "history": history,
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

    def system_snapshot(self) -> dict:
        cfg = load_config()
        hub = load_hub_settings()
        bridge = {}
        bridge_error = ""
        try:
            bridge = self.session.bridge.health() or {}
        except Exception as exc:
            bridge_error = str(exc)
        revision_path = HOME / "data" / "dependency_revision"
        try:
            dependency_revision = revision_path.read_text(encoding="utf-8").strip()
        except Exception:
            dependency_revision = "belum diperiksa"
        return {
            "core_version": VERSION,
            "bridge_target": "1.0.0-rc19",
            "dependency_revision": dependency_revision,
            "bridge": bridge,
            "bridge_error": bridge_error,
            "routing_mode": cfg.routing_mode,
            "model_path": cfg.model_path,
            "device_control_mode": hub.get("device_control_mode", "normal"),
            "skills": hub.get("agent_skills", {}),
            "update": self.get_update_status(),
        }

    def get_update_status(self) -> dict:
        with self.update_lock:
            return dict(self.update_status)

    def _set_update_status(self, **values) -> None:
        with self.update_lock:
            self.update_status.update(values)
            self.update_status["updated_at"] = time.time()
        try:
            UPDATE_STATUS_PATH.write_text(json.dumps(self.update_status, ensure_ascii=False), encoding="utf-8")
            os.chmod(UPDATE_STATUS_PATH, 0o600)
        except Exception:
            pass

    def _run_core_update(self) -> None:
        log_path = HOME / "logs" / "furinahub-inapp-update.log"
        try:
            command = shutil.which("furina")
            if not command:
                raise RuntimeError("launcher furina tidak ditemukan")
            self._set_update_status(state="running", message="Memeriksa Core dan dependency terkelola…", restart_required=False)
            with log_path.open("w", encoding="utf-8") as log:
                proc = subprocess.run(
                    [command, "update"],
                    stdout=log, stderr=subprocess.STDOUT, text=True, timeout=900, check=False,
                )
            if proc.returncode != 0:
                raise RuntimeError(f"updater selesai dengan kode {proc.returncode}")
            self._set_update_status(
                state="done",
                message="Pemeriksaan Core & dependency selesai. Muat ulang FurinaHub untuk memakai Core terbaru.",
                restart_required=True,
            )
        except Exception as exc:
            self._set_update_status(
                state="error",
                message=f"Update gagal: {str(exc)[:260]}",
                restart_required=False,
            )

    def start_core_update(self) -> dict:
        with self.update_lock:
            if self.update_status.get("state") == "running":
                return dict(self.update_status)
            self.update_status = {
                "state": "starting",
                "message": "Menyiapkan pemeriksaan Core & dependency…",
                "restart_required": False,
                "updated_at": time.time(),
            }
        threading.Thread(target=self._run_core_update, name="furinahub-core-update", daemon=True).start()
        return self.get_update_status()

    def chat(self, text: str) -> dict:
        text = str(text or "").strip()
        if not text:
            raise ValueError("pesan kosong")
        if len(text) > 12000:
            raise ValueError("pesan terlalu panjang")
        with self.lock:
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
        if length < 0 or length > 2_000_000:
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
            if path == "/api/update/status":
                self._json(RUNTIME.get_update_status()); return
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
                self._json(RUNTIME.chat(body.get("message", ""))); return
            if path == "/api/settings":
                self._json(RUNTIME.save_settings(body)); return
            if path == "/api/provider":
                self._json(RUNTIME.set_provider(body)); return
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
