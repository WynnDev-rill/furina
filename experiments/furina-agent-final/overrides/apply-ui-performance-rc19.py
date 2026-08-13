#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC19 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def before(text: str, marker: str, block: str, label: str) -> str:
    if block.strip() in text:
        return text
    count = text.count(marker)
    if count != 1:
        raise SystemExit(f"RC19 insertion mismatch {label}: {count}")
    return text.replace(marker, block.rstrip() + "\n\n" + marker, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-ui-performance-rc19.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    agent = core / "agent.py"
    direct = core / "direct_control.py"
    version = core / "version.py"
    for path in (agent, direct, version):
        if not path.is_file():
            raise SystemExit(f"missing RC19 source: {path}")

    # Simple commands should be one Core->Bridge request instead of a screen
    # snapshot followed by a second request.
    d = direct.read_text(encoding="utf-8")
    d = rep(
        d,
        r'_SIMPLE_OPEN = re.compile(r"^\s*(?:buka|open|jalankan|launch)\s+(?:aplikasi\s+|app\s+)?(.+?)\s*[.!]?\s*$", re.I)',
        r'_SIMPLE_OPEN = re.compile(r"^\s*(?:(?:tolong|coba)\s+)?(?:buka|bukakan|bukain|open|jalankan|launch)\s+(?:(?:aplikasi|app|apk)\s+)?(.+?)\s*[.!]?\s*$", re.I)',
        "natural open parser",
    )
    d = rep(d, "        if self._apps_cache and now - self._apps_at < 45:", "        if self._apps_cache and now - self._apps_at < 900:", "app cache")
    d = rep(
        d,
        '''        match = _SCROLL.match(raw)
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
            return DirectResult(False)''',
        '''        match = _SCROLL.match(raw)
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
            return DirectResult(False)''',
        "direct semantic scroll",
    )
    d = rep(
        d,
        '''        match = _TAP.match(raw)
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
            return DirectResult(False)''',
        '''        match = _TAP.match(raw)
        if match and not _SENSITIVE.search(match.group(1)):
            action = {"type": "tap_text", "target": match.group(1)}
            try:
                result = self.bridge.action(action)
                if isinstance(result, dict) and result.get("ok"):
                    self.store.log_event("direct_control", {"type": "tap_text"})
                    return DirectResult(True, "Selesai.")
            except Exception:
                pass
            return DirectResult(False)''',
        "direct semantic tap",
    )
    direct.write_text(d, encoding="utf-8")

    a = agent.read_text(encoding="utf-8")
    methods = r'''    def _compile_ui_sequence(self, goal: str, contract: TaskContract, apps: list[dict]) -> list[dict]:
        if contract.external_expected or EXTERNAL_WORDS.search(goal) or DESTRUCTIVE_WORDS.search(goal):
            return []
        packages = {str(x.get("package") or "") for x in apps if isinstance(x, dict) and x.get("package")}
        prompt = f"""
Ubah tujuan Android menjadi satu urutan UI pendek yang dapat dijalankan lokal tanpa memanggil model di antara langkah.
TUJUAN: {goal}
APLIKASI: {json.dumps(apps, ensure_ascii=False)[:9000]}
Output JSON: {{"confidence":0.0,"steps":[{{"type":"..."}}]}}
Tipe: open_app, tap_text, set_text_best, ime_best, scroll_best, wait_text, wait_package, back, home, recents.
Maksimal 10 langkah. Package harus berasal dari daftar aplikasi. tap_text/wait_text memakai target atau targets (maksimal 4 alternatif label). scroll_best memakai forward/backward. wait_* timeout maksimal 1800 ms.
Jangan buat urutan jika langkah berikutnya membutuhkan penilaian atas konten yang belum terlihat. Jangan gunakan urutan ini untuk tindakan eksternal/destruktif. Jangan gunakan koordinat, screenshot, shell, atau kontrol privileged. Jika tidak cukup pasti, steps=[].
""".strip()
        try:
            raw = self.llm.chat([
                {"role": "system", "content": "Kamu compiler UI Android internal. Output JSON valid saja."},
                {"role": "user", "content": prompt},
            ], max_tokens=650, temperature=0.0, json_mode=True)
            obj = _first_json_object(str(raw)) or {}
            if float(obj.get("confidence", 0.0) or 0.0) < 0.74:
                return []
            items = obj.get("steps")
            if not isinstance(items, list) or not items or len(items) > 10:
                return []
            allowed = {"open_app", "tap_text", "set_text_best", "ime_best", "scroll_best", "wait_text", "wait_package", "back", "home", "recents"}
            out: list[dict] = []
            for item in items:
                if not isinstance(item, dict):
                    return []
                typ = str(item.get("type") or "")
                if typ not in allowed:
                    return []
                step = {"type": typ}
                if typ in {"open_app", "wait_package"}:
                    pkg = str(item.get("package") or "")
                    if pkg not in packages:
                        return []
                    step["package"] = pkg
                if typ in {"tap_text", "wait_text"}:
                    target = sanitize(str(item.get("target") or "")).strip()[:100]
                    targets = []
                    if isinstance(item.get("targets"), list):
                        targets = [sanitize(str(x)).strip()[:80] for x in item["targets"][:4] if str(x).strip()]
                        targets = [x for x in targets if not EXTERNAL_WORDS.search(x) and not DESTRUCTIVE_WORDS.search(x)]
                    if target and not EXTERNAL_WORDS.search(target) and not DESTRUCTIVE_WORDS.search(target):
                        step["target"] = target
                    elif not targets:
                        return []
                    if targets:
                        step["targets"] = targets
                if typ == "set_text_best":
                    value = str(item.get("text") or "")
                    if len(value) > 2000:
                        return []
                    step["text"] = value
                if typ == "scroll_best":
                    step["direction"] = "backward" if str(item.get("direction") or "forward").lower() == "backward" else "forward"
                if typ in {"wait_text", "wait_package"}:
                    try:
                        timeout = int(item.get("timeout_ms", 1100) or 1100)
                    except Exception:
                        timeout = 1100
                    step["timeout_ms"] = max(120, min(timeout, 1800))
                out.append(step)
            return out
        except Exception as exc:
            self.store.log_event("ui_sequence_compile_error", {"error": str(exc)[:240]})
            return []

    def _try_ui_sequence(self, goal: str, contract: TaskContract, apps: list[dict], approve, task_authorized: bool, history: list[dict]):
        steps = self._compile_ui_sequence(goal, contract, apps)
        if not steps:
            return None, None, False
        risk = "write" if any(str(x.get("type") or "") in {"set_text_best", "ime_best"} for x in steps) else "navigate"
        if (not task_authorized) and not approve("Urutan UI lokal Furina", {"type": "run_ui_sequence", "steps": steps}, risk, "menjalankan langkah UI yang sudah direncanakan"):
            return "Aksi itu dibatalkan.", None, True
        started = time.monotonic()
        try:
            result = self.tools.execute({"type": "run_ui_sequence", "steps": steps})
        except Exception as exc:
            self.store.log_event("ui_sequence_error", {"error": str(exc)[:240]})
            return None, None, True
        completed = max(0, min(int(result.get("completed_steps", 0) or 0), len(steps))) if isinstance(result, dict) else 0
        for index, step in enumerate(steps[:completed]):
            typ = str(step.get("type") or "")
            mapped = {"tap_text":"tap_node", "set_text_best":"set_text", "ime_best":"ime_action", "scroll_best":"scroll_global"}.get(typ, typ)
            evidence = {"ok": True}
            if typ == "set_text_best":
                evidence["verified_text"] = True
            history.append({"action": {**step, "type": mapped}, "executed": step, "result": evidence, "risk": "write" if typ in {"set_text_best", "ime_best"} else "navigate", "ui_sequence": True, "step": index + 1, "state_changed": True})
        try:
            screen = self.bridge.screen()
        except Exception:
            screen = None
        self.store.log_event("ui_sequence_run", {"ok": bool(isinstance(result, dict) and result.get("ok")), "steps": len(steps), "completed": completed, "ms": int((time.monotonic() - started) * 1000)})
        if not isinstance(result, dict) or not result.get("ok") or screen is None:
            return None, screen, True
        hard_ok, _ = self._deterministic_gate(contract, screen, history)
        if hard_ok:
            status = self._verify_goal(goal, contract, screen, history)
            if status.done:
                return status.result or "Selesai.", screen, True
        return None, screen, True
'''
    a = before(a, "    def _interruptible(self, cancel_event: threading.Event, fn, label: str):\n", methods, "UI sequence methods")
    a = rep(
        a,
        '''        fast_result, fast_screen, fast_attempted = self._try_fast_skill(
            goal, contract, approve, task_authorized, cancel_event, history
        )
        if fast_result is not None:
            if fast_result == "Selesai." and fast_screen is not None:
                return completed(fast_result, fast_screen)
            return fast_result

        for step_index in range(self.cfg.agent_max_steps):
''',
        '''        fast_result, fast_screen, fast_attempted = self._try_fast_skill(
            goal, contract, approve, task_authorized, cancel_event, history
        )
        if fast_result is not None:
            if fast_result == "Selesai." and fast_screen is not None:
                return completed(fast_result, fast_screen)
            return fast_result

        sequence_result, sequence_screen, sequence_attempted = self._try_ui_sequence(
            goal, contract, apps, approve, task_authorized, history
        )
        if sequence_result is not None:
            if sequence_screen is not None:
                return completed(sequence_result, sequence_screen)
            return sequence_result

        for step_index in range(self.cfg.agent_max_steps):
''',
        "UI sequence invocation",
    )
    agent.write_text(a, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = rep(v, 'VERSION = "1.0.0-rc18"', 'VERSION = "1.0.0-rc19"', "Core version")
    version.write_text(v, encoding="utf-8")
    for path in (agent, direct, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    required = [
        (agent, "def _compile_ui_sequence"),
        (agent, "def _try_ui_sequence"),
        (agent, '"type": "run_ui_sequence"'),
        (direct, '"type": "tap_text"'),
        (direct, '"type": "scroll_best"'),
        (version, 'VERSION = "1.0.0-rc19"'),
    ]
    missing = [needle for path, needle in required if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC19 Core incomplete: " + ", ".join(missing))
    print("Furina Core RC19 continuous UI sequence: OK")


if __name__ == "__main__":
    main()
