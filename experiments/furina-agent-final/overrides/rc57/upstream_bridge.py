from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


class UpstreamCompanionBridge:
    """Thin adapter around pinned, unmodified upstream companion sources.

    GPL Soul of Waifu executes in a separate Python process. Utsuwa's original
    TypeScript state engine executes in a Node sidecar when Node can load its
    pinned source. LumiMuse and ZeroChat are installed whole and kept available
    to their native runtimes; they are never silently reimplemented here.
    """

    def __init__(self, store, llm, user_name: str = ""):
        self.store = store
        self.llm = llm
        self.user_name = (user_name or "User").strip() or "User"
        self.root = Path.home() / ".furina-agent"
        self.upstreams = self.root / "upstreams"
        self.runtime = self.root / "core" / "furina_agent" / "upstream_runtime"
        self.data = self.root / "data" / "upstream_companion"
        self.data.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _lock_meta(self, source_id: str) -> dict:
        p = self.upstreams / ".locks" / f"{source_id}.json"
        try:
            value = json.loads(p.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _source_root(self, source_id: str) -> Path | None:
        meta = self._lock_meta(source_id)
        ref = str(meta.get("ref") or "")
        p = self.upstreams / source_id / ref
        return p if ref and p.is_dir() and meta.get("complete") else None

    def _soul_context(self) -> str:
        base = self.data / "soul" / ".soul" / "Furina" / "chats" / "default" / "memory"
        parts = []
        for name, cap in (("MEMORY.md", 3600), ("USER.md", 2400)):
            p = base / name
            try:
                text = p.read_text(encoding="utf-8").strip()
            except Exception:
                text = ""
            if text:
                parts.append(text[:cap])
        return "\n\n".join(parts)

    def _utsuwa_context(self) -> str:
        state = self.store.get_state("upstream_utsuwa_state", {})
        if not isinstance(state, dict) or not state:
            return ""
        mood = state.get("mood") if isinstance(state.get("mood"), dict) else {}
        return (
            "Relationship signals (internal; never quote numbers): "
            f"affection={state.get('affection', 0)}, trust={state.get('trust', 0)}, "
            f"intimacy={state.get('intimacy', 0)}, comfort={state.get('comfort', 0)}, "
            f"respect={state.get('respect', 0)}; mood={mood.get('primary', 'neutral')}."
        )

    def context(self) -> str:
        pieces = []
        soul = self._soul_context()
        if soul:
            pieces.append("SOUL MEMORY / SUBJECTIVE CONTINUITY:\n" + soul)
        utsuwa = self._utsuwa_context()
        if utsuwa:
            pieces.append("UTSUWA RELATIONSHIP ENGINE:\n" + utsuwa)
        if not pieces:
            return "(upstream companion memory belum terbentuk; jangan menyebut detail teknis ini kepada user)"
        pieces.append(
            "INTERPRETATION RULE: perlakukan konteks di atas sebagai pengalaman dan keadaan internal. "
            "Jangan menyebut nama proyek upstream, kode, runtime, software, model, atau implementasi kepada user "
            "kecuali user sedang membahas teknis proyek Furina."
        )
        return "\n\n".join(pieces)

    @staticmethod
    def _sentiment(text: str) -> float:
        low = text.casefold()
        pos = len(re.findall(r"\b(makasih|bagus|suka|senang|sayang|kangen|mantap|nice|good)\b", low))
        neg = len(re.findall(r"\b(salah|jelek|kesal|marah|benci|gagal|payah|kecewa)\b", low))
        return max(-1.0, min(1.0, (pos - neg) / max(1, pos + neg)))

    def _run_utsuwa(self, user_text: str) -> None:
        source = self._source_root("utsuwa")
        worker = self.runtime / "utsuwa_worker.mjs"
        if not source or not worker.is_file():
            return
        try:
            subprocess.run(["node", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=True)
        except Exception:
            return
        now = datetime.now(timezone.utc)
        state = self.store.get_state("upstream_utsuwa_state", {})
        if not isinstance(state, dict) or not state:
            state = {
                "energy": 82, "affection": 120, "trust": 48, "intimacy": 25,
                "comfort": 45, "respect": 50,
                "mood": {"primary": "neutral", "intensity": 28, "causes": []},
                "lastInteraction": now.isoformat(), "lastDecayAt": None,
            }
        try:
            last = datetime.fromisoformat(str(state.get("lastInteraction") or now.isoformat()).replace("Z", "+00:00"))
            hours = max(0.0, (now - last).total_seconds() / 3600.0)
        except Exception:
            hours = 0.0
        payload = {
            "upstream": str(source), "state": state, "hours_since": hours,
            "sentiment": self._sentiment(user_text),
            "topic_depth": "deep" if len(user_text) > 160 else "moderate" if len(user_text) > 55 else "shallow",
            "is_emotional": bool(re.search(r"\b(sedih|marah|takut|cemas|capek|sayang|kangen|cinta|kecewa)\b", user_text, re.I)),
            "is_question": "?" in user_text,
        }
        try:
            proc = subprocess.run(
                ["node", "--experimental-strip-types", str(worker)],
                input=json.dumps(payload), text=True, capture_output=True, timeout=8,
            )
            if proc.returncode != 0:
                return
            result = json.loads(proc.stdout)
        except Exception:
            return
        decay = result.get("decay") or {}
        impact = result.get("impact") or {}
        mapping = {
            "energyDelta": "energy", "affectionDelta": "affection", "trustDelta": "trust",
            "intimacyDelta": "intimacy", "comfortDelta": "comfort", "respectDelta": "respect",
        }
        caps = {"energy": (0,100), "affection": (0,1000), "trust": (0,100), "intimacy": (0,100), "comfort": (0,100), "respect": (0,100)}
        for source_map in (decay, impact):
            for delta_key, dest in mapping.items():
                if delta_key in source_map:
                    lo, hi = caps[dest]
                    state[dest] = max(lo, min(hi, float(state.get(dest, 0)) + float(source_map[delta_key] or 0)))
        mood_change = decay.get("moodChange") or impact.get("moodChange")
        if isinstance(mood_change, dict) and mood_change.get("emotion"):
            old_mood = state.get("mood") if isinstance(state.get("mood"), dict) else {}
            state["mood"] = {
                "primary": str(mood_change["emotion"]),
                "intensity": max(0, min(100, float(old_mood.get("intensity", 30)) + float(mood_change.get("intensityDelta", 0) or 0))),
                "causes": list(old_mood.get("causes", []))[-4:] + ([str(mood_change.get("cause"))] if mood_change.get("cause") else []),
            }
        state["lastInteraction"] = now.isoformat()
        self.store.set_state("upstream_utsuwa_state", state)

    def _run_soul(self) -> None:
        source = self._source_root("soul_of_waifu")
        worker = self.runtime / "soul_worker.py"
        if not source or not worker.is_file():
            return
        if not self._lock.acquire(blocking=False):
            return
        try:
            messages = self.store.recent_messages(18)
            if len(messages) < 4:
                return
            req = {
                "op": "update", "upstream": str(source), "data_root": str(self.data / "soul"),
                "mode": 1, "batch": 4, "messages": messages, "character": "Furina",
                "user": self.user_name, "chat_id": "default", "force": False,
            }
            log = self.root / "logs" / "upstream-soul.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as err:
                proc = subprocess.Popen(
                    [sys.executable, str(worker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=err, text=True, bufsize=1,
                )
                assert proc.stdin and proc.stdout
                proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
                proc.stdin.flush()
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    event = json.loads(line)
                    if event.get("event") == "llm_request":
                        try:
                            text = self.llm.chat(event.get("messages") or [], max_tokens=760, temperature=0.10, json_mode=True)
                            reply = {"event":"llm_response","id":event.get("id"),"text":text}
                        except Exception as exc:
                            reply = {"event":"llm_response","id":event.get("id"),"error":str(exc)[:300]}
                        proc.stdin.write(json.dumps(reply, ensure_ascii=False) + "\n")
                        proc.stdin.flush()
                    elif event.get("event") == "done":
                        self.store.set_state("upstream_soul_stats", event.get("stats") or {})
                        break
                try:
                    proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception as exc:
            try:
                self.store.log_event("upstream_soul_error", {"error": str(exc)[:300]})
            except Exception:
                pass
        finally:
            self._lock.release()

    def after_turn(self, user_text: str, answer: str) -> None:
        try:
            self._run_utsuwa(user_text)
        except Exception:
            pass
        turn = int(self.store.get_state("upstream_companion_turns", 0) or 0) + 1
        self.store.set_state("upstream_companion_turns", turn)
        if turn % 4 == 0:
            threading.Thread(target=self._delayed_soul, daemon=True).start()

    def _delayed_soul(self):
        time.sleep(14)
        self._run_soul()
