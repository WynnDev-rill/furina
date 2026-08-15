from __future__ import annotations

import re
import time
from dataclasses import dataclass

from .prospective import extract_prospectives
from .intent_guard import conversation_frame
from .hub_settings import effective_device_mode, load_hub_settings


_SIMPLE_OPEN = re.compile(r"^\s*(?:(?:tolong|coba)\s+)?(?:buka|bukakan|bukain|open|jalankan|launch)\s+(?:(?:aplikasi|app|apk)\s+)?(.+?)\s*[.!]?\s*$", re.I)
_BACK = re.compile(r"^\s*(?:kembali|back|tekan\s+back)\s*[.!]?\s*$", re.I)
_HOME = re.compile(r"^\s*(?:home|ke\s+home|kembali\s+ke\s+home)\s*[.!]?\s*$", re.I)
_RECENTS = re.compile(r"^\s*(?:recent|recents|aplikasi\s+terbaru|buka\s+recent)\s*[.!]?\s*$", re.I)
_SCROLL = re.compile(r"^\s*(?:scroll|geser|swipe)\s+(ke\s+)?(atas|bawah|up|down)\s*[.!]?\s*$", re.I)
_TAP = re.compile(r"^\s*(?:tap|klik|click|tekan)\s+(?:tombol\s+)?(.+?)\s*[.!]?\s*$", re.I)
_TYPE = re.compile(r"^\s*(?:ketik|ketikkan|tulis|tuliskan|isi|isikan)\s+(.+?)\s*$", re.I)
_CHAIN = re.compile(r"\b(?:lalu|kemudian|setelah itu|terus|dan kemudian)\b", re.I)
_SENSITIVE = re.compile(r"\b(?:kirim|send|submit|post|publish|share|bagikan|hapus|delete|remove|uninstall|reset|bayar|pay|purchase|beli|transfer|subscribe|berlangganan|login|logout)\b", re.I)


@dataclass
class DirectResult:
    handled: bool
    reply: str = ""
    kind: str = "direct"


