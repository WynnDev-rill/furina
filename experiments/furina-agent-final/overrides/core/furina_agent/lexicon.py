from __future__ import annotations

import json
import math
import re
import time
import unicodedata


_COMMON = {
    "aku", "kamu", "dia", "mereka", "kami", "kita", "ini", "itu", "yang", "dan", "atau", "tapi", "namun",
    "untuk", "dari", "dengan", "pada", "ke", "di", "jadi", "karena", "kalau", "jika", "bisa", "dapat", "akan",
    "sudah", "belum", "masih", "juga", "saja", "aja", "lebih", "kurang", "sangat", "agak", "seperti", "kayak",
    "apa", "siapa", "kenapa", "mengapa", "bagaimana", "mana", "kapan", "ada", "tidak", "tak", "iya", "ya",
    "sebuah", "suatu", "hal", "orang", "buat", "bikin", "mau", "ingin", "coba", "tolong", "terus", "lalu",
    "the", "and", "for", "with", "from", "this", "that", "you", "your", "are", "was", "were", "have", "has",
}

_SENSITIVE = re.compile(
    r"(?:password|passwd|kata\s*sandi|api[ _-]?key|secret|token|otp|pin|private[ _-]?key|bearer)\b",
    re.I,
)
_EMAIL_OR_URL = re.compile(r"(?:https?://|www\.|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b)", re.I)
_EXPLICIT = [
    re.compile(r"\b(?:pakai|gunakan|pake|gunakanlah)\s+(?:kata|istilah|frasa|kosakata)\s*[\"'“”]?(.{1,80}?)[\"'“”]?(?:[.!?,]|$)", re.I),
    re.compile(r"\b(?:biasakan|coba)\s+(?:pakai|bilang|gunakan)\s*[\"'“”](.{1,80}?)[\"'“”]", re.I),
    re.compile(r"\baku\s+(?:biasa|sering)\s+(?:bilang|pakai|ngomong)\s*[\"'“”](.{1,80}?)[\"'“”]", re.I),
]


def canonicalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = re.sub(r"\s+", " ", value).strip()
    value = value.strip(" \t\r\n.,!?;:()[]{}<>\"'“”‘’`~")
    return value[:120]


def context_tag(profile_name: str, user_text: str) -> str:
    name = str(profile_name or "").upper()
    low = str(user_text or "").casefold()
    if name == "SHARP" or re.search(r"\b(?:bug|kode|api|model|error|build|repo|github|termux)\b", low):
        return "technical"
    if name == "CLOSE" or re.search(r"\b(?:sedih|capek|kecewa|marah|takut|cemas|senang|rindu)\b", low):
        return "emotional"
    if re.search(r"\b(?:wkwk|haha|lol|ngakak|becanda|bercanda|nyebelin|sarkas)\b", low):
        return "banter"
    return "casual"


def _tokens(text: str) -> list[str]:
    clean = _EMAIL_OR_URL.sub(" ", unicodedata.normalize("NFKC", str(text or "")))
    return [x for x in re.findall(r"[^\W\d_][^\W_]{1,28}", clean, flags=re.UNICODE) if x]


