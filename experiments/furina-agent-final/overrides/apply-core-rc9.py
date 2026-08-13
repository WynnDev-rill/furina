#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(path: pathlib.Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc9.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    config = core / "config.py"
    memory = core / "memory.py"
    chat = core / "chat.py"
    agent = core / "agent.py"
    version = core / "version.py"
    lexicon = core / "lexicon.py"
    fastpath = core / "fastpath.py"
    for path in (config, memory, chat, agent, version, lexicon, fastpath):
        if not path.is_file():
            raise SystemExit(f"missing RC9 source: {path}")

    # ── Config: fast deterministic path + tiny lexicon prompt budget ───────
    replace_once(config, '    config_revision: int = 8', '    config_revision: int = 9', "RC9 config revision")
    replace_once(
        config,
        '    skill_learning_enabled: bool = True\n',
        '''    skill_learning_enabled: bool = True

    # RC9: learned deterministic actions run before planner/vision when enough
    # verified evidence exists. Timeouts are short because Accessibility events
    # wake the path early; timeout is only the fallback ceiling.
    fast_path_enabled: bool = True
    fast_path_min_successes: int = 2
    fast_path_ui_timeout_ms: int = 420
    fast_path_open_timeout_ms: int = 850
    fast_path_poll_ms: int = 30

    # Personal lexical alignment. The database can grow independently while the
    # prompt receives only a handful of relevant, sufficiently repeated forms.
    lexicon_enabled: bool = True
    lexicon_prompt_limit: int = 8
    lexicon_auto_min_seen: int = 2
''',
        "RC9 config fields",
    )
    replace_once(
        config,
        '    defaults["context_budget_chars"] = max(6000, min(int(defaults["context_budget_chars"]), 24000))\n',
        '''    defaults["context_budget_chars"] = max(6000, min(int(defaults["context_budget_chars"]), 24000))
    defaults["fast_path_min_successes"] = max(1, min(int(defaults["fast_path_min_successes"]), 8))
    defaults["fast_path_ui_timeout_ms"] = max(120, min(int(defaults["fast_path_ui_timeout_ms"]), 1500))
    defaults["fast_path_open_timeout_ms"] = max(250, min(int(defaults["fast_path_open_timeout_ms"]), 2200))
    defaults["fast_path_poll_ms"] = max(15, min(int(defaults["fast_path_poll_ms"]), 120))
    defaults["lexicon_prompt_limit"] = max(2, min(int(defaults["lexicon_prompt_limit"]), 16))
    defaults["lexicon_auto_min_seen"] = max(2, min(int(defaults["lexicon_auto_min_seen"]), 12))
''',
        "RC9 config clamps",
    )

    # ── Learned skills: retain privacy while storing semantic intent tags ──
    replace_once(
        memory,
        '''        action_signature = " > ".join(str(s.get("type") or "") for s in steps if s.get("type"))
        compact_goal = ("app=" + (app_package[:180] or "unknown") + " actions=" + action_signature)[:360]
''',
        r'''        action_signature = " > ".join(str(s.get("type") or "") for s in steps if s.get("type"))
        low_goal = str(goal).casefold()
        intent_tags: list[str] = []
        for tag, pattern in (
            ("buka", r"\b(?:buka|open|jalankan)\b"),
            ("cari", r"\b(?:cari|carikan|search|telusur|telusuri)\b"),
            ("tulis", r"\b(?:tulis|tuliskan|ketik|ketikkan|isi|isikan|catat|catatkan)\b"),
            ("scroll", r"\b(?:scroll|geser|swipe)\b"),
            ("external", r"\b(?:send|kirim|post|share|bagikan|call|telepon|unggah|upload)\b"),
        ):
            if re.search(pattern, low_goal):
                intent_tags.append(tag)
        compact_goal = (
            "app=" + (app_package[:180] or "unknown")
            + " intent=" + "+".join(intent_tags or ["generic"])
            + " actions=" + action_signature
        )[:360]
''',
        "privacy-safe skill intent metadata",
    )

    # ── Chat: lexical entrainment without copying the user ─────────────────
    replace_once(chat, 'from .device_context import context_text as device_sensor_context\n', 'from .device_context import context_text as device_sensor_context\nfrom .lexicon import PersonalLexicon\n', "lexicon import")
    replace_once(
        chat,
        '        self._background_lock = threading.Lock()\n',
        '        self._background_lock = threading.Lock()\n        self.lexicon = PersonalLexicon(store)\n',
        "lexicon init",
    )
    replace_once(
        chat,
        '            + "\\n\\nPOST-HISTORY RULE:\\nJawab pesan terbaru sebagai Furina. Prioritaskan isi pesan terbaru, lalu continuity percakapan, lalu memory. Jangan meniru kalimat contoh secara verbatim."\n',
        '            + "\\n\\nPERSONAL LEXICON (opsional; jangan dipaksa):\\n"\n            + (self.lexicon.prompt_context(user_text, profile.name, int(getattr(self.cfg, "lexicon_prompt_limit", 8)), int(getattr(self.cfg, "lexicon_auto_min_seen", 2))) if getattr(self.cfg, "lexicon_enabled", True) else "(dinonaktifkan)")\n            + "\\n\\nPOST-HISTORY RULE:\\nJawab pesan terbaru sebagai Furina. Prioritaskan isi pesan terbaru, lalu continuity percakapan, lalu memory. Jangan meniru kalimat contoh secara verbatim."\n',
        "lexicon prompt context",
    )
    replace_once(
        chat,
        '''        profile = choose_profile(user_text, self.store)
        messages = self._messages(user_text, profile)
''',
        '''        profile = choose_profile(user_text, self.store)
        if getattr(self.cfg, "lexicon_enabled", True):
            try:
                self.lexicon.observe(user_text, profile.name)
            except Exception as exc:
                self.store.log_event("lexicon_observe_error", {"error": str(exc)[:240]})
        messages = self._messages(user_text, profile)
''',
        "observe user lexicon before prompt",
    )
    replace_once(
        chat,
        '''        answer = naturalize(answer, technical=(profile.name == "SHARP"))
        self.store.add_message("assistant", answer)
''',
        '''        answer = naturalize(answer, technical=(profile.name == "SHARP"))
        if getattr(self.cfg, "lexicon_enabled", True):
            try:
                self.lexicon.mark_used(answer)
            except Exception:
                pass
        self.store.add_message("assistant", answer)
''',
        "lexicon usage reinforcement",
    )

    # ── Agent: deterministic contract + event-driven action completion ─────
    replace_once(
        agent,
        'from .memory import MemoryStore\n',
        'from .memory import MemoryStore\nfrom .fastpath import compile_fast_contract, choose_fast_skill, event_sequence, goal_tags, materialize_step, wait_for_event\n',
        "fast path import",
    )
    replace_once(
        agent,
        '    def _contract(self, goal: str, apps: list[dict]) -> TaskContract:\n        prompt = f"""\n',
        '''    def _contract(self, goal: str, apps: list[dict]) -> TaskContract:
        fast = compile_fast_contract(goal, apps) if getattr(self.cfg, "fast_path_enabled", True) else None
        if fast:
            self.store.log_event("agent_contract_fast", {"goal": str(goal)[:240], "package": fast.get("target_package", "")})
            return TaskContract(
                str(fast.get("summary") or goal)[:300],
                [str(x)[:260] for x in (fast.get("criteria") or [])][:5],
                bool(fast.get("external_expected", False)),
                int(fast.get("required_scrolls", 0) or 0),
                str(fast.get("required_write_text") or "")[:320],
                str(fast.get("target_package") or "")[:180],
            )
        prompt = f"""
''',
        "deterministic contract fast path",
    )

    replace_once(
        agent,
        '    def _interruptible(self, cancel_event: threading.Event, fn, label: str):\n',
        r'''    def _wait_after_action(self, screen: dict, before_event_seq: int, typ: str, cancel_event: threading.Event) -> dict:
        if typ == "set_text":
            timeout = 120
        elif typ == "open_app":
            timeout = int(getattr(self.cfg, "fast_path_open_timeout_ms", 850))
        else:
            timeout = int(getattr(self.cfg, "fast_path_ui_timeout_ms", 420))
        started = time.monotonic()
        woke = wait_for_event(
            self.store,
            before_event_seq,
            timeout_ms=timeout,
            poll_ms=int(getattr(self.cfg, "fast_path_poll_ms", 30)),
            cancel_event=cancel_event,
        )
        if cancel_event.is_set():
            return screen
        try:
            latest = self.bridge.screen()
        except Exception:
            latest = screen
        self.store.log_event("agent_latency", {
            "stage": "ui_event_wait",
            "action": typ,
            "event_wake": bool(woke),
            "ms": int((time.monotonic() - started) * 1000),
        })
        return latest

    def _fast_completion(self, goal: str, contract: TaskContract, screen: dict, history: list[dict], steps: list[dict]) -> bool:
        hard_ok, _ = self._deterministic_gate(contract, screen, history)
        if not hard_ok or contract.external_expected:
            return False
        tags = goal_tags(goal)
        if "cari" in tags:
            submitted = any(
                (h.get("action") or {}).get("type") == "ime_action"
                and self._history_action_succeeded(h)
                and bool(h.get("state_changed"))
                for h in history
            )
            if not submitted:
                return False
            visible = [
                n for n in (screen.get("nodes") or [])
                if isinstance(n, dict) and not n.get("editable") and str(n.get("text") or n.get("desc") or "").strip()
            ]
            return len(visible) >= 2
        # For writes, scrolls and simple opens, all learned deterministic steps
        # have already succeeded and the hard evidence gate verifies the result.
        return bool(tags & {"buka", "tulis", "scroll"})

    def _try_fast_skill(self, goal: str, contract: TaskContract, approve, task_authorized: bool, cancel_event: threading.Event, history: list[dict]):
        if not getattr(self.cfg, "fast_path_enabled", True) or contract.external_expected:
            return None, None, False
        skill = choose_fast_skill(
            self.store,
            goal,
            contract.target_package,
            int(getattr(self.cfg, "fast_path_min_successes", 2)),
        )
        if skill is None:
            return None, None, False
        started = time.monotonic()
        try:
            screen = self.bridge.screen()
        except Exception:
            return None, None, False
        executed_any = False
        for template in skill.steps:
            if cancel_event.is_set():
                return "Tugas dihentikan karena kamu kembali ke Termux.", screen, True
            action = materialize_step(template, screen, contract.required_write_text)
            if action is None:
                self.store.log_event("agent_fastpath_fallback", {"skill": skill.id, "reason": "ambiguous_or_dynamic_step"})
                return None, screen, executed_any
            typ = str(action.get("type") or "")
            risk, detail = self.risk(screen, action)
            if risk in {"blocked", "external", "uncertain"}:
                self.store.log_event("agent_fastpath_fallback", {"skill": skill.id, "reason": "risk_" + risk})
                return None, screen, executed_any
            if (not task_authorized) and risk in {"navigate", "write"} and not approve("Jalur cepat tindakan yang sudah pernah berhasil", action, risk, detail):
                return "Aksi itu dibatalkan.", screen, True

            payload = self._enrich_action(screen, action)
            before = self._screen_signature(screen)
            before_seq = event_sequence(self.store, screen)
            result = self.bridge.action(payload)
            item = {"action": action, "executed": payload, "result": result, "risk": risk, "fast_path": True}
            executed_any = True
            if not self._result_ok(result):
                item["detail"] = "fast path action gagal; kembali ke planner"
                history.append(item)
                self.store.penalize_skills([skill.id])
                self.store.log_event("agent_fastpath_fallback", {"skill": skill.id, "reason": "bridge_failure", "action": typ})
                return None, screen, True

            after = self._wait_after_action(screen, before_seq, typ, cancel_event)
            changed = before != self._screen_signature(after)
            scroll_event = False
            if typ in {"scroll_node", "scroll_global", "swipe"}:
                for event in after.get("recent_events") or []:
                    if not isinstance(event, dict):
                        continue
                    try:
                        seq = int(event.get("seq", 0) or 0)
                    except Exception:
                        seq = 0
                    if seq > before_seq and str(event.get("type") or "") == "scroll":
                        scroll_event = True
                        break
            item["state_changed"] = changed
            item["scroll_event"] = scroll_event
            item["after_package"] = after.get("package")
            history.append(item)
            screen = after

            if typ == "open_app" and contract.target_package and str(screen.get("package") or "") != contract.target_package:
                self.store.penalize_skills([skill.id])
                self.store.log_event("agent_fastpath_fallback", {"skill": skill.id, "reason": "wrong_package"})
                return None, screen, True

        elapsed = int((time.monotonic() - started) * 1000)
        if self._fast_completion(goal, contract, screen, history, skill.steps):
            self.store.log_event("agent_fastpath_complete", {"skill": skill.id, "score": round(skill.score, 3), "ms": elapsed, "steps": len(skill.steps)})
            return "Selesai.", screen, True
        self.store.log_event("agent_fastpath_fallback", {"skill": skill.id, "reason": "needs_semantic_verification", "ms": elapsed})
        return None, screen, True

    def _interruptible(self, cancel_event: threading.Event, fn, label: str):
''',
        "fast path execution helpers",
    )

    # Replace fixed sleeps in the normal planner path with event-driven waits.
    replace_once(
        agent,
        '''            if typ == "open_app":
                # A successful launch means the task has logically left Termux,
                # even if the user returns before the next snapshot is captured.
                left_termux = True
            time.sleep(0.9 if typ == "open_app" else 0.48)
            after_screen = screen
            try:
                after_screen = self.bridge.screen()
                changed = before != self._screen_signature(after_screen)
''',
        '''            if typ == "open_app":
                # A successful launch means the task has logically left Termux,
                # even if the user returns before the next snapshot is captured.
                left_termux = True
            after_screen = self._wait_after_action(screen, before_event_seq, typ, cancel_event)
            try:
                changed = before != self._screen_signature(after_screen)
''',
        "event-driven normal action wait",
    )

    # Try the learned path once before entering planner/vision. If it cannot
    # prove a selector/action safely, normal planning continues from the new state.
    replace_once(
        agent,
        '        for step_index in range(self.cfg.agent_max_steps):\n',
        '''        fast_result, fast_screen, fast_attempted = self._try_fast_skill(
            goal, contract, approve, task_authorized, cancel_event, history
        )
        if fast_result is not None:
            if fast_result == "Selesai." and fast_screen is not None:
                return completed(fast_result, fast_screen)
            return fast_result

        for step_index in range(self.cfg.agent_max_steps):
''',
        "invoke fast path before planner",
    )

    replace_once(version, 'VERSION = "1.0.0-rc8"', 'VERSION = "1.0.0-rc9"', "RC9 version")

    required = [
        ("config", "config_revision: int = 9" in config.read_text(encoding="utf-8")),
        ("lexicon", "PersonalLexicon" in chat.read_text(encoding="utf-8") and "PERSONAL LEXICON" in chat.read_text(encoding="utf-8")),
        ("skill intent", "intent_tags" in memory.read_text(encoding="utf-8")),
        ("fast contract", "compile_fast_contract" in agent.read_text(encoding="utf-8")),
        ("fast replay", "_try_fast_skill" in agent.read_text(encoding="utf-8")),
        ("event wait", "_wait_after_action" in agent.read_text(encoding="utf-8")),
        ("no old sleep", 'time.sleep(0.9 if typ == "open_app" else 0.48)' not in agent.read_text(encoding="utf-8")),
        ("version", 'VERSION = "1.0.0-rc9"' in version.read_text(encoding="utf-8")),
    ]
    failed = [name for name, ok in required if not ok]
    if failed:
        raise SystemExit("RC9 core transform incomplete: " + ", ".join(failed))
    print("Furina RC9 event-driven fast path + adaptive personal lexicon transform: OK")


if __name__ == "__main__":
    main()
