#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC35 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: apply.py <termux-root> <rc35-dir>")
    root = pathlib.Path(sys.argv[1]).resolve()
    src = pathlib.Path(sys.argv[2]).resolve()
    core = root / "core/furina_agent"
    if not core.is_dir():
        raise SystemExit("missing Core")

    version = core / "version.py"
    config = core / "config.py"
    chat = core / "chat.py"
    agent = core / "agent.py"

    v = version.read_text(encoding="utf-8")
    v = rep_once(v, 'VERSION = "1.0.0-rc34"', 'VERSION = "1.0.0-rc35"', "version")
    version.write_text(v, encoding="utf-8")

    c = config.read_text(encoding="utf-8")
    c = rep_once(c, "    config_revision: int = 5\n", "    config_revision: int = 6\n", "config revision")
    c = rep_once(
        c,
        "    agent_task_approval: bool = True\n",
        '    agent_task_approval: bool = True\n    device_control_mode: str = "normal"\n',
        "device control field",
    )
    c = rep_once(
        c,
        '    if defaults.get("routing_mode") not in {"local", "auto", "online"}:\n        defaults["routing_mode"] = "local"\n',
        '    if defaults.get("routing_mode") not in {"local", "auto", "online"}:\n        defaults["routing_mode"] = "local"\n'
        '    if defaults.get("device_control_mode") not in {"normal", "shizuku", "root"}:\n'
        '        defaults["device_control_mode"] = "normal"\n',
        "control mode validation",
    )
    c = rep_once(
        c,
        "    cfg.user_nickname = cfg.user_nickname.strip()[:48]\n    cfg.local_reasoning = False\n",
        '    cfg.user_nickname = cfg.user_nickname.strip()[:48]\n'
        '    cfg.persona_name = cfg.persona_name.strip()[:48] or "FurinaHub"\n'
        '    cfg.device_control_mode = str(getattr(cfg, "device_control_mode", "normal") or "normal").strip().lower()\n'
        '    if cfg.device_control_mode not in {"normal", "shizuku", "root"}:\n'
        '        cfg.device_control_mode = "normal"\n'
        '    cfg.local_reasoning = False\n',
        "save config validation",
    )
    config.write_text(c, encoding="utf-8")

    for name in ("personalization.py", "skills.py", "hub.py"):
        data = (src / name).read_text(encoding="utf-8")
        (core / name).write_text(data, encoding="utf-8")

    ch = chat.read_text(encoding="utf-8")
    ch = rep_once(
        ch,
        "from .psyche import PsycheEngine\n",
        "from .psyche import PsycheEngine\nfrom .personalization import render_personalization_prompt\n",
        "chat personalization import",
    )
    ch = rep_once(
        ch,
        '            build_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)\n'
        '            + "\\n\\nRESPONSE MODE:\\n"\n',
        '            build_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)\n'
        '            + "\\n\\nPERSONALIZATION — USER-CONTROLLED PRESENTATION PREFERENCE:\\n"\n'
        '            + render_personalization_prompt()\n'
        '            + "\\n\\nRESPONSE MODE:\\n"\n',
        "chat personalization packet",
    )
    chat.write_text(ch, encoding="utf-8")

    a = agent.read_text(encoding="utf-8")
    a = rep_once(
        a,
        "from .memory import MemoryStore\n",
        "from .memory import MemoryStore\nfrom .skills import SkillRegistry\n",
        "agent skill import",
    )
    vision_marker = "    def _with_vision(self, goal: str, screen: dict) -> dict:\n"
    if vision_marker not in a:
        raise SystemExit("RC35 vision marker missing")
    if "RC35 skill: vision_fallback" not in a:
        a = a.replace(
            vision_marker,
            vision_marker
            + '        # RC35 skill: vision_fallback is restrictive only; it cannot widen policy.\n'
              '        if not SkillRegistry().enabled("vision_fallback"):\n'
              '            return screen\n',
            1,
        )
    run_marker = "    def run(self, goal: str, approve, *, task_authorized: bool = False) -> str:\n"
    if run_marker not in a:
        raise SystemExit("RC35 agent run marker missing")
    if "agent_skill_blocked" not in a:
        a = a.replace(
            run_marker,
            run_marker
            + '        blocked = SkillRegistry().blocked_reason(goal)\n'
              '        if blocked:\n'
              '            self.store.log_event("agent_skill_blocked", {"goal": goal, "reason": blocked})\n'
              '            return blocked\n',
            1,
        )
    old_mode = (
        '    def _device_mode(self) -> str:\n'
        '        mode = str(getattr(self.cfg, "device_control_mode", "normal") or "normal").strip().lower()\n'
        '        return mode if mode in {"normal", "shizuku", "root"} else "normal"\n'
    )
    new_mode = (
        '    def _device_mode(self) -> str:\n'
        '        mode = str(getattr(self.cfg, "device_control_mode", "normal") or "normal").strip().lower()\n'
        '        mode = mode if mode in {"normal", "shizuku", "root"} else "normal"\n'
        '        if mode in {"shizuku", "root"} and not SkillRegistry().enabled("privileged_control"):\n'
        '            return "normal"\n'
        '        return mode\n'
    )
    a = rep_once(a, old_mode, new_mode, "privileged skill restriction")
    agent.write_text(a, encoding="utf-8")

    for path in (version, config, chat, agent, core / "personalization.py", core / "skills.py", core / "hub.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    final_chat = chat.read_text(encoding="utf-8")
    final_agent = agent.read_text(encoding="utf-8")
    final_hub = (core / "hub.py").read_text(encoding="utf-8")
    required = (
        "render_personalization_prompt",
        "PERSONALIZATION — USER-CONTROLLED PRESENTATION PREFERENCE",
    )
    if any(x not in final_chat for x in required):
        raise SystemExit("RC35 personalization integration incomplete")
    if "agent_skill_blocked" not in final_agent or 'enabled("vision_fallback")' not in final_agent:
        raise SystemExit("RC35 skill gate incomplete")
    if 'HOST = "127.0.0.1"' not in final_hub or "PORT = 8787" not in final_hub:
        raise SystemExit("RC35 Hub loopback boundary missing")
    if "Ringkasan Hubungan" in final_hub:
        raise SystemExit("RC35 Hub must not expose relationship summary UI")
    if 'VERSION = "1.0.0-rc35"' not in version.read_text(encoding="utf-8"):
        raise SystemExit("RC35 version missing")
    print("Furina Core RC35 + FurinaHub local UI: OK")


if __name__ == "__main__":
    main()
