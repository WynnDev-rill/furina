#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC50 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"RC50 block marker mismatch: {label}")
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    hub_path = root / "core/furina_agent/hub.py"
    version_path = root / "core/furina_agent/version.py"
    for path in (hub_path, version_path):
        if not path.is_file():
            raise SystemExit(f"RC50 source missing: {path}")

    hub = hub_path.read_text(encoding="utf-8")

    hub = replace_once(
        hub,
        '        self.model_status = {"state": "idle", "message": "Belum ada unduhan model.", "percent": 0}\n        self._connector_wake_at = 0.0\n        self._rebuild()\n',
        '        self.model_status = {"state": "idle", "message": "Belum ada unduhan model.", "percent": 0}\n        self.chat_progress: dict[str, dict] = {}\n        self.progress_lock = threading.RLock()\n        self._connector_wake_at = 0.0\n        self._rebuild()\n        self._ensure_conversation_schema()\n',
        "runtime state",
    )

    helper_methods = r'''    def _ensure_conversation_schema(self) -> None:
        conn = self.store._conn()
        cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(conversations)").fetchall()}
        if "pinned" not in cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
        if "title_locked" not in cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN title_locked INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    @staticmethod
    def _fallback_title(text: str) -> str:
        clean = re.sub(r"\[(?:Gambar|Image|File):[^\]]+\]", " ", str(text or ""), flags=re.I)
        clean = re.sub(r"https?://\S+", " ", clean)
        clean = " ".join(clean.replace("\n", " ").split()).strip(" .,:;!?-_\"'()[]{}")
        if not clean or re.fullmatch(r"(?i)(hi|hai|halo|hello|hey|tes|test|hmm+|oke|ok)", clean):
            return "Percakapan baru"
        words = clean.split()
        title = " ".join(words[:7])
        if len(title) > 54:
            title = title[:51].rstrip() + "…"
        return title[:1].upper() + title[1:] if title else "Percakapan baru"

    def conversation_list(self) -> list[dict]:
        self._ensure_conversation_schema()
        conn = self.store._conn()
        rows = conn.execute(
            "SELECT id,title,created_at,updated_at,pinned,title_locked FROM conversations "
            "ORDER BY pinned DESC, updated_at DESC, id DESC"
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if not int(item.get("title_locked") or 0) and str(item.get("title") or "").strip().casefold() in {
                "percakapan baru", "percakapan bergambar", "percakapan sebelumnya"
            }:
                first = conn.execute(
                    "SELECT content FROM messages WHERE conversation_id=? AND role='user' ORDER BY id ASC LIMIT 1",
                    (int(item["id"]),),
                ).fetchone()
                if first:
                    candidate = self._fallback_title(str(first[0] or ""))
                    if candidate != "Percakapan baru":
                        conn.execute("UPDATE conversations SET title=? WHERE id=?", (candidate, int(item["id"])))
                        item["title"] = candidate
            item["pinned"] = bool(item.get("pinned"))
            item.pop("title_locked", None)
            result.append(item)
        conn.commit()
        return result

    def _set_progress(self, request_id: str, phase: str, label: str, *, done: bool = False, error: str = "") -> None:
        rid = re.sub(r"[^a-zA-Z0-9_-]", "", str(request_id or ""))[:80]
        if not rid:
            return
        now = time.time()
        with self.progress_lock:
            current = dict(self.chat_progress.get(rid) or {"id": rid, "created_at": now, "events": []})
            events = list(current.get("events") or [])
            if not events or events[-1].get("phase") != phase:
                events.append({"phase": phase, "label": str(label)[:120], "at": now})
            current.update({
                "phase": phase,
                "label": str(label)[:120],
                "events": events[-8:],
                "done": bool(done),
                "error": str(error or "")[:220],
                "updated_at": now,
            })
            self.chat_progress[rid] = current
            cutoff = now - 300
            for key in list(self.chat_progress):
                if float(self.chat_progress[key].get("updated_at") or now) < cutoff:
                    self.chat_progress.pop(key, None)

    def get_chat_progress(self, request_id: str) -> dict:
        rid = re.sub(r"[^a-zA-Z0-9_-]", "", str(request_id or ""))[:80]
        with self.progress_lock:
            return dict(self.chat_progress.get(rid) or {
                "id": rid, "phase": "waiting", "label": "Menyiapkan…", "events": [], "done": False, "error": ""
            })

    def _queue_auto_title(self, conversation_id: int, user_text: str, assistant_text: str) -> None:
        user_text = " ".join(str(user_text or "").split())[:1200]
        assistant_text = " ".join(str(assistant_text or "").split())[:1200]
        fallback = self._fallback_title(user_text)

        def worker():
            try:
                conn = self.store._conn()
                self._ensure_conversation_schema()
                row = conn.execute("SELECT title_locked FROM conversations WHERE id=?", (int(conversation_id),)).fetchone()
                if not row or int(row[0] or 0):
                    return
                title = fallback
                if user_text:
                    with self.lock:
                        raw = self.session.llm.chat([
                            {"role": "system", "content": "Buat judul percakapan sangat singkat dalam bahasa pengguna. Gunakan 3-7 kata, tanpa tanda kutip, tanpa titik akhir, jangan memakai kata 'Percakapan baru'. Tangkap topik atau tujuan utama. Jawab judul saja."},
                            {"role": "user", "content": f"User: {user_text}\nAssistant: {assistant_text}\nJudul:"},
                        ], max_tokens=48, temperature=0.2, role="conversation_title")
                    candidate = " ".join(str(raw or "").replace("\n", " ").split()).strip(" \"'`.-:;!?")
                    candidate = re.sub(r"^(judul|title)\s*:\s*", "", candidate, flags=re.I)
                    if candidate and len(candidate) <= 72 and candidate.casefold() != "percakapan baru":
                        title = candidate
                if title and title != "Percakapan baru":
                    conn.execute(
                        "UPDATE conversations SET title=? WHERE id=? AND COALESCE(title_locked,0)=0",
                        (title[:72], int(conversation_id)),
                    )
                    conn.commit()
            except Exception:
                if fallback != "Percakapan baru":
                    try:
                        conn = self.store._conn()
                        conn.execute(
                            "UPDATE conversations SET title=? WHERE id=? AND COALESCE(title_locked,0)=0",
                            (fallback[:72], int(conversation_id)),
                        )
                        conn.commit()
                    except Exception:
                        pass

        threading.Thread(target=worker, name="furinahub-title", daemon=True).start()
'''
    hub = replace_once(
        hub,
        "    def rebuild(self):\n        self._rebuild()\n\n",
        "    def rebuild(self):\n        self._rebuild()\n        self._ensure_conversation_schema()\n\n" + helper_methods + "\n",
        "conversation/progress helpers",
    )

    hub = hub.replace('"bridge_target": "1.0.0-rc32"', '"bridge_target": "1.0.0-rc34"')
    if '"bridge_target": "1.0.0-rc34"' not in hub:
        raise SystemExit("RC50 bridge target marker missing")

    hub = replace_once(
        hub,
        '            "conversations": self.store.list_conversations(),\n',
        '            "conversations": self.conversation_list(),\n',
        "bootstrap conversation list",
    )

    old_change = '''    def change_conversation(self, payload: dict) -> dict:
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
'''
    new_change = '''    def change_conversation(self, payload: dict) -> dict:
        action = str(payload.get("action") or "list").strip().lower()
        self._ensure_conversation_schema()
        if action == "create":
            self.store.create_conversation(str(payload.get("title") or "Percakapan baru"))
        elif action == "switch":
            self.store.switch_conversation(int(payload.get("id") or 0))
        elif action == "delete":
            self.store.delete_conversation(int(payload.get("id") or 0))
        elif action == "rename":
            conversation_id = int(payload.get("id") or 0)
            title = " ".join(str(payload.get("title") or "").split()).strip()[:72]
            if not title:
                raise ValueError("judul percakapan tidak boleh kosong")
            cur = self.store._conn().execute(
                "UPDATE conversations SET title=?, title_locked=1, updated_at=datetime('now') WHERE id=?",
                (title, conversation_id),
            )
            self.store._conn().commit()
            if not cur.rowcount:
                raise ValueError("percakapan tidak ditemukan")
        elif action == "pin":
            conversation_id = int(payload.get("id") or 0)
            pinned = 1 if bool(payload.get("pinned")) else 0
            cur = self.store._conn().execute("UPDATE conversations SET pinned=? WHERE id=?", (pinned, conversation_id))
            self.store._conn().commit()
            if not cur.rowcount:
                raise ValueError("percakapan tidak ditemukan")
        elif action != "list":
            raise ValueError("aksi percakapan tidak valid")
        return self.bootstrap()
'''
    hub = replace_once(hub, old_change, new_change, "conversation actions")

    new_chat = r'''    def chat(self, text: str, image: dict | None = None, plugins: list | None = None, request_id: str = "") -> dict:
        text = str(text or "").strip()
        if not text and not image:
            raise ValueError("pesan kosong")
        if len(text) > 12000:
            raise ValueError("pesan terlalu panjang")
        request_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(request_id or ""))[:80]
        self._set_progress(request_id, "context", "Membaca konteks percakapan")
        with self.lock:
            plugin_ids = [str(item) for item in (plugins or []) if str(item).strip()]
            if plugin_ids and not image:
                self._set_progress(request_id, "tool", "Menyiapkan alat yang diperlukan")
                result = self._chat_with_plugins(text, plugin_ids)
                self._set_progress(request_id, "done", "Selesai", done=True)
                return result
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
                prompt = text or "Apa yang kamu lihat di gambar ini?"
                self._set_progress(request_id, "vision", "Menganalisis gambar")
                vision_prompt = (
                    "Buat CATATAN VISUAL faktual untuk model companion, bukan jawaban final kepada pengguna. "
                    "Identifikasi objek, teks yang benar-benar terbaca, hubungan spasial, suasana, dan detail yang relevan dengan pertanyaan. "
                    "Tandai ketidakpastian secara eksplisit. Jangan mengarang nama orang, tempat, aplikasi, gim, atau tulisan. "
                    "Tulis ringkas dalam bahasa Indonesia.\n\n"
                    f"Pertanyaan pengguna: {prompt}"
                )
                visual_facts = self.session.llm.vision(
                    vision_prompt, encoded, mime=mime,
                    max_tokens=min(900, int(self.cfg.max_tokens)), json_mode=False,
                )
                common_en = len(re.findall(r"\b(the|this|image|shows|with|and|appears|screen|game)\b", visual_facts.lower()))
                common_id = len(re.findall(r"\b(gambar|ini|dengan|dan|terlihat|menampilkan|layar)\b", visual_facts.lower()))
                if common_en >= 3 and common_en > common_id:
                    visual_facts = self.session.llm.chat([
                        {"role": "system", "content": "Terjemahkan catatan visual ini ke bahasa Indonesia yang alami. Pertahankan ketidakpastian dan jangan menambah fakta. Jawab hanya hasil terjemahan."},
                        {"role": "user", "content": visual_facts},
                    ], max_tokens=min(900, int(self.cfg.max_tokens)), temperature=0.1, role="vision_translation")

                ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime]
                media_id = secrets.token_hex(16)
                CHAT_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                target = CHAT_MEDIA_DIR / (media_id + ext)
                temp = CHAT_MEDIA_DIR / (media_id + ext + ".part")
                temp.write_bytes(raw)
                os.chmod(temp, 0o600)
                os.replace(temp, target)
                attachment = {"kind": "image", "id": media_id, "name": name, "mime": mime, "size": len(raw)}

                active = self.store.active_conversation_id()
                conn = self.store._conn()
                before = conn.execute(
                    "SELECT COALESCE(MAX(id),0) FROM messages WHERE conversation_id=?", (active,)
                ).fetchone()[0]
                self._set_progress(request_id, "compose", "Menyusun jawaban sesuai personalisasi")
                companion_input = (
                    f"{prompt}\n\n"
                    "[Konteks visual internal — gunakan sebagai pengamatanmu sendiri, jangan menyebut bahwa ini laporan model vision]\n"
                    f"{visual_facts}\n"
                    "[Akhir konteks visual]\n\n"
                    "Jawab pertanyaan pengguna secara natural sebagai dirimu sendiri. Pertahankan persona, hubungan, memori, "
                    "gaya bahasa, dan personalisasi yang biasa dipakai dalam percakapan. Jangan berubah menjadi laporan deskripsi gambar "
                    "kecuali pengguna memang meminta deskripsi rinci."
                )
                answer = self.session.chat.respond(companion_input)
                user_row = conn.execute(
                    "SELECT id FROM messages WHERE conversation_id=? AND id>? AND role='user' ORDER BY id DESC LIMIT 1",
                    (active, int(before)),
                ).fetchone()
                if user_row:
                    conn.execute(
                        "UPDATE messages SET content=?, attachment_json=? WHERE id=?",
                        (prompt, json.dumps(attachment, ensure_ascii=False), int(user_row[0])),
                    )
                    conn.commit()
                self._set_progress(request_id, "finalize", "Memeriksa jawaban")
                self._queue_auto_title(active, prompt, answer)
                self._set_progress(request_id, "done", "Selesai", done=True)
                return {"mode": "chat", "answer": answer, "request_id": request_id}

            intent = self.session.classify(text)
            if intent.mode == "chat":
                active = self.store.active_conversation_id()
                self._set_progress(request_id, "compose", "Menyusun jawaban")
                answer = self.session.chat.respond(text)
                self._set_progress(request_id, "finalize", "Memeriksa jawaban")
                self._queue_auto_title(active, text, answer)
                self._set_progress(request_id, "done", "Selesai", done=True)
                return {"mode": "chat", "answer": answer, "request_id": request_id}
            self._set_progress(request_id, "action", "Menyiapkan tindakan perangkat")
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
            self._set_progress(request_id, "done", "Menunggu persetujuan tindakan", done=True)
            return {"mode": "device", "job": self.public_job(job_id), "request_id": request_id}
'''
    hub = replace_block(hub, "    def chat(self, text: str, image: dict | None = None, plugins: list | None = None) -> dict:\n", "    def public_job(self, job_id: str) -> dict:\n", new_chat, "chat pipeline")

    hub = replace_once(
        hub,
        '            if path == "/api/update/status":\n                self._json(RUNTIME.get_update_status()); return\n',
        '            if path == "/api/update/status":\n                self._json(RUNTIME.get_update_status()); return\n            if path.startswith("/api/chat/progress/"):\n                self._json(RUNTIME.get_chat_progress(path.rsplit("/", 1)[-1])); return\n',
        "progress GET endpoint",
    )
    hub = replace_once(
        hub,
        '            if path == "/api/chat":\n                self._json(RUNTIME.chat(body.get("message", ""), body.get("image"), body.get("plugins"))); return\n',
        '            if path == "/api/chat":\n                self._json(RUNTIME.chat(body.get("message", ""), body.get("image"), body.get("plugins"), body.get("request_id", ""))); return\n',
        "progress POST binding",
    )

    hub_path.write_text(hub, encoding="utf-8")

    version = version_path.read_text(encoding="utf-8")
    version = replace_once(version, 'VERSION = "1.0.0-rc49"', 'VERSION = "1.0.0-rc50"', "Core version")
    version_path.write_text(version, encoding="utf-8")

    checks = (
        'VERSION = "1.0.0-rc50"',
        'def conversation_list(',
        'title_locked',
        'def _queue_auto_title(',
        'role="conversation_title"',
        'def get_chat_progress(',
        '/api/chat/progress/',
        'Menganalisis gambar',
        'Menyusun jawaban sesuai personalisasi',
        'self.session.chat.respond(companion_input)',
        'attachment_json',
        '"bridge_target": "1.0.0-rc34"',
    )
    combined = hub + "\n" + version
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"RC50 marker hilang: {missing}")
    print("FURINAHUB_CORE_RC50_COMPANION_UX_OK")


if __name__ == "__main__":
    main()
