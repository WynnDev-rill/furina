from __future__ import annotations

import math
import time


class CharacterSelfState:
    """Small, expiring character state; never a second user-memory store."""

    KEY = "character_self_state_v129"
    EMOTIONS = {
        "neutral", "warm", "shy", "nervous", "curious", "amused",
        "relieved", "careful", "lightly_annoyed", "concerned",
    }
    STANCES = {"open", "reserved", "playful", "gentle", "direct", "careful"}

    def __init__(self, store):
        self.store = store

    def current(self, turn: int | None = None) -> dict:
        raw = self.store.get_state(self.KEY, {}) or {}
        if not isinstance(raw, dict):
            return {}
        now = time.time()
        updated = float(raw.get("updated_at", 0) or 0)
        expires_turn = int(raw.get("expires_turn", 0) or 0)
        current_turn = int(turn if turn is not None else self.store.get_state("companion_turns", 0) or 0)
        if not updated or now - updated > 21600 or (expires_turn and current_turn > expires_turn):
            return {}
        age_hours = max(0.0, (now - updated) / 3600.0)
        intensity = max(0.0, min(1.0, float(raw.get("intensity", 0) or 0))) * math.exp(-age_hours / 3.0)
        if intensity < .10:
            return {}
        return {
            "emotion": str(raw.get("emotion") or "neutral"),
            "stance": str(raw.get("stance") or "open"),
            "intensity": round(intensity, 2),
            "confidence": round(max(0.0, min(1.0, float(raw.get("confidence", 0) or 0))), 2),
            "expires_turn": expires_turn,
        }

    def prompt_context(self) -> str:
        state = self.current()
        if not state:
            return "(tidak ada keadaan karakter sementara yang masih relevan)"
        return (
            f"emotion={state['emotion']}; stance={state['stance']}; "
            f"intensity={state['intensity']:.2f}; confidence={state['confidence']:.2f}. "
            "Ini keadaan ekspresi karakter, bukan fakta tentang user dan bukan izin membuat adegan."
        )

    def update(self, candidate: dict, *, source_message_id: int | None, turn: int) -> None:
        if not isinstance(candidate, dict):
            return
        emotion = str(candidate.get("emotion") or "neutral").strip().casefold()
        stance = str(candidate.get("stance") or "open").strip().casefold()
        try:
            intensity = max(0.0, min(1.0, float(candidate.get("intensity", 0))))
            confidence = max(0.0, min(1.0, float(candidate.get("confidence", 0))))
            ttl = max(1, min(6, int(candidate.get("ttl_turns", 2))))
        except (TypeError, ValueError):
            return
        if emotion not in self.EMOTIONS or stance not in self.STANCES or confidence < .58:
            return
        self.store.set_state(self.KEY, {
            "schema": 1,
            "emotion": emotion,
            "stance": stance,
            "intensity": round(intensity, 3),
            "confidence": round(confidence, 3),
            "source_message_id": int(source_message_id) if source_message_id else None,
            "updated_at": time.time(),
            "expires_turn": int(turn) + ttl,
        })

