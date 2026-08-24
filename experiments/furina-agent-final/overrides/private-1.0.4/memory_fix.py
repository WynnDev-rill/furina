#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
PATH = ROOT / "core/furina_agent/memory.py"


def cls_node(text: str, name: str) -> ast.ClassDef:
    tree = ast.parse(text)
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name), None)
    if node is None:
        raise SystemExit(f"missing class {name}")
    return node


def replace_method(name: str, source: str) -> None:
    text = PATH.read_text(encoding="utf-8")
    cls = cls_node(text, "MemoryStore")
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"MemoryStore.{name}: expected one method, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[: start_line - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    PATH.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


def insert_before(before: str, source: str, guard: str) -> None:
    text = PATH.read_text(encoding="utf-8")
    if guard in text:
        return
    cls = cls_node(text, "MemoryStore")
    node = next((n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == before), None)
    if node is None:
        raise SystemExit(f"MemoryStore.{before} missing")
    lines = text.splitlines(keepends=True)
    pos = sum(len(x) for x in lines[: node.lineno - 1])
    PATH.write_text(text[:pos] + source.rstrip() + "\n\n" + text[pos:], encoding="utf-8")


insert_before("search", r'''    @staticmethod
    def _query_dimensions(query: str) -> set[str]:
        q = " ".join(str(query or "").casefold().split())
        dims: set[str] = set()
        if re.search(r"\b(suka|sukai|kusukai|kesukaan|favorit|favorite|preferensi|benci|tidak suka|nggak suka)\b", q):
            dims.add("preference")
        if re.search(r"\b(tujuan|target|goal|rencana|berencana|cita-cita|ingin|mau)\b", q) or "tahun ini" in q:
            dims.add("goal")
        if re.search(r"\b(biasanya|sering|kebiasaan|rutin|rutinitas|kulakukan|lakukan)\b", q):
            dims.add("pattern")
        if re.search(r"\b(nama|namaku|siapa aku|identitas)\b", q):
            dims.add("identity")
        if re.search(r"\b(umur|usia|tinggal|lokasi|kerja|pekerjaan|profil|tentang aku)\b", q):
            dims.add("profile")
        if re.search(r"\b(hubungan|pasangan|relationship)\b", q):
            dims.add("relationship")
        if re.search(r"\b(kamu ingat apa|ingat apa saja|apa yang kamu ingat|apa saja yang kamu ingat|tentang diriku|tentang aku)\b", q):
            dims.update({"identity", "profile", "preference", "goal", "pattern", "relationship"})
        return dims

    @staticmethod
    def _retrieval_terms(text: str) -> set[str]:
        stop = {
            "apa", "yang", "dan", "atau", "aku", "saya", "kamu", "kau", "itu", "ini", "saja", "tentang", "apakah",
            "bisa", "masih", "ingat", "ingatkah", "biasanya", "tahun", "sekarang", "pernah", "dari", "dengan", "untuk",
            "pada", "seperti", "kalau", "ketika", "mana", "sudah", "belum", "jadi", "lebih", "sering",
            "suka", "favorit", "favorite", "preferensi", "tujuan", "target", "goal", "rencana", "lakukan", "hubungan", "pasangan",
        }
        aliases = {
            "kusukai": "suka", "sukai": "suka", "kesukaan": "suka", "tujuanku": "tujuan", "targetku": "target",
            "rencanaku": "rencana", "kulakukan": "lakukan",
        }
        raw = re.findall(r"[\wÀ-ÿ]{3,}", str(text or "").casefold(), flags=re.UNICODE)
        return {aliases.get(w, w) for w in raw if aliases.get(w, w) not in stop}

    @staticmethod
    def _memory_source_trust(source: str) -> float:
        s = str(source or "").casefold()
        if s in {"explicit", "furinahub", "user_note", "manual"}:
            return 1.0
        if s.startswith("episode:"):
            return 0.78
        if s in {"contradiction", "reflection"}:
            return 0.70
        if s == "consolidation":
            return 0.58
        return 0.52

    @staticmethod
    def _dimension_memory_kinds(dimensions: set[str]) -> set[str]:
        mapping = {
            "identity": {"identity"}, "profile": {"profile"}, "preference": {"preference"},
            "goal": {"goal"}, "relationship": {"relationship"}, "pattern": {"fact"},
        }
        out: set[str] = set()
        for dimension in dimensions:
            out.update(mapping.get(dimension, set()))
        return out''', "def _query_dimensions")

