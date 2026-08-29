from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import dataclass


_TECH = re.compile(r"\b(?:error|bug|kode|code|script|termux|api|model|provider|build|install|database|github|apk|config)\b", re.I)
_DEEP = re.compile(r"\b(?:analisis|audit|bandingkan|strategi|rencana|menyeluruh|mendalam|jelaskan lengkap|kenapa|mengapa)\b", re.I)
_EMOTION = re.compile(r"\b(?:sedih|takut|cemas|kesepian|kecewa|capek|lelah|malu|marah|frustrasi|bingung|curhat)\b", re.I)
_PLAY = re.compile(r"\b(?:wkwk|haha|hehe|goda|ledek|bercanda|lucu|sayang|kangen|rindu)\b", re.I)
_ASKS_ADVICE = re.compile(r"\b(?:menurutmu|gimana|bagaimana|sebaiknya|harus|mending|bantu|solusi|saran)\b", re.I)
_COMPACT = re.compile(r"\b(?:singkat|ringkas|pendek|seperlunya|langsung ke inti|jangan bertele-tele|kepanjangan|terlalu panjang)\b", re.I)
_EXPAND = re.compile(r"\b(?:lebih lengkap|mendalam|detail|panjang tidak apa|terlalu pendek|kurang lengkap)\b", re.I)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[^\W_]+(?:[-'][^\W_]+)*\b", str(text or ""), flags=re.UNICODE))


def _context(text: str) -> str:
    if _TECH.search(text):
        return "technical"
    if _EMOTION.search(text):
        return "emotional"
    if _PLAY.search(text):
        return "playful"
    return "casual"


def _ewma(old: float, value: float, count: int, alpha: float = .16) -> float:
    if count <= 1 or old <= 0:
        return float(value)
    return float(old) * (1.0 - alpha) + float(value) * alpha


class AdaptiveStyleMemory:
    """Small local style model; stores shape, never message contents."""

    STATE_KEY = "adaptive_style_v128"

    def __init__(self, store):
        self.store = store

    def _load(self) -> dict:
        raw = self.store.get_state(self.STATE_KEY, {})
        if not isinstance(raw, dict):
            raw = {}
        raw.setdefault("global", {})
        raw.setdefault("contexts", {})
        raw.setdefault("reply_scale", 1.0)
        return raw

    def observe_user(self, text: str) -> None:
        value = str(text or "").strip()
        if not value:
            return
        state = self._load()
        words = max(1, _word_count(value))
        sentences = max(1, len(re.findall(r"[.!?]+(?:\s|$)", value)) or 1)
        casual = len(re.findall(r"\b(?:nggak|gak|aja|udah|kayak|gimana|bener|kok|sih|dong|deh)\b", value, re.I))
        question_ratio = 1.0 if "?" in value else 0.0
        for key in ("global",):
            bucket = state.setdefault(key, {})
            count = int(bucket.get("samples", 0) or 0) + 1
            bucket["samples"] = count
            bucket["words"] = round(_ewma(float(bucket.get("words", 0) or 0), words, count), 2)
            bucket["sentences"] = round(_ewma(float(bucket.get("sentences", 0) or 0), sentences, count), 2)
            bucket["casuality"] = round(_ewma(float(bucket.get("casuality", 0) or 0), min(1.0, casual / 2.0), count), 3)
            bucket["question_ratio"] = round(_ewma(float(bucket.get("question_ratio", 0) or 0), question_ratio, count), 3)
        ctx = _context(value)
        bucket = state.setdefault("contexts", {}).setdefault(ctx, {})
        count = int(bucket.get("samples", 0) or 0) + 1
        bucket["samples"] = count
        bucket["words"] = round(_ewma(float(bucket.get("words", 0) or 0), words, count, .22), 2)
        bucket["sentences"] = round(_ewma(float(bucket.get("sentences", 0) or 0), sentences, count, .22), 2)

        scale = float(state.get("reply_scale", 1.0) or 1.0)
        if re.search(r"\b(?:kepanjangan|terlalu panjang|jangan sepanjang itu|jangan bertele-tele)\b", value, re.I):
            scale *= .82
        elif re.search(r"\b(?:terlalu pendek|kurang lengkap|jelaskan lebih lengkap)\b", value, re.I):
            scale *= 1.14
        state["reply_scale"] = round(max(.55, min(1.45, scale)), 3)
        self.store.set_state(self.STATE_KEY, state)

    @staticmethod
    def _training_words() -> list[int]:
        try:
            from .training_room import TRAINING_PATH
            raw = json.loads(TRAINING_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
        rows: list[int] = []
        for item in (raw.get("decisions") or [])[-120:]:
            if not isinstance(item, dict) or item.get("category") not in {"length", "natural"}:
                continue
            chosen = str(item.get("chosen") or "").strip()
            count = _word_count(chosen)
            if 3 <= count <= 500:
                rows.append(count)
        return rows[-36:]

    def profile(self, user_text: str) -> dict:
        state = self._load()
        ctx = _context(user_text)
        global_row = state.get("global") if isinstance(state.get("global"), dict) else {}
        context_row = state.get("contexts", {}).get(ctx, {}) if isinstance(state.get("contexts"), dict) else {}
        context_samples = int(context_row.get("samples", 0) or 0)
        global_words = float(global_row.get("words", 18) or 18)
        observed_words = float(context_row.get("words", global_words) or global_words)
        evidence = min(1.0, context_samples / 12.0)
        familiar_words = global_words * (1.0 - evidence) + observed_words * evidence
        training = self._training_words()
        training_target = statistics.median(training) if len(training) >= 3 else 0.0
        return {
            "context": ctx,
            "samples": int(global_row.get("samples", 0) or 0),
            "context_samples": context_samples,
            "familiar_words": round(familiar_words, 1),
            "training_words": round(float(training_target), 1),
            "reply_scale": float(state.get("reply_scale", 1.0) or 1.0),
            "casuality": float(global_row.get("casuality", 0) or 0),
            "question_ratio": float(global_row.get("question_ratio", 0) or 0),
        }


@dataclass(frozen=True)
class TurnPlan:
    mode: str
    strategy: str
    target_words: int
    soft_upper_words: int
    max_tokens: int
    temperature: float
    complexity: float
    uncertainty: float

    def prompt(self) -> str:
        return (
            "ADAPTIVE TURN POLICY — ini sasaran lunak berdasarkan momentum, bukan template kaku.\n"
            f"Mode campuran={self.mode}; strategi={self.strategy}; complexity={self.complexity:.2f}; uncertainty={self.uncertainty:.2f}.\n"
            f"Target alami sekitar {self.target_words} kata; biasanya jangan melewati {self.soft_upper_words} kata. "
            "Jika perlu beberapa kata tambahan untuk menuntaskan kalimat atau isi penting, tuntaskan—jangan berhenti di tengah kata/kalimat. "
            "Jangan menambah paragraf baru hanya untuk memenuhi target.\n"
            "Pilih sendiri respons sosial yang paling cocok: reaksi, jawaban, pendapat, godaan, acknowledgement, atau satu pertanyaan eksplorasi. "
            "Pertanyaan bukan kewajiban; gunakan hanya jika membantu momentum atau memahami cerita yang belum cukup jelas."
        )


def plan_turn(user_text: str, recent: list[dict], style: dict, base_temperature: float = .72) -> TurnPlan:
    text = " ".join(str(user_text or "").split())
    words = max(1, _word_count(text))
    lines = max(1, str(user_text or "").count("\n") + 1)
    question = 1.0 if "?" in text else 0.0
    tech = 1.0 if _TECH.search(text) else 0.0
    deep_signal = 1.0 if _DEEP.search(text) else 0.0
    emotion = 1.0 if _EMOTION.search(text) else 0.0
    playful = 1.0 if _PLAY.search(text) else 0.0
    advice = 1.0 if _ASKS_ADVICE.search(text) else 0.0
    explicit_compact = 1.0 if _COMPACT.search(text) else 0.0
    explicit_expand = 1.0 if _EXPAND.search(text) else 0.0

    length_load = min(1.0, math.log1p(words) / math.log(90))
    structure_load = min(1.0, (lines - 1) / 5.0)
    complexity = max(0.0, min(1.0, .30 * length_load + .24 * structure_load + .30 * tech + .28 * deep_signal + .12 * question))
    uncertainty = max(0.0, min(1.0, .62 * emotion + .20 * (1.0 - question) - .34 * advice + (.18 if text.endswith(("...", "…")) else 0.0)))

    familiar = float(style.get("familiar_words", 18) or 18)
    base = 14.0 + min(38.0, familiar * .72) + min(24.0, words * .42)
    base += complexity * (245.0 if tech or deep_signal else 90.0)
    base += emotion * (26.0 if advice else 12.0)
    base += explicit_expand * 150.0
    base *= float(style.get("reply_scale", 1.0) or 1.0)
    training_words = float(style.get("training_words", 0) or 0)
    if training_words:
        base = base * .72 + training_words * .28
    if words <= 4 and not tech and not deep_signal:
        base = min(base, 24.0)
    if explicit_compact:
        base = min(base, 52.0 if tech else 32.0)

    target = int(round(max(8.0, min(650.0, base))))
    soft_upper = int(round(max(target + 12, target * (1.48 if target < 90 else 1.32))))
    max_tokens = max(160, min(1800, int(soft_upper * 2.35 + 48)))

    if uncertainty >= .58 and not advice:
        strategy = "tanggapi detail konkret lalu eksplorasi satu hal; jangan menyimpulkan"
    elif tech or deep_signal:
        strategy = "jawab inti dan selesaikan penalaran yang memang diperlukan"
    elif question:
        strategy = "jawab langsung; tambah konteks hanya jika berguna"
    elif playful:
        strategy = "balas momentum secara hidup tanpa memperpanjang topik"
    elif words <= 5:
        strategy = "reaksi sosial singkat"
    else:
        strategy = "respons proporsional yang meneruskan percakapan"

    dominant = []
    if tech: dominant.append("technical")
    if emotion: dominant.append("emotional")
    if playful: dominant.append("playful")
    if deep_signal: dominant.append("deep")
    mode = "+".join(dominant) or "casual"
    temperature = max(.54, min(.82, float(base_temperature) - complexity * .12 + playful * .06))
    return TurnPlan(mode, strategy, target, soft_upper, max_tokens, temperature, complexity, uncertainty)
