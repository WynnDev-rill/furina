#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"RC29 marker mismatch {label}: {n}")
    return text.replace(old, new, 1)


def block(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if replacement.strip() in text:
            return text
        raise SystemExit(f"RC29 block marker missing {label}: start={a} end={b}")
    return text[:a] + replacement.rstrip() + "\n\n" + text[b:]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-universal-ui-core-rc29.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    agent = core / "agent.py"
    version = core / "version.py"
    if not agent.is_file() or not version.is_file():
        raise SystemExit("missing RC29 Core source")

    a = agent.read_text(encoding="utf-8")

    compiler = r'''    def _compile_semantic_sequence(self, steps: list[dict], apps: list[dict]) -> list[dict]:
        installed = {str(x.get("package") or "") for x in apps if isinstance(x, dict)}
        out: list[dict] = []
        items = [x for x in steps[:18] if isinstance(x, dict)]
        for index, item in enumerate(items):
            typ = str(item.get("type") or "")
            if typ == "open_app":
                package = str(item.get("package") or "")
                if package not in installed:
                    break
                out.append({"type": "open_app", "package": package, "_semantic_type": "open_app", "_semantic_index": index})
            elif typ == "search":
                query = str(item.get("query") or "").strip()
                if not query:
                    break
                next_target = ""
                if index + 1 < len(items) and str(items[index + 1].get("type") or "") == "select":
                    next_target = sanitize(str(items[index + 1].get("target") or "")).strip()[:120]
                out.append({"type": "tap_text", "role": "search", "max_scrolls": 0, "_semantic_type": "search", "_semantic_index": index})
                out.append({"type": "set_text_best", "text": query[:4000], "role": "search", "_semantic_type": "search", "_semantic_index": index})
                submit = {"type": "ime_best", "role": "search", "_semantic_type": "search", "_semantic_index": index}
                if next_target:
                    submit["optional_if_target_visible"] = next_target
                    submit["result_mode"] = True
                out.append(submit)
            elif typ == "select":
                target = sanitize(str(item.get("target") or "")).strip()[:120]
                if not target or DESTRUCTIVE_WORDS.search(target):
                    break
                out.append({
                    "type": "tap_text",
                    "target": target,
                    "result_mode": True,
                    "max_scrolls": 2,
                    "require_change": True,
                    "transition_timeout_ms": 3200,
                    "_semantic_type": "select",
                    "_semantic_index": index,
                })
            elif typ == "type":
                value = str(item.get("text") or "")
                if not value:
                    break
                role = str(item.get("field_role") or "input").strip().lower()
                if index + 1 < len(items) and str(items[index + 1].get("type") or "") == "send":
                    role = "message"
                if role not in {"search", "message", "input"}:
                    role = "input"
                out.append({
                    "type": "set_text_best",
                    "text": value[:4000],
                    "role": role,
                    "_semantic_type": "type",
                    "_semantic_index": index,
                })
            elif typ == "scroll":
                out.append({
                    "type": "scroll_best",
                    "direction": "backward" if str(item.get("direction") or "") == "backward" else "forward",
                    "_semantic_type": "scroll",
                    "_semantic_index": index,
                })
            elif typ in {"back", "home", "recents"}:
                out.append({"type": typ, "_semantic_type": typ, "_semantic_index": index})
            elif typ == "tap":
                target = sanitize(str(item.get("target") or "")).strip()[:100]
                if not target or EXTERNAL_WORDS.search(target) or DESTRUCTIVE_WORDS.search(target):
                    break
                out.append({
                    "type": "tap_text",
                    "target": target,
                    "max_scrolls": 2,
                    "_semantic_type": "tap",
                    "_semantic_index": index,
                })
            elif typ == "send":
                break
            else:
                break
            if len(out) >= 17:
                return out[:17]
        return out[:17]
'''
    a = block(
        a,
        "    def _compile_semantic_sequence(self, steps: list[dict], apps: list[dict]) -> list[dict]:\n",
        "    def _contract(",
        compiler,
        "result-aware semantic compiler",
    )

    planner = r'''    def _plan(self, goal: str, contract: TaskContract, screen: dict, history: list[dict], apps: list[dict]) -> AgentStep:
        semantic = [
            x for x in getattr(self, "_active_semantic_steps", [])
            if isinstance(x, dict)
        ][:18]
        prompt = (
            f"TUGAS ANDROID: {goal}\n"
            f"TARGET PACKAGE: {contract.target_package}\n"
            f"SEMANTIC_STEPS: {json.dumps(semantic, ensure_ascii=False)[:9000]}\n"
            f"STATE: {json.dumps(self._compact_screen(screen), ensure_ascii=False)[:22000]}\n"
            f"RIWAYAT: {json.dumps(history[-14:], ensure_ascii=False)[:10000]}\n"
            f"APP: {json.dumps(apps, ensure_ascii=False)[:10000]}\n\n"
            "Pilih tepat satu aksi berikutnya sebagai JSON:\n"
            '{"summary":"singkat","action":{"type":"observe|wait|tap_node|tap|long_press|swipe|scroll_node|scroll_global|set_text|ime_action|back|home|recents|open_app|finish", ...}}\n\n'
            "Aturan universal:\n"
            "- Gunakan layar AKTUAL dan SEMANTIC_STEPS sebagai urutan niat. Jangan menebak UI aplikasi tertentu.\n"
            "- Jangan ulangi open_app, query pencarian, atau set_text yang RIWAYAT sudah membuktikan berhasil.\n"
            "- Jika query sudah berada di field pencarian tetapi hasil belum terlihat, pilih wait/observe; JANGAN mengetik query yang sama lagi.\n"
            "- Saat langkah berikutnya adalah select, JANGAN pilih field editable/focused pencarian walaupun teksnya sama dengan target. Pilih kandidat hasil non-editable atau ancestor clickable-nya.\n"
            "- Setelah select/tap yang dimaksudkan membuka item, tunggu perubahan layar nyata sebelum mengetik ke konteks berikutnya.\n"
            "- Untuk type dengan field_role=message, hanya gunakan field pesan/chat/reply/comment. Jangan gunakan field search.\n"
            "- Jika field yang benar belum ada, observe/wait atau navigasi lagi; jangan menulis ke field yang salah.\n"
            "- finish hanya jika tujuan benar-benar terlihat selesai.\n"
            "- open_app hanya package dari daftar APP.\n"
            "- Jangan ulangi aksi eksternal yang mungkin sudah berhasil."
        )
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": "Kamu planner Android internal berbasis state. Output satu JSON valid saja."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=560,
                temperature=0.0,
                json_mode=True,
            )
            obj = _first_json_object(raw) or {}
            action = obj.get("action") if isinstance(obj, dict) else None
            if isinstance(action, dict) and str(action.get("type") or "") in ALLOWED:
                return AgentStep(sanitize(str(obj.get("summary") or ""))[:320], action)
        except Exception as exc:
            self.store.log_event("agent_plan_error", {"error": str(exc)[:300]})
        return AgentStep("Amati layar terbaru", {"type": "observe"})
'''
    a = block(
        a,
        "    def _plan(self, goal: str, contract: TaskContract, screen: dict, history: list[dict], apps: list[dict]) -> AgentStep:\n",
        "    @staticmethod\n    def _node_for_action",
        planner,
        "state-aware planner",
    )

    risk_block = r'''    @staticmethod
    def _screen_has_exact_editable_text(screen: dict, text: str) -> bool:
        wanted = " ".join(str(text or "").split())
        if not wanted:
            return False
        for node in screen.get("nodes") or []:
            if not isinstance(node, dict) or not bool(node.get("editable")):
                continue
            actual = " ".join(str(node.get("text") or "").split())
            if actual == wanted:
                return True
        return False

    def risk(self, screen: dict, action: dict) -> tuple[str, str]:
        typ = str(action.get("type") or "")
        pieces = [str(action.get(k) or "") for k in ("text", "target", "summary")]
        target = action.get("target")
        if isinstance(target, dict):
            pieces.extend(str(target.get(k) or "") for k in ("text", "desc", "view_id", "class"))
        node = self._node_for_action(screen, action)
        if isinstance(node, dict):
            pieces.extend(str(node.get(k) or "") for k in ("text", "desc", "view_id", "class"))
        text = " ".join(pieces)
        if DESTRUCTIVE_WORDS.search(text):
            return "blocked", "aksi destruktif diblokir"
        if bool(action.get("_external")) or typ in {"send", "call"} or EXTERNAL_WORDS.search(text):
            return "external", "aksi berdampak keluar perangkat"
        if typ in {"set_text", "ime_action"}:
            return "write", "mengubah isi field"
        if typ in {"tap_node", "tap", "long_press", "swipe", "scroll_node", "scroll_global", "back", "home", "recents", "open_app"}:
            return "navigate", "navigasi layar"
        if typ in {"observe", "wait", "finish"}:
            return "safe", "tanpa perubahan eksternal"
        return "uncertain", "aksi tidak dikenali"
'''
    a = block(
        a,
        "    def risk(self, screen: dict, action: dict) -> tuple[str, str]:\n",
        "    @staticmethod\n    def _history_action_succeeded",
        risk_block,
        "node-aware risk and exact field guard",
    )

    a = rep(
        a,
        '''        history: list[dict] = []
        apps = self._apps()
''',
        '''        history: list[dict] = []
        self._active_semantic_steps = [dict(x) for x in (semantic_steps or []) if isinstance(x, dict)][:18]
        apps = self._apps()
''',
        "active semantic state",
    )

    duplicate_guard = r'''            if typ == "set_text":
                value = str(payload.get("text") or "")
                normalized = " ".join(value.split())
                recent_same = False
                for previous in reversed(history[-10:]):
                    executed0 = previous.get("executed") or previous.get("action") or {}
                    if not isinstance(executed0, dict):
                        continue
                    previous_type = str(executed0.get("type") or "")
                    previous_text = " ".join(str(executed0.get("text") or "").split())
                    result0 = previous.get("result")
                    succeeded = (
                        (isinstance(result0, dict) and bool(result0.get("ok")))
                        or result0 == "duplicate_suppressed"
                    )
                    if previous_type in {"set_text", "set_text_best"} and succeeded and previous_text == normalized:
                        recent_same = True
                        break
                if normalized and self._screen_has_exact_editable_text(screen, value) and recent_same:
                    history.append({
                        "action": action,
                        "executed": payload,
                        "result": "duplicate_suppressed",
                        "step": step_index + 1,
                        "state_changed": False,
                    })
                    status = self._verify_goal(goal, contract, screen, history)
                    if status.done:
                        return completed(status.result or "Selesai.", screen)
                    continue
'''
    a = block(
        a,
        '            if typ == "set_text":\n',
        '            before = self._screen_signature(screen)\n',
        duplicate_guard,
        "cross-selector duplicate write suppression",
    )

    agent.write_text(a, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = rep(v, 'VERSION = "1.0.0-rc28"', 'VERSION = "1.0.0-rc29"', "Core version")
    version.write_text(v, encoding="utf-8")

    for path in (agent, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    final = agent.read_text(encoding="utf-8")
    required = (
        '"result_mode": True',
        '"optional_if_target_visible"',
        "SEMANTIC_STEPS:",
        "JANGAN pilih field editable/focused pencarian",
        "def _screen_has_exact_editable_text",
        "pieces.extend",
        "self._active_semantic_steps",
        "duplicate_suppressed",
    )
    missing = [needle for needle in required if needle not in final]
    if missing:
        raise SystemExit("RC29 Core incomplete: " + ", ".join(missing))
    if 'VERSION = "1.0.0-rc29"' not in version.read_text(encoding="utf-8"):
        raise SystemExit("RC29 version missing")
    print("Furina Core RC29 universal state-aware UI execution: OK")


if __name__ == "__main__":
    main()
