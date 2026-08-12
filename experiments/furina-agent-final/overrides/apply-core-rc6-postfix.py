#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, got {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc6-postfix.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    chat = root / "core/furina_agent/chat.py"
    agent = root / "core/furina_agent/agent.py"
    config = root / "core/furina_agent/config.py"
    memory = root / "core/furina_agent/memory.py"
    if not chat.is_file() or not agent.is_file() or not config.is_file() or not memory.is_file():
        raise SystemExit("missing RC6 generated core source")

    text = chat.read_text(encoding="utf-8")
    broken = '        return "\n".join(lines) or "(tidak ada device context baru)"'
    fixed = r'        return "\n".join(lines) or "(tidak ada device context baru)"'
    if fixed not in text:
        if broken not in text:
            raise SystemExit("RC6 device-context newline marker not found")
        chat.write_text(text.replace(broken, fixed, 1), encoding="utf-8")

    # Bridge currently publishes its event stream on one private localhost UDP
    # port. Keep Core on the same fixed port instead of exposing a setting that
    # the Bridge cannot follow and would silently desynchronize.
    config_text = config.read_text(encoding="utf-8")
    config_text = replace_once(
        config_text,
        '    defaults["event_port"] = max(1024, min(int(defaults["event_port"]), 65535))',
        '    defaults["event_port"] = 8767  # fixed Bridge/Core localhost event channel',
        "fixed event stream port",
    )
    config.write_text(config_text, encoding="utf-8")

    # Learned skills must never persist the original free-form user command.
    # Store an operation template only, and omit text/description selectors that
    # can contain recipient names, note contents, or other screen PII.
    memory_text = memory.read_text(encoding="utf-8")
    memory_text = replace_once(
        memory_text,
        '                stable = {k: target.get(k) for k in ("view_id", "text", "desc", "class", "editable", "scrollable") if target.get(k) not in (None, "", False)}',
        '                stable = {k: target.get(k) for k in ("view_id", "class", "editable", "scrollable") if target.get(k) not in (None, "", False)}',
        "privacy-safe learned selector",
    )
    memory_text = replace_once(
        memory_text,
        '        compact_goal = " ".join(str(goal).split())[:360]',
        '        action_signature = " > ".join(str(s.get("type") or "") for s in steps if s.get("type"))\n        compact_goal = ("app=" + (app_package[:180] or "unknown") + " actions=" + action_signature)[:360]',
        "redacted learned goal",
    )
    memory_text = replace_once(
        memory_text,
        '            package_bonus = 0.25 if app_package and str(row["app_package"]) == app_package else 0.0\n            wins = int(row["success_count"] or 0); fails = int(row["failure_count"] or 0)',
        '            package_bonus = 0.25 if app_package and str(row["app_package"]) == app_package else 0.0\n            if overlap <= 0.0 and package_bonus <= 0.0:\n                continue\n            wins = int(row["success_count"] or 0); fails = int(row["failure_count"] or 0)',
        "avoid unrelated learned skills",
    )
    memory.write_text(memory_text, encoding="utf-8")

    agent_text = agent.read_text(encoding="utf-8")
    agent_text = replace_once(
        agent_text,
        '''    @staticmethod
    def _history_action_succeeded(item: dict) -> bool:
        result = item.get("result")
        if result in {None, "rejected_by_user", "failed_action"}:
            return False
        return bool(result.get("ok")) if isinstance(result, dict) else True
''',
        '''    @staticmethod
    def _history_action_succeeded(item: dict) -> bool:
        result = item.get("result")
        if result is None:
            return False
        if isinstance(result, str) and result in {"rejected_by_user", "failed_action", "premature_finish", "blocked_high_risk"}:
            return False
        return bool(result.get("ok")) if isinstance(result, dict) else True
''',
        "dict-safe action success",
    )
    agent_text = replace_once(
        agent_text,
        '''                if action.get("type") not in {"scroll_node", "scroll_global", "swipe"}:
                    continue
                if self._history_action_succeeded(item):
                    count += 1
''',
        '''                if action.get("type") not in {"scroll_node", "scroll_global", "swipe"}:
                    continue
                observed_move = bool(item.get("state_changed")) or bool(item.get("scroll_event"))
                if self._history_action_succeeded(item) and observed_move:
                    count += 1
''',
        "observable scroll evidence",
    )
    agent_text = replace_once(
        agent_text,
        '        suggested = self.store.find_skills(goal, "", 3) if getattr(self.cfg, "skill_learning_enabled", True) else []',
        '        suggested = self.store.find_skills(goal, contract.target_package, 3) if getattr(self.cfg, "skill_learning_enabled", True) else []',
        "package-scoped initial skill lookup",
    )
    agent_text = replace_once(
        agent_text,
        '''            payload = self._enrich_action(screen, action)
            before = self._screen_signature(screen)
            result = self.bridge.action(payload)
''',
        '''            payload = self._enrich_action(screen, action)
            before = self._screen_signature(screen)
            try:
                before_event_seq = int(screen.get("event_seq", 0) or 0)
            except Exception:
                before_event_seq = 0
            result = self.bridge.action(payload)
''',
        "event sequence before action",
    )
    agent_text = replace_once(
        agent_text,
        '''            time.sleep(0.9 if typ == "open_app" else 0.48)
            after_screen = screen
''',
        '''            if typ == "open_app":
                # A successful launch means the task has logically left Termux,
                # even if the user returns before the next snapshot is captured.
                left_termux = True
            time.sleep(0.9 if typ == "open_app" else 0.48)
            after_screen = screen
''',
        "logical leave Termux after launch",
    )
    agent_text = replace_once(
        agent_text,
        '''                changed = before != self._screen_signature(after_screen)
                item["state_changed"] = changed
                item["after_package"] = after_screen.get("package")
                stalls = 0 if changed else stalls + 1
''',
        '''                changed = before != self._screen_signature(after_screen)
                scroll_event = False
                if typ in {"scroll_node", "scroll_global", "swipe"}:
                    for event in after_screen.get("recent_events") or []:
                        if not isinstance(event, dict):
                            continue
                        try:
                            event_seq = int(event.get("seq", 0) or 0)
                        except Exception:
                            event_seq = 0
                        if event_seq > before_event_seq and str(event.get("type") or "") == "scroll":
                            scroll_event = True
                            break
                item["scroll_event"] = scroll_event
                item["state_changed"] = changed
                item["after_package"] = after_screen.get("package")
                stalls = 0 if (changed or scroll_event) else stalls + 1
''',
        "scroll event verification",
    )
    agent.write_text(agent_text, encoding="utf-8")

    print("Furina RC6 generated-source postfix + P2 review fixes: OK")


if __name__ == "__main__":
    main()
