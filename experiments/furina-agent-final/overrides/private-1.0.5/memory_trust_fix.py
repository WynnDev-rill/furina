#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
PATH = ROOT / "core/furina_agent/memory.py"


def cls_node(text: str) -> ast.ClassDef:
    tree = ast.parse(text)
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MemoryStore"), None)
    if node is None:
        raise SystemExit("MemoryStore missing")
    return node


def replace_method(name: str, source: str) -> None:
    text = PATH.read_text(encoding="utf-8")
    cls = cls_node(text)
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"MemoryStore.{name}: expected one method, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[: start_line - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    PATH.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


replace_method("_memory_source_trust", r'''    @staticmethod
    def _memory_source_trust(source: str) -> float:
        """Trust only memories whose provenance is tied to user evidence.

        1.0.4 stopped creating unsupported inferred memories, but old rows from
        earlier builds still exist by design. They stay stored for forensic /
        migration safety yet are quarantined from factual personal recall.
        """
        s = str(source or "").casefold()
        if s in {"explicit", "furinahub", "user_note", "manual", "contradiction"}:
            return 1.0
        if s == "user_evidence":
            return 0.96
        if s == "user_evidence_pattern":
            return 0.90
        # Legacy model-authored sources are deliberately not trusted as facts.
        if s in {"consolidation", "reflection"} or s.startswith("episode:"):
            return 0.0
        return 0.0''')

replace_method("search", r'''    def search(self, query: str, limit: int = 7) -> list[Memory]:
        """Provider-neutral personal recall with strict provenance gating."""
        conn = self._conn()
        limit = max(1, min(int(limit), 20))
        query = " ".join(str(query or "").strip().split())
        if not query:
            return []
        qterms = self._retrieval_terms(query)
        dims = self._query_dimensions(query)
        kinds = self._dimension_memory_kinds(dims)
        candidates: dict[int, dict] = {}

        fts = self._fts_query(" ".join(qterms)) if qterms else ""
        if fts:
            try:
                rows = conn.execute(
                    "SELECT m.*, bm25(memories_fts) AS rank FROM memories_fts f JOIN memories m ON m.id=f.rowid "
                    "WHERE memories_fts MATCH ? ORDER BY rank LIMIT ?",
                    (fts, limit * 6),
                ).fetchall()
                for i, row in enumerate(rows):
                    if self._memory_source_trust(str(row["source"] or "")) <= 0:
                        continue
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
                [f"%{w}%" for w in words] + [limit * 8],
            ).fetchall()
            for row in rows:
                if self._memory_source_trust(str(row["source"] or "")) <= 0:
                    continue
                rid = int(row["id"])
                text_terms = self._retrieval_terms(str(row["text"]))
                overlap = len(qterms & text_terms) / max(1, len(qterms))
                item = candidates.setdefault(rid, {"row": row, "lexical": 0.0, "semantic": 0.0, "category": 0.0})
                item["lexical"] = max(float(item["lexical"]), overlap)

        # Category recall ("apa yang kusukai?", "tujuanku?") may not share
        # wording with the stored fact, so trusted category matching is allowed.
        if kinds and not qterms:
            marks = ",".join("?" for _ in kinds)
            rows = conn.execute(
                f"SELECT * FROM memories WHERE kind IN ({marks}) ORDER BY confidence DESC,importance DESC,last_used_at DESC LIMIT ?",
                [*sorted(kinds), limit * 10],
            ).fetchall()
            for row in rows:
                trust = self._memory_source_trust(str(row["source"] or ""))
                if trust < 0.85:
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
                (max(100, limit * 24),),
            ).fetchall()
            scored: list[tuple[float, sqlite3.Row]] = []
            for row in rows:
                if self._memory_source_trust(str(row["source"] or "")) <= 0:
                    continue
                vec = self._unpack_vector(row["vector"], int(row["dims"] or 0))
                if vec and len(vec) == len(query_vec):
                    scored.append((self._cosine(query_vec, vec), row))
            scored.sort(key=lambda item: item[0], reverse=True)
            for similarity, row in scored[: limit * 8]:
                if similarity < 0.56:
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
            if trust <= 0:
                continue
            semantic_floor = 0.56 if trust >= 0.85 else 0.64
            if lexical < 0.20 and semantic < semantic_floor and category <= 0:
                continue
            score = (
                0.35 * semantic + 0.31 * lexical + 0.15 * category
                + 0.07 * float(row["importance"] or 0) + 0.06 * float(row["confidence"] or 0)
                + 0.04 * trust + 0.02 * self._age_score(float(row["last_used_at"] or row["created_at"] or 0))
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

replace_method("relevant_beliefs", r'''    def relevant_beliefs(self, query: str, limit: int = 10) -> list[Belief]:
        """Return only beliefs with user-evidence provenance."""
        conn = self._conn()
        limit = max(1, min(int(limit), 20))
        dims = self._query_dimensions(query)
        qterms = self._retrieval_terms(query)
        rows = conn.execute(
            "SELECT * FROM beliefs WHERE contradicted=0 AND confidence>=0.48 "
            "ORDER BY confidence DESC,evidence DESC,updated_at DESC LIMIT 160"
        ).fetchall()
        ranked: list[tuple[float, sqlite3.Row]] = []
        trusted_sources = {"explicit", "furinahub", "manual", "contradiction", "user_evidence", "user_evidence_pattern"}
        for row in rows:
            source = str(row["source"] or "").casefold()
            if source not in trusted_sources:
                continue
            dimension = str(row["dimension"] or "")
            value = str(row["value"] or "")
            terms = self._retrieval_terms(value)
            overlap = len(qterms & terms) / max(1, len(qterms)) if qterms else 0.0
            category = 1.0 if dims and dimension in dims else 0.0
            if dims and dimension not in dims and overlap < 0.20:
                continue
            if not dims and overlap < 0.20:
                continue
            evidence = int(row["evidence"] or 0)
            confidence = float(row["confidence"] or 0)
            if source == "user_evidence_pattern" and evidence < 2:
                continue
            score = (
                0.43 * category + 0.28 * overlap + 0.18 * confidence
                + 0.08 * min(1.0, evidence / 3.0) + 0.03
            )
            ranked.append((score, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [Belief(**dict(row)) for _, row in ranked[:limit]]''')

text = PATH.read_text(encoding="utf-8")
compile(text, str(PATH), "exec")
print("FURINA_PRIVATE_1_0_5_MEMORY_TRUST_OK")
