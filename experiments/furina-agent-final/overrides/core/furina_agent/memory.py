from __future__ import annotations

import json
import math
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
    confidence: float = 0.65
    strength: float = 0.5
    emotion: float = 0.3
    activations: int = 0
    updated_at: float = 0.0
    source: str = "conversation"


@dataclass
class Belief:
    id: int
    dimension: str
    value: str
    confidence: float
    evidence: int
    source: str
    contradicted: int
    created_at: float
    updated_at: float


@dataclass
class Episode:
    id: int
    summary: str
    themes: str
    importance: float
    emotion: float
    created_at: float
    last_used_at: float
    activations: int


class MemoryStore:
    """Local-first layered memory for the companion.

    The old memories/messages tables stay compatible. RC5 adds structured
    beliefs, episodic memories, relationship state, confidence, reinforcement,
    decay and reranking without requiring a vector database or cloud service.
    """

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
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return conn

    @staticmethod
    def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
        return {str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    @classmethod
    def _ensure_column(cls, conn: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
        if name not in cls._column_names(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

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
            CREATE TABLE IF NOT EXISTS beliefs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              dimension TEXT NOT NULL,
              value TEXT NOT NULL,
              confidence REAL NOT NULL DEFAULT 0.55,
              evidence INTEGER NOT NULL DEFAULT 1,
              source TEXT NOT NULL DEFAULT 'conversation',
              contradicted INTEGER NOT NULL DEFAULT 0,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS beliefs_dimension_idx ON beliefs(dimension, contradicted, confidence);
            CREATE TABLE IF NOT EXISTS episodes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              summary TEXT NOT NULL,
              themes TEXT NOT NULL DEFAULT '',
              importance REAL NOT NULL DEFAULT 0.5,
              emotion REAL NOT NULL DEFAULT 0.3,
              created_at REAL NOT NULL,
              last_used_at REAL NOT NULL,
              activations INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS episodes_time_idx ON episodes(created_at DESC);
            CREATE TABLE IF NOT EXISTS response_routes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              profile TEXT NOT NULL,
              context_key TEXT NOT NULL,
              outcome TEXT,
              created_at REAL NOT NULL
            );
            """
        )
        for name, ddl in (
            ("confidence", "REAL NOT NULL DEFAULT 0.65"),
            ("strength", "REAL NOT NULL DEFAULT 0.5"),
            ("emotion", "REAL NOT NULL DEFAULT 0.3"),
            ("activations", "INTEGER NOT NULL DEFAULT 0"),
            ("updated_at", "REAL NOT NULL DEFAULT 0"),
            ("source", "TEXT NOT NULL DEFAULT 'conversation'"),
        ):
            self._ensure_column(c, "memories", name, ddl)
        c.execute("UPDATE memories SET updated_at=created_at WHERE updated_at IS NULL OR updated_at<=0")
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
        try:
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(summary, themes, content='episodes', content_rowid='id')")
            c.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
                  INSERT INTO episodes_fts(rowid,summary,themes) VALUES(new.id,new.summary,new.themes);
                END;
                CREATE TRIGGER IF NOT EXISTS episodes_ad AFTER DELETE ON episodes BEGIN
                  INSERT INTO episodes_fts(episodes_fts,rowid,summary,themes) VALUES('delete',old.id,old.summary,old.themes);
                END;
                CREATE TRIGGER IF NOT EXISTS episodes_au AFTER UPDATE ON episodes BEGIN
                  INSERT INTO episodes_fts(episodes_fts,rowid,summary,themes) VALUES('delete',old.id,old.summary,old.themes);
                  INSERT INTO episodes_fts(rowid,summary,themes) VALUES(new.id,new.summary,new.themes);
                END;
                """
            )
            c.execute("INSERT INTO episodes_fts(episodes_fts) VALUES('rebuild')")
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

    def recent_messages(self, limit: int = 12) -> list[dict]:
        rows = self._conn().execute(
            "SELECT role,content,created_at FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def message_count(self) -> int:
        return int(self._conn().execute("SELECT count(*) FROM messages").fetchone()[0])

    def add_memory(
        self,
        text: str,
        kind: str = "fact",
        importance: float = 0.5,
        *,
        confidence: float = 0.65,
        emotion: float = 0.3,
        source: str = "conversation",
    ) -> None:
        text = re.sub(r"\s+", " ", str(text).strip())[:600]
        if len(text) < 4:
            return
        now = time.time()
        importance = max(0.0, min(1.0, float(importance)))
        confidence = max(0.05, min(0.99, float(confidence)))
        emotion = max(0.0, min(1.0, float(emotion)))
        strength = min(1.0, 0.35 + importance * 0.35 + emotion * 0.15)
        self._conn().execute(
            """INSERT INTO memories(text,kind,importance,created_at,last_used_at,confidence,strength,emotion,activations,updated_at,source)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(text) DO UPDATE SET
                 importance=max(memories.importance, excluded.importance),
                 confidence=min(0.99, max(memories.confidence, excluded.confidence)),
                 strength=min(1.5, max(memories.strength, excluded.strength) + 0.04),
                 emotion=max(memories.emotion, excluded.emotion),
                 activations=memories.activations+1,
                 last_used_at=excluded.last_used_at,
                 updated_at=excluded.updated_at""",
            (text, kind[:32], importance, now, now, confidence, strength, emotion, 0, now, source[:40]),
        )
        self._conn().commit()

    @staticmethod
    def _words(text: str) -> list[str]:
        return re.findall(r"[\wÀ-ÿ]{3,}", str(text).lower(), flags=re.UNICODE)

    @classmethod
    def _fts_query(cls, text: str) -> str:
        unique: list[str] = []
        for w in cls._words(text):
            if w not in unique:
                unique.append(w)
        return " OR ".join(f'"{w}"' for w in unique[:12])

    @staticmethod
    def _age_score(ts: float, half_life_days: float = 45.0) -> float:
        age_days = max(0.0, (time.time() - float(ts or 0.0)) / 86400.0)
        return math.exp(-math.log(2.0) * age_days / half_life_days)

    def search(self, query: str, limit: int = 7) -> list[Memory]:
        conn = self._conn()
        limit = max(1, min(int(limit), 20))
        candidates: list[tuple[sqlite3.Row, float]] = []
        fts = self._fts_query(query)
        if fts:
            try:
                rows = conn.execute(
                    """SELECT m.*, bm25(memories_fts) AS rank FROM memories_fts f
                       JOIN memories m ON m.id=f.rowid
                       WHERE memories_fts MATCH ?
                       ORDER BY rank LIMIT ?""",
                    (fts, limit * 5),
                ).fetchall()
                for i, row in enumerate(rows):
                    lexical = max(0.0, 1.0 - (i / max(1.0, len(rows))))
                    candidates.append((row, lexical))
            except sqlite3.DatabaseError:
                pass
        if len(candidates) < limit:
            words = self._words(query)[:7]
            if words:
                clauses = " OR ".join("lower(text) LIKE ?" for _ in words)
                rows = conn.execute(
                    f"SELECT * FROM memories WHERE {clauses} ORDER BY importance DESC,last_used_at DESC LIMIT ?",
                    [f"%{w}%" for w in words] + [limit * 4],
                ).fetchall()
                seen = {int(r["id"]) for r, _ in candidates}
                for row in rows:
                    if int(row["id"]) not in seen:
                        overlap = sum(1 for w in words if w in str(row["text"]).lower()) / max(1, len(words))
                        candidates.append((row, overlap))
        if not candidates:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY importance DESC,last_used_at DESC LIMIT ?", (limit,)
            ).fetchall()
            candidates = [(r, 0.05) for r in rows]

        def score(item: tuple[sqlite3.Row, float]) -> float:
            r, lexical = item
            return (
                0.34 * lexical
                + 0.22 * float(r["importance"] or 0)
                + 0.17 * float(r["confidence"] or 0)
                + 0.13 * min(1.0, float(r["strength"] or 0))
                + 0.10 * self._age_score(float(r["last_used_at"] or r["created_at"] or 0))
                + 0.04 * min(1.0, math.log1p(int(r["activations"] or 0)) / 4.0)
            )

        candidates.sort(key=score, reverse=True)
        rows = [r for r, _ in candidates[:limit]]
        now = time.time()
        if rows:
            conn.executemany(
                "UPDATE memories SET last_used_at=?, activations=activations+1, strength=min(1.5,strength+0.025) WHERE id=?",
                [(now, int(r["id"])) for r in rows],
            )
            conn.commit()
        return [Memory(**{k: dict(r).get(k) for k in Memory.__dataclass_fields__}) for r in rows]

    def list_memories(self, limit: int = 50) -> list[Memory]:
        rows = self._conn().execute(
            "SELECT * FROM memories ORDER BY importance DESC,last_used_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Memory(**{k: dict(r).get(k) for k in Memory.__dataclass_fields__}) for r in rows]

    def add_episode(self, summary: str, themes: list[str] | str = "", importance: float = 0.5, emotion: float = 0.3) -> None:
        summary = re.sub(r"\s+", " ", str(summary).strip())[:900]
        if len(summary) < 12:
            return
        if isinstance(themes, list):
            themes = ", ".join(str(x).strip() for x in themes if str(x).strip())
        themes = str(themes)[:240]
        now = time.time()
        self._conn().execute(
            "INSERT INTO episodes(summary,themes,importance,emotion,created_at,last_used_at,activations) VALUES(?,?,?,?,?,?,0)",
            (summary, themes, max(0.0, min(1.0, float(importance))), max(0.0, min(1.0, float(emotion))), now, now),
        )
        self._conn().commit()

    def search_episodes(self, query: str, limit: int = 3) -> list[Episode]:
        conn = self._conn()
        rows: list[sqlite3.Row] = []
        fts = self._fts_query(query)
        if fts:
            try:
                rows = conn.execute(
                    """SELECT e.* FROM episodes_fts f JOIN episodes e ON e.id=f.rowid
                       WHERE episodes_fts MATCH ? ORDER BY bm25(episodes_fts), e.importance DESC LIMIT ?""",
                    (fts, limit * 3),
                ).fetchall()
            except sqlite3.DatabaseError:
                rows = []
        if not rows:
            rows = conn.execute(
                "SELECT * FROM episodes ORDER BY importance DESC,created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        rows = rows[:limit]
        now = time.time()
        if rows:
            conn.executemany("UPDATE episodes SET last_used_at=?,activations=activations+1 WHERE id=?", [(now, r["id"]) for r in rows])
            conn.commit()
        return [Episode(**dict(r)) for r in rows]

    def upsert_belief(self, dimension: str, value: str, confidence: float = 0.55, source: str = "conversation") -> None:
        dimension = re.sub(r"[^a-zA-Z0-9_-]", "", str(dimension).lower())[:32] or "pattern"
        value = re.sub(r"\s+", " ", str(value).strip())[:300]
        if len(value) < 4:
            return
        confidence = max(0.05, min(0.99, float(confidence)))
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM beliefs WHERE dimension=? AND contradicted=0 ORDER BY confidence DESC", (dimension,)
        ).fetchall()
        key = value.lower()[:80]
        existing = next((r for r in rows if str(r["value"]).lower()[:80] == key), None)
        now = time.time()
        if existing:
            n = max(1, int(existing["evidence"] or 1))
            old = float(existing["confidence"] or 0.5)
            updated = min(0.99, (old * n + confidence) / (n + 1))
            conn.execute(
                "UPDATE beliefs SET confidence=?,evidence=evidence+1,updated_at=?,source=? WHERE id=?",
                (updated, now, source[:40], int(existing["id"])),
            )
        else:
            conn.execute(
                "INSERT INTO beliefs(dimension,value,confidence,evidence,source,contradicted,created_at,updated_at) VALUES(?,?,?,?,?,0,?,?)",
                (dimension, value, confidence, 1, source[:40], now, now),
            )
        conn.commit()

    def contradict_belief(self, dimension: str, old_fragment: str, new_value: str, confidence: float = 0.65) -> None:
        conn = self._conn()
        old_fragment = str(old_fragment).lower().strip()[:120]
        rows = conn.execute(
            "SELECT id,value FROM beliefs WHERE dimension=? AND contradicted=0", (dimension[:32],)
        ).fetchall()
        for row in rows:
            if old_fragment and old_fragment in str(row["value"]).lower():
                conn.execute("UPDATE beliefs SET contradicted=1,updated_at=? WHERE id=?", (time.time(), int(row["id"])))
        conn.commit()
        self.upsert_belief(dimension, new_value, confidence, source="contradiction")

    def beliefs(self, dimension: str | None = None, min_confidence: float = 0.45, limit: int = 18) -> list[Belief]:
        conn = self._conn()
        if dimension:
            rows = conn.execute(
                "SELECT * FROM beliefs WHERE contradicted=0 AND confidence>=? AND dimension=? ORDER BY confidence DESC,evidence DESC LIMIT ?",
                (min_confidence, dimension, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM beliefs WHERE contradicted=0 AND confidence>=? ORDER BY confidence DESC,evidence DESC,updated_at DESC LIMIT ?",
                (min_confidence, limit),
            ).fetchall()
        return [Belief(**dict(r)) for r in rows]

    def set_state(self, key: str, value) -> None:
        raw = json.dumps(value, ensure_ascii=False)
        self._conn().execute(
            "INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, raw),
        )
        self._conn().commit()

    def get_state(self, key: str, default=None):
        row = self._conn().execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return default

    def increment_state(self, key: str, amount: int = 1) -> int:
        try:
            value = int(self.get_state(key, 0) or 0) + int(amount)
        except Exception:
            value = int(amount)
        self.set_state(key, value)
        return value

    def relationship_state(self) -> dict[str, float]:
        raw = self.get_state("relationship", {})
        if not isinstance(raw, dict):
            raw = {}
        base = {"closeness": 0.28, "trust": 0.45, "friction": 0.08, "playfulness": 0.45, "curiosity": 0.55}
        for k in base:
            try:
                base[k] = max(0.0, min(1.0, float(raw.get(k, base[k]))))
            except Exception:
                pass
        return base

    def update_relationship(self, user_text: str) -> dict[str, float]:
        s = self.relationship_state()
        low = str(user_text).lower()
        intimate = bool(re.search(r"\b(jujur|sejujurnya|aku merasa|aku takut|aku sedih|aku marah|cerita|rahasia|percaya)\b", low))
        positive = bool(re.search(r"\b(makasih|terima kasih|bagus|mantap|berhasil|tepat|lanjut|oke|ok)\b", low))
        negative = bool(re.search(r"\b(salah|payah|jelek|gagal|nggak sesuai|tidak sesuai|bodoh|kesal|wtf)\b", low))
        teasing = bool(re.search(r"\b(hehe|haha|wkwk|ledek|ejek|nyebelin|sombong)\b", low))
        if intimate:
            s["closeness"] += 0.025
            s["trust"] += 0.02
        if positive:
            s["trust"] += 0.012
            s["friction"] -= 0.02
        if negative:
            s["friction"] += 0.05
            s["trust"] -= 0.012
        else:
            s["friction"] *= 0.94
        if teasing:
            s["playfulness"] += 0.03
        s["curiosity"] = min(1.0, s["curiosity"] * 0.985 + (0.015 if len(user_text) > 80 else 0.0))
        for k in s:
            s[k] = round(max(0.0, min(1.0, s[k])), 4)
        self.set_state("relationship", s)
        return s

    def record_route(self, profile: str, context_key: str) -> None:
        self._conn().execute(
            "INSERT INTO response_routes(profile,context_key,outcome,created_at) VALUES(?,?,NULL,?)",
            (profile[:24], context_key[:80], time.time()),
        )
        self._conn().commit()

    def mark_last_route_outcome(self, outcome: str) -> None:
        if outcome not in {"positive", "negative", "neutral"}:
            return
        row = self._conn().execute("SELECT id FROM response_routes WHERE outcome IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            self._conn().execute("UPDATE response_routes SET outcome=? WHERE id=?", (outcome, int(row["id"])))
            self._conn().commit()

    def route_stats(self, profile: str, context_key: str) -> tuple[int, float]:
        rows = self._conn().execute(
            "SELECT outcome FROM response_routes WHERE profile=? AND context_key=? AND outcome IS NOT NULL ORDER BY id DESC LIMIT 60",
            (profile[:24], context_key[:80]),
        ).fetchall()
        if not rows:
            return 0, 0.5
        positive = sum(1 for r in rows if r["outcome"] == "positive")
        negative = sum(1 for r in rows if r["outcome"] == "negative")
        effective = positive + negative
        return len(rows), (positive / effective if effective else 0.5)

    def decay_memories(self) -> None:
        conn = self._conn()
        now = time.time()
        rows = conn.execute("SELECT id,strength,emotion,last_used_at,importance FROM memories").fetchall()
        for row in rows:
            days = max(0.0, (now - float(row["last_used_at"] or now)) / 86400.0)
            if days < 1.0:
                continue
            protection = 0.35 if float(row["emotion"] or 0) >= 0.7 or float(row["importance"] or 0) >= 0.82 else 1.0
            new_strength = max(0.02, float(row["strength"] or 0.5) - days * 0.004 * protection)
            conn.execute("UPDATE memories SET strength=? WHERE id=?", (new_strength, int(row["id"])))
        conn.commit()

    def log_event(self, event_type: str, payload: dict) -> None:
        self._conn().execute(
            "INSERT INTO events(event_type,payload,created_at) VALUES(?,?,?)",
            (event_type, json.dumps(payload, ensure_ascii=False), time.time()),
        )
        self._conn().commit()


EXPLICIT_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"\b(?:namaku|nama saya)\s+([^,.!?]{2,60})", re.I), "identity", 0.96),
    (re.compile(r"\b(?:aku|saya)\s+(?:suka|menyukai)\s+([^.!?]{3,120})", re.I), "preference", 0.76),
    (re.compile(r"\b(?:aku|saya)\s+(?:tidak suka|nggak suka|benci)\s+([^.!?]{3,120})", re.I), "preference", 0.82),
    (re.compile(r"\b(?:aku|saya)\s+(?:tinggal|berada)\s+di\s+([^.!?]{2,100})", re.I), "profile", 0.84),
    (re.compile(r"\b(?:aku|saya)\s+(?:ingin|mau|berencana)\s+([^.!?]{4,180})", re.I), "goal", 0.62),
    (re.compile(r"\b(?:ingat|ingatlah|jangan lupa)\s+(?:bahwa\s+)?([^.!?]{4,180})", re.I), "explicit", 0.92),
]


def extract_explicit_memories(text: str) -> Iterable[tuple[str, str, float]]:
    for pattern, kind, importance in EXPLICIT_PATTERNS:
        m = pattern.search(text)
        if m:
            yield (m.group(0).strip(), kind, importance)
