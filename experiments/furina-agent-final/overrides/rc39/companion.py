from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .agent import AndroidAgent
from .bridge import AndroidBridge
from .chat import FurinaChat
from .config import Config
from .memory import MemoryStore
from .long_input import router_view
from .prospective import ReminderDaemon
from .events import DeviceEventDaemon
from .direct_control import DirectDeviceControl, DirectResult
from .intent_guard import committed_device_intent, conversation_frame, strong_device_request


@dataclass
class Intent:
    mode: str
    goal: str
    confidence: float = 0.0
    steps: list[dict] = field(default_factory=list)
    requires_screen: bool = False



def _first_json_object(raw: str) -> dict | None:
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(str(raw or "")):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(str(raw)[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


class CompanionSession:
    """One natural-language entry point for conversation and Android actions."""

    def __init__(self, cfg: Config, store: MemoryStore, llm):
        self.cfg = cfg
        self.store = store
        self.llm = llm
        self.chat = FurinaChat(cfg, store, llm)
        self.bridge = AndroidBridge(cfg)
        self.agent = AndroidAgent(cfg, store, llm, self.bridge)
        self.events = DeviceEventDaemon(cfg, store, self.bridge)
        self.events.start()
        self.direct = DirectDeviceControl(cfg, store, self.bridge)

    def _installed_apps(self) -> list[dict]:
        def read_apps() -> list[dict]:
            raw = self.bridge.apps()
            apps = raw.get("apps") if isinstance(raw, dict) else []
            if not isinstance(apps, list):
                return []
            return [x for x in apps if isinstance(x, dict) and x.get("package")]

        try:
            return read_apps()
        except Exception as first_error:
            # Pairing/token loss must not silently erase the installed-app
            # inventory. Recover once through the loopback bootstrap and retry.
            try:
                if self.bridge.ensure_paired():
                    apps = read_apps()
                    self.store.log_event(
                        "bridge_pairing_recovered",
                        {"apps": len(apps)},
                    )
                    return apps
            except Exception as retry_error:
                self.store.log_event(
                    "installed_apps_error",
                    {
                        "first": str(first_error)[:220],
                        "retry": str(retry_error)[:220],
                    },
                )
                return []
            self.store.log_event(
                "installed_apps_error",
                {"first": str(first_error)[:220], "retry": "pairing unavailable"},
            )
            return []

    @staticmethod
    def _app_keys(label: str, package: str = "") -> set[str]:
        raw = str(label or "").strip()
        parts: list[str] = []
        token = ""
        for ch in raw:
            if not ch.isalnum():
                if token:
                    parts.append(token)
                    token = ""
                continue
            if token and ch.isupper() and token[-1].islower():
                parts.append(token)
                token = ch
            else:
                token += ch
        if token:
            parts.append(token)

        normalized_parts = ["".join(ch.casefold() for ch in part if ch.isalnum()) for part in parts]
        normalized_parts = [part for part in normalized_parts if part]
        keys: set[str] = set(normalized_parts)
        if normalized_parts:
            keys.add("".join(normalized_parts))
            initials = "".join(part[0] for part in normalized_parts if part)
            if len(initials) >= 2:
                for size in range(2, min(4, len(initials)) + 1):
                    keys.add(initials[:size])
        package_tail = str(package or "").rsplit(".", 1)[-1]
        package_key = "".join(ch.casefold() for ch in package_tail if ch.isalnum())
        if package_key:
            keys.add(package_key)
        return {key for key in keys if key}

    @classmethod
    def _resolve_app_hint(cls, hint: str, apps: list[dict]) -> str:
        wanted = "".join(ch for ch in str(hint or "").casefold() if ch.isalnum())
        if not wanted:
            return ""
        best_score = 0.0
        best_package = ""
        tied = False
        for app in apps:
            package = str(app.get("package") or "")
            if not package:
                continue
            keys = cls._app_keys(str(app.get("label") or ""), package)
            if wanted in keys:
                score = 1.0
            elif len(wanted) <= 3:
                score = 0.0
            else:
                score = 0.0
                for key in keys:
                    if len(key) < 3:
                        continue
                    if wanted in key or key in wanted:
                        score = max(score, 0.90)
                    else:
                        score = max(score, SequenceMatcher(None, wanted, key).ratio())
            if score > best_score + 0.02:
                best_score, best_package, tied = score, package, False
            elif score > 0 and abs(score - best_score) <= 0.02 and package != best_package:
                tied = True
        threshold = 0.98 if len(wanted) <= 3 else 0.62
        return best_package if best_score >= threshold and not tied else ""

    @classmethod
    def _app_anchors(cls, text: str, apps: list[dict]) -> list[str]:
        tokens: list[str] = []
        current = ""
        for ch in str(text or "").casefold():
            if ch.isalnum():
                current += ch
            elif current:
                tokens.append(current)
                current = ""
        if current:
            tokens.append(current)
        token_set = set(tokens)
        compact = "".join(tokens)
        matches: list[str] = []
        for app in apps:
            package = str(app.get("package") or "")
            if not package:
                continue
            keys = cls._app_keys(str(app.get("label") or ""), package)
            found = False
            for key in keys:
                if len(key) <= 3:
                    found = key in token_set
                else:
                    found = key in token_set or key in compact
                if found:
                    break
            if found and package not in matches:
                matches.append(package)
        return matches

    @classmethod
    def _normalize_semantic_steps(cls, raw_steps, apps: list[dict]) -> list[dict]:
        allowed = {"open_app", "search", "tap", "type", "scroll", "back", "home", "recents", "read", "select", "send", "unknown"}
        packages = {str(x.get("package") or "") for x in apps}
        out: list[dict] = []
        if not isinstance(raw_steps, list):
            return out
        for item in raw_steps[:18]:
            if not isinstance(item, dict):
                continue
            typ = str(item.get("type") or "").strip().lower()
            if typ not in allowed:
                typ = "unknown"
            step = {"type": typ}
            package = str(item.get("package") or "").strip()
            app_hint = str(item.get("app") or "").strip()[:120]
            if package not in packages and app_hint:
                package = cls._resolve_app_hint(app_hint, apps)
            if package in packages:
                step["package"] = package
            if app_hint:
                step["app"] = app_hint
            for key, limit in (("query", 1000), ("text", 4000), ("target", 180)):
                value = str(item.get(key) or "").strip()
                if value:
                    step[key] = value[:limit]
            field_role = str(item.get("field_role") or item.get("role") or "").strip().lower()
            if field_role in {"search", "message", "input"}:
                step["field_role"] = field_role
            if typ == "scroll":
                direction = str(item.get("direction") or "forward").strip().lower()
                step["direction"] = "backward" if direction in {"backward", "up"} else "forward"
            out.append(step)

        # Repair common model omissions without app-specific hardcoding.  If an
        # external send exists, a payload must be typed before it, and a search
        # result normally needs to be selected before typing into the next UI.
        send_index = next((i for i in range(len(out) - 1, -1, -1) if str(out[i].get("type") or "") == "send"), -1)
        if send_index >= 0:
            has_type = any(str(x.get("type") or "") == "type" and str(x.get("text") or "") for x in out[:send_index])
            send_text = str(out[send_index].get("text") or "")
            if not has_type and send_text:
                out.insert(send_index, {"type": "type", "text": send_text[:4000], "field_role": "message"})
                send_index += 1
            type_index = next((i for i in range(send_index - 1, -1, -1) if str(out[i].get("type") or "") == "type"), -1)
            if type_index >= 0:
                search_index = next((i for i in range(type_index - 1, -1, -1) if str(out[i].get("type") or "") == "search"), -1)
                if search_index >= 0 and not any(str(out[i].get("type") or "") in {"select", "tap"} for i in range(search_index + 1, type_index)):
                    query = str(out[search_index].get("query") or "").strip()
                    if query:
                        out.insert(search_index + 1, {"type": "select", "target": query[:180]})
        return out[:18]

    @staticmethod
    def _requires_screen(steps: list[dict]) -> bool:
        if len(steps) != 1:
            return bool(steps)
        return str(steps[0].get("type") or "") not in {"open_app", "back", "home", "recents"}

    def try_direct(self, text: str) -> DirectResult:
        if not getattr(self.cfg, "direct_control_enabled", True):
            return DirectResult(False)
        try:
            return self.direct.try_execute(text)
        except Exception as exc:
            self.store.log_event("direct_control_error", {"error": str(exc)[:240]})
            return DirectResult(False)

    @classmethod
    def _fallback_device_steps(cls, text: str, apps: list[dict]) -> list[dict]:
        """Small deterministic safety net used only when semantic routing fails.

        It parses structural imperative chains, not app-specific commands. App
        identity is still resolved exclusively from the live installed-app list.
        """
        raw = " ".join(str(text or "").strip().split())
        if not raw:
            return []

        action_tail = r"(?:cari|search|find|ketik|tulis|kirim|send|tekan|tap|klik|click|scroll|geser|swipe|pilih|select)"
        joiner = r"(?:\s*[,;]\s*|\s+(?:lalu|kemudian|terus|dan)\s+)"
        opened = re.search(
            rf"^\s*(?:buka|open|jalankan|launch)\s+(.+?)(?={joiner}{action_tail}\b|$)",
            raw,
            re.I,
        )
        if not opened:
            return []

        app_hint = opened.group(1).strip(" ,.;:-")[:120]
        package = cls._resolve_app_hint(app_hint, apps)
        if not package:
            # If the user included filler after the app name, progressively try
            # the leading phrase. This remains generic and inventory-backed.
            words = app_hint.split()
            for size in range(min(4, len(words)), 0, -1):
                package = cls._resolve_app_hint(" ".join(words[:size]), apps)
                if package:
                    break
        if not package:
            return []

        steps: list[dict] = [{"type": "open_app", "app": app_hint, "package": package}]

        search_match = re.search(
            rf"\b(?:cari|search|find)\b\s+(?:(?:kontak|contact|chat|percakapan|akun|account|user)\s+)?(.+?)(?={joiner}(?:kirim|send|ketik|tulis|tekan|tap|klik|click|scroll|geser|swipe|pilih|select)\b|$)",
            raw,
            re.I,
        )
        query = ""
        if search_match:
            query = search_match.group(1).strip(" ,.;:-")[:1000]
            if query:
                steps.append({"type": "search", "query": query})

        send_match = re.search(
            r"\b(?:kirim|send)(?:kan)?\b\s*(?:(?:pesan|message)\b\s*)?(.+?)\s*$",
            raw,
            re.I,
        )
        if send_match:
            payload = send_match.group(1).strip(" ,.;:-")[:4000]
            if payload:
                if query:
                    steps.append({"type": "select", "target": query[:180]})
                steps.append({"type": "type", "text": payload, "field_role": "message"})
                steps.append({"type": "send"})

        return steps[:18]

    @staticmethod
    def _looks_like_device_imperative(text: str) -> bool:
        # Last-resort routing only. This never executes anything by itself; it
        # merely prevents an explicit imperative from being misrouted to chat
        # when both semantic routing and app inventory are unavailable.
        return bool(
            re.match(
                r"^\s*(?:buka|open|jalankan|launch|cari|search|kirim|send|balas|reply|ketik|tulis|tekan|tap|klik|click|scroll|geser|swipe|pilih|select)\b",
                str(text or ""),
                re.I,
            )
        )

    def classify(self, text: str) -> Intent:
        text = text.strip()
        if not text:
            return Intent("chat", text, 1.0)

        # Clear discussion/report/hypothetical frames are chat before any app
        # inventory or LLM output gets a chance to widen them into device work.
        if conversation_frame(text):
            self.store.log_event("intent_chat_frame", {"text": text[:240]})
            return Intent("chat", text, 1.0, [], False)

        apps = self._installed_apps()
        anchors = self._app_anchors(text, apps)
        fallback_steps = self._fallback_device_steps(text, apps) if strong_device_request(text) else []
        app_context = [
            {"label": str(x.get("label") or "")[:80], "package": str(x.get("package") or "")[:180]}
            for x in apps[:220]
        ]
        routed_text = router_view(text)
        prompt = f"""
Pahami maksud pesan pengguna secara semantik. Default ke CHAT jika ada ambiguitas.
Nama aplikasi hanya konteks/target; menyebut aplikasi TIDAK berarti meminta perangkat bertindak.

Pesan pengguna:
{routed_text}

Aplikasi terpasang:
{json.dumps(app_context, ensure_ascii=False)[:12000]}

Output JSON tunggal:
{{
  "mode":"chat|device",
  "speech_act":"command|request|question|discussion|report|hypothetical|quote",
  "explicit_device_action":false,
  "action_span":"kutipan PERSIS dari pesan user yang meminta aksi; kosong jika chat",
  "goal":"maksud lengkap pengguna",
  "confidence":0.0,
  "steps":[
    {{"type":"open_app|search|tap|type|scroll|back|home|recents|read|select|send|unknown","app":"nama aplikasi bila relevan","package":"package dari daftar bila diketahui","query":"","text":"","target":"","field_role":"search|message|input","direction":"forward|backward"}}
  ]
}}

Aturan penting:
- device HANYA bila user benar-benar meminta Furina melakukan tindakan Android sekarang.
- Percakapan tentang aplikasi, laporan masa lalu, pertanyaan penjelasan, hipotesis, contoh, kutipan perintah, dan keluhan adalah chat.
- "WhatsApp lagi lambat menurutmu kenapa?" = chat.
- "Tadi aku buka WhatsApp lalu chat Ariel" = chat/report.
- "Kalau aku bilang 'buka WhatsApp', kamu bakal apa?" = chat/hypothetical.
- "Jangan buka WhatsApp" = chat; tidak ada aksi.
- "Bisa buka WhatsApp?" = device/request.
- "Tolong bukain WhatsApp" = device/request.
- action_span harus merupakan substring persis dari pesan user dan memuat kata aksi yang diminta.
- Untuk mode chat: explicit_device_action=false, action_span="", steps=[].
- Untuk mode device: speech_act harus command/request dan explicit_device_action=true.
- Pertahankan semua sub-tugas device. Pisahkan type dan send. Jangan menambah aksi.
""".strip()

        errors: list[str] = []
        for json_mode in (True, False):
            try:
                raw = self.llm.chat(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Kamu intent classifier Android konservatif. App mention bukan permission. "
                                "Jika ragu, pilih chat. Output satu objek JSON valid saja."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=620,
                    temperature=0.0,
                    json_mode=json_mode,
                    role="intent",
                )
                obj = _first_json_object(raw)
                if not isinstance(obj, dict):
                    raise ValueError("semantic parser tidak menghasilkan objek JSON")
                mode = str(obj.get("mode") or "").strip().lower()
                if mode not in {"chat", "device"}:
                    raise ValueError(f"mode semantic tidak valid: {mode!r}")
                try:
                    confidence = max(0.0, min(1.0, float(obj.get("confidence", 0.5) or 0.5)))
                except Exception:
                    confidence = 0.5

                if mode == "chat":
                    # conversation_frame() has already rejected discussion,
                    # quotes and hypotheticals. A structurally explicit Android
                    # imperative must therefore win over a weak local model
                    # that incorrectly answers the command as ordinary chat.
                    if fallback_steps:
                        self.store.log_event(
                            "semantic_chat_overridden_by_explicit_request",
                            {"text": text[:240], "steps": len(fallback_steps), "confidence": confidence},
                        )
                        return Intent("device", text, 0.72, fallback_steps, self._requires_screen(fallback_steps))
                    goal = str(obj.get("goal") or text).strip() or text
                    return Intent("chat", goal, confidence, [], False)

                steps = self._normalize_semantic_steps(obj.get("steps"), apps)
                if not committed_device_intent(text, obj, steps, confidence):
                    self.store.log_event(
                        "semantic_device_rejected",
                        {
                            "text": text[:240],
                            "confidence": confidence,
                            "speech_act": str(obj.get("speech_act") or "")[:40],
                            "explicit": obj.get("explicit_device_action") is True,
                            "anchors": anchors[:4],
                        },
                    )
                    return Intent("chat", text, confidence, [], False)

                if any(str(step.get("type") or "") == "unknown" for step in steps):
                    self.store.log_event(
                        "semantic_intent_deferred_to_planner",
                        {"text": text[:240], "steps": len(steps)},
                    )
                    steps = []
                return Intent("device", text, confidence, steps, True if not steps else self._requires_screen(steps))
            except Exception as exc:
                errors.append(f"{'json' if json_mode else 'plain'}:{str(exc)[:220]}")

        # Provider/parser failure is chat-first. Only a structurally explicit
        # request may recover into device mode; an app-name anchor alone never can.
        if fallback_steps:
            self.store.log_event(
                "semantic_intent_structural_fallback",
                {"text": text[:240], "steps": len(fallback_steps), "errors": errors[-2:]},
            )
            return Intent("device", text, 0.72, fallback_steps, self._requires_screen(fallback_steps))

        if strong_device_request(text):
            self.store.log_event(
                "semantic_intent_unresolved_explicit_request",
                {"text": text[:240], "errors": errors[-2:]},
            )
            return Intent("device", text, 0.20, [], True)

        self.store.log_event(
            "semantic_intent_error_chat_fallback",
            {"text": text[:240], "anchors": anchors[:4], "errors": errors[-2:]},
        )
        return Intent("chat", text, 0.0, [], False)

    def try_direct_intent(self, intent: Intent) -> DirectResult:
        if intent.mode != "device" or intent.requires_screen or len(intent.steps) != 1:
            return DirectResult(False)
        try:
            return self.direct.try_execute_step(intent.steps[0])
        except Exception as exc:
            self.store.log_event("direct_semantic_error", {"error": str(exc)[:240]})
            return DirectResult(False)

    def respond(self, text: str, approve, *, task_authorized: bool = False) -> tuple[str, str]:
        direct = self.try_direct(text)
        if direct.handled:
            self.store.add_message("user", text)
            self.store.add_message("assistant", direct.reply)
            return direct.reply, direct.kind
        intent = self.classify(text)
        semantic_direct = self.try_direct_intent(intent)
        if semantic_direct.handled:
            self.store.add_message("user", text)
            self.store.add_message("assistant", semantic_direct.reply)
            return semantic_direct.reply, semantic_direct.kind
        if intent.mode == "device":
            result = self.agent.run(intent.goal, approve, task_authorized=task_authorized, semantic_steps=intent.steps)
            return result, "device"
        return self.chat.respond(text), "chat"
