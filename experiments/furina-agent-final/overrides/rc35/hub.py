from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import subprocess
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .bridge import AndroidBridge
from .companion import CompanionSession
from .config import HOME, MODELS_DIR, RUN_DIR, load_config, save_config
from .memory import MemoryStore
from .personalization import (
    apply_archetype,
    catalog as personalization_catalog,
    load_personalization,
    save_personalization,
)
from .providers import PROVIDER_LABELS, ProviderSecrets
from .routing import RoutingLLM
from .skills import CATALOG as SKILL_CATALOG, catalog_with_state, load_skills, save_skills
from .version import VERSION

HOST = "127.0.0.1"
PORT = 8787
PID_PATH = RUN_DIR / "furinahub.pid"
UPDATE_LOG = HOME / "logs" / "furinahub-update.log"
DEPS_LOG = HOME / "logs" / "furinahub-deps.log"


def _json_safe(obj):
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)


class ApprovalBroker:
    def __init__(self):
        self._lock = threading.Lock()
        self._pending: dict[str, dict] = {}

    def request(self, summary: str, action: dict, risk: str, detail: str) -> bool:
        if risk not in {"external", "uncertain"}:
            return True
        ident = secrets.token_urlsafe(12)
        event = threading.Event()
        item = {
            "id": ident,
            "summary": str(summary or "")[:300],
            "action": _json_safe(action),
            "risk": risk,
            "detail": str(detail or "")[:500],
            "created_at": time.time(),
            "decision": None,
            "_event": event,
        }
        with self._lock:
            self._pending[ident] = item
        event.wait(90.0)
        with self._lock:
            item = self._pending.pop(ident, item)
        return item.get("decision") is True

    def visible(self) -> list[dict]:
        with self._lock:
            return [{k: v for k, v in item.items() if not k.startswith("_")} for item in self._pending.values()]

    def decide(self, ident: str, allow: bool) -> bool:
        with self._lock:
            item = self._pending.get(str(ident))
            if not item:
                return False
            item["decision"] = bool(allow)
            item["_event"].set()
            return True