replace_method("search", r'''    def search(self, query: str, limit: int = 7) -> list[Memory]:
        """Return relevant shared memories only; no unrelated importance fallback."""
        conn = self._conn()
        limit = max(1, min(int(limit), 20))
        query = " ".join(str(query or "").strip().split())
        if not query:
            return []
        qterms = self._retrieval_terms(query)
        dims = self._query_dimensions(query)
        kinds = self._dimension_memory_kinds(dims)
        candidates: dict[int, dict] = {}

        # Category-only recall such as "apa yang kusukai?" must not FTS-match
        # generic tokens like "aku". It uses the trusted category path below.
        fts = self._fts_query(" ".join(qterms)) if qterms else ""
        if fts:
            try:
                rows = conn.execute(
                    "SELECT m.*, bm25(memories_fts) AS rank FROM memories_fts f JOIN memories m ON m.id=f.rowid "
                    "WHERE memories_fts MATCH ? ORDER BY rank LIMIT ?",
                    (fts, limit * 6),
                ).fetchall()
                for i, row in enumerate(rows):
                    text_terms = self._retrieval_terms(str(row["text"]))
                    overlap = len(qterms & text_terms) / max(1, len(qterms))
                    rank_hint = max(0.0, 1.0 - i / max(1.0, len(rows)))
                    candidates[int(row["id"])] = {
                        "row": row, "lexical": min(1.0, overlap + 0.05 * rank_hint), "semantic": 0.0, "category": 0.0,
                    }
            except sqlite3.DatabaseError:
                pass

        if qterms:
            words = list(qterms)[:10]
            clauses = " OR ".join("lower(text) LIKE ?" for _ in words)
            rows = conn.execute(
                f"SELECT * FROM memories WHERE {clauses} ORDER BY importance DESC,last_used_at DESC LIMIT ?",
                [f"%{w}%" for w in words] + [limit * 6],
            ).fetchall()
            for row in rows:
                rid = int(row["id"])
                text_terms = self._retrieval_terms(str(row["text"]))
                overlap = len(qterms & text_terms) / max(1, len(qterms))
                item = candidates.setdefault(rid, {"row": row, "lexical": 0.0, "semantic": 0.0, "category": 0.0})
                item["lexical"] = max(float(item["lexical"]), overlap)

        # General recall can retrieve direct facts by category even if the query
        # does not contain the wording used when that fact was stored.
        if kinds and not qterms:
            marks = ",".join("?" for _ in kinds)
            rows = conn.execute(
                f"SELECT * FROM memories WHERE kind IN ({marks}) ORDER BY confidence DESC,importance DESC,last_used_at DESC LIMIT ?",
                [*sorted(kinds), limit * 8],
            ).fetchall()
            for row in rows:
                trust = self._memory_source_trust(str(row["source"] or ""))
                reinforced = int(row["activations"] or 0) >= 2 and float(row["confidence"] or 0) >= 0.78
                if trust < 0.75 and not reinforced:
                    continue
                rid = int(row["id"])
                item = candidates.setdefault(rid, {"row": row, "lexical": 0.0, "semantic": 0.0, "category": 0.0})
                item["category"] = 1.0

        query_vec = self._embed_text(query)
        if query_vec:
            self.backfill_vector_index(220)
            rows = conn.execute(
                "SELECT m.*,v.vector,v.dims FROM memory_vectors v JOIN memories m ON m.id=v.memory_id "
                "ORDER BY m.importance DESC,m.last_used_at DESC LIMIT ?",
                (max(100, limit * 20),),
            ).fetchall()
            scored: list[tuple[float, sqlite3.Row]] = []
            for row in rows:
                vec = self._unpack_vector(row["vector"], int(row["dims"] or 0))
                if vec and len(vec) == len(query_vec):
                    scored.append((self._cosine(query_vec, vec), row))
            scored.sort(key=lambda item: item[0], reverse=True)
            for similarity, row in scored[: limit * 8]:
                if similarity < 0.52:
                    continue
                if kinds and str(row["kind"] or "") not in kinds:
                    continue
                rid = int(row["id"])
                item = candidates.setdefault(rid, {"row": row, "lexical": 0.0, "semantic": 0.0, "category": 0.0})
                item["semantic"] = max(float(item["semantic"]), max(0.0, similarity))

        eligible: list[tuple[float, dict]] = []
        for item in candidates.values():
            row = item["row"]
            lexical = float(item["lexical"])
            semantic = float(item["semantic"])
            category = float(item["category"])
            trust = self._memory_source_trust(str(row["source"] or ""))
            semantic_floor = 0.56 if trust >= 0.75 else 0.68
            if lexical < 0.20 and semantic < semantic_floor and category <= 0:
                continue
            direct = trust >= 0.75
            reinforced = int(row["activations"] or 0) >= 2 and float(row["confidence"] or 0) >= 0.78
            # Old inferred memories remain stored, but cannot become a personal
            # fact merely because one old model produced them once.
            if not direct and not reinforced:
                continue
            score = (
                0.34 * semantic + 0.31 * lexical + 0.15 * category + 0.07 * float(row["importance"] or 0)
                + 0.06 * float(row["confidence"] or 0) + 0.04 * trust
                + 0.03 * self._age_score(float(row["last_used_at"] or row["created_at"] or 0))
            )
            eligible.append((score, item))

        eligible.sort(key=lambda item: item[0], reverse=True)
        rows = [item["row"] for _, item in eligible[:limit]]
        now = time.time()
        if rows:
            conn.executemany(
                "UPDATE memories SET last_used_at=?,activations=activations+1,strength=min(1.5,strength+0.015) WHERE id=?",
                [(now, int(row["id"])) for row in rows],
            )
            conn.commit()
        return [Memory(**{key: dict(row).get(key) for key in Memory.__dataclass_fields__}) for row in rows]''')

