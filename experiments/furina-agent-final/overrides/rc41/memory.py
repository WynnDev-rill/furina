from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import struct
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
        self._embedder = None
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
            CREATE TABLE IF NOT EXISTS conversations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL DEFAULT 'Percakapan baru',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
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
            CREATE TABLE IF NOT EXISTS memory_vectors (
              memory_id INTEGER PRIMARY KEY,
              vector BLOB NOT NULL,
              dims INTEGER NOT NULL,
              model TEXT NOT NULL,
              updated_at REAL NOT NULL,
              FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS learned_skills (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              app_package TEXT NOT NULL DEFAULT '',
              signature TEXT NOT NULL,
              goal_text TEXT NOT NULL,
              steps_json TEXT NOT NULL,
              success_count INTEGER NOT NULL DEFAULT 1,
              failure_count INTEGER NOT NULL DEFAULT 0,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              last_success_at REAL NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS learned_skills_unique_idx ON learned_skills(app_package,signature);
            CREATE INDEX IF NOT EXISTS learned_skills_score_idx ON learned_skills(success_count,failure_count,last_success_at);
            CREATE TABLE IF NOT EXISTS memory_vector_lsh (
              memory_id INTEGER PRIMARY KEY,
              bucket INTEGER NOT NULL,
              bucket2 INTEGER NOT NULL,
              updated_at REAL NOT NULL,
              FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS memory_vector_lsh_bucket_idx ON memory_vector_lsh(bucket);
            CREATE INDEX IF NOT EXISTS memory_vector_lsh_bucket2_idx ON memory_vector_lsh(bucket2);
            CREATE TABLE IF NOT EXISTS prospective_memories (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              text TEXT NOT NULL,
              due_at REAL NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'pending',
              source TEXT NOT NULL DEFAULT 'conversation',
              created_at REAL NOT NULL,
              fired_at REAL NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS prospective_due_idx ON prospective_memories(status,due_at);
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
        self._ensure_column(c, "messages", "conversation_id", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column(c, "messages", "attachment_json", "TEXT NOT NULL DEFAULT ''")
        now = time.time()
        c.execute(
            "INSERT OR IGNORE INTO conversations(id,title,created_at,updated_at) VALUES(1,?,?,?)",
            ("Percakapan sebelumnya", now, now),
        )
        c.execute("UPDATE messages SET conversation_id=1 WHERE conversation_id IS NULL OR conversation_id<=0")
        if not c.execute("SELECT 1 FROM kv WHERE key='active_conversation_id'").fetchone():
            c.execute("INSERT INTO kv(key,value) VALUES('active_conversation_id','1')")
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

    def add_message(self, role: str, content: str, attachment: dict | None = None) -> int:
        conversation_id = self.active_conversation_id()
        now = time.time()
        cur = self._conn().execute(
            "INSERT INTO messages(role, content, created_at, conversation_id, attachment_json) VALUES(?,?,?,?,?)",
            (role, content, now, conversation_id, json.dumps(attachment, ensure_ascii=False) if attachment else ""),
        )
        if role == "user":
            title = re.sub(r"\s+", " ", str(content or "")).strip()[:54] or "Percakapan baru"
            self._conn().execute(
                "UPDATE conversations SET title=CASE WHEN title IN ('Percakapan baru','Percakapan sebelumnya') THEN ? ELSE title END, updated_at=? WHERE id=?",
                (title, now, conversation_id),
            )
        else:
            self._conn().execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))
        self._conn().commit()
        return int(cur.lastrowid)

    def recent_messages(self, limit: int = 12) -> list[dict]:
        rows = self._conn().execute(
            "SELECT role,content,created_at FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
            (self.active_conversation_id(), limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def message_count(self) -> int:
        return int(self._conn().execute(
            "SELECT count(*) FROM messages WHERE conversation_id=?", (self.active_conversation_id(),)
        ).fetchone()[0])

    def active_conversation_id(self) -> int:
        row = self._conn().execute("SELECT value FROM kv WHERE key='active_conversation_id'").fetchone()
        try:
            value = int(row[0]) if row else 1
        except Exception:
            value = 1
        if not self._conn().execute("SELECT 1 FROM conversations WHERE id=?", (value,)).fetchone():
            latest = self._conn().execute("SELECT id FROM conversations ORDER BY updated_at DESC,id DESC LIMIT 1").fetchone()
            value = int(latest[0]) if latest else self.create_conversation()
        return value

    def list_conversations(self, limit: int = 60) -> list[dict]:
        active = self.active_conversation_id()
        rows = self._conn().execute(
            """SELECT c.id,c.title,c.created_at,c.updated_at,count(m.id) AS message_count
               FROM conversations c LEFT JOIN messages m ON m.conversation_id=c.id
               GROUP BY c.id ORDER BY c.updated_at DESC,c.id DESC LIMIT ?""",
            (max(1, min(int(limit), 100)),),
        ).fetchall()
        return [{**dict(row), "active": int(row["id"]) == active} for row in rows]

    def create_conversation(self, title: str = "Percakapan baru") -> int:
        now = time.time()
        clean = re.sub(r"\s+", " ", str(title or "")).strip()[:80] or "Percakapan baru"
        cur = self._conn().execute(
            "INSERT INTO conversations(title,created_at,updated_at) VALUES(?,?,?)", (clean, now, now)
        )
        value = int(cur.lastrowid)
        self._conn().execute(
            "INSERT INTO kv(key,value) VALUES('active_conversation_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(value),),
        )
        self._conn().commit()
        return value

    def switch_conversation(self, conversation_id: int) -> int:
        value = int(conversation_id)
        if not self._conn().execute("SELECT 1 FROM conversations WHERE id=?", (value,)).fetchone():
            raise ValueError("percakapan tidak ditemukan")
        self._conn().execute(
            "INSERT INTO kv(key,value) VALUES('active_conversation_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(value),),
        )
        self._conn().commit()
        return value

    def delete_conversation(self, conversation_id: int) -> int:
        value = int(conversation_id)
        rows = int(self._conn().execute("SELECT count(*) FROM conversations").fetchone()[0])
        if rows <= 1:
            self._conn().execute("DELETE FROM messages WHERE conversation_id=?", (value,))
            self._conn().execute("UPDATE conversations SET title='Percakapan baru',updated_at=? WHERE id=?", (time.time(), value))
            self._conn().commit()
            return value
        self._conn().execute("DELETE FROM messages WHERE conversation_id=?", (value,))
        self._conn().execute("DELETE FROM conversations WHERE id=?", (value,))
        latest = self._conn().execute("SELECT id FROM conversations ORDER BY updated_at DESC,id DESC LIMIT 1").fetchone()
        self._conn().commit()
        return self.switch_conversation(int(latest[0]))

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

    def _embed_text(self, text: str) -> list[float] | None:
        try:
            if self._embedder is None:
                from .config import load_config
                from .embeddings import LocalEmbeddingEngine
                cfg = load_config()
                if not cfg.embedding_enabled or not Path(cfg.embedding_model_path).expanduser().is_file():
                    return None
                self._embedder = LocalEmbeddingEngine(cfg)
            return self._embedder.embed(text)
        except Exception:
            return None

    @staticmethod
    def _pack_vector(vec: list[float]) -> bytes:
        return struct.pack("<" + "f" * len(vec), *vec)

    @staticmethod
    def _unpack_vector(blob: bytes, dims: int) -> list[float] | None:
        try:
            if not blob or dims <= 0 or len(blob) != dims * 4:
                return None
            return list(struct.unpack("<" + "f" * dims, blob))
        except Exception:
            return None

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(y * y for y in b))
        if na <= 1e-12 or nb <= 1e-12:
            return 0.0
        return max(-1.0, min(1.0, dot / (na * nb)))

    @staticmethod
    def _lsh_buckets(vec: list[float], bits: int = 12) -> tuple[int, int]:
        if not vec:
            return 0, 0
        bits = max(6, min(int(bits), 16))
        n = len(vec)
        b1 = 0
        b2 = 0
        for i in range(bits):
            idx1 = min(n - 1, int((i + 0.5) * n / bits))
            idx2 = (idx1 + max(1, n // (bits * 2))) % n
            if vec[idx1] >= 0:
                b1 |= 1 << i
            if vec[idx2] >= 0:
                b2 |= 1 << i
        return b1, b2

    @staticmethod
    def _lsh_neighbors(bucket: int, bits: int = 12) -> list[int]:
        out = [int(bucket)]
        for i in range(max(6, min(int(bits), 16))):
            out.append(int(bucket) ^ (1 << i))
        return out

    def _vectorize_memory(self, memory_id: int, text: str) -> bool:
        vec = self._embed_text(text)
        if not vec:
            return False
        model = "local"
        try:
            model = Path(self._embedder.model_path).name if self._embedder else "local"
        except Exception:
            pass
        now = time.time()
        self._conn().execute(
            "INSERT INTO memory_vectors(memory_id,vector,dims,model,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(memory_id) DO UPDATE SET vector=excluded.vector,dims=excluded.dims,model=excluded.model,updated_at=excluded.updated_at",
            (int(memory_id), self._pack_vector(vec), len(vec), model[:120], now),
        )
        b1, b2 = self._lsh_buckets(vec)
        self._conn().execute(
            "INSERT INTO memory_vector_lsh(memory_id,bucket,bucket2,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(memory_id) DO UPDATE SET bucket=excluded.bucket,bucket2=excluded.bucket2,updated_at=excluded.updated_at",
            (int(memory_id), b1, b2, now),
        )
        self._conn().commit()
        return True

    def backfill_vectors(self, limit: int = 16) -> int:
        rows = self._conn().execute(
            "SELECT m.id,m.text FROM memories m LEFT JOIN memory_vectors v ON v.memory_id=m.id "
            "WHERE v.memory_id IS NULL ORDER BY m.importance DESC,m.updated_at DESC LIMIT ?",
            (max(1, min(int(limit), 50)),),
        ).fetchall()
        done = 0
        for row in rows:
            if self._vectorize_memory(int(row["id"]), str(row["text"])):
                done += 1
            else:
                break
        return done

    def backfill_vector_index(self, limit: int = 160) -> int:
        rows = self._conn().execute(
            "SELECT v.memory_id,v.vector,v.dims FROM memory_vectors v LEFT JOIN memory_vector_lsh l ON l.memory_id=v.memory_id "
            "WHERE l.memory_id IS NULL LIMIT ?",
            (max(1, min(int(limit), 1000)),),
        ).fetchall()
        done = 0
        now = time.time()
        for row in rows:
            vec = self._unpack_vector(row["vector"], int(row["dims"] or 0))
            if not vec:
                continue
            b1, b2 = self._lsh_buckets(vec)
            self._conn().execute(
                "INSERT OR REPLACE INTO memory_vector_lsh(memory_id,bucket,bucket2,updated_at) VALUES(?,?,?,?)",
                (int(row["memory_id"]), b1, b2, now),
            )
            done += 1
        if done:
            self._conn().commit()
        return done

    def vector_coverage(self) -> tuple[int, int]:
        total = int(self._conn().execute("SELECT count(*) FROM memories").fetchone()[0])
        vectors = int(self._conn().execute("SELECT count(*) FROM memory_vectors").fetchone()[0])
        return vectors, total

    def search(self, query: str, limit: int = 7) -> list[Memory]:
        conn = self._conn()
        limit = max(1, min(int(limit), 20))
        candidates: dict[int, dict] = {}
        fts = self._fts_query(query)
        if fts:
            try:
                rows = conn.execute(
                    "SELECT m.*, bm25(memories_fts) AS rank FROM memories_fts f JOIN memories m ON m.id=f.rowid "
                    "WHERE memories_fts MATCH ? ORDER BY rank LIMIT ?",
                    (fts, limit * 6),
                ).fetchall()
                for i, row in enumerate(rows):
                    lexical = max(0.0, 1.0 - i / max(1.0, len(rows)))
                    candidates[int(row["id"])] = {"row": row, "lexical": lexical, "semantic": 0.0}
            except sqlite3.DatabaseError:
                pass
        words = self._words(query)[:8]
        if words and len(candidates) < limit * 3:
            clauses = " OR ".join("lower(text) LIKE ?" for _ in words)
            rows = conn.execute(
                f"SELECT * FROM memories WHERE {clauses} ORDER BY importance DESC,last_used_at DESC LIMIT ?",
                [f"%{w}%" for w in words] + [limit * 5],
            ).fetchall()
            for row in rows:
                rid = int(row["id"])
                overlap = sum(1 for w in words if w in str(row["text"]).lower()) / max(1, len(words))
                item = candidates.setdefault(rid, {"row": row, "lexical": 0.0, "semantic": 0.0})
                item["lexical"] = max(float(item["lexical"]), overlap)

        query_vec = self._embed_text(query)
        if query_vec:
            self.backfill_vector_index(220)
            b1, b2 = self._lsh_buckets(query_vec)
            n1 = self._lsh_neighbors(b1)
            n2 = self._lsh_neighbors(b2)
            p1 = ",".join("?" for _ in n1)
            p2 = ",".join("?" for _ in n2)
            total_vectors = int(conn.execute("SELECT count(*) FROM memory_vectors").fetchone()[0])
            if total_vectors <= 240:
                rows = conn.execute(
                    "SELECT m.*,v.vector,v.dims FROM memory_vectors v JOIN memories m ON m.id=v.memory_id"
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT m.*,v.vector,v.dims FROM memory_vector_lsh l "
                    f"JOIN memory_vectors v ON v.memory_id=l.memory_id JOIN memories m ON m.id=v.memory_id "
                    f"WHERE l.bucket IN ({p1}) OR l.bucket2 IN ({p2}) "
                    f"ORDER BY m.importance DESC,m.last_used_at DESC LIMIT ?",
                    [*n1, *n2, max(80, limit * 18)],
                ).fetchall()
                if len(rows) < limit * 4:
                    extra = conn.execute(
                        "SELECT m.*,v.vector,v.dims FROM memory_vectors v JOIN memories m ON m.id=v.memory_id "
                        "ORDER BY m.importance DESC,m.last_used_at DESC LIMIT ?",
                        (max(80, limit * 12),),
                    ).fetchall()
                    seen = {int(r["id"]) for r in rows}
                    rows = list(rows) + [r for r in extra if int(r["id"]) not in seen]
            semantic_rows: list[tuple[float, sqlite3.Row]] = []
            for row in rows:
                vec = self._unpack_vector(row["vector"], int(row["dims"] or 0))
                if vec and len(vec) == len(query_vec):
                    semantic_rows.append((self._cosine(query_vec, vec), row))
            semantic_rows.sort(key=lambda x: x[0], reverse=True)
            for similarity, row in semantic_rows[: limit * 7]:
                rid = int(row["id"])
                item = candidates.setdefault(rid, {"row": row, "lexical": 0.0, "semantic": 0.0})
                item["semantic"] = max(float(item["semantic"]), max(0.0, similarity))

        if not candidates:
            rows = conn.execute("SELECT * FROM memories ORDER BY importance DESC,last_used_at DESC LIMIT ?", (limit,)).fetchall()
            for row in rows:
                candidates[int(row["id"])] = {"row": row, "lexical": 0.05, "semantic": 0.0}

        def score(item: dict) -> float:
            r = item["row"]
            return (
                0.30 * float(item["semantic"])
                + 0.25 * float(item["lexical"])
                + 0.14 * float(r["importance"] or 0)
                + 0.11 * float(r["confidence"] or 0)
                + 0.08 * min(1.0, float(r["strength"] or 0))
                + 0.08 * self._age_score(float(r["last_used_at"] or r["created_at"] or 0))
                + 0.04 * min(1.0, math.log1p(int(r["activations"] or 0)) / 4.0)
            )

        ranked = sorted(candidates.values(), key=score, reverse=True)[:limit]
        rows = [item["row"] for item in ranked]
        now = time.time()
        if rows:
            conn.executemany(
                "UPDATE memories SET last_used_at=?,activations=activations+1,strength=min(1.5,strength+0.025) WHERE id=?",
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

    @staticmethod
    def _skill_words(text: str) -> set[str]:
        stop = {"yang", "dan", "lalu", "terus", "untuk", "dengan", "dari", "pada", "sekarang", "tolong", "please"}
        return {w for w in MemoryStore._words(text) if w not in stop}

    def learn_skill(self, goal: str, history: list[dict], app_package: str = "") -> int | None:
        steps: list[dict] = []
        for item in history:
            result = item.get("result")
            ok = bool(result.get("ok")) if isinstance(result, dict) else result not in {None, "failed_action", "rejected_by_user", "premature_finish"}
            if not ok:
                continue
            action = item.get("executed") or item.get("action") or {}
            typ = str(action.get("type") or "")
            if typ in {"observe", "wait", "finish", "tap"}:
                continue
            step = {"type": typ}
            if typ == "open_app" and action.get("package"):
                step["package"] = str(action.get("package"))
            if typ in {"tap_node", "long_press", "scroll_node", "set_text", "ime_action"}:
                target = action.get("target") if isinstance(action.get("target"), dict) else {}
                stable = {k: target.get(k) for k in ("view_id", "class", "editable", "scrollable") if target.get(k) not in (None, "", False)}
                if stable:
                    step["target"] = stable
            if typ in {"scroll_node", "scroll_global"}:
                step["direction"] = str(action.get("direction") or "forward")
            if typ == "set_text":
                step["input"] = "from_current_goal"
            steps.append(step)
        if not steps:
            return None
        action_signature = " > ".join(str(s.get("type") or "") for s in steps if s.get("type"))
        low_goal = str(goal).casefold()
        intent_tags: list[str] = []
        for tag, pattern in (
            ("buka", r"\b(?:buka|open|jalankan)\b"),
            ("cari", r"\b(?:cari|carikan|search|telusur|telusuri)\b"),
            ("tulis", r"\b(?:tulis|tuliskan|ketik|ketikkan|isi|isikan|catat|catatkan)\b"),
            ("scroll", r"\b(?:scroll|geser|swipe)\b"),
            ("external", r"\b(?:send|kirim|post|share|bagikan|call|telepon|unggah|upload)\b"),
        ):
            if re.search(pattern, low_goal):
                intent_tags.append(tag)
        compact_goal = (
            "app=" + (app_package[:180] or "unknown")
            + " intent=" + "+".join(intent_tags or ["generic"])
            + " actions=" + action_signature
        )[:360]
        signature_src = app_package + "|" + "|".join(s.get("type", "") + ":" + str(s.get("target", {}).get("view_id", "")) for s in steps)
        signature = hashlib.sha1(signature_src.encode("utf-8")).hexdigest()[:24]
        now = time.time()
        conn = self._conn()
        row = conn.execute("SELECT id FROM learned_skills WHERE app_package=? AND signature=?", (app_package[:180], signature)).fetchone()
        if row:
            sid = int(row["id"])
            conn.execute(
                "UPDATE learned_skills SET goal_text=?,steps_json=?,success_count=success_count+1,updated_at=?,last_success_at=? WHERE id=?",
                (compact_goal, json.dumps(steps, ensure_ascii=False), now, now, sid),
            )
        else:
            cur = conn.execute(
                "INSERT INTO learned_skills(app_package,signature,goal_text,steps_json,success_count,failure_count,created_at,updated_at,last_success_at) VALUES(?,?,?,?,1,0,?,?,?)",
                (app_package[:180], signature, compact_goal, json.dumps(steps, ensure_ascii=False), now, now, now),
            )
            sid = int(cur.lastrowid)
        conn.commit()
        return sid

    def find_skills(self, goal: str, app_package: str = "", limit: int = 3) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM learned_skills ORDER BY last_success_at DESC LIMIT 120"
        ).fetchall()
        q = self._skill_words(goal)
        scored: list[tuple[float, sqlite3.Row]] = []
        now = time.time()
        for row in rows:
            words = self._skill_words(str(row["goal_text"]))
            overlap = len(q & words) / max(1, len(q | words)) if q or words else 0.0
            package_bonus = 0.25 if app_package and str(row["app_package"]) == app_package else 0.0
            if overlap <= 0.0 and package_bonus <= 0.0:
                continue
            wins = int(row["success_count"] or 0); fails = int(row["failure_count"] or 0)
            reliability = (wins + 1.0) / (wins + fails + 2.0)
            age_days = max(0.0, (now - float(row["last_success_at"] or now)) / 86400.0)
            recency = math.exp(-age_days / 30.0)
            score = 0.50 * overlap + 0.22 * reliability + 0.13 * recency + package_bonus
            if score >= 0.22:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[dict] = []
        for score, row in scored[: max(1, min(int(limit), 5))]:
            try:
                steps = json.loads(row["steps_json"])
            except Exception:
                steps = []
            out.append({"id": int(row["id"]), "score": round(score, 3), "goal": str(row["goal_text"]), "steps": steps})
        return out

    def penalize_skills(self, skill_ids: list[int]) -> None:
        ids = [int(x) for x in skill_ids if int(x) > 0][:8]
        if not ids:
            return
        self._conn().executemany(
            "UPDATE learned_skills SET failure_count=failure_count+1,updated_at=? WHERE id=?",
            [(time.time(), sid) for sid in ids],
        )
        self._conn().commit()

    def add_prospective(self, text: str, due_at: float = 0.0, source: str = "conversation") -> int:
        clean = re.sub(r"\s+", " ", str(text or "").strip())[:500]
        if not clean:
            return 0
        row = self._conn().execute(
            "SELECT id FROM prospective_memories WHERE text=? AND status IN ('pending','due') AND abs(due_at-?)<60 LIMIT 1",
            (clean, float(due_at or 0)),
        ).fetchone()
        if row:
            return int(row["id"])
        cur = self._conn().execute(
            "INSERT INTO prospective_memories(text,due_at,status,source,created_at,fired_at) VALUES(?,?,'pending',?,?,0)",
            (clean, float(due_at or 0), str(source)[:40], time.time()),
        )
        self._conn().commit()
        return int(cur.lastrowid)

    def pending_prospectives(self, limit: int = 8) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM prospective_memories WHERE status IN ('pending','due') ORDER BY CASE WHEN due_at<=0 THEN 1 ELSE 0 END,due_at,created_at LIMIT ?",
            (max(1, min(int(limit), 30)),),
        ).fetchall()
        return [dict(r) for r in rows]

    def due_prospectives(self, now: float | None = None, limit: int = 8) -> list[dict]:
        at = time.time() if now is None else float(now)
        rows = self._conn().execute(
            "SELECT * FROM prospective_memories WHERE status='pending' AND due_at>0 AND due_at<=? ORDER BY due_at LIMIT ?",
            (at, max(1, min(int(limit), 30))),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_prospective_fired(self, reminder_id: int) -> None:
        self._conn().execute(
            "UPDATE prospective_memories SET status='notified',fired_at=? WHERE id=?",
            (time.time(), int(reminder_id)),
        )
        self._conn().commit()

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
