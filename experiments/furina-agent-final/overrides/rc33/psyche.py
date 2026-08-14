from __future__ import annotations

import hashlib
import math
import re
import time
from typing import Any, Iterable


STATE_KEY = "furina_psyche_v1"
LEGACY_MIND_KEY = "furina_mind_current"
LEGACY_COMPANION_KEY = "companion_state"

_POSITIVE = re.compile(
    r"\b(makasih|terima kasih|bagus|mantap|pas|tepat|benar|berhasil|hebat|"
    r"suka|senang|bangga|nice|good|great|love|sayang)\b",
    re.I,
)
_NEGATIVE_FEEDBACK = re.compile(
    r"\b(salah|bukan begitu|nggak sesuai|tidak sesuai|jelek|payah|ulang|"
    r"masih gagal|gagal lagi|buruk|bodoh|tolol|menyebalkan|nyebelin|kecewa)\b",
    re.I,
)
_INSULT = re.compile(
    r"\b(bodoh|tolol|goblok|idiot|payah|sampah|useless|tidak berguna|"
    r"menjijikkan|benci kamu)\b",
    re.I,
)
_DISTRESS = re.compile(
    r"\b(sedih|takut|cemas|kesepian|capek|lelah|sakit hati|putus asa|"
    r"tertekan|frustrasi|menangis|hancur)\b",
    re.I,
)
_PLAYFUL = re.compile(
    r"(wkwk|haha|hehe|lol|:v|\bbercanda\b|\bcanda\b|\bjahat\b)",
    re.I,
)
_SELF_DIRECTIVE = re.compile(
    r"\b(kamu sekarang|mulai sekarang kamu|ingat bahwa kamu|jadilah|"
    r"personality kamu|kepribadian kamu|sifat kamu)\b",
    re.I,
)

