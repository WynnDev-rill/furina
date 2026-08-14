from __future__ import annotations

import time

from .psyche import PsycheEngine


class FurinaMind:
    """Compatibility facade for pre-RC33 callers.

    Psychological truth now lives only in PsycheEngine. Agent capability
    reliability remains separate and cannot mutate personality.
    """

    AGENT_KEY = "furina_agent_capabilities"

    def __init__(self, store):
        self.store = store
        self.psyche = PsycheEngine(store)

    def record(self, items, *, source: str = "reflection") -> None:
        self.psyche.record_self_items(items)

    def observe_user_feedback(self, user_text: str) -> None:
        self.psyche.observe_user(user_text)

    def record_agent_outcome(self, capability: str, ok: bool, *, ms: int = 0) -> None:
        raw = self.store.get_state(self.AGENT_KEY, {})
        data = raw if isinstance(raw, dict) else {}
        key = " ".join(str(capability or "unknown").split())[:80] or "unknown"
        row = data.get(key) if isinstance(data.get(key), dict) else {}
        uses = int(row.get("uses", 0) or 0) + 1
        wins = int(row.get("successes", 0) or 0) + (1 if ok else 0)
        row.update(
            uses=uses,
            successes=wins,
            reliability=round((wins + 1.0) / (uses + 2.0), 4),
            last_ms=max(0, int(ms)),
            updated_at=time.time(),
        )
        data[key] = row
        if len(data) > 96:
            data = dict(
                sorted(
                    data.items(),
                    key=lambda kv: float(kv[1].get("updated_at", 0.0)),
                    reverse=True,
                )[:72]
            )
        self.store.set_state(self.AGENT_KEY, data)

    def current_context(self) -> str:
        return self.psyche.current_context()

    def context(self, limit: int = 10) -> str:
        return self.psyche.context(limit)
