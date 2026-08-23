#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


def replace_node(text: str, predicate, replacement: str) -> str:
    tree = ast.parse(text)
    node = next((item for item in tree.body if predicate(item)), None)
    if node is None or node.end_lineno is None:
        raise SystemExit("final updater boundary missing")
    lines = text.splitlines(keepends=True)
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]) - 1
    return "".join(lines[:start]) + replacement.rstrip() + "\n\n" + "".join(lines[node.end_lineno:])


STATE_AND_UI = r'''
def interactive_tui() -> bool:
    forced = os.environ.get("FURINA_FORCE_TUI") == "1"
    machine = os.environ.get("FURINAHUB_MACHINE_PROGRESS") == "1"
    return not machine and (forced or sys.stdout.isatty())


class TerminalUI:
    """Tiny dependency-free surface matching Furina Lite's green terminal language."""

    MINT = "\033[38;2;158;252;231m"
    GREEN = "\033[38;2;93;228;199m"
    DARK = "\033[38;2;31;110;90m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    def __init__(self, source: str) -> None:
        self.enabled = interactive_tui()
        self.started = False
        self.live = False
        self.section = "Update" if source != "installer" else "Instalasi"

    def _start(self) -> None:
        if not self.enabled or self.started:
            return
        self.started = True
        print(f"{self.BOLD}{self.MINT}Furina{self.RESET} {self.GREEN}By Wynn{self.RESET}  {self.DARK}·{self.RESET}  {self.BOLD}{self.section}{self.RESET}")
        print(f"{self.DARK}{'─' * 52}{self.RESET}")

    @staticmethod
    def _bar(percent: int, width: int = 24) -> str:
        percent = max(0, min(100, int(percent)))
        done = int(width * percent / 100)
        return "━" * done + "─" * (width - done)

    def progress(self, percent: int, message: str) -> None:
        if not self.enabled:
            print(f"PROGRESS {percent} {message}", flush=True)
            return
        self._start()
        bar = self._bar(percent)
        sys.stdout.write(f"\r\033[2K{self.GREEN}{bar}{self.RESET}  {percent:>3}%  {message[:56]}")
        sys.stdout.flush()
        self.live = True

    def finish(self, message: str) -> None:
        if not self.enabled:
            print(f"PROGRESS 100 {message}", flush=True)
            return
        self._start()
        if self.live:
            sys.stdout.write("\r\033[2K")
        print(f"{self.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━{self.RESET}  100%  {message}")
        print(f"{self.GREEN}✓{self.RESET} Selesai")
        self.live = False

    def error(self, stage: str, message: str) -> None:
        if not self.enabled:
            print(f"ERROR {stage} {message}", file=sys.stderr, flush=True)
            return
        self._start()
        if self.live:
            sys.stdout.write("\r\033[2K")
        print(f"\033[38;2;255;120;140m×{self.RESET} {message}", file=sys.stderr)
        self.live = False


class State:
    def __init__(self, root: Path, source: str) -> None:
        self.root = root
        self.path = root / "run/furinahub-update.json"
        self.source = source
        self.stage = "checking"
        self.percent = 0
        self.ui = TerminalUI(source)

    def write(self, *, state: str, result: str = "", stage: str | None = None, percent: int | None = None, message: str = "", channel: dict | None = None) -> None:
        if stage is not None:
            self.stage = stage
        if percent is not None:
            self.percent = percent
        payload = {
            "schema": STATE_SCHEMA,
            "protocol": PROTOCOL,
            "state": state,
            "result": result,
            "stage": self.stage,
            "percent": self.percent,
            "message": message,
            "source": self.source,
            "bundle_id": (channel or {}).get("bundle_id", ""),
            "target_version": ((channel or {}).get("core") or {}).get("version", ""),
            "target_revision": ((channel or {}).get("core") or {}).get("revision", ""),
            "updated_at": time.time(),
        }
        atomic_text(self.path, json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

    def progress(self, percent: int, stage: str, message: str, channel: dict | None = None) -> None:
        self.write(state="running", stage=stage, percent=percent, message=message, channel=channel)
        self.ui.progress(percent, message)

    def finish(self, result: str, message: str, channel: dict) -> None:
        self.write(state="done", result=result, stage="done", percent=100, message=message, channel=channel)
        self.ui.finish(message)

    def fail(self, message: str, channel: dict | None) -> None:
        self.write(state="error", result="error", message=message, channel=channel)
        self.ui.error(self.stage, message)
'''


