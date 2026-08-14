#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"RC27 marker mismatch {label}: {n}")
    return text.replace(old, new, 1)


def block(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if replacement.strip() in text:
            return text
        raise SystemExit(f"RC27 block marker missing {label}: start={a} end={b}")
    return text[:a] + replacement.rstrip() + "\n\n" + text[b:]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-runtime-recovery-rc27.py <termux-root>")

    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    companion = core / "companion.py"
    chat = core / "chat_surface.py"
    version = core / "version.py"
    for path in (companion, chat, version):
        if not path.is_file():
            raise SystemExit(f"missing RC27 source: {path}")

    c = companion.read_text(encoding="utf-8")

    installed_apps = '''    def _installed_apps(self) -> list[dict]:
        def read_apps() -> list[dict]:
            raw = self.bridge.apps()
            apps = raw.get("apps") if isinstance(raw, dict) else []
            if not isinstance(apps, list):
                return []
            return [x for x in apps if isinstance(x, dict) and x.get("package")]

        try:
            return read_apps()
        except Exception as first_error:
            # Pairing/token loss must not silently erase the installed-app
            # inventory. Recover once through the loopback bootstrap and retry.
            try:
                if self.bridge.ensure_paired():
                    apps = read_apps()
                    self.store.log_event(
                        "bridge_pairing_recovered",
                        {"apps": len(apps)},
                    )
                    return apps
            except Exception as retry_error:
                self.store.log_event(
                    "installed_apps_error",
                    {
                        "first": str(first_error)[:220],
                        "retry": str(retry_error)[:220],
                    },
                )
                return []
            self.store.log_event(
                "installed_apps_error",
                {"first": str(first_error)[:220], "retry": "pairing unavailable"},
            )
            return []
'''
    c = block(
        c,
        "    def _installed_apps(self) -> list[dict]:\n",
        "    @staticmethod\n    def _app_keys",
        installed_apps,
        "installed app recovery",
    )

    fallback_helpers = r'''    @classmethod
    def _fallback_device_steps(cls, text: str, apps: list[dict]) -> list[dict]:
        """Small deterministic safety net used only when semantic routing fails.

        It parses structural imperative chains, not app-specific commands. App
        identity is still resolved exclusively from the live installed-app list.
        """
        raw = " ".join(str(text or "").strip().split())
        if not raw:
            return []

        action_tail = r"(?:cari|search|find|ketik|tulis|kirim|send|tekan|tap|klik|click|scroll|geser|swipe|pilih|select)"
        joiner = r"(?:\s*[,;]\s*|\s+(?:lalu|kemudian|terus|dan)\s+)"
        opened = re.search(
            rf"^\s*(?:buka|open|jalankan|launch)\s+(.+?)(?={joiner}{action_tail}\b|$)",
            raw,
            re.I,
        )
        if not opened:
            return []

        app_hint = opened.group(1).strip(" ,.;:-")[:120]
        package = cls._resolve_app_hint(app_hint, apps)
        if not package:
            # If the user included filler after the app name, progressively try
            # the leading phrase. This remains generic and inventory-backed.
            words = app_hint.split()
            for size in range(min(4, len(words)), 0, -1):
                package = cls._resolve_app_hint(" ".join(words[:size]), apps)
                if package:
                    break
        if not package:
            return []

        steps: list[dict] = [{"type": "open_app", "app": app_hint, "package": package}]

        search_match = re.search(
            rf"\b(?:cari|search|find)\b\s+(?:(?:kontak|contact|chat|percakapan|akun|account|user)\s+)?(.+?)(?={joiner}(?:kirim|send|ketik|tulis|tekan|tap|klik|click|scroll|geser|swipe|pilih|select)\b|$)",
            raw,
            re.I,
        )
        query = ""
        if search_match:
            query = search_match.group(1).strip(" ,.;:-")[:1000]
            if query:
                steps.append({"type": "search", "query": query})

        send_match = re.search(
            r"\b(?:kirim|send)(?:kan)?\b\s*(?:(?:pesan|message)\b\s*)?(.+?)\s*$",
            raw,
            re.I,
        )
        if send_match:
            payload = send_match.group(1).strip(" ,.;:-")[:4000]
            if payload:
                if query:
                    steps.append({"type": "select", "target": query[:180]})
                steps.append({"type": "type", "text": payload, "field_role": "message"})
                steps.append({"type": "send"})

        return steps[:18]

    @staticmethod
    def _looks_like_device_imperative(text: str) -> bool:
        # Last-resort routing only. This never executes anything by itself; it
        # merely prevents an explicit imperative from being misrouted to chat
        # when both semantic routing and app inventory are unavailable.
        return bool(
            re.match(
                r"^\s*(?:buka|open|jalankan|launch|cari|search|kirim|send|balas|reply|ketik|tulis|tekan|tap|klik|click|scroll|geser|swipe|pilih|select)\b",
                str(text or ""),
                re.I,
            )
        )
'''
    marker = "    def classify(self, text: str) -> Intent:\n"
    if fallback_helpers.strip() not in c:
        if c.count(marker) != 1:
            raise SystemExit(f"RC27 classify insertion marker mismatch: {c.count(marker)}")
        c = c.replace(marker, fallback_helpers + "\n" + marker, 1)

    c = rep(
        c,
        '''        apps = self._installed_apps()
        anchors = self._app_anchors(text, apps)
''',
        '''        apps = self._installed_apps()
        anchors = self._app_anchors(text, apps)
        fallback_steps = self._fallback_device_steps(text, apps)
''',
        "fallback parse initialization",
    )

    c = rep(
        c,
        '''                if mode == "chat":
                    # Trust a confident semantic chat classification. If the
                    # parser itself is unsure while an installed app is clearly
                    # referenced, defer to the Android planner instead of
                    # silently converting an execution request into chat.
                    if confidence < 0.40 and anchors:
''',
        '''                if mode == "chat":
                    # A structurally explicit, inventory-resolved imperative is
                    # stronger evidence than a mistaken chat classification.
                    if fallback_steps:
                        self.store.log_event(
                            "semantic_chat_overridden_by_structure",
                            {"text": text[:240], "steps": len(fallback_steps), "confidence": confidence},
                        )
                        return Intent("device", text, max(confidence, 0.70), fallback_steps, self._requires_screen(fallback_steps))
                    # Trust a confident semantic chat classification otherwise.
                    # If the parser itself is unsure while an installed app is
                    # clearly referenced, defer to the Android planner.
                    if confidence < 0.40 and anchors:
''',
        "chat structural override",
    )

    c = rep(
        c,
        '''        # Never fail-open into ordinary chat merely because the parser/provider
        # had a transient problem. A reference to an actually installed app is
        # strong device context and is derived generically from labels/packages,
        # including camel-case acronyms such as WhatsApp -> WA or YouTube -> YT.
        if anchors:
''',
        '''        # Never fail-open into ordinary chat merely because the parser/provider
        # had a transient problem. First use the deterministic structural plan
        # when it can be grounded to the installed-app inventory.
        if fallback_steps:
            self.store.log_event(
                "semantic_intent_structural_fallback",
                {"text": text[:240], "steps": len(fallback_steps), "errors": errors[-2:]},
            )
            return Intent("device", text, 0.72, fallback_steps, self._requires_screen(fallback_steps))

        # A reference to an actually installed app is strong device context and
        # is derived generically from labels/packages, including camel-case
        # acronyms such as WhatsApp -> WA or YouTube -> YT.
        if anchors:
''',
        "structural parser provider fallback",
    )

    c = rep(
        c,
        '''        self.store.log_event("semantic_intent_error", {"text": text[:240], "errors": errors[-2:]})
        return Intent("chat", text, 0.0, [], False)
''',
        '''        if self._looks_like_device_imperative(text):
            self.store.log_event(
                "semantic_intent_unresolved_device_fallback",
                {"text": text[:240], "errors": errors[-2:]},
            )
            return Intent("device", text, 0.20, [], True)

        self.store.log_event("semantic_intent_error", {"text": text[:240], "errors": errors[-2:]})
        return Intent("chat", text, 0.0, [], False)
''',
        "last resort device routing",
    )
    companion.write_text(c, encoding="utf-8")

    ch = chat.read_text(encoding="utf-8")
    if "import traceback\n" not in ch:
        if "from pathlib import Path\n" in ch:
            ch = rep(ch, "import time\n", "import time\nimport traceback\n", "runtime traceback import")
        else:
            ch = rep(ch, "import time\n", "import time\nimport traceback\nfrom pathlib import Path\n", "runtime traceback imports")

    if "chat-runtime.log" not in ch:
        call_marker = "                self.call_from_thread(self._fail, assistant_id)\n"
        if ch.count(call_marker) != 1:
            raise SystemExit(f"RC27 marker mismatch failure call: {ch.count(call_marker)}")
        logging_call = '''                try:
                    trace = traceback.format_exc()
                    log_dir = Path.home() / ".furina-agent" / "logs"
                    log_dir.mkdir(parents=True, exist_ok=True)
                    with (log_dir / "chat-runtime.log").open("a", encoding="utf-8") as fh:
                        fh.write(f"\\n[{time.strftime('%Y-%m-%d %H:%M:%S')}]\\n")
                        fh.write(trace)
                    tail = trace.strip().splitlines()[-1] if trace.strip() else "unknown runtime error"
                    self.session.store.log_event(
                        "chat_surface_runtime_error",
                        {"error": tail[:500]},
                    )
                except Exception:
                    pass
                self.call_from_thread(self._fail, assistant_id)
'''
        ch = ch.replace(call_marker, logging_call, 1)
    chat.write_text(ch, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = rep(v, 'VERSION = "1.0.0-rc26"', 'VERSION = "1.0.0-rc27"', "Core version")
    version.write_text(v, encoding="utf-8")

    for path in (companion, chat, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    checks = [
        (companion, "bridge_pairing_recovered"),
        (companion, "def _fallback_device_steps"),
        (companion, "semantic_intent_structural_fallback"),
        (companion, "semantic_intent_unresolved_device_fallback"),
        (chat, "chat-runtime.log"),
        (chat, "traceback.format_exc()"),
        (version, 'VERSION = "1.0.0-rc27"'),
    ]
    missing = [needle for path, needle in checks if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC27 incomplete: " + ", ".join(missing))

    print("Furina Core RC27 pairing recovery + structural device fallback + runtime traceback: OK")


if __name__ == "__main__":
    main()
