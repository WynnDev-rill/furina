#!/usr/bin/env python3
"""Final private-build policy: chat-only Hub, separated histories, bounded data."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"

version = CORE / "version.py"
text = version.read_text(encoding="utf-8")
if 'VERSION = "1.1.9"' not in text:
    raise SystemExit("expected Core 1.1.9")
version.write_text(text.replace('VERSION = "1.1.9"', 'VERSION = "1.1.11"', 1), encoding="utf-8")

# The process conversation created by Termux is deliberately marked separate.
# Durable memory, relationship, personality and selected model remain shared.
memory = CORE / "memory.py"
with memory.open("a", encoding="utf-8") as out:
    out.write(r'''

# FURINA_FINAL_112_CONVERSATION_BOUNDARY
_furina_112_original_init_db = MemoryStore._init_db
def _furina_112_init_db(self, _original=_furina_112_original_init_db):
    _original(self)
    conn = self._conn()
    self._ensure_column(conn, "conversations", "surface", "TEXT NOT NULL DEFAULT 'hub'")
    conn.execute("UPDATE conversations SET surface='hub' WHERE surface IS NULL OR surface NOT IN ('hub','termux')")
    conn.commit()

def _furina_112_create_session(self, title="Percakapan baru"):
    now = time.time(); clean = re.sub(r"\s+", " ", str(title or "")).strip()[:80] or "Percakapan baru"
    cur = self._conn().execute("INSERT INTO conversations(title,created_at,updated_at,surface) VALUES(?,?,?,?)", (clean, now, now, "termux"))
    self._conn().commit(); self._conversation_override = int(cur.lastrowid); return self._conversation_override

def _furina_112_list(self, limit=60):
    active = self.active_conversation_id()
    rows = self._conn().execute("""SELECT c.id,c.title,c.created_at,c.updated_at,count(m.id) AS message_count
      FROM conversations c LEFT JOIN messages m ON m.conversation_id=c.id WHERE c.surface='hub'
      GROUP BY c.id ORDER BY c.updated_at DESC,c.id DESC LIMIT ?""", (max(1, min(int(limit), 100)),)).fetchall()
    return [{**dict(row), "active": int(row["id"]) == active} for row in rows]

def _furina_112_create_hub(self, title="Percakapan baru"):
    now = time.time(); clean = re.sub(r"\s+", " ", str(title or "")).strip()[:80] or "Percakapan baru"
    cur = self._conn().execute("INSERT INTO conversations(title,created_at,updated_at,surface) VALUES(?,?,?,?)", (clean, now, now, "hub"))
    value = int(cur.lastrowid)
    self._conn().execute("INSERT INTO kv(key,value) VALUES('active_conversation_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(value),))
    self._conn().commit(); return value

def _furina_112_switch_hub(self, conversation_id):
    value = int(conversation_id)
    if not self._conn().execute("SELECT 1 FROM conversations WHERE id=? AND surface='hub'", (value,)).fetchone():
        raise ValueError("percakapan Hub tidak ditemukan")
    self._conn().execute("INSERT INTO kv(key,value) VALUES('active_conversation_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(value),))
    self._conn().commit(); return value

def _furina_112_prune(self):
    # Keep history useful but bounded: 1,000 messages per surface conversation,
    # 180 Hub threads and media only while referenced by an image message.
    conn = self._conn()
    for row in conn.execute("SELECT id FROM conversations").fetchall():
        cid = int(row[0]); conn.execute("DELETE FROM messages WHERE id IN (SELECT id FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT -1 OFFSET 1000)", (cid,))
    old = conn.execute("SELECT id FROM conversations WHERE surface='hub' ORDER BY updated_at DESC,id DESC LIMIT -1 OFFSET 180").fetchall()
    for row in old:
        conn.execute("DELETE FROM messages WHERE conversation_id=?", (int(row[0]),)); conn.execute("DELETE FROM conversations WHERE id=?", (int(row[0]),))
    conn.commit()

_furina_112_add_message = MemoryStore.add_message
def _furina_112_add_message_bounded(self, *args, **kwargs):
    value = _furina_112_add_message(self, *args, **kwargs); _furina_112_prune(self); return value

MemoryStore._init_db = _furina_112_init_db
MemoryStore.create_session_conversation = _furina_112_create_session
MemoryStore.list_conversations = _furina_112_list
MemoryStore.create_conversation = _furina_112_create_hub
MemoryStore.switch_conversation = _furina_112_switch_hub
MemoryStore.add_message = _furina_112_add_message_bounded
''')

hub = CORE / "hub.py"
text = hub.read_text(encoding="utf-8")
text = text.replace('EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r59"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r61"', 1)
text = text.replace('furina-2026.08.25-private-1.1.9', 'furina-2026.08.25-private-1.1.11')
# Remove all HTTP surfaces that can invoke the retired Android agent or APK/Core updater.
for block in (
    '            if path == "/api/update/status":\n                self._json(RUNTIME.get_update_status()); return\n',
    '            if path.startswith("/api/agent/jobs/"):\n                self._json(RUNTIME.public_job(path.rsplit("/", 1)[-1])); return\n',
    '            if path == "/api/device/probe":\n                self._json(RUNTIME.probe_device_mode(body)); return\n',
    '            if path == "/api/update/core":\n                self._json(RUNTIME.start_core_update()); return\n',
    '            if path.startswith("/api/agent/jobs/") and path.endswith("/decision"):\n                job_id = path.split("/")[-2]\n                self._json(RUNTIME.decide_job(job_id, bool(body.get("allow")))); return\n',
):
    if block not in text: raise SystemExit(f"hub route marker missing: {block[:35]}")
    text = text.replace(block, '', 1)
with hub.open("w", encoding="utf-8") as out:
    out.write(text)
    out.write(r'''

# FURINA_FINAL_112_CHAT_ONLY
class _FurinaChatCancelled(Exception): pass
_furina_112_old_chat = Runtime.chat
def _furina_112_chat(self, text, image=None, plugins=None, request_id="", on_token=None):
    # Image handling stays in the vetted visual path; regular requests never
    # classify into device actions or invoke privileged control.
    if image is not None:
        return _furina_112_old_chat(self, text, image, None, request_id, on_token)
    text = str(text or "").strip()
    if not text: raise ValueError("pesan kosong")
    if len(text) > 12000: raise ValueError("pesan terlalu panjang")
    active = self.store.active_conversation_id(); conn = self.store._conn()
    before = int(conn.execute("SELECT COALESCE(MAX(id),0) FROM messages WHERE conversation_id=?", (active,)).fetchone()[0])
    self._set_progress(request_id, "compose", "Menyusun jawaban")
    answer = self.session.chat.respond(text, on_token=on_token)
    rows = conn.execute("SELECT id,role FROM messages WHERE conversation_id=? AND id>? ORDER BY id", (active, before)).fetchall()
    user_id = next((int(row["id"]) for row in rows if row["role"] == "user"), 0)
    assistant_id = next((int(row["id"]) for row in reversed(rows) if row["role"] == "assistant"), 0)
    self._queue_auto_title(active, text, answer); self._set_progress(request_id, "done", "Selesai", done=True)
    return {"mode":"chat", "answer":answer, "request_id":request_id, "user_message_id":user_id, "assistant_message_id":assistant_id}

def _furina_112_start_chat(self, text, image=None, plugins=None, request_id=""):
    rid = re.sub(r"[^a-zA-Z0-9_-]", "", str(request_id or ""))[:80] or ("chat-" + secrets.token_hex(8))
    with self.progress_lock:
        active = getattr(self, "_final_active_chat", "")
        if active and not (self.chat_progress.get(active) or {}).get("done"):
            raise ValueError("Masih ada satu percakapan yang diproses. Hentikan atau tunggu selesai.")
        self._final_active_chat = rid
        self.chat_progress[rid] = {"id":rid,"phase":"queued","label":"Menyiapkan…","events":[],"done":False,"cancelled":False,"error":"","partial":"","result":None,"created_at":time.time(),"updated_at":time.time()}
    def worker():
        pieces=[]
        def emit(piece):
            with self.progress_lock:
                state = self.chat_progress.get(rid) or {}
                if state.get("cancelled"): raise _FurinaChatCancelled()
                pieces.append(str(piece)); state.update({"phase":"stream","label":"Menjawab…","partial":"".join(pieces),"updated_at":time.time()}); self.chat_progress[rid]=state
        try:
            result = self.chat(text, image, None, rid, emit)
            with self.progress_lock:
                state = self.chat_progress.get(rid) or {}
                if not state.get("cancelled"):
                    state.update({"done":True,"phase":"done","label":"Selesai","partial":str(result.get("answer") or state.get("partial") or ""),"result":result,"updated_at":time.time()})
                self.chat_progress[rid]=state
        except _FurinaChatCancelled:
            pass
        except Exception as exc:
            with self.progress_lock:
                state=self.chat_progress.get(rid) or {}; state.update({"done":True,"phase":"error","label":"Gagal","error":str(exc)[:500],"updated_at":time.time()}); self.chat_progress[rid]=state
        finally:
            with self.progress_lock:
                if getattr(self,"_final_active_chat","")==rid: self._final_active_chat=""
    threading.Thread(target=worker,name=f"furinahub-chat-{rid[-12:]}",daemon=True).start()
    return {"accepted":True,"request_id":rid}

def _furina_112_cancel_chat(self, request_id):
    rid = str(request_id or "")
    with self.progress_lock:
        state = self.chat_progress.get(rid)
        if not state: raise ValueError("percakapan tidak ditemukan")
        state.update({"done":True,"cancelled":True,"phase":"cancelled","label":"Dihentikan","error":"","updated_at":time.time()}); self.chat_progress[rid]=state
    return {"request_id":rid,"cancelled":True}
Runtime.chat = _furina_112_chat
Runtime.start_chat = _furina_112_start_chat
Runtime.cancel_chat = _furina_112_cancel_chat
''')

# Add cancellation endpoint after the well-scoped chat start route.
text = hub.read_text(encoding="utf-8")
needle = '            if path == "/api/chat":\n                self._json(RUNTIME.chat(body.get("message", ""), body.get("image"), body.get("plugins"), body.get("request_id", ""))); return\n'
if needle not in text: raise SystemExit("chat endpoint marker missing")
text = text.replace(needle, needle + '            if path == "/api/chat/cancel":\n                self._json(RUNTIME.cancel_chat(body.get("request_id", ""))); return\n', 1)
hub.write_text(text, encoding="utf-8")

# Termux selector fits all 20 traits without a hidden page.
tui = CORE / "tui.py"; text = tui.read_text(encoding="utf-8")
if 'page_size = 16' not in text: raise SystemExit("trait page size marker missing")
tui.write_text(text.replace('page_size = 16', 'page_size = 20', 1), encoding="utf-8")
print("FURINA_FINAL_112_CORE_OK")
