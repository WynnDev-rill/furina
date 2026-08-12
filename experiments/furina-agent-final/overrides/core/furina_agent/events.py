from __future__ import annotations

import json
import socket
import threading
import time
from collections import deque

from .bridge import AndroidBridge
from .config import Config
from .memory import MemoryStore


class DeviceEventDaemon:
    """Low-power event receiver for Bridge Accessibility events.

    The Android Bridge pushes compact UDP datagrams only when meaningful device
    events occur. No screen polling and no LLM call happens here. The daemon
    updates a small local device-context model that Furina can use on demand.
    """

    def __init__(self, cfg: Config, store: MemoryStore, bridge: AndroidBridge | None = None):
        self.cfg = cfg
        self.store = store
        self.bridge = bridge
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._recent: deque[dict] = deque(maxlen=24)

    def start(self) -> bool:
        if not self.cfg.proactive_events_enabled:
            return False
        if self._thread and self._thread.is_alive():
            return True
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", int(self.cfg.event_port)))
            sock.settimeout(1.0)
        except OSError:
            return False
        self._sock = sock
        self._seed_from_bridge()
        self._thread = threading.Thread(target=self._loop, name="furina-device-events", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _seed_from_bridge(self) -> None:
        if not self.bridge:
            return
        try:
            screen = self.bridge.screen()
        except Exception:
            return
        for event in (screen.get("recent_events") or [])[-12:]:
            if isinstance(event, dict):
                self._record(event, persist=False)
        package = str(screen.get("package") or "")
        if package:
            self.store.set_state("device_foreground_package", package)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                raw, _ = self._sock.recvfrom(8192) if self._sock else (b"", None)
            except socket.timeout:
                continue
            except OSError:
                return
            if not raw:
                continue
            try:
                event = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception:
                continue
            if isinstance(event, dict):
                self._record(event, persist=True)

    def _record(self, event: dict, *, persist: bool) -> None:
        now = time.time()
        compact = {
            "seq": int(event.get("seq", 0) or 0),
            "type": str(event.get("type") or "")[:48],
            "package": str(event.get("package") or "")[:160],
            "class": str(event.get("class") or "")[:120],
            "text": str(event.get("text") or "")[:260],
            "at": float(event.get("at", now) or now),
        }
        self._recent.append(compact)
        package = compact["package"]
        if package:
            self.store.set_state("device_foreground_package", package)
            usage = self.store.get_state("device_usage_counts", {})
            if not isinstance(usage, dict):
                usage = {}
            hour_bucket = time.localtime(compact["at"]).tm_hour // 4
            key = f"{package}|{hour_bucket}"
            usage[key] = min(100000, int(usage.get(key, 0) or 0) + 1)
            if len(usage) > 160:
                usage = dict(sorted(usage.items(), key=lambda kv: kv[1], reverse=True)[:120])
            self.store.set_state("device_usage_counts", usage)
        if compact["type"] == "notification" and compact["text"]:
            notifications = self.store.get_state("device_notifications", [])
            if not isinstance(notifications, list):
                notifications = []
            notifications.append({"package": package, "text": compact["text"], "at": compact["at"]})
            self.store.set_state("device_notifications", notifications[-12:])
        self.store.set_state("device_last_event", compact)
        self.store.set_state("device_recent_events", list(self._recent))
        if persist:
            self.store.log_event("device_event", compact)

    def context(self) -> str:
        last = self.store.get_state("device_last_event", {})
        recent = self.store.get_state("device_recent_events", [])
        notifications = self.store.get_state("device_notifications", [])
        if not isinstance(last, dict):
            last = {}
        if not isinstance(recent, list):
            recent = []
        if not isinstance(notifications, list):
            notifications = []
        now = time.time()
        lines: list[str] = []
        package = str(last.get("package") or self.store.get_state("device_foreground_package", "") or "")
        if package:
            age = max(0, int(now - float(last.get("at", now) or now)))
            lines.append(f"foreground/recent app: {package} ({age}s ago)")
        meaningful = [e for e in recent[-8:] if isinstance(e, dict) and str(e.get("text") or "").strip()]
        if meaningful:
            lines.append("recent device events: " + " | ".join(
                f"{e.get('type')}:{str(e.get('text'))[:90]}" for e in meaningful[-4:]
            ))
        fresh_notifs = [n for n in notifications[-6:] if isinstance(n, dict) and now - float(n.get("at", 0) or 0) < 3600]
        if fresh_notifs:
            lines.append("recent notifications: " + " | ".join(
                f"{n.get('package')}:{str(n.get('text'))[:90]}" for n in fresh_notifs[-3:]
            ))
        return "\n".join(lines) or "(tidak ada device context baru)"
