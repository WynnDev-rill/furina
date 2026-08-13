from __future__ import annotations

import re
import time
from typing import Iterable


_ALLOWED_KINDS = {
    "observation",
    "lesson",
    "preference",
    "opinion",
    "uncertainty",
    "expectation",
    "goal",
    "behavior",
}

_POSITIVE = re.compile(
    r"\b(makasih|terima kasih|bagus|mantap|pas|tepat|benar|berhasil|nah gitu|lanjut|suka jawabanmu)\b",
    re.I,
)
_NEGATIVE = re.compile(
    r"\b(salah|bukan begitu|nggak sesuai|tidak sesuai|jelek|payah|ulang|terlalu panjang|terlalu pendek|jangan begitu|masih gagal)\b",
    re.I,
)


def _clean(text: str, limit: int = 360) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def _key(kind: str, text: str) -> str:
    words = re.findall(r"[\wÀ-ÿ]{3,}", text.casefold(), flags=re.UNICODE)
    return kind + ":" + " ".join(words[:18])


class FurinaMind:
    """Persistent learned self for the companion.

    Core persona is intentionally not writable here. This layer stores only
    experience-derived self-knowledge so Furina can evolve without identity
    drift. Conversation is the primary source; agent performance stays in a
    separate capability ledger and does not define personality.
    """

    STATE_KEY = "furina_mind_v2"
    CURRENT_KEY = "furina_mind_current"
    AGENT_KEY = "furina_agent_capabilities"

    def __init__(self, store):
        self.store = store

    def _load(self) -> list[dict]:
        raw = self.store.get_state(self.STATE_KEY, [])
        return raw if isinstance(raw, list) else []

    def _save(self, rows: list[dict]) -> None:
        rows = sorted(
            rows,
            key=lambda x: (
                float(x.get("confidence", 0.0)),
                int(x.get("evidence", 0)),
                float(x.get("updated_at", 0.0)),
            ),
            reverse=True,
        )[:72]
        self.store.set_state(self.STATE_KEY, rows)

    def record(self, items: Iterable[dict], *, source: str = "reflection") -> None:
        rows = self._load()
        now = time.time()
        by_key = {
            _key(str(r.get("kind") or ""), str(r.get("text") or "")): r
            for r in rows
        }
        for item in items:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").strip().lower()
            text = _clean(item.get("text"))
            if kind not in _ALLOWED_KINDS or len(text) < 8:
                continue
            try:
                confidence = max(
                    0.2, min(0.97, float(item.get("confidence", 0.55) or 0.55))
                )
            except Exception:
                confidence = 0.55
            k = _key(kind, text)
            existing = by_key.get(k)
            if existing:
                n = max(1, int(existing.get("evidence", 1) or 1))
                prior = float(existing.get("confidence", 0.5) or 0.5)
                existing["confidence"] = round(
                    min(0.97, (prior * n + confidence) / (n + 1)), 4
                )
                existing["evidence"] = n + 1
                existing["text"] = text
                existing["updated_at"] = now
                existing["source"] = source[:32]
            else:
                row = {
                    "kind": kind,
                    "text": text,
                    "confidence": round(confidence, 4),
                    "evidence": 1,
                    "source": source[:32],
                    "created_at": now,
                    "updated_at": now,
                }
                rows.append(row)
                by_key[k] = row
        self._save(rows)

    def observe_user_feedback(self, user_text: str) -> None:
        current = self.store.get_state(self.CURRENT_KEY, {})
        if not isinstance(current, dict):
            current = {}
        state = {
            "energy": float(current.get("energy", 0.72) or 0.72),
            "curiosity": float(current.get("curiosity", 0.55) or 0.55),
            "irritation": float(current.get("irritation", 0.04) or 0.04),
            "confidence": float(current.get("confidence", 0.68) or 0.68),
            "engagement": float(current.get("engagement", 0.58) or 0.58),
        }
        text = str(user_text or "")
        if _POSITIVE.search(text):
            state["confidence"] += 0.035
            state["engagement"] += 0.035
            state["irritation"] *= 0.82
        elif _NEGATIVE.search(text):
            state["confidence"] -= 0.045
            state["engagement"] += 0.015
            state["irritation"] += 0.025
        else:
            state["irritation"] *= 0.94
            state["confidence"] += (0.68 - state["confidence"]) * 0.025
        if "?" in text or len(text) > 120:
            state["curiosity"] += 0.018
        else:
            state["curiosity"] += (0.55 - state["curiosity"]) * 0.02
        for key in state:
            state[key] = round(max(0.0, min(1.0, state[key])), 4)
        state["updated_at"] = time.time()
        self.store.set_state(self.CURRENT_KEY, state)

    def record_agent_outcome(self, capability: str, ok: bool, *, ms: int = 0) -> None:
        """Secondary engineering memory; deliberately excluded from identity."""
        raw = self.store.get_state(self.AGENT_KEY, {})
        data = raw if isinstance(raw, dict) else {}
        key = _clean(capability, 80) or "unknown"
        row = data.get(key) if isinstance(data.get(key), dict) else {}
        uses = int(row.get("uses", 0) or 0) + 1
        wins = int(row.get("successes", 0) or 0) + (1 if ok else 0)
        row.update(
            {
                "uses": uses,
                "successes": wins,
                "reliability": round((wins + 1.0) / (uses + 2.0), 4),
                "last_ms": max(0, int(ms)),
                "updated_at": time.time(),
            }
        )
        data[key] = row
        if len(data) > 96:
            data = dict(
                sorted(
                    data.items(),
                    key=lambda kv: float(kv[1].get("updated_at", 0)),
                    reverse=True,
                )[:72]
            )
        self.store.set_state(self.AGENT_KEY, data)

    def current_context(self) -> str:
        current = self.store.get_state(self.CURRENT_KEY, {})
        if not isinstance(current, dict) or not current:
            return "state internal stabil; belum ada perubahan penting"
        keys = ("energy", "curiosity", "irritation", "confidence", "engagement")
        return "; ".join(
            f"{k}={float(current.get(k, 0.0)):.2f}" for k in keys
        )

    def context(self, limit: int = 10) -> str:
        rows = self._load()
        if not rows:
            return "(belum ada learned-self yang cukup kuat)"
        priority = {
            "uncertainty": 1.10,
            "lesson": 1.08,
            "behavior": 1.05,
            "opinion": 1.02,
            "preference": 1.02,
            "expectation": 1.0,
            "goal": 0.98,
            "observation": 0.92,
        }
        now = time.time()

        def score(row: dict) -> float:
            age_days = max(
                0.0,
                (now - float(row.get("updated_at", now) or now)) / 86400.0,
            )
            recency = 1.0 / (1.0 + age_days / 45.0)
            return priority.get(str(row.get("kind")), 0.9) * (
                0.55 * float(row.get("confidence", 0.5) or 0.5)
                + 0.25 * min(1.0, int(row.get("evidence", 1) or 1) / 4.0)
                + 0.20 * recency
            )

        selected = sorted(rows, key=score, reverse=True)[
            : max(3, min(int(limit), 14))
        ]
        lines = ["learned self (pengalaman, bukan identitas inti):"]
        for row in selected:
            lines.append(
                f"- {row.get('kind')}: {row.get('text')} "
                f"[conf={float(row.get('confidence', 0.5)):.2f}; "
                f"evidence={int(row.get('evidence', 1))}]"
            )
        return "\n".join(lines)[:3600]
