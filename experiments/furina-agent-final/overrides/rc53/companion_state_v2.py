from __future__ import annotations

import math
import re
import time


_POSITIVE = re.compile(r"\b(makasih|terima kasih|bagus|mantap|pas|tepat|benar|berhasil|suka|senang|hebat|nice|good)\b", re.I)
_NEGATIVE = re.compile(r"\b(salah|bukan begitu|tidak sesuai|nggak sesuai|jelek|payah|gagal|kesal|marah|kecewa|ulang|buruk)\b", re.I)
_AFFECTION = re.compile(r"\b(sayang|kangen|rindu|cinta|dekat|teman|temen|percaya|nyaman|care|miss you|love you)\b", re.I)
_PLAY = re.compile(r"\b(wkwk+|haha+|hehe+|lol|becanda|bercanda|goda|jahil|lucu)\b", re.I)
_CONCERN = re.compile(r"\b(sedih|takut|cemas|khawatir|capek|lelah|sakit|sendiri|kesepian|stress|stres|putus asa)\b", re.I)
_CORRECTION = re.compile(r"\b(salah|bukan begitu|maksudku|maksud saya|koreksi|ulang|jangan begitu)\b", re.I)
_QUESTION = re.compile(r"[?？]")

_BASE = {
    "valence": 0.54,
    "arousal": 0.42,
    "irritation": 0.05,
    "curiosity": 0.56,
    "social_energy": 0.72,
    "fatigue": 0.08,
    "trust": 0.48,
    "comfort": 0.46,
    "attachment": 0.34,
    "playfulness": 0.44,
    "tension": 0.08,
}

