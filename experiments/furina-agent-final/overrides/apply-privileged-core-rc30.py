#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"RC30 marker mismatch {label}: {n}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-privileged-core-rc30.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    agent = core / "agent.py"
    version = core / "version.py"
    if not agent.is_file() or not version.is_file():
        raise SystemExit("missing RC30 Core source")

    a = agent.read_text(encoding="utf-8")

    helper = '''    def _device_mode(self) -> str:
        mode = str(getattr(self.cfg, "device_control_mode", "normal") or "normal").strip().lower()
        return mode if mode in {"normal", "shizuku", "root"} else "normal"

    def _with_device_mode(self, action: dict) -> dict:
        out = dict(action)
        out.setdefault("mode", self._device_mode())
        return out

'''
    marker = "    def _compile_semantic_sequence(self, steps: list[dict], apps: list[dict]) -> list[dict]:\n"
    if helper.strip() not in a:
        if a.count(marker) != 1:
            raise SystemExit(f"RC30 helper insertion mismatch: {a.count(marker)}")
        a = a.replace(marker, helper + marker, 1)

    # Every semantic sequence now carries the selected backend. Bridge RC17
    # decides per primitive whether privileged injection is actually superior.
    old = '            result = self.tools.execute({"type": "run_ui_sequence", "steps": steps})\n'
    new = '            result = self.tools.execute({"type": "run_ui_sequence", "steps": steps, "mode": self._device_mode()})\n'
    a = rep_once(a, old, new, "semantic sequence mode")

    # All live-planner and deterministic payloads that pass through the generic
    # action boundary carry mode too. This intentionally does not add an extra
    # RPC or capability probe per action.
    needle = '            payload = self._enrich_action(screen, action)\n'
    replacement = '            payload = self._enrich_action(screen, action)\n            payload.setdefault("mode", self._device_mode())\n'
    count = a.count(needle)
    if replacement not in a:
        if count < 1:
            raise SystemExit(f"RC30 payload mode marker missing: {count}")
        a = a.replace(needle, replacement)

    # Make the planner aware of capability level without changing its semantic
    # reasoning. This is metadata only; it does not cause an additional model call.
    planner_anchor = '            f"TARGET PACKAGE: {contract.target_package}\\n"\n'
    planner_new = '            f"TARGET PACKAGE: {contract.target_package}\\n"\n            f"CONTROL_MODE: {self._device_mode()}\\n"\n'
    a = rep_once(a, planner_anchor, planner_new, "planner capability metadata")

    agent.write_text(a, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = rep_once(v, 'VERSION = "1.0.0-rc29"', 'VERSION = "1.0.0-rc30"', "Core version")
    version.write_text(v, encoding="utf-8")

    for path in (agent, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    final = agent.read_text(encoding="utf-8")
    required = (
        "def _device_mode",
        "def _with_device_mode",
        '"run_ui_sequence", "steps": steps, "mode": self._device_mode()',
        'payload.setdefault("mode", self._device_mode())',
        "CONTROL_MODE:",
    )
    missing = [x for x in required if x not in final]
    if missing:
        raise SystemExit("RC30 Core incomplete: " + ", ".join(missing))
    if 'VERSION = "1.0.0-rc30"' not in version.read_text(encoding="utf-8"):
        raise SystemExit("RC30 version missing")
    print("Furina Core RC30 capability-aware execution routing: OK")


if __name__ == "__main__":
    main()