replace_method("search_episodes", r'''    def search_episodes(self, query: str, limit: int = 3) -> list[Episode]:
        # Episodes are evidence, never an unrelated continuity fallback.
        conn = self._conn()
        limit = max(1, min(int(limit), 8))
        terms = self._retrieval_terms(query)
        if not terms:
            return []
        fts = self._fts_query(" ".join(terms))
        rows = []
        if fts:
            try:
                rows = conn.execute(
                    "SELECT e.* FROM episodes_fts f JOIN episodes e ON e.id=f.rowid WHERE episodes_fts MATCH ? "
                    "ORDER BY bm25(episodes_fts),e.importance DESC LIMIT ?",
                    (fts, limit * 4),
                ).fetchall()
            except sqlite3.DatabaseError:
                rows = []
        if not rows:
            return []
        rows = rows[:limit]
        now = time.time()
        conn.executemany(
            "UPDATE episodes SET last_used_at=?,activations=activations+1 WHERE id=?",
            [(now, int(row["id"])) for row in rows],
        )
        conn.commit()
        return [Episode(**dict(row)) for row in rows]''')

insert_before("beliefs", r'''    def relevant_beliefs(self, query: str, limit: int = 10) -> list[Belief]:
        conn = self._conn()
        limit = max(1, min(int(limit), 20))
        dims = self._query_dimensions(query)
        qterms = self._retrieval_terms(query)
        rows = conn.execute(
            "SELECT * FROM beliefs WHERE contradicted=0 AND confidence>=0.48 "
            "ORDER BY confidence DESC,evidence DESC,updated_at DESC LIMIT 120"
        ).fetchall()
        ranked: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            dimension = str(row["dimension"] or "")
            value = str(row["value"] or "")
            terms = self._retrieval_terms(value)
            overlap = len(qterms & terms) / max(1, len(qterms)) if qterms else 0.0
            category = 1.0 if dims and dimension in dims else 0.0
            if dims and dimension not in dims and overlap < 0.20:
                continue
            if not dims and overlap < 0.20:
                continue
            source = str(row["source"] or "").casefold()
            evidence = int(row["evidence"] or 0)
            confidence = float(row["confidence"] or 0)
            direct = source in {"explicit", "furinahub", "manual", "contradiction"}
            # Inferred patterns need repeated evidence; one old reflection is
            # not enough to tell the user "I remember you usually do X".
            if category and overlap < 0.20 and not direct and evidence < 2:
                continue
            score = (
                0.42 * category + 0.28 * overlap + 0.18 * confidence
                + 0.08 * min(1.0, evidence / 3.0) + (0.04 if direct else 0.0)
            )
            ranked.append((score, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [Belief(**dict(row)) for _, row in ranked[:limit]]''', "def relevant_beliefs")

text = PATH.read_text(encoding="utf-8")
compile(text, str(PATH), "exec")
print("FURINA_PRIVATE_1_0_4_MEMORY_FIX_OK")