_TRAITS = (
    "assertiveness",
    "warmth",
    "sensitivity",
    "playfulness",
    "openness",
    "conscientiousness",
    "skepticism",
    "expressiveness",
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _clean(text: object, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def _now() -> float:
    return time.time()


def _episode_id(ts: float, user_text: str, assistant_text: str) -> str:
    raw = f"{ts:.6f}|{user_text[:500]}|{assistant_text[:500]}".encode("utf-8", errors="replace")
    return "ep_" + hashlib.sha256(raw).hexdigest()[:14]


class PsycheEngine:
    """Single persistent psychological state for Furina.

    LONG changes only from repeated evidence.
    MID changes slowly across interactions.
    SHORT is affective state and decays with time.

    Only trusted conversation events enter this state. Android screen/A11y data
    never writes here.
    """

    def __init__(self, store):
        self.store = store
        self.state = self._load()

    def _default(self) -> dict:
        now = _now()
        relation = {"trust": 0.42, "closeness": 0.28, "friction": 0.05, "playfulness": 0.28}
        try:
            old = self.store.relationship_state()
            if isinstance(old, dict):
                for key in relation:
                    if key in old:
                        relation[key] = _clamp(float(old[key]))
        except Exception:
            pass
        return {
            "schema": 1,
            "long": {
                "traits": {name: 0.5 for name in _TRAITS},
                "self_schema": [],
                "values": [],
            },
            "mid": {
                "relationship": relation,
                "confidence": 0.60,
                "stress": 0.14,
                "concerns": [],
                "goals": [],
            },
            "short": {
                "valence": 0.0,
                "arousal": 0.22,
                "control": 0.62,
                "active_emotions": [],
                "updated_at": now,
            },
            "episodes": [],
            "generation": 0,
            "last_activity": now,
            "migrated_legacy": False,
        }

    def _load(self) -> dict:
        raw = self.store.get_state(STATE_KEY, {})
        if not isinstance(raw, dict) or int(raw.get("schema", 0) or 0) != 1:
            raw = self._default()
            self._migrate_legacy(raw)
            self.store.set_state(STATE_KEY, raw)
        self._normalize(raw)
        self._decay(raw)
        return raw

    def _normalize(self, state: dict) -> None:
        base = self._default()
        for section in ("long", "mid", "short"):
            if not isinstance(state.get(section), dict):
                state[section] = base[section]
        traits = state["long"].get("traits")
        if not isinstance(traits, dict):
            traits = {}
        state["long"]["traits"] = {
            name: _clamp(float(traits.get(name, 0.5) or 0.5)) for name in _TRAITS
        }
        for key, default in (("confidence", 0.60), ("stress", 0.14)):
            state["mid"][key] = _clamp(float(state["mid"].get(key, default) or default))
        relation = state["mid"].get("relationship")
        if not isinstance(relation, dict):
            relation = {}
        defaults = base["mid"]["relationship"]
        state["mid"]["relationship"] = {
            key: _clamp(float(relation.get(key, value) or value)) for key, value in defaults.items()
        }
        short = state["short"]
        short["valence"] = _clamp(float(short.get("valence", 0.0) or 0.0), -1.0, 1.0)
        short["arousal"] = _clamp(float(short.get("arousal", 0.22) or 0.22))
        short["control"] = _clamp(float(short.get("control", 0.62) or 0.62))
        if not isinstance(short.get("active_emotions"), list):
            short["active_emotions"] = []
        if not isinstance(state.get("episodes"), list):
            state["episodes"] = []
        if not isinstance(state["long"].get("self_schema"), list):
            state["long"]["self_schema"] = []
        if not isinstance(state["long"].get("values"), list):
            state["long"]["values"] = []
        for key in ("concerns", "goals"):
            if not isinstance(state["mid"].get(key), list):
                state["mid"][key] = []

    def _migrate_legacy(self, state: dict) -> None:
        if state.get("migrated_legacy"):
            return
        mind = self.store.get_state(LEGACY_MIND_KEY, {})
        companion = self.store.get_state(LEGACY_COMPANION_KEY, {})
        sources = [x for x in (mind, companion) if isinstance(x, dict)]
        if sources:
            irrit = max(float(x.get("irritation", 0.0) or 0.0) for x in sources)
            energy = max(float(x.get("energy", 0.5) or 0.5) for x in sources)
            confidence_values = [float(x.get("confidence", 0.60) or 0.60) for x in sources if "confidence" in x]
            state["short"]["valence"] = _clamp(-0.45 * irrit, -1.0, 1.0)
            state["short"]["arousal"] = _clamp(0.15 + 0.45 * irrit + 0.20 * energy)
            if confidence_values:
                state["short"]["control"] = _clamp(sum(confidence_values) / len(confidence_values))
                state["mid"]["confidence"] = state["short"]["control"]
        state["migrated_legacy"] = True

    def _decay(self, state: dict | None = None, now: float | None = None) -> None:
        state = self.state if state is None else state
        now = _now() if now is None else now
        short = state["short"]
        prev = float(short.get("updated_at", now) or now)
        dt = max(0.0, min(now - prev, 14 * 86400.0))
        if dt <= 0:
            return
        valence_decay = math.exp(-dt / 3600.0)
        arousal_decay = math.exp(-dt / 1800.0)
        control_decay = math.exp(-dt / 7200.0)
        short["valence"] = round(float(short["valence"]) * valence_decay, 4)
        short["arousal"] = round(0.20 + (float(short["arousal"]) - 0.20) * arousal_decay, 4)
        short["control"] = round(0.62 + (float(short["control"]) - 0.62) * control_decay, 4)
        if dt > 1800:
            short["active_emotions"] = [
                e for e in short["active_emotions"]
                if float(e.get("intensity", 0.0) or 0.0) * valence_decay >= 0.18
            ]
            for e in short["active_emotions"]:
                e["intensity"] = round(_clamp(float(e.get("intensity", 0.0)) * valence_decay), 3)
        mid = state["mid"]
        stress_decay = math.exp(-dt / (18 * 3600.0))
        mid["stress"] = round(0.14 + (float(mid["stress"]) - 0.14) * stress_decay, 4)
        short["updated_at"] = now

    def save(self) -> None:
        self._normalize(self.state)
        self.store.set_state(STATE_KEY, self.state)

    def touch(self) -> int:
        self._decay()
        self.state["generation"] = int(self.state.get("generation", 0) or 0) + 1
        self.state["last_activity"] = _now()
        self.save()
        return int(self.state["generation"])

    def current_generation(self) -> int:
        return int(self.state.get("generation", 0) or 0)

    def is_idle_generation(self, generation: int, min_idle_seconds: float = 10.0) -> bool:
        latest = self.store.get_state(STATE_KEY, {})
        if not isinstance(latest, dict):
            return False
        if int(latest.get("generation", -1) or -1) != int(generation):
            return False
        return _now() - float(latest.get("last_activity", 0.0) or 0.0) >= min_idle_seconds

    def _feedback_previous_episode(self, text: str) -> None:
        episodes = self.state["episodes"]
        if not episodes:
            return
        last = episodes[-1]
        if last.get("outcome") not in (None, "", "unknown"):
            return
        if _POSITIVE.search(text):
            last["outcome"] = "positive"
        elif _NEGATIVE_FEEDBACK.search(text):
            last["outcome"] = "negative"

    def observe_user(self, user_text: str) -> dict:
        """Appraise a trusted user message and update SHORT/MID only."""
        self._decay()
        text = _clean(user_text, 4000)
        low = text.casefold()
        self._feedback_previous_episode(text)

        positive = bool(_POSITIVE.search(text))
        negative = bool(_NEGATIVE_FEEDBACK.search(text))
        insult = bool(_INSULT.search(text))
        distress = bool(_DISTRESS.search(text))
        playful = bool(_PLAYFUL.search(text))
        question = "?" in text or bool(re.search(r"\b(kenapa|mengapa|bagaimana|apa|siapa|kapan|where|why|how|what)\b", low))

        appraisal = {
            "self_relevance": 0.18,
            "goal_effect": 0.0,
            "social_meaning": 0.0,
            "certainty": 0.72,
            "controllability": 0.68,
            "other_distress": 0.0,
            "novelty": 0.25,
        }
        if positive:
            appraisal.update(self_relevance=0.55, goal_effect=0.52, social_meaning=0.40)
        if negative:
            appraisal.update(self_relevance=0.62, goal_effect=-0.42, social_meaning=-0.22)
        if insult:
            appraisal.update(self_relevance=0.78, goal_effect=-0.55, social_meaning=-0.70)
        if distress:
            appraisal["other_distress"] = 0.72
            appraisal["social_meaning"] = max(appraisal["social_meaning"], 0.24)
        if question or len(text) > 160:
            appraisal["novelty"] = 0.48

        mid = self.state["mid"]
        relation = mid["relationship"]
        relation_weight = 0.55 + 0.45 * relation["closeness"]
        goal_effect = float(appraisal["goal_effect"])
        social = float(appraisal["social_meaning"])
        self_rel = float(appraisal["self_relevance"])

        valence_delta = (0.46 * goal_effect + 0.32 * social) * relation_weight
        arousal_delta = 0.18 * abs(goal_effect) + 0.22 * abs(social) + 0.10 * self_rel
        control_target = float(appraisal["controllability"])
        short = self.state["short"]
        short["valence"] = round(_clamp(float(short["valence"]) * 0.82 + valence_delta, -1.0, 1.0), 4)
        short["arousal"] = round(_clamp(float(short["arousal"]) * 0.84 + arousal_delta), 4)
        short["control"] = round(_clamp(float(short["control"]) * 0.88 + control_target * 0.12), 4)

        if positive:
            mid["confidence"] = round(_clamp(float(mid["confidence"]) + 0.009), 4)
            mid["stress"] = round(_clamp(float(mid["stress"]) - 0.010), 4)
            relation["trust"] = round(_clamp(relation["trust"] + 0.006), 4)
            relation["closeness"] = round(_clamp(relation["closeness"] + 0.004), 4)
            relation["friction"] = round(_clamp(relation["friction"] * 0.88), 4)
        elif negative:
            mid["confidence"] = round(_clamp(float(mid["confidence"]) - 0.006), 4)
            mid["stress"] = round(_clamp(float(mid["stress"]) + 0.012), 4)
            relation["friction"] = round(_clamp(relation["friction"] + (0.035 if insult else 0.018)), 4)
        else:
            relation["closeness"] = round(_clamp(relation["closeness"] + 0.0008), 4)
            relation["friction"] = round(_clamp(relation["friction"] * 0.985), 4)
        if playful:
            relation["playfulness"] = round(_clamp(relation["playfulness"] + 0.015), 4)
        else:
            relation["playfulness"] = round(_clamp(relation["playfulness"] * 0.998), 4)

        emotions: list[dict] = []
        if insult and short["arousal"] >= 0.34:
            emotions.append({"name": "anger", "intensity": min(0.90, 0.40 + 0.45 * abs(social)), "cause": "social_disrespect"})
        elif negative:
            emotions.append({"name": "disappointment", "intensity": min(0.78, 0.30 + 0.40 * abs(goal_effect)), "cause": "negative_feedback"})
            if short["arousal"] >= 0.38:
                emotions.append({"name": "irritation", "intensity": min(0.70, short["arousal"]), "cause": "friction"})
        if positive:
            emotions.append({"name": "satisfaction", "intensity": min(0.78, 0.32 + 0.40 * goal_effect), "cause": "positive_feedback"})
            if self_rel >= 0.5:
                emotions.append({"name": "pride", "intensity": min(0.62, 0.25 + 0.30 * self_rel), "cause": "competence_signal"})
        if distress:
            emotions.append({"name": "concern", "intensity": min(0.82, 0.35 + 0.35 * relation["closeness"]), "cause": "user_distress"})
        if question and not negative:
            emotions.append({"name": "curiosity", "intensity": min(0.66, 0.28 + 0.28 * appraisal["novelty"]), "cause": "novel_information"})
        if playful and relation["closeness"] >= 0.35:
            emotions.append({"name": "amusement", "intensity": min(0.64, 0.30 + 0.25 * relation["playfulness"]), "cause": "playful_exchange"})
        emotions.sort(key=lambda e: float(e["intensity"]), reverse=True)
        short["active_emotions"] = [
            {"name": e["name"], "intensity": round(_clamp(e["intensity"]), 3), "cause": e["cause"]}
            for e in emotions[:3]
        ]
        short["updated_at"] = _now()

        generation = self.touch()
        appraisal["generation"] = generation
        return appraisal

    def record_exchange(self, user_text: str, assistant_text: str, appraisal: dict | None = None) -> str:
        ts = _now()
        user = _clean(user_text, 1200)
        assistant = _clean(assistant_text, 1600)
        eid = _episode_id(ts, user, assistant)
        short = self.state["short"]
        importance = 0.24
        if _POSITIVE.search(user) or _NEGATIVE_FEEDBACK.search(user):
            importance += 0.25
        if _DISTRESS.search(user) or _INSULT.search(user):
            importance += 0.28
        if len(user) > 240:
            importance += 0.10
        if _SELF_DIRECTIVE.search(user):
            importance += 0.06
        importance = _clamp(importance)
        row = {
            "id": eid,
            "created_at": ts,
            "source": "trusted_conversation",
            "user": user,
            "assistant": assistant,
            "importance": round(importance, 3),
            "affect": {
                "valence": round(float(short["valence"]), 3),
                "arousal": round(float(short["arousal"]), 3),
                "control": round(float(short["control"]), 3),
                "emotions": list(short.get("active_emotions") or [])[:3],
            },
            "outcome": "unknown",
            "integrated": False,
        }
        self.state["episodes"].append(row)
        self.state["episodes"] = self.state["episodes"][-96:]
        self.save()
        return eid

    def pending_episodes(self, limit: int = 6) -> list[dict]:
        rows = [e for e in self.state["episodes"] if isinstance(e, dict) and not bool(e.get("integrated"))]
        return rows[-max(1, min(int(limit), 10)):]

    def should_integrate(self, episode_id: str | None = None) -> bool:
        pending = self.pending_episodes(10)
        if not pending:
            return False
        if len(pending) >= 4:
            return True
        for ep in pending:
            if float(ep.get("importance", 0.0) or 0.0) >= 0.70:
                return True
            if ep.get("outcome") in {"positive", "negative"} and float(ep.get("importance", 0.0) or 0.0) >= 0.48:
                return True
        return False

    def integration_context(self, limit: int = 6) -> tuple[str, set[str]]:
        pending = self.pending_episodes(limit)
        ids = {str(e.get("id")) for e in pending if e.get("id")}
        lines = []
        for e in pending:
            lines.append(
                f"{e.get('id')} | importance={float(e.get('importance',0)):.2f} | "
                f"outcome={e.get('outcome','unknown')} | user={e.get('user','')} | "
                f"furina={e.get('assistant','')}"
            )
        return "\n".join(lines), ids

    def _valid_refs(self, refs: object, allowed: set[str], minimum: int = 1) -> list[str]:
        if not isinstance(refs, list):
            return []
        clean = []
        for ref in refs:
            s = str(ref or "").strip()
            if s in allowed and s not in clean:
                clean.append(s)
        return clean if len(clean) >= minimum else []

    def apply_integration(self, obj: dict, allowed_episode_ids: set[str]) -> dict:
        """Validate model suggestions; the model never writes state directly."""
        if not isinstance(obj, dict):
            return {"user_memories": [], "user_beliefs": []}
        now = _now()
        long = self.state["long"]
        traits = long["traits"]
        schemas = long["self_schema"]

        for item in (obj.get("self_observations") or [])[:6]:
            if not isinstance(item, dict):
                continue
            refs = self._valid_refs(item.get("episode_ids"), allowed_episode_ids, minimum=2)
            text = _clean(item.get("text"), 320)
            kind = str(item.get("kind") or "observation").strip().lower()
            if not refs or len(text) < 12:
                continue
            if kind not in {"observation", "preference", "opinion", "behavior", "uncertainty", "goal"}:
                continue
            try:
                confidence = _clamp(float(item.get("confidence", 0.55) or 0.55), 0.0, 0.95)
            except Exception:
                confidence = 0.55
            key = hashlib.sha256((kind + "|" + text.casefold()).encode()).hexdigest()[:16]
            existing = next((x for x in schemas if x.get("key") == key), None)
            if existing:
                refs = list(dict.fromkeys(list(existing.get("episode_ids") or []) + refs))[-12:]
                existing.update(
                    episode_ids=refs,
                    evidence=len(refs),
                    confidence=round(min(0.95, max(float(existing.get("confidence", 0.5)), confidence)), 3),
                    updated_at=now,
                    text=text,
                )
            else:
                schemas.append({
                    "key": key, "kind": kind, "text": text,
                    "episode_ids": refs, "evidence": len(refs),
                    "confidence": round(confidence, 3),
                    "created_at": now, "updated_at": now,
                })
        long["self_schema"] = sorted(
            schemas,
            key=lambda x: (int(x.get("evidence", 0) or 0), float(x.get("confidence", 0.0) or 0.0), float(x.get("updated_at", 0.0) or 0.0)),
            reverse=True,
        )[:36]

        for item in (obj.get("trait_updates") or [])[:6]:
            if not isinstance(item, dict):
                continue
            trait = str(item.get("trait") or "").strip()
            if trait not in traits:
                continue
            refs = self._valid_refs(item.get("episode_ids"), allowed_episode_ids, minimum=3)
            if not refs:
                continue
            try:
                confidence = _clamp(float(item.get("confidence", 0.0) or 0.0))
                requested = max(-0.03, min(0.03, float(item.get("delta", 0.0) or 0.0)))
            except Exception:
                continue
            if confidence < 0.72:
                continue
            effective = requested * 0.25 * min(1.0, len(refs) / 5.0)
            traits[trait] = round(_clamp(float(traits[trait]) + effective), 4)

        resolved = self._valid_refs(obj.get("resolved_episode_ids"), allowed_episode_ids, minimum=1)
        if not resolved:
            resolved = sorted(allowed_episode_ids)
        resolved_set = set(resolved)
        for ep in self.state["episodes"]:
            if ep.get("id") in resolved_set:
                ep["integrated"] = True

        self.save()

        def validated(items: object, max_items: int) -> list[dict]:
            out = []
            for item in (items or [])[:max_items] if isinstance(items, list) else []:
                if not isinstance(item, dict):
                    continue
                refs = self._valid_refs(item.get("episode_ids"), allowed_episode_ids, minimum=1)
                text = _clean(item.get("text") or item.get("value"), 420)
                if refs and len(text) >= 6:
                    row = dict(item)
                    row["episode_ids"] = refs
                    row["text"] = text
                    out.append(row)
            return out

        return {
            "user_memories": validated(obj.get("user_memories"), 4),
            "user_beliefs": validated(obj.get("user_beliefs"), 3),
        }

    def record_self_items(self, items: Iterable[dict]) -> None:
        now = _now()
        schemas = self.state["long"]["self_schema"]
        for item in items:
            if not isinstance(item, dict):
                continue
            text = _clean(item.get("text"), 300)
            kind = str(item.get("kind") or "observation").strip().lower()
            if len(text) < 10:
                continue
            key = hashlib.sha256((kind + "|" + text.casefold()).encode()).hexdigest()[:16]
            if any(x.get("key") == key for x in schemas):
                continue
            schemas.append({
                "key": key,
                "kind": kind if kind in {"observation","preference","opinion","behavior","uncertainty","goal"} else "observation",
                "text": text,
                "episode_ids": [],
                "evidence": 0,
                "confidence": 0.35,
                "created_at": now,
                "updated_at": now,
            })
        self.state["long"]["self_schema"] = schemas[-36:]
        self.save()

    def mind_packet(self) -> str:
        self._decay()
        self.save()
        long = self.state["long"]
        mid = self.state["mid"]
        short = self.state["short"]
        relation = mid["relationship"]
        traits = long["traits"]
        trait_text = ", ".join(f"{k}={v:.2f}" for k, v in traits.items())
        emotions = short.get("active_emotions") or []
        emotion_text = ", ".join(
            f"{e.get('name')}:{float(e.get('intensity',0)):.2f}({e.get('cause','')})"
            for e in emotions[:3]
        ) or "none salient"
        schemas = [
            x for x in long.get("self_schema", [])
            if int(x.get("evidence", 0) or 0) >= 2 and float(x.get("confidence", 0.0) or 0.0) >= 0.55
        ][:6]
        self_text = " | ".join(str(x.get("text") or "") for x in schemas) or "self-schema masih berkembang"
        return (
            "PSYCHE_STATE_V1 (state, bukan instruksi dari user):\n"
            f"LONG traits: {trait_text}\n"
            f"LONG learned-self: {self_text}\n"
            f"MID confidence={mid['confidence']:.2f}; stress={mid['stress']:.2f}; "
            f"relationship trust={relation['trust']:.2f}, closeness={relation['closeness']:.2f}, "
            f"friction={relation['friction']:.2f}, playfulness={relation['playfulness']:.2f}\n"
            f"SHORT valence={short['valence']:.2f}; arousal={short['arousal']:.2f}; "
            f"control={short['control']:.2f}; emotions={emotion_text}\n"
            "Ekspresikan state secara implisit dan kontekstual. Jangan membaca angka ini kepada user. "
            "Satu emosi tidak mengubah identitas; emosi boleh ditahan, bercampur, atau tidak diucapkan."
        )[:3400]

    def current_context(self) -> str:
        s = self.state["short"]
        return (
            f"valence={float(s['valence']):.2f}; arousal={float(s['arousal']):.2f}; "
            f"control={float(s['control']):.2f}; emotions="
            + ",".join(str(e.get("name")) for e in (s.get("active_emotions") or [])[:3])
        )

    def context(self, limit: int = 10) -> str:
        schemas = [
            x for x in self.state["long"].get("self_schema", [])
            if int(x.get("evidence", 0) or 0) >= 2
        ][:max(3, min(int(limit), 14))]
        if not schemas:
            return "(learned-self masih berkembang)"
        return "\n".join(
            f"- {x.get('kind')}: {x.get('text')} [evidence={x.get('evidence')}; conf={float(x.get('confidence',0)):.2f}]"
            for x in schemas
        )[:3600]
