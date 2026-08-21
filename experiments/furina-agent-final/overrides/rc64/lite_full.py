from __future__ import annotations

"""Shared product layer for Furina Lite (Termux) and FurinaHub Full.

This module deliberately contains no UI code.  Both surfaces call the same
small service instead of keeping their own copies of focus, profile, or memory
review state.  The database remains local to the user's Furina installation.
"""

import json
import re
import time
import zipfile
from pathlib import Path

from .config import CONFIG_PATH, DATA_DIR, HOME, load_config, save_config


PROFILES = {
    "fast": {"label": "Cepat", "routing_mode": "auto", "max_tokens": 768, "temperature": 0.60},
    "natural": {"label": "Natural", "routing_mode": "auto", "max_tokens": 1536, "temperature": 0.72},
    "deep": {"label": "Mendalam", "routing_mode": "online", "max_tokens": 3072, "temperature": 0.70},
    "private": {"label": "Privat / Lokal", "routing_mode": "local", "max_tokens": 1536, "temperature": 0.66},
}


class ProductWorkspace:
    def __init__(self, store):
        self.store = store
        self.ensure_schema()

    def ensure_schema(self) -> None:
        conn = self.store._conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS furina_focus_items (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              text TEXT NOT NULL,
              due_at REAL NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'active',
              source TEXT NOT NULL DEFAULT 'manual',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS furina_focus_status_due
              ON furina_focus_items(status, due_at, updated_at DESC);
            CREATE TABLE IF NOT EXISTS furina_memory_inbox (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              text TEXT NOT NULL,
              source_ref TEXT NOT NULL DEFAULT '',
              state TEXT NOT NULL DEFAULT 'pending',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS furina_memory_inbox_state
              ON furina_memory_inbox(state, updated_at DESC);
            """
        )
        conn.commit()

    @staticmethod
    def _text(value: object, *, low: int = 3, high: int = 600) -> str:
        text = " ".join(str(value or "").split())
        if not low <= len(text) <= high:
            raise ValueError(f"teks harus {low}–{high} karakter")
        return text

    @staticmethod
    def _parse_due(value: object) -> float:
        raw = str(value or "").strip()
        if not raw:
            return 0.0
        try:
            import dateparser
            parsed = dateparser.parse(raw, languages=["id", "en"], settings={"RETURN_AS_TIMEZONE_AWARE": False})
            if parsed:
                return float(parsed.timestamp())
        except Exception:
            pass
        # The dateparser dependency is installed by the shared runtime.  Keep a
        # tiny deterministic fallback for the most common Indonesian commands
        # so Focus still works during recovery or a partially repaired setup.
        now = time.time(); folded = raw.casefold()
        if folded in {"besok", "besok pagi", "besok siang", "besok sore", "besok malam"}:
            hour = {"besok pagi": 8, "besok siang": 12, "besok sore": 16, "besok malam": 20}.get(folded, 9)
            base = time.localtime(now + 86400)
            return time.mktime((base.tm_year, base.tm_mon, base.tm_mday, hour, 0, 0, base.tm_wday, base.tm_yday, base.tm_isdst))
        match = re.fullmatch(r"dalam\s+(\d{1,4})\s*(menit|jam|hari|minggu)", folded)
        if match:
            amount = int(match.group(1)); unit = match.group(2)
            return now + amount * {"menit": 60, "jam": 3600, "hari": 86400, "minggu": 604800}[unit]
        raise ValueError("waktu belum dipahami; coba misalnya ‘besok sore’ atau ‘24 Agustus 19:00’")

    def profile(self) -> dict:
        cfg = load_config()
        current = str(self.store.get_state("furina_response_profile", "natural") or "natural")
        if current not in PROFILES:
            current = "natural"
        return {"current": current, "profiles": [{"id": key, "label": item["label"]} for key, item in PROFILES.items()], "routing_mode": cfg.routing_mode}

    def set_profile(self, profile: object) -> dict:
        key = str(profile or "").strip().lower()
        if key not in PROFILES:
            raise ValueError("profil respons tidak valid")
        option = PROFILES[key]
        cfg = load_config()
        cfg.routing_mode = option["routing_mode"]
        cfg.max_tokens = option["max_tokens"]
        cfg.temperature = option["temperature"]
        save_config(cfg)
        self.store.set_state("furina_response_profile", key)
        return self.profile()

    def focus_list(self, *, include_done: bool = False) -> list[dict]:
        self.ensure_schema()
        where = "" if include_done else "WHERE status='active'"
        rows = self.store._conn().execute(
            f"SELECT id,text,due_at,status,source,created_at,updated_at FROM furina_focus_items {where} "
            "ORDER BY CASE WHEN due_at>0 THEN 0 ELSE 1 END, due_at ASC, updated_at DESC LIMIT 80"
        ).fetchall()
        return [dict(row) for row in rows]

    def change_focus(self, payload: dict) -> dict:
        action = str(payload.get("action") or "").strip().lower()
        conn = self.store._conn(); now = time.time()
        if action == "add":
            text = self._text(payload.get("text"), low=3, high=480)
            due_at = self._parse_due(payload.get("when"))
            conn.execute("INSERT INTO furina_focus_items(text,due_at,status,source,created_at,updated_at) VALUES(?,?, 'active', ?, ?, ?)", (text, due_at, str(payload.get("source") or "manual")[:48], now, now))
        elif action in {"done", "snooze", "cancel", "reopen"}:
            item_id = int(payload.get("id") or 0)
            if action == "snooze":
                due_at = self._parse_due(payload.get("when"))
                cur = conn.execute("UPDATE furina_focus_items SET due_at=?,status='active',updated_at=? WHERE id=?", (due_at, now, item_id))
            else:
                status = {"done": "done", "cancel": "cancelled", "reopen": "active"}[action]
                cur = conn.execute("UPDATE furina_focus_items SET status=?,updated_at=? WHERE id=?", (status, now, item_id))
            if not cur.rowcount:
                raise ValueError("item Fokus tidak ditemukan")
        else:
            raise ValueError("aksi Fokus tidak valid")
        conn.commit()
        return self.snapshot()

    def inbox_list(self) -> list[dict]:
        self.ensure_schema()
        rows = self.store._conn().execute("SELECT id,text,source_ref,state,created_at,updated_at FROM furina_memory_inbox WHERE state='pending' ORDER BY updated_at DESC LIMIT 40").fetchall()
        return [dict(row) for row in rows]

    def propose_memory(self, text: object, source_ref: object = "") -> dict:
        clean = self._text(text, low=4, high=600); now = time.time()
        self.store._conn().execute("INSERT INTO furina_memory_inbox(text,source_ref,state,created_at,updated_at) VALUES(?,?, 'pending',?,?)", (clean, str(source_ref or "")[:160], now, now))
        self.store._conn().commit()
        return self.snapshot()

    def decide_memory(self, inbox_id: object, action: object, edited_text: object = "") -> dict:
        state = str(action or "").strip().lower()
        if state not in {"accept", "reject"}:
            raise ValueError("keputusan memori tidak valid")
        conn = self.store._conn(); row = conn.execute("SELECT text FROM furina_memory_inbox WHERE id=? AND state='pending'", (int(inbox_id or 0),)).fetchone()
        if not row:
            raise ValueError("usulan memori tidak ditemukan")
        text = self._text(edited_text or row[0], low=4, high=600)
        if state == "accept":
            self.store.add_memory(text, kind="user_note", importance=0.78, confidence=0.92, source="memory_inbox")
        conn.execute("UPDATE furina_memory_inbox SET state=?,updated_at=? WHERE id=?", ("accepted" if state == "accept" else "rejected", time.time(), int(inbox_id)))
        conn.commit()
        return self.snapshot()

    def create_backup(self) -> dict:
        """Create a local export without copying provider secrets or model files."""
        backups = HOME / "backups"; backups.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = backups / f"furina-export-{stamp}.zip"
        report = {
            "schema": 1,
            "created_at": time.time(),
            "includes": ["memory database", "non-secret configuration"],
            "excludes": ["API keys", "provider secrets", "local models", "logs"],
        }
        cfg = {}
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        for key in ("bridge_token",):
            cfg.pop(key, None)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            if self.store.path.exists():
                archive.write(self.store.path, "furina.db")
            archive.writestr("config.json", json.dumps(cfg, ensure_ascii=False, indent=2))
            archive.writestr("manifest.json", json.dumps(report, ensure_ascii=False, indent=2))
        try:
            target.chmod(0o600)
        except OSError:
            pass
        return {"path": str(target), "name": target.name, "bytes": target.stat().st_size, "notice": "Ekspor lokal dibuat tanpa API key, provider secret, model, atau log."}

    def snapshot(self) -> dict:
        return {"profile": self.profile(), "focus": self.focus_list(), "memory_inbox": self.inbox_list()}