_HALF_LIFE_HOURS = {
    "valence": 18.0,
    "arousal": 2.5,
    "irritation": 3.5,
    "curiosity": 8.0,
    "social_energy": 6.0,
    "fatigue": 4.0,
    "trust": 720.0,
    "comfort": 480.0,
    "attachment": 960.0,
    "playfulness": 12.0,
    "tension": 5.0,
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _clean(text: str, limit: int = 220) -> str:
    return " ".join(str(text or "").split())[:limit]


class CompanionStateV2:
    """Persistent low-cost companion state kept outside the LLM."""

    STATE_KEY = "companion_state_v2"
    DIARY_KEY = "companion_diary_v2"
    LAST_USER_KEY = "companion_last_user_at"

    def __init__(self, store):
        self.store = store

    def _load(self, now: float | None = None) -> dict:
        now = float(now or time.time())
        raw = self.store.get_state(self.STATE_KEY, {})
        state = dict(raw) if isinstance(raw, dict) else {}
        for key, default in _BASE.items():
            try:
                state[key] = _clamp(float(state.get(key, default)))
            except Exception:
                state[key] = default
        state["updated_at"] = float(state.get("updated_at", now) or now)
        state["turns"] = max(0, int(state.get("turns", 0) or 0))
        causes = state.get("causes")
        state["causes"] = causes[-8:] if isinstance(causes, list) else []
        return self._decay(state, now)

    def _save(self, state: dict, now: float | None = None) -> None:
        state["updated_at"] = float(now or time.time())
        state["causes"] = list(state.get("causes") or [])[-8:]
        self.store.set_state(self.STATE_KEY, state)

    @staticmethod
    def _decay(state: dict, now: float) -> dict:
        elapsed_h = max(0.0, (now - float(state.get("updated_at", now) or now)) / 3600.0)
        if elapsed_h <= 0.0001:
            return state
        for key, base in _BASE.items():
            current = float(state.get(key, base) or base)
            retain = math.pow(0.5, elapsed_h / _HALF_LIFE_HOURS[key])
            state[key] = _clamp(base + (current - base) * retain)
        state["social_energy"] = _clamp(state["social_energy"] + min(0.20, elapsed_h * 0.018))
        state["fatigue"] = _clamp(state["fatigue"] - min(0.28, elapsed_h * 0.035))
        state["updated_at"] = now
        return state

    @staticmethod
    def _nudge(state: dict, key: str, delta: float) -> None:
        state[key] = _clamp(float(state.get(key, _BASE[key])) + delta)

    def _cause(self, state: dict, kind: str, reason: str, weight: float, now: float) -> None:
        causes = list(state.get("causes") or [])
        causes.append({
            "kind": str(kind)[:32],
            "reason": _clean(reason, 140),
            "weight": round(_clamp(weight), 3),
            "at": now,
        })
        state["causes"] = causes[-8:]

    def _append_diary(self, kind: str, note: str, weight: float, now: float) -> None:
        note = _clean(note, 260)
        if not note:
            return
        raw = self.store.get_state(self.DIARY_KEY, [])
        rows = list(raw) if isinstance(raw, list) else []
        candidate = {"kind": str(kind)[:32], "note": note, "weight": round(_clamp(weight), 3), "at": now}
        if rows and isinstance(rows[-1], dict) and rows[-1].get("kind") == candidate["kind"] and rows[-1].get("note") == note:
            rows[-1]["at"] = now
            rows[-1]["weight"] = max(float(rows[-1].get("weight", 0.0) or 0.0), candidate["weight"])
        else:
            rows.append(candidate)
        self.store.set_state(self.DIARY_KEY, rows[-24:])

    def before_user(self, text: str, now: float | None = None) -> dict:
        now = float(now or time.time())
        text = str(text or "")
        state = self._load(now)
        try:
            previous = float(self.store.get_state(self.LAST_USER_KEY, 0.0) or 0.0)
        except Exception:
            previous = 0.0
        gap_h = max(0.0, (now - previous) / 3600.0) if previous > 0 else 0.0
        state["last_gap_hours"] = gap_h

        if gap_h >= 6.0:
            self._nudge(state, "curiosity", min(0.10, 0.02 + gap_h / 240.0))
            self._nudge(state, "social_energy", 0.06)
            self._cause(state, "return", f"user kembali setelah sekitar {gap_h:.1f} jam", min(1.0, gap_h / 48.0), now)
            self._append_diary("return", f"User kembali setelah jeda sekitar {gap_h:.1f} jam.", min(1.0, gap_h / 48.0), now)

        positive = bool(_POSITIVE.search(text))
        negative = bool(_NEGATIVE.search(text))
        affection = bool(_AFFECTION.search(text))
        playful = bool(_PLAY.search(text))
        concern = bool(_CONCERN.search(text))
        correction = bool(_CORRECTION.search(text))

        self._nudge(state, "arousal", 0.018 if len(text) > 140 else 0.006)
        self._nudge(state, "curiosity", 0.022 if _QUESTION.search(text) else 0.006)
        self._nudge(state, "social_energy", -0.006)
        self._nudge(state, "fatigue", 0.004)

        if positive:
            self._nudge(state, "valence", 0.055)
            self._nudge(state, "trust", 0.012)
            self._nudge(state, "comfort", 0.018)
            self._nudge(state, "irritation", -0.035)
            self._cause(state, "positive_feedback", "user memberi respons positif", 0.55, now)
        if negative:
            self._nudge(state, "valence", -0.055)
            self._nudge(state, "tension", 0.050)
            self._nudge(state, "irritation", 0.045)
            self._nudge(state, "comfort", -0.012)
            self._cause(state, "negative_feedback", "user menunjukkan ketidakpuasan atau koreksi", 0.62, now)
        if correction:
            self._nudge(state, "curiosity", 0.035)
            self._append_diary("correction", "User mengoreksi respons; respons berikut perlu lebih presisi dan tidak defensif.", 0.65, now)
        if affection:
            self._nudge(state, "attachment", 0.022)
            self._nudge(state, "trust", 0.014)
            self._nudge(state, "comfort", 0.025)
            self._cause(state, "closeness", "interaksi menunjukkan kedekatan atau kepercayaan", 0.58, now)
        if playful:
            self._nudge(state, "playfulness", 0.07)
            self._nudge(state, "valence", 0.025)
        if concern:
            self._nudge(state, "playfulness", -0.055)
            self._nudge(state, "tension", 0.025)
            self._nudge(state, "curiosity", 0.028)
            self._cause(state, "user_concern", "user menyampaikan keadaan yang perlu ditanggapi lebih peka", 0.7, now)

        try:
            rel = self.store.relationship_state()
        except Exception:
            rel = {}
        if isinstance(rel, dict):
            for dest, src, weight in (
                ("trust", "trust", 0.12),
                ("playfulness", "playfulness", 0.10),
                ("comfort", "closeness", 0.08),
                ("attachment", "closeness", 0.05),
            ):
                try:
                    observed = _clamp(float(rel.get(src, state[dest]) or state[dest]))
                    state[dest] = _clamp(state[dest] * (1.0 - weight) + observed * weight)
                except Exception:
                    pass

        self.store.set_state(self.LAST_USER_KEY, now)
        self._save(state, now)
        return state

    def after_turn(self, user_text: str, answer: str, now: float | None = None) -> None:
        now = float(now or time.time())
        state = self._load(now)
        state["turns"] = int(state.get("turns", 0) or 0) + 1
        answer_len = len(str(answer or ""))
        self._nudge(state, "fatigue", min(0.018, answer_len / 90000.0))
        self._nudge(state, "social_energy", -min(0.014, answer_len / 120000.0))
        if len(str(user_text or "")) >= 220:
            self._nudge(state, "curiosity", 0.010)
        if state["turns"] % 8 == 0:
            self._append_diary(
                "continuity",
                "Percakapan berlanjut cukup panjang; pertahankan continuity dan jangan mengulang pengenalan atau fakta yang sudah mapan.",
                0.45,
                now,
            )
        self._save(state, now)

    def maintenance(self, now: float | None = None) -> None:
        now = float(now or time.time())
        state = self._load(now)
        self._save(state, now)

    @staticmethod
    def _band(value: float, low: str, mid: str, high: str) -> str:
        return high if value >= 0.68 else mid if value >= 0.38 else low

    def context(self, now: float | None = None) -> str:
        now = float(now or time.time())
        state = self._load(now)
        gap_h = float(state.get("last_gap_hours", 0.0) or 0.0)
        mood = self._band(state["valence"], "agak negatif", "stabil/netral", "positif")
        energy = self._band(state["social_energy"], "rendah", "cukup", "tinggi")
        tension = self._band(state["tension"], "tenang", "sedikit tegang", "tegang")
        curiosity = self._band(state["curiosity"], "rendah", "aktif", "sangat aktif")
        closeness = self._band((state["trust"] + state["comfort"] + state["attachment"]) / 3.0, "menjaga jarak", "cukup dekat", "dekat")
        play = self._band(state["playfulness"], "serius", "fleksibel", "playful")

        causes = []
        for item in list(state.get("causes") or [])[-4:]:
            if not isinstance(item, dict):
                continue
            age_h = max(0.0, (now - float(item.get("at", now) or now)) / 3600.0)
            if age_h <= 24.0:
                reason = _clean(item.get("reason"), 120)
                if reason:
                    causes.append(reason)

        diary_raw = self.store.get_state(self.DIARY_KEY, [])
        diary = []
        if isinstance(diary_raw, list):
            for item in diary_raw[-3:]:
                if isinstance(item, dict) and _clean(item.get("note"), 160):
                    diary.append(_clean(item.get("note"), 160))

        time_note = "tidak ada jeda panjang yang relevan"
        if gap_h >= 24:
            time_note = f"user kembali setelah sekitar {gap_h/24.0:.1f} hari"
        elif gap_h >= 6:
            time_note = f"user kembali setelah sekitar {gap_h:.1f} jam"

        lines = [
            "STATE COMPANION PERSISTEN (internal; jangan menyebut angka/state ini kepada user):",
            f"- suasana={mood}; energi sosial={energy}; ketegangan={tension}; rasa ingin tahu={curiosity}",
            f"- kedekatan={closeness}; gaya sosial={play}; waktu={time_note}",
        ]
        if causes:
            lines.append("- penyebab state terbaru: " + " | ".join(causes))
        if diary:
            lines.append("- continuity notes: " + " | ".join(diary))
        lines.extend([
            "BEHAVIOR CONTRACT:",
            "- Pertahankan identitas/personality inti; state hanya memengaruhi ekspresi, bukan mengganti karakter.",
            "- Untuk chat santai/emosional, jangan otomatis berubah menjadi esai atau customer-support. Variasikan panjang secara wajar.",
            "- Boleh memakai 1-3 potongan pendek dipisah baris kosong bila ritme percakapan memang lebih natural; jangan dipaksakan.",
            "- Jangan selalu menutup dengan tawaran 'kalau mau aku bisa...'. Jangan mengulang pertanyaan user sebagai pembuka.",
            "- Jika ada kontradiksi dengan memory kuat, tanyakan atau koreksi secara natural daripada mengarang continuity.",
            "- Untuk tugas teknis/berisiko, utamakan presisi dan keselamatan di atas gaya companion.",
        ])
        return "\n".join(lines)[:4200]
