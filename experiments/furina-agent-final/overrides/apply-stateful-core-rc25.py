#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"RC25 marker mismatch {label}: {n}")
    return text.replace(old, new, 1)


def block(text: str, start: str, end: str, new: str, label: str) -> str:
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if new.strip() in text:
            return text
        raise SystemExit(f"RC25 block marker missing {label}")
    return text[:a] + new.rstrip() + "\n\n" + text[b:]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-stateful-core-rc25.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    companion = core / "companion.py"
    agent = core / "agent.py"
    version = core / "version.py"
    for path in (companion, agent, version):
        if not path.is_file():
            raise SystemExit(f"missing RC25 source: {path}")

    c = companion.read_text(encoding="utf-8")
    c = rep(
        c,
        '''            for key, limit in (("query", 1000), ("text", 4000), ("target", 180)):
                value = str(item.get(key) or "").strip()
                if value:
                    step[key] = value[:limit]
            if typ == "scroll":
''',
        '''            for key, limit in (("query", 1000), ("text", 4000), ("target", 180)):
                value = str(item.get(key) or "").strip()
                if value:
                    step[key] = value[:limit]
            field_role = str(item.get("field_role") or item.get("role") or "").strip().lower()
            if field_role in {"search", "message", "input"}:
                step["field_role"] = field_role
            if typ == "scroll":
''',
        "semantic field role",
    )
    c = rep(
        c,
        '''    {{"type":"open_app|search|tap|type|scroll|back|home|recents|read|select|send|unknown","app":"nama aplikasi bila relevan","package":"package dari daftar bila diketahui","query":"","text":"","target":"","direction":"forward|backward"}}
''',
        '''    {{"type":"open_app|search|tap|type|scroll|back|home|recents|read|select|send|unknown","app":"nama aplikasi bila relevan","package":"package dari daftar bila diketahui","query":"","text":"","target":"","field_role":"search|message|input","direction":"forward|backward"}}
''',
        "semantic schema",
    )
    c = rep(
        c,
        '''- search berarti benar-benar membuka UI pencarian, mengisi query, dan submit; bukan sekadar membuka aplikasi.
- Jika pengguna hanya bertanya atau meminta penjelasan, mode=chat dan steps=[].
- Jangan menambah tindakan yang tidak diminta.
''',
        '''- search berarti benar-benar membuka UI pencarian, mengisi query, dan submit; bukan sekadar membuka aplikasi.
- Jika hasil pencarian harus dibuka sebelum langkah berikutnya, tambahkan select dengan target teks/label hasil yang harus dipilih. Jangan melompati select.
- type berarti mengisi field pada konteks SAAT ITU. Untuk pesan/chat/reply/comment gunakan field_role=message; untuk form umum gunakan field_role=input. Jangan menaruh isi pesan ke field pencarian.
- send adalah efek eksternal terakhir untuk mengirim/submit isi yang sudah disiapkan. Pisahkan type dan send menjadi dua langkah; jangan menganggap mengetik berarti sudah terkirim.
- Untuk contoh "buka WhatsApp, cari Ariel, kirim pesan test": langkah yang benar adalah open_app -> search(query=Ariel) -> select(target=Ariel) -> type(text=test, field_role=message) -> send.
- Jika pengguna hanya bertanya atau meminta penjelasan, mode=chat dan steps=[].
- Jangan menambah tindakan yang tidak diminta.
''',
        "semantic state rules",
    )
    c = rep(c, "                max_tokens=360,\n", "                max_tokens=520,\n", "semantic token budget")
    companion.write_text(c, encoding="utf-8")

    a = agent.read_text(encoding="utf-8")
    semantic_method = '''    def _compile_semantic_sequence(self, steps: list[dict], apps: list[dict]) -> list[dict]:
        installed = {str(x.get("package") or "") for x in apps if isinstance(x, dict)}
        out: list[dict] = []
        for index, item in enumerate(steps[:18]):
            if not isinstance(item, dict):
                break
            typ = str(item.get("type") or "")
            if typ == "open_app":
                package = str(item.get("package") or "")
                if package not in installed:
                    break
                out.append({"type": "open_app", "package": package})
            elif typ == "search":
                query = str(item.get("query") or "").strip()
                if not query:
                    break
                out.extend([
                    {"type": "tap_text", "role": "search", "max_scrolls": 0},
                    {"type": "set_text_best", "text": query[:4000], "role": "search"},
                    {"type": "ime_best", "role": "search"},
                ])
            elif typ == "select":
                target = sanitize(str(item.get("target") or "")).strip()[:120]
                if not target or DESTRUCTIVE_WORDS.search(target):
                    break
                out.append({
                    "type": "tap_text",
                    "target": target,
                    "max_scrolls": 3,
                    "require_change": True,
                    "transition_timeout_ms": 2800,
                })
            elif typ == "type":
                value = str(item.get("text") or "")
                if not value:
                    break
                role = str(item.get("field_role") or "input").strip().lower()
                if index + 1 < len(steps) and isinstance(steps[index + 1], dict) and str(steps[index + 1].get("type") or "") == "send":
                    role = "message"
                if role not in {"search", "message", "input"}:
                    role = "input"
                out.append({"type": "set_text_best", "text": value[:4000], "role": role})
            elif typ == "scroll":
                out.append({"type": "scroll_best", "direction": "backward" if str(item.get("direction") or "") == "backward" else "forward"})
            elif typ in {"back", "home", "recents"}:
                out.append({"type": typ})
            elif typ == "tap":
                target = sanitize(str(item.get("target") or "")).strip()[:100]
                if not target or EXTERNAL_WORDS.search(target) or DESTRUCTIVE_WORDS.search(target):
                    break
                out.append({"type": "tap_text", "target": target, "max_scrolls": 2})
            elif typ == "send":
                # External send is appended only after a fresh, specific confirmation.
                break
            else:
                break
            if len(out) >= 17:
                return out[:17]
        return out[:17]
'''
    a = block(a, "    def _compile_semantic_sequence(self, steps: list[dict], apps: list[dict]) -> list[dict]:\n", "    def _try_ui_sequence(", semantic_method, "semantic compiler")

    helper = '''    def _semantic_send_action(self, semantic_steps: list[dict] | None) -> tuple[dict | None, str, str]:
        items = [x for x in (semantic_steps or []) if isinstance(x, dict)]
        if not items or str(items[-1].get("type") or "") != "send":
            return None, "", ""
        supported = {"open_app", "search", "select", "tap", "type", "scroll", "back", "home", "recents"}
        if any(str(x.get("type") or "") not in supported for x in items[:-1]):
            return None, "", ""
        message = ""
        target = ""
        for item in items[:-1]:
            typ = str(item.get("type") or "")
            if typ == "type" and str(item.get("text") or ""):
                message = str(item.get("text") or "")[:4000]
            if typ == "select" and str(item.get("target") or ""):
                target = sanitize(str(item.get("target") or "")).strip()[:120]
        if not message:
            return None, "", ""
        send_target = sanitize(str(items[-1].get("target") or "")).strip()[:100]
        action = {"type": "tap_text", "role": "send", "max_scrolls": 0, "_external": True}
        if send_target:
            action["targets"] = [send_target]
        summary = f"Kirim pesan ke {target}" if target else "Kirim pesan"
        detail = f'mengirim pesan "{message[:180]}"' + (f' ke "{target}"' if target else "")
        return action, summary, detail

'''
    marker = "    def _try_ui_sequence("
    if helper.strip() not in a:
        if a.count(marker) != 1:
            raise SystemExit(f"RC25 helper marker mismatch: {a.count(marker)}")
        a = a.replace(marker, helper + marker, 1)

    a = rep(
        a,
        '''        if not steps:
            return None, None, False
        risk = "write" if any(str(x.get("type") or "") in {"set_text_best", "ime_best"} for x in steps) else "navigate"
        if (not task_authorized) and not approve("Urutan UI lokal Furina", {"type": "run_ui_sequence", "steps": steps}, risk, "menjalankan langkah UI yang sudah direncanakan"):
            return "Aksi itu dibatalkan.", None, True
        started = time.monotonic()
        try:
            result = self.tools.execute({"type": "run_ui_sequence", "steps": steps})
''',
        '''        if not steps:
            return None, None, False
        risk = "write" if any(str(x.get("type") or "") in {"set_text_best", "ime_best"} for x in steps) else "navigate"
        if (not task_authorized) and not approve("Urutan UI lokal Furina", {"type": "run_ui_sequence", "steps": steps}, risk, "menjalankan langkah UI yang sudah direncanakan"):
            return "Aksi itu dibatalkan.", None, True
        send_action, send_summary, send_detail = self._semantic_send_action(semantic_steps)
        if send_action is not None:
            if not approve(send_summary, send_action, "external", send_detail):
                return "Pengiriman dibatalkan.", None, True
            steps = [*steps, send_action]
        started = time.monotonic()
        try:
            result = self.tools.execute({"type": "run_ui_sequence", "steps": steps})
''',
        "specific send approval",
    )
    a = rep(
        a,
        '''            history.append({"action": {**step, "type": mapped}, "executed": step, "result": evidence, "risk": "write" if typ in {"set_text_best", "ime_best"} else "navigate", "ui_sequence": True, "step": index + 1, "state_changed": True})
''',
        '''            step_risk = "external" if bool(step.get("_external")) else ("write" if typ in {"set_text_best", "ime_best"} else "navigate")
            history.append({"action": {**step, "type": mapped}, "executed": step, "result": evidence, "risk": step_risk, "ui_sequence": True, "step": index + 1, "state_changed": True})
''',
        "sequence risk history",
    )
    a = rep(
        a,
        '''        if not isinstance(result, dict) or not result.get("ok") or screen is None:
            return None, screen, True
        hard_ok, _ = self._deterministic_gate(contract, screen, history)
''',
        '''        if not isinstance(result, dict) or not result.get("ok") or screen is None:
            if send_action is not None and isinstance(result, dict) and int(result.get("completed_steps", 0) or 0) >= max(0, len(steps) - 1):
                self.store.log_event("semantic_send_not_executed", {"goal": goal, "result": result})
                return "Pesan sudah disiapkan, tetapi tombol kirim belum berhasil dijalankan. Tidak dicoba ulang otomatis agar tidak berisiko terkirim dua kali.", screen, True
            return None, screen, True
        if send_action is not None:
            self.store.log_event("semantic_send_completed", {"goal": goal, "steps": len(steps)})
            return "Berhasil.", screen, True
        hard_ok, _ = self._deterministic_gate(contract, screen, history)
''',
        "send terminal result",
    )

    a = rep(a, "        task_started = time.monotonic()\n", "        task_started = time.monotonic()\n        task_started_wall = time.time()\n", "wall clock lifecycle")

    watcher = '''        def watch_user_return():
            seen_outside = False
            returned_at = 0.0
            last_probe_at = 0.0
            while not cancel_event.is_set() and time.monotonic() - task_started < 300:
                package = str(self.store.get_state("device_foreground_package", "") or "")
                session = self.store.get_state("termux_session", {})
                if not isinstance(session, dict):
                    session = {}
                session_package = str(session.get("foreground_package") or "")
                try:
                    session_returned = float(session.get("last_returned_at", 0) or 0) >= task_started_wall - 0.10
                except Exception:
                    session_returned = False
                if (package and package not in TERMUX_PACKAGES) or bool(session.get("currently_away")) or (session_package and session_package not in TERMUX_PACKAGES):
                    seen_outside = True
                now = time.monotonic()
                returned = seen_outside and (package in TERMUX_PACKAGES or session_package in TERMUX_PACKAGES or session_returned)
                if not returned and seen_outside and now - last_probe_at >= 0.35:
                    last_probe_at = now
                    try:
                        probe = self.bridge.screen()
                        probe_package = str(probe.get("package") or "") if isinstance(probe, dict) else ""
                        probe_session = probe.get("termux_session") if isinstance(probe, dict) else {}
                        if not isinstance(probe_session, dict):
                            probe_session = {}
                        probe_session_package = str(probe_session.get("foreground_package") or "")
                        try:
                            probe_returned = float(probe_session.get("last_returned_at", 0) or 0) >= task_started_wall - 0.10
                        except Exception:
                            probe_returned = False
                        returned = probe_package in TERMUX_PACKAGES or probe_session_package in TERMUX_PACKAGES or probe_returned
                    except Exception:
                        pass
                if returned:
                    if returned_at <= 0.0:
                        returned_at = now
                    elif now - returned_at >= 0.08:
                        cancel_event.set()
                        return
                else:
                    returned_at = 0.0
                time.sleep(0.04)
        threading.Thread(target=watch_user_return, name="furina-return-watch", daemon=True).start()
'''
    a = block(a, "        def watch_user_return():\n", "        suggested = self.store.find_skills(", watcher, "return watcher")

    return_helper = '''        def user_returned_to_termux(screen: dict) -> bool:
            nonlocal left_termux, termux_return_candidate_at, last_external_screen
            package = str(screen.get("package") or "")
            session = screen.get("termux_session") if isinstance(screen, dict) else {}
            if not isinstance(session, dict):
                session = self.store.get_state("termux_session", {})
            if not isinstance(session, dict):
                session = {}
            session_package = str(session.get("foreground_package") or "")
            try:
                session_returned = float(session.get("last_returned_at", 0) or 0) >= task_started_wall - 0.10
            except Exception:
                session_returned = False
            now = time.monotonic()
            outside = (package and package not in TERMUX_PACKAGES) or bool(session.get("currently_away")) or (session_package and session_package not in TERMUX_PACKAGES)
            if outside:
                left_termux = True
                last_external_screen = screen
                termux_return_candidate_at = 0.0
                return False
            returned = left_termux and (package in TERMUX_PACKAGES or session_package in TERMUX_PACKAGES or session_returned)
            if returned:
                if termux_return_candidate_at <= 0.0:
                    termux_return_candidate_at = now
                    return False
                return now - termux_return_candidate_at >= 0.08
            termux_return_candidate_at = 0.0
            return False
'''
    a = block(a, "        def user_returned_to_termux(screen: dict) -> bool:\n", "        fast_result, fast_screen, fast_attempted = self._try_fast_skill(\n", return_helper, "return snapshot detector")
    a = rep(
        a,
        '''            if cancel_event.is_set():
                return "Tugas dihentikan karena kamu kembali ke Termux."
            if typ == "set_text":
''',
        '''            if cancel_event.is_set():
                return return_to_termux_result(last_external_screen)
            if typ == "set_text":
''',
        "post approval cancellation",
    )
    agent.write_text(a, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = rep(v, 'VERSION = "1.0.0-rc24"', 'VERSION = "1.0.0-rc25"', "core version")
    version.write_text(v, encoding="utf-8")

    for path in (companion, agent, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    checks = [
        (companion, '"field_role":"search|message|input"'),
        (companion, 'open_app -> search(query=Ariel) -> select(target=Ariel)'),
        (agent, 'elif typ == "select"'),
        (agent, '"require_change": True'),
        (agent, 'def _semantic_send_action'),
        (agent, 'semantic_send_completed'),
        (agent, 'task_started_wall = time.time()'),
        (agent, 'now - last_probe_at >= 0.35'),
        (version, 'VERSION = "1.0.0-rc25"'),
    ]
    missing = [needle for path, needle in checks if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC25 Core incomplete: " + ", ".join(missing))
    print("Furina Core RC25 state-aware semantic execution: OK")


if __name__ == "__main__":
    main()