class DirectDeviceControl:
    """Deterministic first-hop executor.

    Clear, low-risk commands bypass the LLM planner. Ambiguous, external and
    destructive work deliberately falls back to the full Android agent.
    """

    def __init__(self, cfg, store, bridge):
        self.cfg = cfg
        self.store = store
        self.bridge = bridge
        self._apps_cache: list[dict] = []
        self._apps_at = 0.0

    def _mode(self) -> str:
        fallback = str(getattr(self.cfg, "device_control_mode", "normal") or "normal").lower()
        mode = effective_device_mode(load_hub_settings(), fallback=fallback)
        if mode in {"shizuku", "root"}:
            try:
                status = self.bridge.control_status() or {}
                if not bool(status.get(mode + "_ready")):
                    return "normal"
            except Exception:
                return "normal"
        return mode

    def _control(self, action: dict):
        payload = dict(action)
        payload.setdefault("mode", self._mode())
        return self.bridge.control(payload)

    def _apps(self) -> list[dict]:
        now = time.monotonic()
        if self._apps_cache and now - self._apps_at < 900:
            return self._apps_cache
        try:
            raw = self.bridge.apps()
            apps = raw.get("apps") if isinstance(raw, dict) else []
            self._apps_cache = [x for x in apps if isinstance(x, dict)] if isinstance(apps, list) else []
            self._apps_at = now
        except Exception:
            pass
        return self._apps_cache

    def _resolve_app(self, name: str, *, exact: bool = False) -> str:
        wanted = " ".join(str(name or "").casefold().split()).strip(" .!?")
        aliases = {
            "wa": "whatsapp", "yt": "youtube", "ig": "instagram",
            "browser": "chrome", "google chrome": "chrome",
        }
        wanted = aliases.get(wanted, wanted)
        if not wanted:
            return ""
        scored: list[tuple[int, str]] = []
        for app in self._apps():
            label = " ".join(str(app.get("label") or "").casefold().split())
            package = str(app.get("package") or "")
            if not package:
                continue
            score = 0
            if label == wanted:
                score = 100
            elif package.casefold() == wanted:
                score = 100
            elif not exact and (label.startswith(wanted) or wanted.startswith(label)):
                score = 80
            elif not exact and wanted in label:
                score = 65
            elif not exact and wanted in package.casefold():
                score = 55
            if score:
                scored.append((score, package))
        if not scored:
            return ""
        scored.sort(reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0] and scored[0][1] != scored[1][1]:
            return ""
        return scored[0][1]

    @staticmethod
    def _node_label(node: dict) -> str:
        return " ".join(str(node.get(k) or "") for k in ("text", "desc", "view_id")).strip()

    def _single_node(self, target: str, *, editable: bool = False) -> dict | None:
        try:
            screen = self.bridge.screen()
        except Exception:
            return None
        wanted = " ".join(str(target or "").casefold().split()).strip(" .!?")
        matches: list[dict] = []
        for node in screen.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            if editable and not node.get("editable"):
                continue
            if not editable and not node.get("clickable"):
                continue
            parts = [str(node.get(k) or "").strip() for k in ("text", "desc")]
            labels = [" ".join(x.casefold().split()) for x in parts if x]
            if wanted and wanted in labels:
                matches.append(node)
        if len(matches) == 1:
            return matches[0]
        if editable:
            editable_nodes = [n for n in (screen.get("nodes") or []) if isinstance(n, dict) and n.get("editable")]
            focused = [n for n in editable_nodes if n.get("focused")]
            if len(focused) == 1:
                return focused[0]
            if len(editable_nodes) == 1:
                return editable_nodes[0]
        return None

    def try_execute_step(self, step: dict) -> DirectResult:
        """Execute only a semantically parsed, atomic low-risk primitive."""
        if not isinstance(step, dict):
            return DirectResult(False)
        typ = str(step.get("type") or "")
        if typ == "open_app":
            package = str(step.get("package") or "").strip()
            if not package or package not in {str(x.get("package") or "") for x in self._apps()}:
                return DirectResult(False)
            try:
                result = self._control({"type": "open_app", "package": package})
                if isinstance(result, dict) and result.get("ok"):
                    self.store.log_event("direct_control", {"type": "open_app", "package": package, "semantic": True})
                    return DirectResult(True, "Selesai.")
            except Exception:
                pass
            return DirectResult(False)
        if typ in {"back", "home", "recents"}:
            try:
                result = self._control({"type": typ})
                if isinstance(result, dict) and result.get("ok"):
                    self.store.log_event("direct_control", {"type": typ, "semantic": True})
                    return DirectResult(True, "Selesai.")
            except Exception:
                pass
        return DirectResult(False)

    def try_execute(self, text: str) -> DirectResult:
        raw = " ".join(str(text or "").split())
        if not raw:
            return DirectResult(False)
        if conversation_frame(raw):
            self.store.log_event("direct_control_chat_guard", {"text": raw[:240]})
            return DirectResult(False)

        # Android Bridge owns scheduling. No Termux daemon is required after
        # the alarm has been registered.
        reminders = extract_prospectives(raw)
        if reminders:
            reminder_text, due_at = reminders[0]
            if due_at > time.time() + 1:
                try:
                    result = self._control({"type": "schedule_reminder", "text": reminder_text[:500], "at_ms": int(due_at * 1000)})
                    if isinstance(result, dict) and result.get("ok"):
                        self.store.log_event("direct_control", {"type": "schedule_reminder", "at": due_at})
                        return DirectResult(True, "Sudah. Aku akan mengingatkanmu.", "reminder")
                except Exception:
                    return DirectResult(False)
            return DirectResult(False)

        # Never shortcut chained, external, destructive or account-sensitive
        # requests. Those retain the full agent safety/verification path.
        if _CHAIN.search(raw) or _SENSITIVE.search(raw):
            return DirectResult(False)

        match = _SIMPLE_OPEN.match(raw)
        if match:
            package = self._resolve_app(match.group(1), exact=True)
            if package:
                try:
                    result = self._control({"type": "open_app", "package": package})
                    if isinstance(result, dict) and result.get("ok"):
                        self.store.log_event("direct_control", {"type": "open_app", "package": package})
                        return DirectResult(True, "Selesai.")
                except Exception:
                    pass
            return DirectResult(False)

        if _BACK.match(raw):
            typ = "back"
        elif _HOME.match(raw):
            typ = "home"
        elif _RECENTS.match(raw):
            typ = "recents"
        else:
            typ = ""
        if typ:
            try:
                result = self._control({"type": typ})
                if isinstance(result, dict) and result.get("ok"):
                    self.store.log_event("direct_control", {"type": typ, "mode": self._mode()})
                    return DirectResult(True, "Selesai.")
            except Exception:
                pass
            return DirectResult(False)

        match = _SCROLL.match(raw)
        if match:
            direction = match.group(2).casefold()
            action = {"type": "scroll_best", "direction": "backward" if direction in {"atas", "up"} else "forward"}
            try:
                result = self.bridge.action(action)
                if isinstance(result, dict) and result.get("ok"):
                    self.store.log_event("direct_control", {"type": "scroll_best"})
                    return DirectResult(True, "Selesai.")
            except Exception:
                pass
            return DirectResult(False)

        match = _TAP.match(raw)
        if match and not _SENSITIVE.search(match.group(1)):
            action = {"type": "tap_text", "target": match.group(1)}
            try:
                result = self.bridge.action(action)
                if isinstance(result, dict) and result.get("ok"):
                    self.store.log_event("direct_control", {"type": "tap_text"})
                    return DirectResult(True, "Selesai.")
            except Exception:
                pass
            return DirectResult(False)

        match = _TYPE.match(raw)
        if match and len(match.group(1)) <= 500:
            node = self._single_node("", editable=True)
            if node:
                action = {"type": "set_text", "node": int(node.get("id", -1)), "text": match.group(1)}
                try:
                    result = self.bridge.action(action)
                    if isinstance(result, dict) and result.get("ok"):
                        self.store.log_event("direct_control", {"type": "set_text"})
                        return DirectResult(True, "Selesai.")
                except Exception:
                    pass
            return DirectResult(False)

        return DirectResult(False)
