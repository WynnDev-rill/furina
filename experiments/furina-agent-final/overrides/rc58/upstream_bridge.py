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
    """Adapters around pinned upstream implementations.

    The engines themselves remain in their full vendored source trees. Furina
    only converts its local data into each upstream module's native boundary.
    """

    def __init__(self, store, llm, user_name: str = ""):
        self.store = store
        self.llm = llm
        self.user_name = (user_name or "User").strip() or "User"
        self.root = Path.home() / ".furina-agent"
        self.upstreams = self.root / "upstreams"
        self.runtime = self.root / "core" / "furina_agent" / "upstream_runtime"
        self.data = self.root / "data" / "upstream_companion"
        self.typescript_root = self.root / "upstream-node"
        self.data.mkdir(parents=True, exist_ok=True)
        self._soul_lock = threading.Lock()
        self._zero_lock = threading.Lock()
        self._background_llm_lock = threading.Lock()

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

    @staticmethod
    def _iso(ts) -> str:
        try:
            return datetime.fromtimestamp(float(ts), timezone.utc).isoformat()
        except Exception:
            return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _lumi_kind(kind: str) -> str:
        value = str(kind or "fact").casefold()
        if "promise" in value or "janji" in value:
            return "character_promise"
        if value in {"preference", "preferensi"}:
            return "user_preference"
        if value in {"relationship", "event", "episode"}:
            return "relationship_event"
        if value in {"world", "world_state"}:
            return "world_state"
        return "user_fact"

    def _to_lumi_memory(self, memory, *, prefix: str = "m") -> dict:
        kind = str(getattr(memory, "kind", "fact") or "fact")
        lumi_kind = self._lumi_kind(kind)
        category = {
            "character_promise": "承诺",
            "user_preference": "偏好习惯",
            "relationship_event": "关系动态",
            "world_state": "重要事件",
            "user_fact": "用户信息",
        }.get(lumi_kind, "话题历史")
        created = float(getattr(memory, "created_at", time.time()) or time.time())
        updated = float(getattr(memory, "updated_at", created) or created)
        return {
            "id": f"{prefix}-{getattr(memory, 'id', 0)}",
            "character_id": "furina",
            "category": category,
            "content": str(getattr(memory, "text", "") or "").strip(),
            "confidence": float(getattr(memory, "confidence", 0.65) or 0.65),
            "tags": [kind] if kind else [],
            "source_msg_ids": [],
            "memory_kind": lumi_kind,
            "importance": float(getattr(memory, "importance", 0.5) or 0.5),
            "emotional_weight": float(getattr(memory, "emotion", 0.3) or 0.3),
            "status": "active",
            "pinned": bool(float(getattr(memory, "importance", 0.5) or 0.5) >= 0.92),
            "last_used_at": self._iso(getattr(memory, "last_used_at", updated)),
            "usage_count": int(getattr(memory, "activations", 0) or 0),
            "metadata": {"furina_source": str(getattr(memory, "source", "conversation"))},
            "created_at": self._iso(created),
            "updated_at": self._iso(updated),
        }

    def _soul_context(self) -> str:
        base = self.data / "soul" / ".soul" / "Furina" / "chats" / "default" / "memory"
        parts = []
        for name, cap in (("MEMORY.md", 2600), ("USER.md", 1500)):
            p = base / name
            try:
                text = p.read_text(encoding="utf-8").strip()
            except Exception:
                text = ""
            if text:
                parts.append(text[:cap])
        return "\n\n".join(parts)

    def _zero_context(self) -> str:
        value = self.store.get_state("upstream_zerochat_context", "")
        return str(value or "").strip()[:1200]

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

    def _lumimuse_context(self, user_text: str) -> str:
        source = self._source_root("lumimuse")
        worker = self.runtime / "lumimuse_worker.cjs"
        ts = self.typescript_root / "node_modules" / "typescript"
        if not source or not worker.is_file() or not ts.exists():
            return ""
        try:
            relevant = self.store.search(user_text, 18)
            all_memories = self.store.list_memories(50)
            priority = [m for m in all_memories if float(getattr(m, "importance", 0) or 0) >= 0.85][:8]
            memories = [self._to_lumi_memory(m) for m in relevant]
            seen = {m["id"] for m in memories}
            for ep in self.store.search_episodes(user_text, 3):
                row = {
                    "id": f"ep-{ep.id}", "character_id": "furina", "category": "关系动态",
                    "content": ep.summary, "confidence": 0.72, "tags": [x.strip() for x in str(ep.themes).split(",") if x.strip()][:5],
                    "source_msg_ids": [], "memory_kind": "relationship_event", "importance": float(ep.importance),
                    "emotional_weight": float(ep.emotion), "status": "active", "pinned": bool(float(ep.importance) >= 0.92),
                    "last_used_at": self._iso(ep.last_used_at), "usage_count": int(ep.activations), "metadata": {"furina_source":"episode"},
                    "created_at": self._iso(ep.created_at), "updated_at": self._iso(ep.created_at),
                }
                if row["id"] not in seen:
                    memories.append(row); seen.add(row["id"])
            payload = {
                "upstream": str(source), "typescript_root": str(self.typescript_root), "query": user_text,
                "memories": memories,
                "priority_memories": [self._to_lumi_memory(m) for m in priority],
                "token_budget": 1200, "final_top_k": 14,
            }
            proc = subprocess.run(
                ["node", str(worker)], input=json.dumps(payload, ensure_ascii=False),
                text=True, capture_output=True, timeout=5,
            )
            if proc.returncode != 0:
                self.store.log_event("upstream_lumimuse_error", {"error": proc.stderr[-300:]})
                return ""
            result = json.loads(proc.stdout)
            if result.get("ok"):
                self.store.set_state("upstream_lumimuse_diag", {
                    "mode": result.get("mode"), "token_count": result.get("tokenCount"),
                    "selected": len(result.get("selectedIds") or []),
                })
                return str(result.get("text") or "")[:5200]
        except Exception as exc:
            try:
                self.store.log_event("upstream_lumimuse_error", {"error": str(exc)[:300]})
            except Exception:
                pass
        return ""

    def context(self, user_text: str = "") -> str:
        pieces = []
        lumi = self._lumimuse_context(str(user_text or ""))
        if lumi:
            pieces.append("WORKING MEMORY PACKAGE:\n" + lumi)
        soul = self._soul_context()
        if soul:
            pieces.append("SOUL MEMORY / SUBJECTIVE CONTINUITY:\n" + soul)
        zero = self._zero_context()
        if zero:
            pieces.append("CORE RELATIONSHIP SUMMARY:\n" + zero)
        utsuwa = self._utsuwa_context()
        if utsuwa:
            pieces.append("RELATIONSHIP / MOOD STATE:\n" + utsuwa)
        if not pieces:
            return "(belum ada upstream companion memory yang relevan; jangan menyebut detail teknis ini kepada user)"
        pieces.append(
            "INTERPRETATION RULE: perlakukan semua bagian di atas sebagai ingatan, pengalaman, dan keadaan internalmu sendiri. "
            "Jangan menyebut nama proyek upstream, kode, runtime, software, model, database, retrieval, atau implementasi kepada user "
            "kecuali user sedang membahas teknis proyek Furina. Jangan mengklaim tubuh biologis atau kepastian kesadaran subjektif."
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
        worker = self.runtime / "utsuwa_worker.cjs"
        ts = self.typescript_root / "node_modules" / "typescript"
        if not source or not worker.is_file() or not ts.exists():
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
            "upstream": str(source), "typescript_root": str(self.typescript_root), "state": state, "hours_since": hours,
            "sentiment": self._sentiment(user_text),
            "topic_depth": "deep" if len(user_text) > 160 else "moderate" if len(user_text) > 55 else "shallow",
            "is_emotional": bool(re.search(r"\b(sedih|marah|takut|cemas|capek|sayang|kangen|cinta|kecewa)\b", user_text, re.I)),
            "is_question": "?" in user_text,
        }
        try:
            proc = subprocess.run(["node", str(worker)], input=json.dumps(payload), text=True, capture_output=True, timeout=5)
            if proc.returncode != 0:
                self.store.log_event("upstream_utsuwa_error", {"error": proc.stderr[-300:]})
                return
            result = json.loads(proc.stdout)
        except Exception as exc:
            try: self.store.log_event("upstream_utsuwa_error", {"error": str(exc)[:300]})
            except Exception: pass
            return
        decay = result.get("decay") or {}; impact = result.get("impact") or {}
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
        self.store.set_state("upstream_utsuwa_active", True)

    def _rpc_worker(self, command: list[str], request: dict, log_name: str, timeout: float = 180.0) -> dict:
        log = self.root / "logs" / log_name
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as err:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1)
            assert proc.stdin and proc.stdout
            proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n"); proc.stdin.flush()
            deadline = time.monotonic() + timeout
            done = {}
            while time.monotonic() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break
                event = json.loads(line)
                if event.get("event") == "llm_request":
                    try:
                        with self._background_llm_lock:
                            text = self.llm.chat(
                                event.get("messages") or [], max_tokens=760,
                                temperature=float(event.get("temperature", 0.10) or 0.10),
                                json_mode=bool(event.get("json_mode", False)),
                            )
                        reply = {"event":"llm_response","id":event.get("id"),"text":text}
                    except Exception as exc:
                        reply = {"event":"llm_response","id":event.get("id"),"error":str(exc)[:300]}
                    proc.stdin.write(json.dumps(reply, ensure_ascii=False) + "\n"); proc.stdin.flush()
                elif event.get("event") == "done":
                    done = event; break
            try: proc.wait(timeout=4)
            except subprocess.TimeoutExpired: proc.kill()
            return done

    def _run_soul(self) -> None:
        source = self._source_root("soul_of_waifu"); worker = self.runtime / "soul_worker.py"
        if not source or not worker.is_file() or not self._soul_lock.acquire(blocking=False): return
        try:
            messages = self.store.recent_messages(18)
            if len(messages) < 4: return
            req = {
                "op":"update", "upstream":str(source), "data_root":str(self.data/"soul"), "mode":1, "batch":4,
                "messages":messages, "character":"Furina", "user":self.user_name, "chat_id":"default", "force":False,
            }
            event = self._rpc_worker([sys.executable, str(worker)], req, "upstream-soul.log")
            if event:
                self.store.set_state("upstream_soul_stats", event.get("stats") or {})
                self.store.set_state("upstream_soul_active", True)
        except Exception as exc:
            try: self.store.log_event("upstream_soul_error", {"error":str(exc)[:300]})
            except Exception: pass
        finally:
            self._soul_lock.release()

    def _run_zerochat(self, user_text: str, answer: str) -> None:
        source = self._source_root("zerochat"); worker = self.runtime / "zerochat_worker.py"
        if not source or not worker.is_file() or not self._zero_lock.acquire(blocking=False): return
        try:
            req = {
                "op":"update", "upstream":str(source), "data_root":str(self.data/"zerochat"), "role_id":"furina",
                "user_text":user_text, "answer":answer, "allow_summary":True,
            }
            event = self._rpc_worker([sys.executable, str(worker)], req, "upstream-zerochat.log", timeout=120)
            if event:
                self.store.set_state("upstream_zerochat_context", event.get("context") or "")
                self.store.set_state("upstream_zerochat_stats", {
                    "short_term_count":event.get("short_term_count",0),
                    "message_count_since_summary":event.get("message_count_since_summary",0),
                })
                self.store.set_state("upstream_zerochat_active", True)
        except Exception as exc:
            try: self.store.log_event("upstream_zerochat_error", {"error":str(exc)[:300]})
            except Exception: pass
        finally:
            self._zero_lock.release()

    def after_turn(self, user_text: str, answer: str) -> None:
        try: self._run_utsuwa(user_text)
        except Exception: pass
        turn = int(self.store.get_state("upstream_companion_turns", 0) or 0) + 1
        self.store.set_state("upstream_companion_turns", turn)
        threading.Thread(target=self._delayed_zero, args=(user_text,answer), daemon=True).start()
        if turn % 4 == 0:
            threading.Thread(target=self._delayed_soul, daemon=True).start()

    def _delayed_zero(self, user_text: str, answer: str) -> None:
        time.sleep(6)
        self._run_zerochat(user_text, answer)

    def _delayed_soul(self) -> None:
        time.sleep(14)
        self._run_soul()
