#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"RC28 marker mismatch {label}: {n}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-runtime-core-rc28.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    agent = core / "agent.py"
    version = core / "version.py"
    if not agent.is_file() or not version.is_file():
        raise SystemExit("missing RC28 Core source")

    a = agent.read_text(encoding="utf-8")
    runtime = '''    def _contract(self, goal: str, apps: list[dict], semantic_steps: list[dict] | None = None) -> TaskContract:
        semantic = self._semantic_contract(goal, semantic_steps or [], apps)
        if semantic is not None:
            self.store.log_event("agent_contract_semantic", {"goal": str(goal)[:240], "steps": len(semantic_steps or [])})
            return semantic
        installed = {str(x.get("package") or "") for x in apps if isinstance(x, dict)}
        package = ""
        for step in semantic_steps or []:
            if isinstance(step, dict) and str(step.get("type") or "") == "open_app":
                candidate = str(step.get("package") or "")
                if candidate in installed:
                    package = candidate
                    break
        if not package:
            low = str(goal or "").casefold()
            labels = sorted(
                [(str(x.get("label") or "").strip(), str(x.get("package") or "").strip()) for x in apps if isinstance(x, dict)],
                key=lambda item: len(item[0]), reverse=True,
            )
            for label, candidate in labels:
                if label and candidate and label.casefold() in low:
                    package = candidate
                    break
        return TaskContract(
            str(goal)[:300],
            [str(goal)[:300]],
            bool(EXTERNAL_WORDS.search(str(goal or ""))),
            self._requested_scrolls(goal),
            self._requested_write_text(goal),
            package,
        )

    @staticmethod
    def _compact_screen(screen: dict) -> dict:
        nodes = []
        for n in (screen.get("nodes") or [])[:120]:
            if not isinstance(n, dict):
                continue
            if not any(n.get(k) not in (None, "", False) for k in ("text", "desc", "view_id", "clickable", "editable", "scrollable")):
                continue
            nodes.append({k: n.get(k) for k in ("id", "text", "desc", "view_id", "class", "clickable", "editable", "scrollable", "focused", "bounds") if k in n})
        return {
            "ok": screen.get("ok"),
            "package": screen.get("package"),
            "window_title": screen.get("window_title"),
            "nodes": nodes,
            "vision_elements": (screen.get("vision_elements") or [])[:20],
        }

    @staticmethod
    def _actionable_count(screen: dict) -> int:
        return sum(1 for n in (screen.get("nodes") or []) if isinstance(n, dict) and any(bool(n.get(k)) for k in ("clickable", "editable", "scrollable", "focusable")))

    def _with_vision(self, goal: str, screen: dict) -> dict:
        # RC28 keeps the live Accessibility state authoritative. Vision remains
        # optional and must never be required for the basic agent runtime.
        return screen

    def _plan(self, goal: str, contract: TaskContract, screen: dict, history: list[dict], apps: list[dict]) -> AgentStep:
        prompt = f"""
TUGAS ANDROID: {goal}
TARGET PACKAGE: {contract.target_package}
STATE: {json.dumps(self._compact_screen(screen), ensure_ascii=False)[:22000]}
RIWAYAT: {json.dumps(history[-12:], ensure_ascii=False)[:9000]}
APP: {json.dumps(apps, ensure_ascii=False)[:10000]}

Pilih tepat satu aksi berikutnya sebagai JSON:
{{"summary":"singkat","action":{{"type":"observe|wait|tap_node|tap|long_press|swipe|scroll_node|scroll_global|set_text|ime_action|back|home|recents|open_app|finish", ...}}}}
Gunakan state layar aktual. Jangan mengarang target. open_app hanya package dari daftar APP. finish hanya jika tujuan benar-benar terlihat selesai.
""".strip()
        try:
            raw = self.llm.chat(
                [{"role": "system", "content": "Kamu planner Android internal. Output satu JSON valid saja."}, {"role": "user", "content": prompt}],
                max_tokens=520,
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

    @staticmethod
    def _node_for_action(screen: dict, action: dict) -> dict | None:
        try:
            node_id = int(action.get("node"))
        except Exception:
            return None
        for node in screen.get("nodes") or []:
            if isinstance(node, dict) and int(node.get("id", -1) or -1) == node_id:
                return node
        return None

    @staticmethod
    def _selector_from_node(node: dict | None) -> dict | None:
        if not isinstance(node, dict):
            return None
        out = {}
        for key in ("id", "view_id", "text", "desc", "class", "path", "bounds"):
            if node.get(key) not in (None, ""):
                out[key] = node.get(key)
        return out or None

    def _enrich_action(self, screen: dict, action: dict) -> dict:
        out = dict(action)
        node = self._node_for_action(screen, action)
        selector = self._selector_from_node(node)
        if selector is not None and "target" not in out:
            out["target"] = selector
        return out

    @staticmethod
    def _screen_signature(screen: dict) -> str:
        try:
            compact = {
                "package": screen.get("package"),
                "window_title": screen.get("window_title"),
                "nodes": [
                    (n.get("text"), n.get("desc"), n.get("view_id"), n.get("focused"), n.get("selected"), n.get("checked"))
                    for n in (screen.get("nodes") or [])[:100]
                    if isinstance(n, dict)
                ],
            }
            return json.dumps(compact, ensure_ascii=False, sort_keys=True, default=str)
        except Exception:
            return repr(screen)[:12000]

    @staticmethod
    def _result_ok(result) -> bool:
        if isinstance(result, dict):
            return bool(result.get("ok"))
        return bool(result)

    def risk(self, screen: dict, action: dict) -> tuple[str, str]:
        typ = str(action.get("type") or "")
        text = " ".join(str(action.get(k) or "") for k in ("text", "target", "summary"))
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

    @staticmethod
    def _history_action_succeeded(item: dict) -> bool:
        if not isinstance(item, dict):
            return False
        result = item.get("result")
        return bool(result.get("ok")) if isinstance(result, dict) else bool(result)

    @staticmethod
    def _screen_text(screen: dict) -> str:
        parts = []
        for n in screen.get("nodes") or []:
            if not isinstance(n, dict):
                continue
            for key in ("text", "desc"):
                value = str(n.get(key) or "").strip()
                if value:
                    parts.append(value)
        return "\n".join(parts)

    def _deterministic_gate(self, contract: TaskContract, screen: dict, history: list[dict]) -> tuple[bool, str]:
        package = str(screen.get("package") or "")
        if contract.target_package and package != contract.target_package:
            return False, "target package belum aktif"
        if contract.required_write_text:
            needle = " ".join(str(contract.required_write_text).casefold().split())
            hay = " ".join(self._screen_text(screen).casefold().split())
            wrote = any(
                str((h.get("action") or {}).get("type") or "") in {"set_text", "set_text_best"}
                and needle in " ".join(str((h.get("action") or {}).get("text") or "").casefold().split())
                and self._history_action_succeeded(h)
                for h in history if isinstance(h, dict)
            )
            if needle and needle not in hay and not wrote:
                return False, "teks yang diminta belum terverifikasi"
        if int(contract.required_scrolls or 0) > 0:
            scrolls = sum(1 for h in history if isinstance(h, dict) and str((h.get("action") or {}).get("type") or "") in {"scroll_node", "scroll_global", "swipe", "scroll_best"} and self._history_action_succeeded(h))
            if scrolls < int(contract.required_scrolls or 0):
                return False, "scroll yang diminta belum cukup"
        if contract.external_expected:
            external_ok = any(h.get("risk") == "external" and self._history_action_succeeded(h) for h in history if isinstance(h, dict))
            if not external_ok:
                return False, "aksi eksternal belum berhasil"
        return True, "bukti deterministik terpenuhi"

    def _verify_goal(self, goal: str, contract: TaskContract, screen: dict, history: list[dict]) -> GoalStatus:
        hard_ok, reason = self._deterministic_gate(contract, screen, history)
        if not hard_ok:
            return GoalStatus(False, 0.99, "", reason)
        low = str(goal or "").casefold()
        if any(word in low for word in ("cari", "search", "find")):
            submitted = any(str((h.get("action") or {}).get("type") or "") in {"ime_action", "ime_best"} and self._history_action_succeeded(h) for h in history if isinstance(h, dict))
            if not submitted:
                return GoalStatus(False, 0.90, "", "pencarian belum disubmit")
        return GoalStatus(True, 0.90, "Berhasil.", reason)

    def _finish_ready(self, goal: str, screen: dict, history: list[dict]) -> tuple[bool, str]:
        contract = TaskContract(str(goal)[:300], [str(goal)[:300]], bool(EXTERNAL_WORDS.search(str(goal or ""))))
        status = self._verify_goal(goal, contract, screen, history)
        return status.done, status.reason or status.result

    def _wait_after_action(self, screen: dict, before_event_seq: int, typ: str, cancel_event: threading.Event) -> dict:
        deadline = time.monotonic() + (1.2 if typ == "open_app" else 0.45)
        latest = screen
        while time.monotonic() < deadline and not cancel_event.is_set():
            time.sleep(0.06)
            try:
                candidate = self.bridge.screen()
            except Exception:
                continue
            if isinstance(candidate, dict):
                latest = candidate
                if self._screen_signature(candidate) != self._screen_signature(screen):
                    break
        return latest

    def _fast_completion(self, goal: str, contract: TaskContract, screen: dict, history: list[dict], steps: list[dict]) -> bool:
        ok, _ = self._deterministic_gate(contract, screen, history)
        return bool(ok and not contract.external_expected)

    def _try_fast_skill(self, goal: str, contract: TaskContract, approve, task_authorized: bool, cancel_event: threading.Event, history: list[dict]):
        # RC28 intentionally disables replay of learned UI skills until the
        # repaired runtime has accumulated fresh successful evidence. Semantic
        # sequence and live-state planner remain active.
        return None, None, False

'''

    if "    def _contract(" not in a:
        marker = "    def _semantic_send_action("
        if marker not in a:
            marker = "    def _try_ui_sequence("
        if a.count(marker) != 1:
            raise SystemExit(f"RC28 runtime insertion marker mismatch: {a.count(marker)}")
        a = a.replace(marker, runtime + marker, 1)
    agent.write_text(a, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = rep(v, 'VERSION = "1.0.0-rc27"', 'VERSION = "1.0.0-rc28"', "Core version")
    version.write_text(v, encoding="utf-8")

    for path in (agent, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    final = agent.read_text(encoding="utf-8")
    required = (
        "def _contract(",
        "def _compact_screen(",
        "def _plan(",
        "def risk(",
        "def _deterministic_gate(",
        "def _verify_goal(",
        "def _wait_after_action(",
        "def _try_fast_skill(",
        "def _try_ui_sequence(",
    )
    missing = [x for x in required if x not in final]
    if missing:
        raise SystemExit("RC28 runtime restore incomplete: " + ", ".join(missing))
    if 'VERSION = "1.0.0-rc28"' not in version.read_text(encoding="utf-8"):
        raise SystemExit("RC28 version missing")
    print("Furina Core RC28 AndroidAgent runtime method restore: OK")


if __name__ == "__main__":
    main()