class HubRuntime:
    def __init__(self):
        self.lock = threading.RLock()
        self.approvals = ApprovalBroker()
        self._update_proc: subprocess.Popen | None = None
        self._deps_proc: subprocess.Popen | None = None
        self.reload()

    def reload(self):
        with self.lock:
            self.cfg = load_config()
            self.store = MemoryStore()
            self.llm = RoutingLLM(self.cfg)
            self.session = CompanionSession(self.cfg, self.store, self.llm)

    def status(self) -> dict:
        cfg = load_config()
        bridge = None
        bridge_error = ""
        try:
            bridge = AndroidBridge(cfg).health()
        except Exception as exc:
            bridge_error = str(exc)[:240]
        local_models = []
        try:
            local_models = sorted(
                [{"path": str(p), "name": p.name, "bytes": p.stat().st_size} for p in MODELS_DIR.glob("*.gguf")],
                key=lambda x: x["name"].lower(),
            )
        except Exception:
            pass
        provider_secrets = ProviderSecrets()
        configured = set(provider_secrets.configured())
        return {
            "core_version": VERSION,
            "app_name": cfg.persona_name,
            "user_nickname": cfg.user_nickname,
            "routing_mode": cfg.routing_mode,
            "device_control_mode": getattr(cfg, "device_control_mode", "normal"),
            "model_path": cfg.model_path,
            "local_models": local_models,
            "providers": [
                {"id": key, "label": label, "configured": key in configured, "masked": provider_secrets.masked(key)}
                for key, label in PROVIDER_LABELS.items()
            ],
            "bridge": bridge,
            "bridge_error": bridge_error,
            "memory_count": len(self.store.list_memories(limit=999)),
            "update": self.job_status("core"),
            "dependencies": self.job_status("deps"),
        }

    def settings(self) -> dict:
        cfg = load_config()
        return {
            "persona_name": cfg.persona_name,
            "user_nickname": cfg.user_nickname,
            "routing_mode": cfg.routing_mode,
            "model_path": cfg.model_path,
            "device_control_mode": getattr(cfg, "device_control_mode", "normal"),
            "auto_start": bool(cfg.auto_start),
            "context_size": int(cfg.context_size),
            "threads": int(cfg.threads),
        }

    def update_settings(self, raw: dict) -> dict:
        cfg = load_config()
        if "persona_name" in raw:
            cfg.persona_name = str(raw["persona_name"] or "FurinaHub").strip()[:48] or "FurinaHub"
        if "user_nickname" in raw:
            cfg.user_nickname = str(raw["user_nickname"] or "").strip()[:48]
        if "routing_mode" in raw and str(raw["routing_mode"]) in {"local", "auto", "online"}:
            cfg.routing_mode = str(raw["routing_mode"])
        if "device_control_mode" in raw and str(raw["device_control_mode"]) in {"normal", "shizuku", "root"}:
            cfg.device_control_mode = str(raw["device_control_mode"])
        if "model_path" in raw:
            candidate = str(raw["model_path"] or "").strip()
            if candidate:
                p = Path(candidate).expanduser()
                if not p.is_absolute():
                    p = MODELS_DIR / candidate
                if p.parent.resolve() != MODELS_DIR.resolve() or p.suffix.lower() != ".gguf":
                    raise ValueError("Model harus berupa GGUF di folder model Furina.")
                if not p.exists():
                    raise ValueError("File model tidak ditemukan.")
                cfg.model_path = str(p)
            else:
                cfg.model_path = ""
        if "auto_start" in raw:
            cfg.auto_start = bool(raw["auto_start"])
        if "context_size" in raw:
            cfg.context_size = max(2048, min(int(raw["context_size"]), 16384))
        if "threads" in raw:
            cfg.threads = max(1, min(int(raw["threads"]), 12))
        save_config(cfg)
        self.reload()
        return self.settings()

    def providers_update(self, raw: dict) -> dict:
        name = str(raw.get("provider") or "").strip().lower()
        if name not in PROVIDER_LABELS:
            raise ValueError("Provider tidak dikenal.")
        secrets_store = ProviderSecrets()
        if raw.get("remove"):
            secrets_store.remove(name)
        else:
            key = str(raw.get("api_key") or "").strip()
            if not key:
                raise ValueError("API key kosong.")
            secrets_store.set(name, key)
        return self.status()["providers"]

    def memory_snapshot(self) -> dict:
        memories = []
        for m in self.store.list_memories(limit=80):
            memories.append({
                "kind": m.kind,
                "text": m.text,
                "importance": round(float(m.importance), 3),
                "confidence": round(float(getattr(m, "confidence", 0.0) or 0.0), 3),
                "source": str(getattr(m, "source", ""))[:96],
            })
        preferences = []
        open_loops = []
        try:
            for b in self.store.beliefs(min_confidence=0.38, limit=60):
                item = {"dimension": b.dimension, "value": b.value, "confidence": round(float(b.confidence), 3)}
                if b.dimension == "preference":
                    preferences.append(item)
                elif b.dimension == "goal":
                    open_loops.append(item)
        except Exception:
            pass
        return {"memories": memories, "preferences": preferences[:20], "open_loops": open_loops[:20]}

    def history(self) -> list[dict]:
        try:
            items = self.store.recent_messages(80)
        except Exception:
            items = []
        return [{"role": str(x.get("role", "")), "content": str(x.get("content", ""))} for x in items]

    def chat(self, text: str, approve_task: bool = False) -> dict:
        text = str(text or "").strip()
        if not text:
            raise ValueError("Pesan kosong.")
        with self.lock:
            intent = self.session.classify(text)
            if intent.mode == "device":
                if not approve_task:
                    return {
                        "kind": "task_approval",
                        "goal": intent.goal,
                        "message": "Perintah ini membutuhkan kontrol perangkat. Izinkan FurinaHub menjalankan tugas ini?",
                    }
                self.store.add_message("user", text)
                reply = self.session.agent.run(intent.goal, self.approvals.request, task_authorized=True)
                self.store.add_message("assistant", reply)
                return {"kind": "device", "reply": reply}
            reply = self.session.chat.respond(text)
            return {"kind": "chat", "reply": reply}

    def _spawn(self, kind: str, cmd: list[str], log_path: Path):
        proc_attr = "_update_proc" if kind == "core" else "_deps_proc"
        current = getattr(self, proc_attr)
        if current is not None and current.poll() is None:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fp = open(log_path, "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, stdout=fp, stderr=subprocess.STDOUT, start_new_session=True)
        setattr(self, proc_attr, proc)

    def start_core_update(self):
        self._spawn("core", ["furina", "update"], UPDATE_LOG)

    def start_dependency_update(self):
        helper = os.environ.get("FURINAHUB_DEPS_BIN", "furinahub-deps")
        self._spawn("deps", [helper], DEPS_LOG)

    def job_status(self, kind: str) -> dict:
        proc = self._update_proc if kind == "core" else self._deps_proc
        log_path = UPDATE_LOG if kind == "core" else DEPS_LOG
        if proc is None:
            state = "idle"; code = None
        elif proc.poll() is None:
            state = "running"; code = None
        else:
            code = int(proc.returncode)
            state = "success" if code == 0 else "failed"
        tail = ""
        try:
            tail = "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-18:])
        except Exception:
            pass
        return {"state": state, "returncode": code, "log": tail}


RUNTIME = HubRuntime()

HTML = '<!doctype html>\n<html lang="id">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n<meta name="color-scheme" content="light">\n<title>FurinaHub</title>\n<style>\n:root{--bg:#f8f8fc;--surface:#fff;--surface2:#f3f1fb;--ink:#161722;--muted:#707284;--line:#e7e5ef;--accent:#7466ee;--accent2:#9a8df4;--ok:#2c9b64;--warn:#d18a2e;--bad:#cf4f5b;--shadow:0 8px 32px rgba(58,46,116,.08);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}\n*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);min-height:100vh}.app{height:100vh;display:flex;flex-direction:column;overflow:hidden}\n.top{height:60px;display:flex;align-items:center;gap:12px;padding:env(safe-area-inset-top) 16px 0;background:rgba(248,248,252,.95);border-bottom:1px solid var(--line);flex:none}.menu{border:0;background:transparent;font-size:24px;padding:8px}.brand{font-weight:760;letter-spacing:.02em;flex:1}.modelchip{font-size:12px;border:1px solid var(--line);background:#fff;border-radius:999px;padding:7px 10px;max-width:42vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n.page{display:none;flex:1;overflow:auto;padding:16px 16px calc(26px + env(safe-area-inset-bottom))}.page.active{display:block}.chatpage.active{display:flex;flex-direction:column;padding:0;overflow:hidden}\n.messages{flex:1;overflow:auto;padding:18px 16px 12px}.msg{max-width:84%;padding:11px 13px;border-radius:17px;margin:7px 0;line-height:1.42;white-space:pre-wrap;word-break:break-word;font-size:15px}.msg.user{margin-left:auto;background:#e8e3ff;border-bottom-right-radius:6px}.msg.assistant{background:#fff;border:1px solid var(--line);border-bottom-left-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,.025)}.msg.system{max-width:92%;margin:10px auto;background:var(--surface2);color:var(--muted);font-size:13px}\n.composer{padding:10px 12px calc(10px + env(safe-area-inset-bottom));border-top:1px solid var(--line);background:#fbfbfe;display:flex;gap:8px;align-items:flex-end}.composer textarea{flex:1;border:1px solid var(--line);background:#fff;border-radius:20px;min-height:43px;max-height:126px;padding:11px 14px;resize:none;font:inherit;outline:none}.round{width:43px;height:43px;border:0;border-radius:50%;background:var(--accent);color:white;font-size:19px}.ghost{background:#efedf6;color:#5f6170}\n.drawer{position:fixed;z-index:30;inset:0 auto 0 0;width:min(86vw,340px);background:#fff;box-shadow:20px 0 50px rgba(20,20,40,.16);transform:translateX(-105%);transition:.22s;padding:calc(16px + env(safe-area-inset-top)) 12px 20px}.drawer.open{transform:translateX(0)}.shade{display:none;position:fixed;z-index:29;inset:0;background:rgba(0,0,0,.25)}.shade.open{display:block}.drawtitle{padding:12px 12px 18px;font-size:20px;font-weight:800;color:var(--accent)}.nav{display:flex;width:100%;gap:12px;align-items:center;padding:13px 12px;border:0;border-radius:14px;background:transparent;color:var(--ink);font:inherit;text-align:left}.nav.active{background:var(--surface2);color:var(--accent);font-weight:700}.sep{height:1px;background:var(--line);margin:10px 8px}\nh1{font-size:25px;margin:4px 0 4px}h2{font-size:16px;margin:22px 0 10px}.sub{color:var(--muted);font-size:13px;margin-bottom:16px}.card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:14px;margin:10px 0;box-shadow:0 3px 14px rgba(34,30,65,.025)}.row{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #efedf4}.row:last-child{border-bottom:0}.grow{flex:1}.label{font-weight:650}.desc{font-size:12px;color:var(--muted);margin-top:3px}.pill{font-size:11px;padding:5px 8px;border-radius:999px;background:var(--surface2);color:var(--accent)}.pill.ok{background:#e7f6ee;color:var(--ok)}.pill.warn{background:#fff1df;color:var(--warn)}\ninput[type=text],input[type=password],select,textarea.setting{width:100%;border:1px solid var(--line);border-radius:12px;padding:11px 12px;background:#fff;color:var(--ink);font:inherit}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:9px}.btn{border:0;border-radius:12px;padding:11px 14px;background:var(--accent);color:#fff;font-weight:700}.btn.secondary{background:#eeecf7;color:#4d4e5d}.btn.danger{background:#fde9eb;color:#a33f49}.btn:disabled{opacity:.45}.switch{appearance:none;width:46px;height:26px;border-radius:13px;background:#d8d6df;position:relative;transition:.18s}.switch:checked{background:var(--accent)}.switch:after{content:"";position:absolute;width:20px;height:20px;left:3px;top:3px;border-radius:50%;background:#fff;transition:.18s;box-shadow:0 1px 4px #7775}.switch:checked:after{left:23px}.slider{width:100%;accent-color:var(--accent)}.trait{display:grid;grid-template-columns:110px 1fr 38px;gap:8px;align-items:center;margin:12px 0;font-size:13px}.small{font-size:12px;color:var(--muted)}.empty{text-align:center;color:var(--muted);padding:24px 10px}.toast{position:fixed;z-index:50;left:50%;bottom:24px;transform:translate(-50%,30px);opacity:0;transition:.2s;background:#222330;color:#fff;border-radius:12px;padding:10px 14px;font-size:13px;max-width:88vw}.toast.show{opacity:1;transform:translate(-50%,0)}\n.modalwrap{display:none;position:fixed;z-index:60;inset:0;background:rgba(20,20,30,.35);align-items:flex-end}.modalwrap.open{display:flex}.modal{background:#fff;border-radius:22px 22px 0 0;padding:20px 18px calc(22px + env(safe-area-inset-bottom));width:100%;box-shadow:0 -10px 40px #0002}.modal h3{margin:0 0 8px}.modalactions{display:flex;gap:8px;margin-top:16px}.modalactions button{flex:1}.log{white-space:pre-wrap;font:12px ui-monospace,SFMono-Regular,monospace;background:#f6f5f9;border-radius:10px;padding:10px;max-height:210px;overflow:auto}\n@media(min-width:760px){.page{max-width:760px;width:100%;margin:auto}.messages,.composer{padding-left:max(16px,calc((100vw - 760px)/2));padding-right:max(16px,calc((100vw - 760px)/2))}.drawer{width:320px}}\n</style></head>\n<body><div class="app">\n<header class="top"><button class="menu" onclick="Hub.drawer(true)">☰</button><div class="brand" id="brand">FurinaHub</div><button class="modelchip" id="modelchip" onclick="Hub.page(\'models\')">Model</button></header>\n<main id="chat" class="page chatpage active"><div id="messages" class="messages"></div><div class="composer"><button class="round ghost" title="Lampiran belum diaktifkan pada RC35">＋</button><textarea id="chatbox" rows="1" placeholder="Ketik pesan..."></textarea><button class="round" id="send" onclick="Hub.send()">➤</button></div></main>\n<main id="memory" class="page"><h1>Memori</h1><div class="sub">Memory yang benar-benar disimpan Core. Tidak ada ringkasan hubungan.</div><div id="memorybody"></div></main>\n<main id="models" class="page"><h1>Model & Provider</h1><div class="sub">Setting ini sama dengan yang dipakai Furina di Termux.</div><div id="modelsbody"></div></main>\n<main id="personalization" class="page"><h1>Personalisasi</h1><div class="sub">Atur cara FurinaHub berbicara tanpa mengubah izin Agent atau policy.</div><div id="personalbody"></div></main>\n<main id="agent" class="page"><h1>Agent & Skills</h1><div class="sub">Normal, Shizuku, root, dan skill bersifat opt-in/restrictive.</div><div id="agentbody"></div></main>\n<main id="settings" class="page"><h1>Pengaturan</h1><div class="sub">Identitas, Core, update, dependency, dan diagnostik.</div><div id="settingsbody"></div></main>\n</div>\n<div id="shade" class="shade" onclick="Hub.drawer(false)"></div>\n<aside id="drawer" class="drawer"><div class="drawtitle">FurinaHub</div>\n<button class="nav active" data-page="chat" onclick="Hub.page(\'chat\')">◉ <span>Chat</span></button>\n<button class="nav" data-page="memory" onclick="Hub.page(\'memory\')">◌ <span>Memori</span></button>\n<button class="nav" data-page="models" onclick="Hub.page(\'models\')">◇ <span>Model & Provider</span></button>\n<button class="nav" data-page="personalization" onclick="Hub.page(\'personalization\')">✦ <span>Personalisasi</span></button>\n<button class="nav" data-page="agent" onclick="Hub.page(\'agent\')">⌁ <span>Agent & Skills</span></button>\n<div class="sep"></div><button class="nav" data-page="settings" onclick="Hub.page(\'settings\')">⚙ <span>Pengaturan & Update</span></button>\n</aside>\n<div id="toast" class="toast"></div>\n<div id="modalwrap" class="modalwrap"><div class="modal"><h3 id="modaltitle">Konfirmasi</h3><div id="modaltext"></div><div class="modalactions"><button class="btn secondary" id="modaldeny">Batal</button><button class="btn" id="modalallow">Izinkan</button></div></div></div>\n<script>\nconst Hub=(()=>{\nlet token=\'\',status=null,personal=null,skills=null,pendingSend=null;\nconst $=x=>document.getElementById(x);\nconst esc=s=>String(s??\'\').replace(/[&<>"\']/g,c=>({\'&\':\'&amp;\',\'<\':\'&lt;\',\'>\':\'&gt;\',\'"\':\'&quot;\',"\'":\'&#39;\'}[c]));\nasync function api(path,opt={}){opt.headers=Object.assign({\'X-FurinaHub-Token\':token,\'Content-Type\':\'application/json\'},opt.headers||{});let r=await fetch(path,opt);let j=await r.json();if(!r.ok)throw new Error(j.error||(\'HTTP \'+r.status));return j}\nfunction toast(t){let e=$(\'toast\');e.textContent=t;e.classList.add(\'show\');setTimeout(()=>e.classList.remove(\'show\'),2400)}\nfunction drawer(open){$(\'drawer\').classList.toggle(\'open\',open);$(\'shade\').classList.toggle(\'open\',open)}\nfunction page(id){document.querySelectorAll(\'.page\').forEach(x=>x.classList.toggle(\'active\',x.id===id));document.querySelectorAll(\'.nav\').forEach(x=>x.classList.toggle(\'active\',x.dataset.page===id));drawer(false);if(id===\'memory\')loadMemory();if(id===\'models\')loadModels();if(id===\'personalization\')loadPersonal();if(id===\'agent\')loadAgent();if(id===\'settings\')loadSettings()}\nfunction add(role,text){let e=document.createElement(\'div\');e.className=\'msg \'+role;e.textContent=text;$(\'messages\').appendChild(e);$(\'messages\').scrollTop=$(\'messages\').scrollHeight}\nasync function history(){let j=await api(\'/api/chat/history\');$(\'messages\').innerHTML=\'\';if(!j.items.length)add(\'assistant\',\'Halo. Aku di sini.\');j.items.forEach(x=>add(x.role===\'user\'?\'user\':\'assistant\',x.content))}\nasync function send(approved=false){let box=$(\'chatbox\'),text=pendingSend||box.value.trim();if(!text)return;if(!approved){add(\'user\',text);box.value=\'\';pendingSend=text}$(\'send\').disabled=true;try{let j=await api(\'/api/chat\',{method:\'POST\',body:JSON.stringify({message:text,approve_task:approved})});if(j.kind===\'task_approval\'){confirmModal(\'Kontrol perangkat\',j.message+\'\\n\\n\'+j.goal,()=>send(true),()=>{pendingSend=null;add(\'system\',\'Kontrol perangkat dibatalkan.\')});return}add(\'assistant\',j.reply);pendingSend=null}catch(e){add(\'system\',\'Gagal: \'+e.message)}finally{$(\'send\').disabled=false}}\nfunction confirmModal(title,text,yes,no){$(\'modaltitle\').textContent=title;$(\'modaltext\').textContent=text;$(\'modalwrap\').classList.add(\'open\');$(\'modalallow\').onclick=()=>{$(\'modalwrap\').classList.remove(\'open\');yes&&yes()};$(\'modaldeny\').onclick=()=>{$(\'modalwrap\').classList.remove(\'open\');no&&no()}}\nasync function pollApproval(){if(!token)return;try{let j=await api(\'/api/approvals\');let p=j.items&&j.items[0];if(p&&!$(\'modalwrap\').classList.contains(\'open\'))confirmModal(\'Konfirmasi aksi \'+p.risk,(p.summary||\'\')+\'\\n\'+(p.detail||\'\'),()=>decision(p.id,true),()=>decision(p.id,false))}catch(e){}}\nasync function decision(id,allow){try{await api(\'/api/approvals\',{method:\'POST\',body:JSON.stringify({id,allow})})}catch(e){toast(e.message)}}\nfunction row(label,desc,right=\'\'){return `<div class="row"><div class="grow"><div class="label">${esc(label)}</div><div class="desc">${esc(desc)}</div></div>${right}</div>`}\nasync function refreshStatus(){status=await api(\'/api/status\');$(\'brand\').textContent=status.app_name||\'FurinaHub\';let m=status.model_path?status.model_path.split(\'/\').pop():(status.routing_mode===\'local\'?\'Local\':status.routing_mode.toUpperCase());$(\'modelchip\').textContent=m}\nasync function loadMemory(){let j=await api(\'/api/memory\');let h=\'<h2>Memori penting</h2><div class="card">\';if(!j.memories.length)h+=\'<div class="empty">Belum ada memory tersimpan.</div>\';j.memories.slice(0,30).forEach(m=>h+=row(m.kind,m.text,`<span class="pill">${Math.round(m.importance*100)}%</span>`));h+=\'</div><h2>Preferensi yang dipelajari</h2><div class="card">\';if(!j.preferences.length)h+=\'<div class="empty">Belum ada preferensi yang cukup yakin.</div>\';j.preferences.forEach(x=>h+=row(x.value,\'confidence \'+Math.round(x.confidence*100)+\'%\'));h+=\'</div><h2>Open loops</h2><div class="card">\';if(!j.open_loops.length)h+=\'<div class="empty">Tidak ada goal terbuka yang tersimpan.</div>\';j.open_loops.forEach(x=>h+=row(x.value,\'confidence \'+Math.round(x.confidence*100)+\'%\'));h+=\'</div>\';$(\'memorybody\').innerHTML=h}\nasync function loadModels(){status=await api(\'/api/status\');let s=await api(\'/api/settings\');let h=\'<div class="card"><h2 style="margin-top:0">Mode AI</h2><select id="routing"><option value="local">Local</option><option value="auto">Auto — online lalu local fallback</option><option value="online">Online only</option></select></div><h2>Model lokal</h2><div class="card">\';if(!status.local_models.length)h+=\'<div class="empty">Belum ada GGUF di folder model.</div>\';status.local_models.forEach(m=>h+=row(m.name,(m.bytes/1073741824).toFixed(2)+\' GB\',`<input type="radio" name="model" value="${esc(m.path)}" ${m.path===s.model_path?\'checked\':\'\'}>`));h+=\'</div><h2>Provider online</h2><div class="card">\';status.providers.forEach(p=>h+=`<div class="row"><div class="grow"><div class="label">${esc(p.label)}</div><div class="desc">${esc(p.masked||\'Belum diatur\')}</div></div><button class="btn secondary" onclick="Hub.provider(\'${p.id}\')">${p.configured?\'Ubah\':\'Atur\'}</button></div>`);h+=\'</div><button class="btn" onclick="Hub.saveModels()">Simpan model</button>\';$(\'modelsbody\').innerHTML=h;$(\'routing\').value=s.routing_mode}\nasync function saveModels(){let radio=document.querySelector(\'input[name=model]:checked\');let body={routing_mode:$(\'routing\').value};if(radio)body.model_path=radio.value;await api(\'/api/settings\',{method:\'POST\',body:JSON.stringify(body)});await refreshStatus();toast(\'Model tersimpan\')}\nfunction provider(id){let k=prompt(\'Masukkan API key. Kosongkan lalu OK untuk menghapus.\');if(k===null)return;api(\'/api/providers\',{method:\'POST\',body:JSON.stringify({provider:id,api_key:k,remove:!k.trim()})}).then(()=>{toast(\'Provider diperbarui\');loadModels()}).catch(e=>toast(e.message))}\nasync function loadPersonal(){let j=await api(\'/api/personalization\');personal=j.value;let cat=j.catalog;let h=\'<div class="card"><div class="row"><div class="grow"><div class="label">Aktifkan personalisasi</div><div class="desc">Psyche tetap berkembang; ini hanya bias gaya.</div></div><input id="penabled" class="switch" type="checkbox" \'+(personal.enabled?\'checked\':\'\')+\'></div><h2>Gaya & nada dasar</h2><select id="basestyle">\';cat.base_styles.forEach(x=>h+=`<option value="${x.id}">${esc(x.id)} — ${esc(x.description)}</option>`);h+=\'</select><h2>Preset karakter</h2><select id="archetype" onchange="Hub.applyPreset(this.value)">\';cat.archetypes.forEach(x=>h+=`<option value="${x.id}">${esc(x.label)} — ${esc(x.description)}</option>`);h+=\'</select></div><h2>Karakteristik</h2><div class="card">\';let labels={warmth:\'Kehangatan\',intimacy:\'Kemesraan\',expressiveness:\'Ekspresif\',playfulness:\'Playful\',sarcasm:\'Sinis / Sarkas\',directness:\'Keterusterangan\',formality:\'Formalitas\',verbosity:\'Panjang jawaban\',emotional_sensitivity:\'Sensitivitas emosi\'};cat.traits.forEach(k=>h+=`<div class="trait"><span>${labels[k]||k}</span><input class="slider" id="tr_${k}" type="range" min="0" max="100" value="${personal[k]}" oninput="document.getElementById(\'tv_${k}\').textContent=this.value"><span id="tv_${k}">${personal[k]}</span></div>`);h+=\'</div><h2>Instruksi khusus</h2><textarea id="custom" class="setting" rows="7" placeholder="Contoh: jangan terlalu sering memakai panggilan sayang; boleh bercanda lebih tajam saat suasana santai."></textarea><div style="height:10px"></div><button class="btn" onclick="Hub.savePersonal()">Simpan personalisasi</button>\';$(\'personalbody\').innerHTML=h;$(\'basestyle\').value=personal.base_style;$(\'archetype\').value=personal.archetype;$(\'custom\').value=personal.custom_instructions}\nasync function applyPreset(name){let j=await api(\'/api/personalization\',{method:\'POST\',body:JSON.stringify({archetype:name,apply_preset:true})});personal=j.value;toast(\'Preset diterapkan\');loadPersonal()}\nasync function savePersonal(){let cat=(await api(\'/api/personalization\')).catalog;let body={enabled:$(\'penabled\').checked,base_style:$(\'basestyle\').value,archetype:$(\'archetype\').value,custom_instructions:$(\'custom\').value};cat.traits.forEach(k=>body[k]=Number($(\'tr_\'+k).value));let j=await api(\'/api/personalization\',{method:\'POST\',body:JSON.stringify(body)});personal=j.value;toast(\'Personalisasi tersimpan\')}\nasync function loadAgent(){let s=await api(\'/api/settings\');let j=await api(\'/api/skills\');skills=j.items;let h=\'<h2>Mode kontrol perangkat</h2><div class="card"><select id="controlmode"><option value="normal">Biasa — Accessibility / Android</option><option value="shizuku">Shizuku</option><option value="root">Root</option></select><div class="desc" style="margin-top:8px">Mode tidak memberi izin baru. Permission dan RC32 Action Firewall tetap berlaku.</div></div><h2>Skill Agent</h2><div class="card">\';skills.forEach(x=>h+=`<div class="row"><div class="grow"><div class="label">${esc(x.label)}</div><div class="desc">${esc(x.description)}</div></div><input class="switch" type="checkbox" data-skill="${x.id}" ${x.enabled?\'checked\':\'\'}></div>`);h+=\'</div><button class="btn" onclick="Hub.saveAgent()">Simpan Agent</button>\';$(\'agentbody\').innerHTML=h;$(\'controlmode\').value=s.device_control_mode}\nasync function saveAgent(){await api(\'/api/settings\',{method:\'POST\',body:JSON.stringify({device_control_mode:$(\'controlmode\').value})});let body={};document.querySelectorAll(\'[data-skill]\').forEach(x=>body[x.dataset.skill]=x.checked);await api(\'/api/skills\',{method:\'POST\',body:JSON.stringify(body)});toast(\'Pengaturan Agent tersimpan\')}\nasync function loadSettings(){await refreshStatus();let s=await api(\'/api/settings\');let appUpdate=\'\';try{appUpdate=window.FurinaHubNative?window.FurinaHubNative.appUpdateStatus():\'\'}catch(e){}let h=`<h2>Identitas</h2><div class="card"><div class="label">Nama AI</div><input id="ainame" type="text" value="${esc(s.persona_name)}"><div style="height:10px"></div><div class="label">Nama panggilan user</div><input id="nickname" type="text" value="${esc(s.user_nickname)}"><div style="height:12px"></div><button class="btn" onclick="Hub.saveIdentity()">Simpan identitas</button></div><h2>Update</h2><div class="card">${row(\'FurinaHub APK\',appUpdate||\'Periksa versi APK dan pasang lewat installer Android.\',`<button class="btn secondary" onclick="Hub.nativeUpdate()">Periksa</button>`)}${row(\'Core \'+status.core_version,status.update.state===\'running\'?\'Update sedang berjalan\':\'Update Core Termux dengan verifikasi integritas.\',`<button class="btn secondary" onclick="Hub.coreUpdate()">Update</button>`)}${row(\'Dependency Furina\',status.dependencies.state===\'running\'?\'Pengecekan sedang berjalan\':\'Reconcile dependency yang dibutuhkan Furina saja.\',`<button class="btn secondary" onclick="Hub.depsUpdate()">Periksa</button>`)}</div><h2>Diagnostik</h2><div class="card">${row(\'Bridge\',status.bridge?\'Terhubung\':\'Tidak terhubung\',`<span class="pill ${status.bridge?\'ok\':\'warn\'}">${status.bridge?\'OK\':\'Cek\'}</span>`)}${row(\'Mode kontrol\',s.device_control_mode,\'\')}${row(\'Memory\',status.memory_count+\' item\',\'\')}</div><div class="card"><div class="label">Log update Core</div><div class="log">${esc(status.update.log||\'Belum ada log update.\')}</div></div>`;$(\'settingsbody\').innerHTML=h}\nasync function saveIdentity(){await api(\'/api/settings\',{method:\'POST\',body:JSON.stringify({persona_name:$(\'ainame\').value,user_nickname:$(\'nickname\').value})});await refreshStatus();toast(\'Identitas tersimpan\')}\nfunction nativeUpdate(){try{if(window.FurinaHubNative){window.FurinaHubNative.checkAppUpdate();toast(\'Memeriksa FurinaHub APK…\');setTimeout(loadSettings,1600)}else toast(\'Update APK tersedia saat dibuka dari FurinaHub APK.\')}catch(e){toast(e.message)}}\nasync function coreUpdate(){await api(\'/api/update/core\',{method:\'POST\',body:\'{}\'});toast(\'Update Core dimulai\');setTimeout(loadSettings,800)}\nasync function depsUpdate(){await api(\'/api/update/dependencies\',{method:\'POST\',body:\'{}\'});toast(\'Pengecekan dependency dimulai\');setTimeout(loadSettings,800)}\nasync function boot(t){token=t||new URLSearchParams(location.search).get(\'token\')||\'\';if(!token){$(\'messages\').innerHTML=\'<div class="empty">Buka FurinaHub dari APK atau gunakan URL bertoken dari Termux.</div>\';return}try{await refreshStatus();await history();setInterval(pollApproval,900)}catch(e){add(\'system\',\'Tidak dapat menghubungi Core: \'+e.message)}}\n$(\'chatbox\').addEventListener(\'keydown\',e=>{if(e.key===\'Enter\'&&!e.shiftKey){e.preventDefault();send()}});\nreturn{boot,drawer,page,send,provider,saveModels,applyPreset,savePersonal,saveAgent,saveIdentity,nativeUpdate,coreUpdate,depsUpdate,nativeStatus:s=>{toast(String(s||\'\'));loadSettings()}};\n})();\nwindow.FurinaHub=Hub;\n</script></body></html>'


class Handler(BaseHTTPRequestHandler):
    server_version = "FurinaHub/1"

    def log_message(self, fmt, *args):
        return

    @property
    def token(self):
        return self.server.hub_token

    def _send_json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _authorized(self):
        header = self.headers.get("X-FurinaHub-Token", "")
        if secrets.compare_digest(str(header), str(self.token)):
            return True
        q = parse_qs(urlparse(self.path).query)
        candidate = (q.get("token") or [""])[0]
        return bool(candidate and secrets.compare_digest(str(candidate), str(self.token)))

    def _need_auth(self):
        if self._authorized():
            return True
        self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        return False

    def _body(self):
        try:
            n = min(int(self.headers.get("Content-Length", "0") or 0), 1024 * 128)
        except Exception:
            n = 0
        raw = self.rfile.read(n) if n > 0 else b"{}"
        try:
            obj = json.loads(raw.decode("utf-8"))
        except Exception:
            obj = {}
        return obj if isinstance(obj, dict) else {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self._send_json({"ok": True, "version": VERSION, "name": "FurinaHub"})
        if path in {"/", "/index.html"}:
            raw = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-src 'none'; base-uri 'none'")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if not path.startswith("/api/") or not self._need_auth():
            return
        try:
            if path == "/api/status":
                return self._send_json(RUNTIME.status())
            if path == "/api/settings":
                return self._send_json(RUNTIME.settings())
            if path == "/api/personalization":
                return self._send_json({"value": load_personalization(), "catalog": personalization_catalog()})
            if path == "/api/skills":
                return self._send_json({"items": catalog_with_state()})
            if path == "/api/memory":
                return self._send_json(RUNTIME.memory_snapshot())
            if path == "/api/chat/history":
                return self._send_json({"items": RUNTIME.history()})
            if path == "/api/approvals":
                return self._send_json({"items": RUNTIME.approvals.visible()})
            return self._send_json({"error": "not found"}, 404)
        except Exception as exc:
            return self._send_json({"error": str(exc)[:500]}, 500)

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._need_auth():
            return
        body = self._body()
        try:
            if path == "/api/chat":
                return self._send_json(RUNTIME.chat(body.get("message", ""), bool(body.get("approve_task"))))
            if path == "/api/approvals":
                ok = RUNTIME.approvals.decide(body.get("id", ""), bool(body.get("allow")))
                return self._send_json({"ok": ok}, 200 if ok else 404)
            if path == "/api/settings":
                return self._send_json(RUNTIME.update_settings(body))
            if path == "/api/providers":
                return self._send_json({"providers": RUNTIME.providers_update(body)})
            if path == "/api/personalization":
                current = load_personalization()
                if "archetype" in body and body.get("apply_preset"):
                    current = apply_archetype(body["archetype"], current)
                    current.update({k: v for k, v in body.items() if k != "apply_preset"})
                    value = save_personalization(current)
                else:
                    value = save_personalization({**current, **body})
                return self._send_json({"value": value, "catalog": personalization_catalog()})
            if path == "/api/skills":
                current = load_skills()
                for key, value in body.items():
                    if key in SKILL_CATALOG:
                        current[key] = bool(value)
                current = save_skills(current)
                items = [
                    {"id": k, "label": meta["label"], "description": meta["description"], "enabled": bool(current[k])}
                    for k, meta in SKILL_CATALOG.items()
                ]
                return self._send_json({"items": items})
            if path == "/api/update/core":
                RUNTIME.start_core_update()
                return self._send_json({"ok": True, "job": RUNTIME.job_status("core")})
            if path == "/api/update/dependencies":
                RUNTIME.start_dependency_update()
                return self._send_json({"ok": True, "job": RUNTIME.job_status("deps")})
            return self._send_json({"error": "not found"}, 404)
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, 400)
        except Exception as exc:
            return self._send_json({"error": str(exc)[:500]}, 500)


def _replace_old_server():
    try:
        old = int(PID_PATH.read_text(encoding="utf-8").strip())
    except Exception:
        old = 0
    if old and old != os.getpid():
        try:
            os.kill(old, signal.SIGTERM)
            for _ in range(20):
                time.sleep(0.08)
                try:
                    os.kill(old, 0)
                except ProcessLookupError:
                    break
        except Exception:
            pass


def serve(token: str, replace: bool = False):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    if replace:
        _replace_old_server()
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    os.chmod(PID_PATH, 0o600)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.hub_token = token
    try:
        server.serve_forever(poll_interval=0.4)
    finally:
        server.server_close()
        try:
            if PID_PATH.exists() and PID_PATH.read_text().strip() == str(os.getpid()):
                PID_PATH.unlink()
        except Exception:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog="furinahub")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("serve")
    p.add_argument("--token", default="")
    p.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    if args.command != "serve":
        parser.print_help()
        return 2
    token = str(args.token or "").strip() or secrets.token_urlsafe(32)
    if not args.token:
        print(f"FurinaHub UI: http://{HOST}:{PORT}/?token={token}", flush=True)
    serve(token, args.replace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