UPDATE = r'''
def update(args: argparse.Namespace) -> int:
    root = root_dir()
    root.mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    source = os.environ.get("FURINA_UPDATE_SOURCE", "termux")
    state = State(root, source)
    with acquire_lock(root), tempfile.TemporaryDirectory(prefix="furina-update-") as td:
        work = Path(td)
        channel: dict | None = None
        try:
            state.progress(3, "checking", "Memeriksa pembaruan Furina")
            channel = load_channel(work, args.channel_file)
            maybe_reexec(root, channel, work, sys.argv[1:])
            install_launchers(root)

            if args.command == "apk-only":
                changed = sync_apk(root, channel, work, state)
                message = "Installer FurinaHub dibuka" if changed else "FurinaHub sudah terbaru"
                state.finish("updated" if changed else "no_update", message, channel)
                return 0

            force_core = bool(args.force or args.command == "repair")
            core_current = installed_is_current(root, channel)

            # Fast path: an already-current Core never pays package/npm/plugin
            # reconciliation cost. APK confirmation is independent and cheap.
            if core_current and not force_core:
                changed_apk = sync_apk(root, channel, work, state)
                message = "Installer FurinaHub dibuka" if changed_apk else "Tidak ada pembaruan terbaru"
                state.finish("updated" if changed_apk else "no_update", message, channel)
                return 0

            # Only a real Core install/repair needs the Termux integration and
            # optional Plugin runtime. Keep these before the atomic swap so an
            # external dependency failure cannot leave half of a new Core live.
            ensure_termux_properties()
            ensure_openconnector(root, state, channel)
            changed_core = install_core(root, channel, work, state, force=force_core)
            install_launchers(root)
            changed_apk = sync_apk(root, channel, work, state)
            if changed_core and changed_apk:
                message = "Core diperbarui; installer FurinaHub dibuka"
            elif changed_core:
                message = "Core diperbarui"
            elif changed_apk:
                message = "Installer FurinaHub dibuka"
            else:
                message = "Tidak ada pembaruan terbaru"
            state.finish("updated" if (changed_core or changed_apk) else "no_update", message, channel)
            return 0
        except Exception as exc:
            state.fail(f"Pembaruan gagal: {exc}", channel)
            return 1
'''


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_client.py <runtime-r39/update_client.py> <output>")
    source = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    text = source.read_text(encoding="utf-8")
    text = text.replace('CLIENT_VERSION = "1.0.0"', 'CLIENT_VERSION = "1.1.0"', 1)
    text = replace_node(text, lambda n: isinstance(n, ast.ClassDef) and n.name == "State", STATE_AND_UI)
    text = replace_node(text, lambda n: isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "update", UPDATE)
    compile(text, str(output), "exec")
    active_update = text[text.index("def update("):text.index("def status(")]
    if "ensure_termux_packages()" in active_update:
        raise SystemExit("final updater still reconciles packages on the top-level update path")
    if active_update.index("core_current = installed_is_current") > active_update.index("ensure_openconnector("):
        raise SystemExit("final updater no-op gate is after Plugin setup")
    required = ("class TerminalUI", "FURINA_FORCE_TUI", "state.finish", "state.fail", 'CLIENT_VERSION = "1.1.0"')
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit(f"final updater incomplete: {missing}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print("FURINA_FINAL_UPDATER_BUILD_OK")


if __name__ == "__main__":
    main()
