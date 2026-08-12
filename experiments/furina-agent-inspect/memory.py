from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import DATA_DIR, ensure_dirs

DB_PATH = DATA_DIR / "furina.db"


@dataclass
class Memory:
    id: int
    text: str
    kind: str
    importance: float
    created_at: float
    last_used_at: float


class MemoryStore:
    def __init__(self, path: Path = DB_PATH):
        ensure_dirs()
        self.path = path
        self._local = threading.local()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    def _init_db(self) -> None:
        c = sqlite3.connect(self.path)
        c.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              text TEXT NOT NULL UNIQUE,
              kind TEXT NOT NULL DEFAULT 'fact',
              importance REAL NOT NULL DEFAULT 0.5,
              created_at REAL NOT NULL,
              last_used_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              event_type TEXT NOT NULL,
              payload TEXT NOT NULL,
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kv (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            """
        )
        try:
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(text, content='memories', content_rowid='id')")
            c.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                  INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                  INSERT INTO memories_fts(memories_fts, rowid, text) VALUES('delete', old.id, old.text);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                  INSERT INTO memories_fts(memories_fts, rowid, text) VALUES('delete', old.id, old.text);
                  INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text);
                END;
                """
            )
            c.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
        except sqlite3.DatabaseError:
            pass
        c.commit()
        c.close()

    def add_message(self, role: str, content: str) -> int:
        cur = self._conn().execute(
            "INSERT INTO messages(role, content, created_at) VALUES(?,?,?)",
            (role, content, time.time()),
        )
        self._conn().commit()
        return int(cur.lastrowid)

    def recent_messages(self, limit: int = 10) -> list[dict]:
        rows = self._conn().execute(
            "SELECT role,content,created_at FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def add_memory(self, text: str, kind: str = "fact", importance: float = 0.5) -> None:
        text = re.sub(r"\s+", " ", text.strip())[:500]
        if len(text) < 4:
            return
        now = time.time()
        self._conn().execute(
            """INSERT INTO memories(text,kind,importance,created_at,last_used_at)
               VALUES(?,?,?,?,?)
               ON CONFLICT(text) DO UPDATE SET
                 importance=max(memories.importance, excluded.importance),
                 last_used_at=excluded.last_used_at""",
            (text, kind[:32], max(0.0, min(1.0, importance)), now, now),
        )
        self._conn().commit()

    @staticmethod
    def _fts_query(text: str) -> str:
        words = re.findall(r"[\wÀ-ÿ]{3,}", text.lower(), flags=re.UNICODE)
        unique = []
        for w in words:
            if w not in unique:
                unique.append(w)
        return " OR ".join(f'"{w}"' for w in unique[:10])

    def search(self, query: str, limit: int = 6) -> list[Memory]:
        conn = self._conn()
        rows = []
        fts = self._fts_query(query)
        if fts:
            try:
                rows = conn.execute(
                    """SELECT m.* FROM memories_fts f
                       JOIN memories m ON m.id=f.rowid
                       WHERE memories_fts MATCH ?
                       ORDER BY bm25(memories_fts), m.importance DESC
                       LIMIT ?""",
                    (fts, limit),
                ).fetchall()
            except sqlite3.DatabaseError:
                rows = []
        if len(rows) < limit:
            words = re.findall(r"[\wÀ-ÿ]{3,}", query.lower(), flags=re.UNICODE)[:5]
            if words:
                clauses = " OR ".join("lower(text) LIKE ?" for _ in words)
                params = [f"%{w}%" for w in words] + [limit]
                extra = conn.execute(
                    f"SELECT * FROM memories WHERE {clauses} ORDER BY importance DESC,last_used_at DESC LIMIT ?",
                    params,
                ).fetchall()
                seen = {r["id"] for r in rows}
                rows += [r for r in extra if r["id"] not in seen]
        rows = rows[:limit]
        now = time.time()
        if rows:
            conn.executemany("UPDATE memories SET last_used_at=? WHERE id=?", [(now, r["id"]) for r in rows])
            conn.commit()
        return [Memory(**dict(r)) for r in rows]

    def list_memories(self, limit: int = 50) -> list[Memory]:
        rows = self._conn().execute(
            "SELECT * FROM memories ORDER BY importance DESC,last_used_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Memory(**dict(r)) for r in rows]

    def log_event(self, event_type: str, payload: dict) -> None:
        self._conn().execute(
            "INSERT INTO events(event_type,payload,created_at) VALUES(?,?,?)",
            (event_type, json.dumps(payload, ensure_ascii=False), time.time()),
        )
        self._conn().commit()


EXPLICIT_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"\b(?:namaku|nama saya)\s+([^,.!?]{2,60})", re.I), "identity", 0.95),
    (re.compile(r"\b(?:aku|saya)\s+(?:suka|menyukai)\s+([^.!?]{3,120})", re.I), "preference", 0.72),
    (re.compile(r"\b(?:aku|saya)\s+(?:tidak suka|benci)\s+([^.!?]{3,120})", re.I), "preference", 0.76),
    (re.compile(r"\b(?:aku|saya)\s+(?:tinggal|berada)\s+di\s+([^.!?]{2,100})", re.I), "profile", 0.80),
    (re.compile(r"\b(?:aku|saya)\s+(?:ingin|mau|berencana)\s+([^.!?]{4,160})", re.I), "goal", 0.58),
]


def extract_explicit_memories(text: str) -> Iterable[tuple[str, str, float]]:
    for pattern, kind, importance in EXPLICIT_PATTERNS:
        m = pattern.search(text)
        if m:
            yield (m.group(0).strip(), kind, importance)
