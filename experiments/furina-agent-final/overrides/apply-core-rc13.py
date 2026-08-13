#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC13 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc13.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    config = core / "config.py"
    bridge = core / "bridge.py"
    companion = core / "companion.py"
    prospective = core / "prospective.py"
    chat_surface = core / "chat_surface.py"
    tui = core / "tui.py"
    version = core / "version.py"
    for p in (config, bridge, companion, prospective, chat_surface, tui, version):
        if not p.is_file():
            raise SystemExit(f"missing RC13 source: {p}")

    direct = r'''from __future__ import annotations

import re
import time
from dataclasses import dataclass

from .prospective import extract_prospectives


_SIMPLE_OPEN = re.compile(r"^\s*(?:buka|open|jalankan|launch)\s+(?:aplikasi\s+|app\s+)?(.+?)\s*[.!]?\s*$", re.I)
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
        mode = str(getattr(self.cfg, "device_control_mode", "normal") or "normal").lower()
        return mode if mode in {"normal", "shizuku", "root"} else "normal"

    def _control(self, action: dict):
        payload = dict(action)
        payload.setdefault("mode", self._mode())
        return self.bridge.control(payload)

    def _apps(self) -> list[dict]:
        now = time.monotonic()
        if self._apps_cache and now - self._apps_at < 45:
            return self._apps_cache
        try:
            raw = self.bridge.apps()
            apps = raw.get("apps") if isinstance(raw, dict) else []
            self._apps_cache = [x for x in apps if isinstance(x, dict)] if isinstance(apps, list) else []
            self._apps_at = now
        except Exception:
            pass
        return self._apps_cache

    def _resolve_app(self, name: str) -> str:
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
            elif label.startswith(wanted) or wanted.startswith(label):
                score = 80
            elif wanted in label:
                score = 65
            elif wanted in package.casefold():
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

    def try_execute(self, text: str) -> DirectResult:
        raw = " ".join(str(text or "").split())
        if not raw:
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
            package = self._resolve_app(match.group(1))
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
            action = {"type": "scroll_global", "direction": "backward" if direction in {"atas", "up"} else "forward"}
            try:
                result = self.bridge.action(action)
                if isinstance(result, dict) and result.get("ok"):
                    self.store.log_event("direct_control", {"type": "scroll_global"})
                    return DirectResult(True, "Selesai.")
            except Exception:
                pass
            return DirectResult(False)

        match = _TAP.match(raw)
        if match and not _SENSITIVE.search(match.group(1)):
            node = self._single_node(match.group(1))
            if node:
                action = {"type": "tap_node", "node": int(node.get("id", -1))}
                try:
                    result = self.bridge.action(action)
                    if isinstance(result, dict) and result.get("ok"):
                        self.store.log_event("direct_control", {"type": "tap_node"})
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
'''
    (core / "direct_control.py").write_text(direct, encoding="utf-8")

    # Bridge client: privileged/direct endpoint is separate from Accessibility.
    b = bridge.read_text(encoding="utf-8")
    b = replace_once(
        b,
        '''    def action(self, action: dict):
        return self._request("POST", "/action", action)

    def screenshot_base64(self) -> str:
''',
        '''    def action(self, action: dict):
        return self._request("POST", "/action", action)

    def control(self, action: dict):
        return self._request("POST", "/control", action, timeout=20)

    def control_status(self):
        return self._request("GET", "/control/status", timeout=6)

    def screenshot_base64(self) -> str:
''',
        "bridge direct control endpoint",
    )
    bridge.write_text(b, encoding="utf-8")

    # Config migration: explicit user-selectable Normal/Shizuku/Root mode.
    c = config.read_text(encoding="utf-8")
    c = replace_once(c, '    config_revision: int = 9\n', '    config_revision: int = 10\n', "config revision")
    c = replace_once(
        c,
        '    agent_task_approval: bool = True\n',
        '    agent_task_approval: bool = True\n    device_control_mode: str = "normal"\n    direct_control_enabled: bool = True\n',
        "device control config",
    )
    c = replace_once(
        c,
        '    if defaults.get("routing_mode") not in {"local", "auto", "online"}:\n        defaults["routing_mode"] = "local"\n',
        '    if defaults.get("routing_mode") not in {"local", "auto", "online"}:\n        defaults["routing_mode"] = "local"\n    if defaults.get("device_control_mode") not in {"normal", "shizuku", "root"}:\n        defaults["device_control_mode"] = "normal"\n',
        "device mode validation",
    )
    config.write_text(c, encoding="utf-8")

    # Accept natural Indonesian suffix: "5 menit lagi" as well as "dalam 5 menit".
    p = prospective.read_text(encoding="utf-8")
    p = replace_once(
        p,
        '_IN = re.compile(r"\\bdalam\\s+(\\d{1,4})\\s*(menit|minute|minutes|jam|hour|hours|hari|day|days)\\b", re.I)\n',
        '_IN = re.compile(r"\\bdalam\\s+(\\d{1,4})\\s*(menit|minute|minutes|jam|hour|hours|hari|day|days)\\b", re.I)\n_LATER = re.compile(r"\\b(\\d{1,4})\\s*(menit|minute|minutes|jam|hour|hours|hari|day|days)\\s+lagi\\b", re.I)\n',
        "relative reminder suffix",
    )
    p = replace_once(p, '    relative = _IN.search(low)\n', '    relative = _IN.search(low) or _LATER.search(low)\n', "relative reminder parser")
    prospective.write_text(p, encoding="utf-8")

    # Companion owns the deterministic first hop. The legacy Termux reminder
    # thread is not started anymore; Android Bridge persists scheduled alarms.
    co = companion.read_text(encoding="utf-8")
    co = replace_once(co, 'from .events import DeviceEventDaemon\n', 'from .events import DeviceEventDaemon\nfrom .direct_control import DirectDeviceControl, DirectResult\n', "direct import")
    co = replace_once(
        co,
        '''        self.events = DeviceEventDaemon(cfg, store, self.bridge)
        self.events.start()
        self.reminders = ReminderDaemon(store)
        self.reminders.start()
''',
        '''        self.events = DeviceEventDaemon(cfg, store, self.bridge)
        self.events.start()
        self.direct = DirectDeviceControl(cfg, store, self.bridge)
''',
        "android reminder ownership",
    )
    co = replace_once(
        co,
        '    def classify(self, text: str) -> Intent:\n',
        '''    def try_direct(self, text: str) -> DirectResult:
        if not getattr(self.cfg, "direct_control_enabled", True):
            return DirectResult(False)
        try:
            return self.direct.try_execute(text)
        except Exception as exc:
            self.store.log_event("direct_control_error", {"error": str(exc)[:240]})
            return DirectResult(False)

    def classify(self, text: str) -> Intent:
''',
        "direct method",
    )
    co = replace_once(
        co,
        '''    def respond(self, text: str, approve, *, task_authorized: bool = False) -> tuple[str, str]:
        intent = self.classify(text)
''',
        '''    def respond(self, text: str, approve, *, task_authorized: bool = False) -> tuple[str, str]:
        direct = self.try_direct(text)
        if direct.handled:
            self.store.add_message("user", text)
            self.store.add_message("assistant", direct.reply)
            return direct.reply, direct.kind
        intent = self.classify(text)
''',
        "legacy direct first",
    )
    companion.write_text(co, encoding="utf-8")

    # Textual chat: direct actions complete before intent LLM/planner. No mode,
    # backend, diagnostics or tool traces are added to the conversation surface.
    ch = chat_surface.read_text(encoding="utf-8")
    ch = replace_once(
        ch,
        '''        def _respond(self, text: str, assistant_id: str) -> None:
            try:
                intent = self.session.classify(text)
''',
        '''        def _respond(self, text: str, assistant_id: str) -> None:
            try:
                direct = self.session.try_direct(text)
                if direct.handled:
                    self.session.store.add_message("user", text)
                    self.session.store.add_message("assistant", direct.reply)
                    self.call_from_thread(self._finalize, assistant_id, direct.reply)
                    return
                intent = self.session.classify(text)
''',
        "chat direct first",
    )
    chat_surface.write_text(ch, encoding="utf-8")

    # Settings only: status stays outside chat to keep conversation clean.
    t = tui.read_text(encoding="utf-8")
    context_line = r'''        console.print(f"[dim]Context[/]    {cfg.context_size}\n")
'''
    status_block = r'''        status = ""
        try:
            control = AndroidBridge(cfg).control_status()
            selected = str(cfg.device_control_mode).lower()
            if selected == "shizuku":
                status = "siap" if control.get("shizuku_ready") else "perlu izin"
            elif selected == "root":
                status = "siap" if control.get("root_ready") else "perlu izin"
            else:
                status = "Accessibility"
        except Exception:
            status = "Bridge offline"
        console.print(f"[dim]Kontrol[/]     {cfg.device_control_mode.upper()} · {status}")
'''
    t = replace_once(t, context_line, status_block + context_line, "settings status row")
    old_choice = '        choice = _choose("", ["Nama panggilan", "Nama Furina", "Toggle local auto-start", "Back"], height=6)\n'
    new_choice = '        choice = _choose("", ["Nama panggilan", "Nama Furina", "Kontrol perangkat", "Toggle local auto-start", "Back"], height=7)\n'
    t = replace_once(t, old_choice, new_choice, "settings control choice")
    toggle_marker = '        elif choice == "Toggle local auto-start":\n'
    mode_block = r'''        elif choice == "Kontrol perangkat":
            mode = _choose("Kontrol perangkat", ["Normal", "Shizuku", "Root", "Back"], height=6)
            if mode in {"Normal", "Shizuku", "Root"}:
                cfg.device_control_mode = mode.lower()
                if mode in {"Shizuku", "Root"}:
                    try:
                        result = AndroidBridge(cfg).control({"type": "prepare_" + mode.lower(), "mode": mode.lower()})
                        message = str(result.get("message") or ("Siap" if result.get("ok") else "Izin belum aktif"))
                        console.print(f"[dim]{message}[/]")
                        _pause()
                    except Exception:
                        console.print("[yellow]Bridge belum siap. Mode tersimpan; aktifkan izinnya nanti.[/]")
                        _pause()
'''
    t = replace_once(t, toggle_marker, mode_block + toggle_marker, "settings mode selection")
    tui.write_text(t, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = replace_once(v, 'VERSION = "1.0.0-rc11"', 'VERSION = "1.0.0-rc13"', "core version")
    version.write_text(v, encoding="utf-8")

    for pth in (config, bridge, companion, prospective, chat_surface, tui, core / "direct_control.py", version):
        compile(pth.read_text(encoding="utf-8"), str(pth), "exec")

    required = [
        (config, 'device_control_mode: str = "normal"'),
        (config, 'config_revision: int = 10'),
        (bridge, '"/control"'),
        (companion, 'self.direct = DirectDeviceControl'),
        (companion, 'def try_direct'),
        (chat_surface, 'direct = self.session.try_direct(text)'),
        (tui, '"Kontrol perangkat"'),
        (prospective, '_LATER = re.compile'),
        (version, 'VERSION = "1.0.0-rc13"'),
    ]
    missing = [needle for pth, needle in required if needle not in pth.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC13 core incomplete: " + ", ".join(missing))
    if "self.reminders.start()" in companion.read_text(encoding="utf-8"):
        raise SystemExit("RC13 must not depend on Termux reminder daemon")
    print("Furina RC13 direct-first control + Android reminder routing: OK")


if __name__ == "__main__":
    main()
