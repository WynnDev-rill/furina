#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import shutil
import sys


def rep_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC35 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root> [template-dir]")
    root = pathlib.Path(sys.argv[1]).resolve()
    templates = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else pathlib.Path(__file__).resolve().parent
    core = root / "core/furina_agent"
    bridge = root / "bridge/app"
    version = core / "version.py"
    config = core / "config.py"
    chat = core / "chat.py"
    agent = core / "agent.py"
    runtime = core / "tool_runtime.py"
    manifest = bridge / "src/main/AndroidManifest.xml"
    main_activity = bridge / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
    updater = bridge / "src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"
    gradle = bridge / "build.gradle"
    bridge_present = bridge.is_dir()

    for path in (version, config, chat, agent, runtime):
        if not path.is_file():
            raise SystemExit(f"RC35 source missing: {path}")
    if bridge_present:
        for path in (manifest, main_activity, updater, gradle):
            if not path.is_file():
                raise SystemExit(f"RC35 bridge source missing: {path}")

    v = version.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc35"' in v:
        print("FurinaHub RC35 already applied")
        return
    if 'VERSION = "1.0.0-rc34"' not in v:
        raise SystemExit("RC35 hanya dapat diterapkan dari Core RC34")

    for name in ("hub_settings.py", "hub.py", "hub_web.py"):
        src = templates / name
        if not src.is_file():
            raise SystemExit(f"RC35 template hilang: {src}")
        shutil.copyfile(src, core / name)

    c = config.read_text(encoding="utf-8")
    if "device_control_mode: str" not in c:
        c = rep_once(
            c,
            "    agent_task_approval: bool = True\n",
            "    agent_task_approval: bool = True\n    device_control_mode: str = \"normal\"\n",
            "device control config",
        )
    config.write_text(c, encoding="utf-8")

    ch = chat.read_text(encoding="utf-8")
    if "from .hub_settings import personalization_prompt" not in ch:
        ch = rep_once(
            ch,
            "from .config import Config\n",
            "from .config import Config\nfrom .hub_settings import personalization_prompt\n",
            "chat personalization import",
        )
    old = '''        system = (
            build_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)
            + "\\n\\nRESPONSE MODE:\\n"
'''
    new = '''        system = (
            build_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)
            + "\\n\\n"
            + personalization_prompt()
            + "\\n\\nRESPONSE MODE:\\n"
'''
    ch = rep_once(ch, old, new, "chat personalization packet")
    chat.write_text(ch, encoding="utf-8")

    rt = runtime.read_text(encoding="utf-8")
    if "from .hub_settings import load_hub_settings, skill_allows_action" not in rt:
        rt = rep_once(
            rt,
            "from .bridge import AndroidBridge\n",
            "from .bridge import AndroidBridge\nfrom .hub_settings import load_hub_settings, skill_allows_action\n",
            "runtime skill import",
        )
    guard_anchor = '''        if not action_type:
            raise ValueError("action.type kosong")

        fingerprint = self._fingerprint(action)
'''
    guard_new = '''        if not action_type:
            raise ValueError("action.type kosong")

        if not skill_allows_action(action_type, load_hub_settings()):
            self.store.log_event(
                "agent_skill_blocked",
                {"action": action_type, "reason": "skill_disabled"},
            )
            return {
                "ok": False,
                "error": "agent_skill_disabled",
                "action": action_type,
                "policy_preserved": True,
            }

        fingerprint = self._fingerprint(action)
'''
    rt = rep_once(rt, guard_anchor, guard_new, "runtime skill gate")
    runtime.write_text(rt, encoding="utf-8")

    a = agent.read_text(encoding="utf-8")
    if "from .hub_settings import effective_device_mode, load_hub_settings, skill_enabled" not in a:
        anchor = "from .memory import MemoryStore\n"
        if anchor not in a:
            raise SystemExit("RC35 agent import anchor missing")
        a = a.replace(
            anchor,
            anchor + "from .hub_settings import effective_device_mode, load_hub_settings, skill_enabled\n",
            1,
        )
    old_mode = '''    def _device_mode(self) -> str:
        mode = str(getattr(self.cfg, "device_control_mode", "normal") or "normal").strip().lower()
        return mode if mode in {"normal", "shizuku", "root"} else "normal"
'''
    new_mode = '''    def _device_mode(self) -> str:
        fallback = str(getattr(self.cfg, "device_control_mode", "normal") or "normal").strip().lower()
        return effective_device_mode(load_hub_settings(), fallback=fallback)
'''
    a = rep_once(a, old_mode, new_mode, "privileged skill mode")

    vision_anchor = '''    def _with_vision(self, goal: str, screen: dict) -> dict:
        # Screenshot understanding is a rescue path only. UI text is data, not
'''
    vision_new = '''    def _with_vision(self, goal: str, screen: dict) -> dict:
        if not skill_enabled("vision_fallback", load_hub_settings()):
            self.store.log_event("agent_vision_disabled", {"package": screen.get("package")})
            return screen
        # Screenshot understanding is a rescue path only. UI text is data, not
'''
    a = rep_once(a, vision_anchor, vision_new, "vision skill gate")
    agent.write_text(a, encoding="utf-8")

    v = v.replace('VERSION = "1.0.0-rc34"', 'VERSION = "1.0.0-rc35"', 1)
    version.write_text(v, encoding="utf-8")

    if bridge_present:
        shutil.copyfile(templates / "MainActivity.java", main_activity)

        m = manifest.read_text(encoding="utf-8")
        if 'android.permission.RUN_COMMAND' not in m:
            m = rep_once(
                m,
                '    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />\n',
                '    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />\n'
                '    <uses-permission android:name="com.termux.permission.RUN_COMMAND" />\n',
                "Termux permission",
            )
        if '<package android:name="com.termux" />' not in m:
            m = rep_once(
                m,
                "    <queries>\n",
                '    <queries>\n        <package android:name="com.termux" />\n',
                "Termux visibility",
            )
        m = m.replace('android:label="Furina Bridge"', 'android:label="FurinaHub"', 1)
        if 'android:usesCleartextTraffic="true"' not in m:
            m = rep_once(
                m,
                '        android:label="FurinaHub"\n',
                '        android:label="FurinaHub"\n        android:usesCleartextTraffic="true"\n',
                "loopback WebView cleartext",
            )
        manifest.write_text(m, encoding="utf-8")

        u = updater.read_text(encoding="utf-8")
        u = u.replace('"furina-bridge-update-check"', '"furinahub-update-check"')
        u = u.replace('"furina-bridge-update-download"', '"furinahub-update-download"')
        updater.write_text(u, encoding="utf-8")

        java_root = bridge / "src/main/java/com/wynndev/furinaagentbridge"
        for java_file in java_root.glob("*.java"):
            body = java_file.read_text(encoding="utf-8")
            if "Furina Bridge" in body:
                java_file.write_text(body.replace("Furina Bridge", "FurinaHub"), encoding="utf-8")

        g = gradle.read_text(encoding="utf-8")
        g = rep_once(g, "versionCode 10018", "versionCode 10019", "FurinaHub versionCode")
        g = rep_once(g, "versionName '1.0.0-rc18'", "versionName '1.0.0-rc19'", "FurinaHub versionName")
        gradle.write_text(g, encoding="utf-8")

    for path in (
        core / "hub_settings.py",
        core / "hub.py",
        core / "hub_web.py",
        config,
        chat,
        agent,
        runtime,
        version,
    ):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    checks = {
        core / "hub.py": ("127.0.0.1", "8787", "ThreadingHTTPServer", "task_approval_required"),
        core / "hub_settings.py": ("tsundere", "agent_skills", "privileged_controls", "EXPRESSION BIAS"),
        core / "hub_web.py": ("FurinaHub", "Personalisasi", "Skill Agent", "Memori & Psyche"),
        chat: ("personalization_prompt()",),
        runtime: ("agent_skill_disabled", "policy_preserved"),
        agent: ('skill_enabled("vision_fallback"', "effective_device_mode"),
    }
    if bridge_present:
        checks.update({
            main_activity: ("http://127.0.0.1:8787/", "com.termux.RUN_COMMAND", "FurinaNative"),
            manifest: ("FurinaHub", "com.termux.permission.RUN_COMMAND", 'android:name="com.termux"'),
            gradle: ("versionCode 10019", "versionName '1.0.0-rc19'"),
        })
    for path, markers in checks.items():
        text = path.read_text(encoding="utf-8")
        missing = [x for x in markers if x not in text]
        if missing:
            raise SystemExit(f"RC35 marker hilang di {path.name}: {missing}")

    if "Ringkasan Hubungan" in (core / "hub_web.py").read_text(encoding="utf-8"):
        raise SystemExit("UI FurinaHub tidak boleh menampilkan Ringkasan Hubungan")
    if "0.0.0.0" in (core / "hub.py").read_text(encoding="utf-8"):
        raise SystemExit("FurinaHub server tidak boleh bind ke semua interface")

    print("FurinaHub Core RC35 + Android RC19: OK")


if __name__ == "__main__":
    main()
