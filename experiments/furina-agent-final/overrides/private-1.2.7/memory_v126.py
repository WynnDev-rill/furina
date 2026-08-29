from __future__ import annotations

import re
import time


def install_memory_v126(ns: dict) -> None:
    MemoryStore = ns["MemoryStore"]
    base_claims = ns["_furina_120_claims"]
    base_record = ns["_furina_120_record_claims"]
    base_active = ns["_furina_120_active_claims"]
    base_extract = ns["extract_explicit_memories"]
    base_add_message = MemoryStore.add_message

    def claims(text: str):
        out = list(base_claims(text))
        clean = " ".join(str(text or "").strip().split())
        extra = (
            ("profile:work", r"\b(?:aku|saya)\s+(?:adalah|seorang)\s+([^,.!?]{2,100})", .92),
            ("profile:study", r"\b(?:aku|saya)\s+(?:kuliah|sekolah|belajar)\s+(?:di|sebagai|jurusan)?\s*([^,.!?]{2,110})", .90),
            ("profile:pet", r"\b(?:aku|saya)\s+(?:punya|memiliki)\s+(?:seekor\s+)?(kucing|anjing|burung|kelinci|hewan peliharaan)(?:\s+bernama\s+([^,.!?]{2,50}))?", .92),
            ("profile:birthday", r"\b(?:ulang tahunku|ulang tahun saya)\s+(?:tanggal\s+)?([^,.!?]{2,60})", .94),
            ("goal:project", r"\b(?:aku|saya)\s+(?:sedang|lagi)\s+(?:mengerjakan|membuat|membangun)\s+([^,.!?]{3,140})", .86),
        )
        existing = {x[0] for x in out}
        for slot, pattern, confidence in extra:
            match = re.search(pattern, clean, re.I)
            if not match or slot in existing:
                continue
            value = " ".join(x for x in match.groups() if x).strip()
            if value:
                out.append((slot, value, confidence))
        return out[:10]

    def record_claims(self, user_text: str, source_message_id=None):
        # Structured explicit facts are safe even when raw full-history archive
        # is disabled. This path is independent and does not mutate a process-
        # global feature flag, so concurrent chats cannot affect one another.
        source_message_id = source_message_id or self.last_user_message_id(user_text)
        if not source_message_id:
            return []
        conn = self._conn(); now = time.time(); written = []
        normalize_value = ns["_furina_120_norm"]
        for slot, value, confidence in claims(user_text):
            normalized = normalize_value(value)
            current = conn.execute(
                "SELECT * FROM memory_claims_120 WHERE slot=? AND status='active' ORDER BY updated_at DESC LIMIT 1", (slot,)
            ).fetchone()
            if current and str(current["normalized_value"]) == normalized:
                updated = min(.99, max(float(current["confidence"]), confidence) + .015)
                conn.execute("UPDATE memory_claims_120 SET confidence=?,updated_at=? WHERE id=?", (updated, now, int(current["id"])))
                written.append(int(current["id"])); continue
            replaced = int(current["id"]) if current else None
            if current:
                conn.execute("UPDATE memory_claims_120 SET status='superseded',updated_at=? WHERE id=?", (now, replaced))
            cur = conn.execute(
                "INSERT OR IGNORE INTO memory_claims_120(slot,value,normalized_value,confidence,status,source_message_id,replaces_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (slot, str(value)[:300], normalized, float(confidence), "active", int(source_message_id), replaced, now, now),
            )
            if cur.lastrowid:
                written.append(int(cur.lastrowid))
        conn.commit(); return written

    def active_claims(self, query: str = "", limit: int = 4):
        qterms = self._retrieval_terms(query); dims = self._query_dimensions(query)
        rows = self._conn().execute(
            "SELECT * FROM memory_claims_120 WHERE status='active' ORDER BY confidence DESC,updated_at DESC LIMIT 80"
        ).fetchall(); ranked = []
        for row in rows:
            slot = str(row["slot"]); terms = self._retrieval_terms(str(row["value"]))
            overlap = len(qterms & terms) / max(1, len(qterms)) if qterms else 0.0
            category = 1.0 if any(slot.startswith(dim + ":") or slot == dim for dim in dims) else 0.0
            if overlap < .20 and category <= 0: continue
            score = .60 * overlap + .25 * category + .15 * float(row["confidence"])
            ranked.append((score, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [{**dict(row), "score": round(score, 4), "citation": f"msg#{int(row['source_message_id'])}"} for score, row in ranked[:max(1, min(int(limit), 6))]]

    def continuity_capsule(self, limit: int = 8) -> list[dict]:
        conn = self._conn()
        rows = [dict(row) for row in conn.execute(
            "SELECT slot,value,confidence,source_message_id,updated_at FROM memory_claims_120 "
            "WHERE status='active' AND confidence>=.84 ORDER BY confidence DESC,updated_at DESC LIMIT 40"
        ).fetchall()]
        known = {(str(row["slot"]), str(row["value"]).casefold()) for row in rows}
        for row in conn.execute(
            "SELECT dimension,value,confidence,updated_at FROM beliefs WHERE contradicted=0 "
            "AND source='explicit' AND confidence>=.72 AND dimension IN ('identity','profile','preference','goal') "
            "ORDER BY confidence DESC,updated_at DESC LIMIT 30"
        ).fetchall():
            item = {"slot": "belief:" + str(row["dimension"]), "value": str(row["value"]), "confidence": float(row["confidence"]), "source_message_id": 0, "updated_at": float(row["updated_at"])}
            key = (item["slot"], item["value"].casefold())
            if key not in known: known.add(key); rows.append(item)
        for row in conn.execute(
            "SELECT text,kind,confidence,updated_at FROM memories WHERE source='explicit' AND confidence>=.72 "
            "ORDER BY confidence DESC,updated_at DESC LIMIT 30"
        ).fetchall():
            item = {"slot": "memory:" + str(row["kind"]), "value": str(row["text"]), "confidence": float(row["confidence"]), "source_message_id": 0, "updated_at": float(row["updated_at"])}
            key = (item["slot"], item["value"].casefold())
            if key not in known: known.add(key); rows.append(item)
        priority = ("identity:", "profile:", "preference:", "goal:")
        ordered = sorted(rows, key=lambda row: (next((i for i, key in enumerate(priority) if str(row['slot']).startswith(key)), 9), -float(row["confidence"])))
        return ordered[:max(1, min(int(limit), 12))]

    def add_message(self, role: str, content: str, attachment=None):
        message_id = base_add_message(self, role, content, attachment)
        if str(role) == "user" and claims(content) and not ns["_furina_120_enabled"]():
            record_claims(self, str(content), int(message_id))
        return message_id

    def extract(text: str):
        seen = set()
        for item in base_extract(text):
            key = (str(item[0]).casefold(), str(item[1]))
            if key not in seen:
                seen.add(key); yield item
        for slot, value, confidence in claims(text):
            rendered = f"{slot.split(':', 1)[-1]}: {value}"
            kind = "preference" if slot.startswith("preference:") else "goal" if slot.startswith("goal:") else "identity" if slot.startswith("identity:") else "profile"
            key = (rendered.casefold(), kind)
            if key not in seen:
                seen.add(key); yield (rendered, kind, min(.96, confidence))

    ns["_furina_120_claims"] = claims
    ns["extract_explicit_memories"] = extract
    MemoryStore.record_claims = record_claims
    MemoryStore.active_claims = active_claims
    MemoryStore.continuity_capsule = continuity_capsule
    MemoryStore.add_message = add_message