class PersonalLexicon:
    """Local user-vocabulary model with canonical deduplication.

    Lightweight test/router stores do not necessarily expose the persistent
    SQLite connection. In that case this component becomes a clean no-op rather
    than making the whole companion session depend on optional lexical memory.
    """

    def __init__(self, store):
        self.store = store
        self.available = callable(getattr(store, "_conn", None))
        if self.available:
            self._ensure_schema()

    def _conn(self):
        if not self.available:
            raise RuntimeError("persistent lexicon store unavailable")
        return self.store._conn()

    def _ensure_schema(self) -> None:
        conn = self._conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS personal_lexicon (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              canonical TEXT NOT NULL UNIQUE,
              surface TEXT NOT NULL,
              kind TEXT NOT NULL DEFAULT 'word',
              contexts_json TEXT NOT NULL DEFAULT '{}',
              seen_count INTEGER NOT NULL DEFAULT 1,
              explicit_count INTEGER NOT NULL DEFAULT 0,
              used_count INTEGER NOT NULL DEFAULT 0,
              confidence REAL NOT NULL DEFAULT 0.20,
              first_seen_at REAL NOT NULL,
              last_seen_at REAL NOT NULL,
              last_used_at REAL NOT NULL DEFAULT 0
            );
            CREATE UNIQUE INDEX IF NOT EXISTS personal_lexicon_canonical_idx ON personal_lexicon(canonical);
            CREATE INDEX IF NOT EXISTS personal_lexicon_rank_idx ON personal_lexicon(explicit_count,seen_count,last_seen_at);
            """
        )
        conn.commit()

    @staticmethod
    def _safe_surface(text: str) -> str:
        value = " ".join(str(text or "").split()).strip(" \t\r\n.,!?;:()[]{}<>\"'“”‘’`")
        return value[:120]

    def _upsert(self, surface: str, *, context: str, explicit: bool, kind: str) -> bool:
        if not self.available:
            return False
        surface = self._safe_surface(surface)
        key = canonicalize(surface)
        if not key or len(key) < 2 or _SENSITIVE.search(surface) or _EMAIL_OR_URL.search(surface):
            return False
        if key.isdigit() or len(key) > 120:
            return False
        now = time.time()
        conn = self._conn()
        row = conn.execute("SELECT * FROM personal_lexicon WHERE canonical=?", (key,)).fetchone()
        if row:
            try:
                contexts = json.loads(row["contexts_json"] or "{}")
            except Exception:
                contexts = {}
            contexts[str(context)] = min(100000, int(contexts.get(str(context), 0) or 0) + 1)
            seen = int(row["seen_count"] or 0) + 1
            explicit_count = int(row["explicit_count"] or 0) + (1 if explicit else 0)
            confidence = min(0.99, float(row["confidence"] or 0.2) + (0.18 if explicit else 0.035))
            preferred = surface if explicit or len(surface) >= len(str(row["surface"] or "")) else str(row["surface"])
            conn.execute(
                "UPDATE personal_lexicon SET surface=?,kind=?,contexts_json=?,seen_count=?,explicit_count=?,confidence=?,last_seen_at=? WHERE id=?",
                (preferred, kind, json.dumps(contexts, ensure_ascii=False), seen, explicit_count, confidence, now, int(row["id"])),
            )
        else:
            contexts = {str(context): 1}
            conn.execute(
                "INSERT INTO personal_lexicon(canonical,surface,kind,contexts_json,seen_count,explicit_count,used_count,confidence,first_seen_at,last_seen_at,last_used_at) VALUES(?,?,?,?,1,?,0,?,?,?,0)",
                (key, surface, kind, json.dumps(contexts, ensure_ascii=False), 1 if explicit else 0, 0.72 if explicit else 0.20, now, now),
            )
        conn.commit()
        return True

    def observe(self, user_text: str, profile_name: str = "CASUAL") -> int:
        if not self.available:
            return 0
        text = str(user_text or "").strip()
        if not text:
            return 0
        ctx = context_tag(profile_name, text)
        learned = 0
        explicit_values: set[str] = set()
        for rx in _EXPLICIT:
            for match in rx.finditer(text):
                value = self._safe_surface(match.group(1))
                if value and self._upsert(value, context=ctx, explicit=True, kind="phrase" if " " in value else "word"):
                    explicit_values.add(canonicalize(value))
                    learned += 1

        if _SENSITIVE.search(text) or len(text) > 1800:
            return learned

        toks = _tokens(text)
        normalized = [(tok, canonicalize(tok)) for tok in toks]
        useful = [(tok, key) for tok, key in normalized if key and key not in _COMMON and 3 <= len(key) <= 28]
        for tok, key in useful[:8]:
            if key in explicit_values:
                continue
            if self._upsert(tok, context=ctx, explicit=False, kind="word"):
                learned += 1

        surfaces = [tok for tok, key in normalized if key and key not in _COMMON]
        seen_phrase: set[str] = set()
        for width in (2, 3):
            for i in range(max(0, len(surfaces) - width + 1)):
                phrase = " ".join(surfaces[i:i + width])
                key = canonicalize(phrase)
                if key in seen_phrase or len(key) > 64:
                    continue
                seen_phrase.add(key)
                if key in explicit_values:
                    continue
                if self._upsert(phrase, context=ctx, explicit=False, kind="phrase"):
                    learned += 1
                if len(seen_phrase) >= 8:
                    break
            if len(seen_phrase) >= 8:
                break
        self._prune_if_needed()
        return learned

    def _prune_if_needed(self) -> None:
        if not self.available:
            return
        conn = self._conn()
        total = int(conn.execute("SELECT count(*) FROM personal_lexicon").fetchone()[0])
        if total <= 1800:
            return
        cutoff = time.time() - 45 * 86400
        conn.execute(
            "DELETE FROM personal_lexicon WHERE id IN (SELECT id FROM personal_lexicon WHERE explicit_count=0 AND seen_count<2 AND last_seen_at<? ORDER BY last_seen_at ASC LIMIT ?)",
            (cutoff, min(300, total - 1500)),
        )
        conn.commit()

    def relevant(self, user_text: str, profile_name: str = "CASUAL", limit: int = 8, auto_min_seen: int = 2) -> list[dict]:
        if not self.available:
            return []
        limit = max(1, min(int(limit), 16))
        ctx = context_tag(profile_name, user_text)
        query_words = {canonicalize(x) for x in _tokens(user_text) if canonicalize(x)}
        rows = self._conn().execute(
            "SELECT * FROM personal_lexicon WHERE explicit_count>0 OR seen_count>=? ORDER BY explicit_count DESC,seen_count DESC,last_seen_at DESC LIMIT 220",
            (max(2, int(auto_min_seen)),),
        ).fetchall()
        now = time.time()
        scored: list[tuple[float, object]] = []
        for row in rows:
            try:
                contexts = json.loads(row["contexts_json"] or "{}")
            except Exception:
                contexts = {}
            seen = max(1, int(row["seen_count"] or 1))
            explicit = int(row["explicit_count"] or 0)
            confidence = float(row["confidence"] or 0.0)
            age_days = max(0.0, (now - float(row["last_seen_at"] or now)) / 86400.0)
            recency = math.exp(-age_days / 45.0)
            context_hits = int(contexts.get(ctx, 0) or 0)
            context_score = min(1.0, context_hits / max(1.0, seen * 0.55))
            lex_words = set(str(row["canonical"] or "").split())
            topical = len(query_words & lex_words) / max(1, len(lex_words))
            score = (
                0.30 * min(1.0, explicit / 2.0)
                + 0.22 * min(1.0, math.log1p(seen) / 3.0)
                + 0.18 * confidence
                + 0.15 * context_score
                + 0.08 * recency
                + 0.07 * topical
            )
            if score >= 0.23:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [dict(row) | {"score": round(score, 3)} for score, row in scored[:limit]]

    def prompt_context(self, user_text: str, profile_name: str = "CASUAL", limit: int = 8, auto_min_seen: int = 2) -> str:
        if not self.available:
            return "(personal lexicon tidak tersedia untuk sesi ini)"
        rows = self.relevant(user_text, profile_name, limit, auto_min_seen)
        if not rows:
            return "(belum ada kosakata personal yang cukup kuat)"
        words = [str(row.get("surface") or "") for row in rows if str(row.get("surface") or "").strip()]
        text = ", ".join(f'"{x}"' for x in words)[:520]
        return (
            "Pilihan kata/frasa yang terasa akrab bagi pengguna: " + text + ". "
            "Gunakan paling banyak 1-2 bila benar-benar alami untuk konteks ini. Jangan memaksakan, jangan meniru typo, "
            "dan jangan mengubah identitas atau emosi Furina hanya agar mirip pengguna."
        )

    def mark_used(self, assistant_text: str, candidates: list[dict] | None = None) -> int:
        if not self.available:
            return 0
        low = canonicalize(assistant_text)
        if not low:
            return 0
        rows = candidates or self.relevant(assistant_text, "CASUAL", 20, 2)
        used_ids: list[int] = []
        for row in rows:
            key = str(row.get("canonical") or "")
            if key and re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", low, re.I):
                used_ids.append(int(row["id"]))
        if used_ids:
            now = time.time()
            self._conn().executemany(
                "UPDATE personal_lexicon SET used_count=used_count+1,last_used_at=? WHERE id=?",
                [(now, rid) for rid in used_ids[:20]],
            )
            self._conn().commit()
        return len(used_ids)

    def count(self) -> int:
        if not self.available:
            return 0
        return int(self._conn().execute("SELECT count(*) FROM personal_lexicon").fetchone()[0])
