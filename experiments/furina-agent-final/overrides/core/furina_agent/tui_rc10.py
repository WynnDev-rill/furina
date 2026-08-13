from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .bridge import AndroidBridge
from .companion import CompanionSession
from .config import load_config, save_config
from .llm import LocalLLM
from .memory import MemoryStore
from .providers import PROVIDER_LABELS, OpenAICompatibleProvider, ProviderSecrets
from .routing import RoutingLLM
from .version import VERSION

ACCENT = "212"
CYAN = "51"
MUTED = "245"
GREEN = "42"
RED = "196"


def _rich():
    try:
        from rich.console import Console
        from rich.live import Live
        from rich.markdown import Markdown
        from rich.prompt import Confirm, Prompt
        from rich.table import Table
        from rich.text import Text
        return Console, Live, Markdown, Confirm, Prompt, Table, Text
    except ImportError as exc:
        raise SystemExit("UI Furina membutuhkan Rich. Jalankan: pkg install python-pip -y && python -m pip install rich") from exc


def _gum() -> str | None:
    return shutil.which("gum")


def _clear() -> None:
    print("\033[2J\033[H", end="", flush=True)


def _run_gum(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_gum(), *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def _choose(title: str, options: list[str], *, height: int | None = None) -> str:
    if _gum():
        h = height or min(max(6, len(options) + 2), 12)
        result = _run_gum([
            "choose",
            "--header", title,
            "--height", str(h),
            "--cursor-prefix", "› ",
            "--selected-prefix", "› ",
            "--unselected-prefix", "  ",
            "--cursor.foreground", ACCENT,
            "--header.foreground", CYAN,
            *options,
        ])
        return result.stdout.strip() if result.returncode == 0 else ""
    _, _, _, _, Prompt, _, _ = _rich()
    for i, option in enumerate(options, 1):
        print(f"{i:>2}. {option}")
    raw = Prompt.ask(title, default="1").strip()
    try:
        return options[int(raw) - 1]
    except Exception:
        return ""


def _input(prompt: str, *, value: str = "", placeholder: str = "", password: bool = False) -> str:
    if _gum():
        args = [
            "input",
            "--prompt", prompt,
            "--prompt.foreground", CYAN,
            "--cursor.foreground", ACCENT,
        ]
        if value:
            args += ["--value", value]
        if placeholder:
            args += ["--placeholder", placeholder]
        if password:
            args += ["--password"]
        result = _run_gum(args)
        return result.stdout.rstrip("\n") if result.returncode == 0 else ""
    _, _, _, _, Prompt, _, _ = _rich()
    return Prompt.ask(prompt.strip(), default=value or None, password=password).strip()


def _confirm(text: str, *, default: bool = False) -> bool:
    if _gum():
        args = [
            "confirm", text,
            "--prompt.foreground", CYAN,
            "--selected.background", ACCENT,
            "--selected.foreground", "0",
        ]
        if default:
            args.append("--default")
        return _run_gum(args).returncode == 0
    _, _, _, Confirm, _, _, _ = _rich()
    return Confirm.ask(text, default=default)


def _pause(label: str = "Enter untuk kembali") -> None:
    if _gum():
        _run_gum(["input", "--prompt", "", "--placeholder", label])
    else:
        input(f"\n{label}")


def _status_snapshot():
    cfg = load_config()
    local = LocalLLM(cfg)
    bridge = AndroidBridge(cfg)
    store = MemoryStore()
    secrets = ProviderSecrets()
    try:
        bridge_data = bridge.health()
        bridge_ok = bool(bridge_data.get("foreground")) and bool(bridge_data.get("accessibility"))
    except Exception:
        bridge_data = None
        bridge_ok = False
    return cfg, bool(local.health()), bridge_data, bridge_ok, len(store.list_memories(limit=999)), secrets.configured()


def _dot(ok: bool) -> str:
    return "[green]●[/]" if ok else "[dim]○[/]"


def _header(console, section: str = "") -> None:
    cfg, local_ok, bridge, bridge_ok, memory_count, providers = _status_snapshot()
    route = {"local": "LOCAL", "auto": "AUTO", "online": "ONLINE"}.get(cfg.routing_mode, cfg.routing_mode.upper())
    title = f"[bold bright_cyan]FURINA[/] [dim]rc{VERSION.rsplit('rc', 1)[-1]}[/]"
    if section:
        title += f"  [dim]·[/]  [bold]{section}[/]"
    console.print(title)
    console.print(
        f"{_dot(local_ok)} [dim]local[/]   "
        f"{_dot(bridge_ok)} [dim]bridge[/]   "
        f"[bright_cyan]{memory_count}[/] [dim]memory[/]   "
        f"[bright_magenta]{route}[/]"
    )
    console.print("[dim]" + "─" * max(16, min(console.width, 72)) + "[/]")


def _main_menu(console) -> str:
    return _choose(
        "",
        ["Chat", "Memory", "Provider", "Settings", "System", "Update", "Exit"],
        height=9,
    )


def _stream_chat(console, session, text: str):
    _, Live, Markdown, _, _, _, _ = _rich()
    buffer: list[str] = []
    last_draw = [0.0]
    console.print("[bold bright_magenta]Furina[/]")
    with Live("[dim]…[/]", console=console, refresh_per_second=12, transient=False) as live:
        def on_token(piece: str):
            buffer.append(piece)
            now = time.monotonic()
            if now - last_draw[0] < 0.045 and len(piece) < 24:
                return
            last_draw[0] = now
            live.update(Markdown("".join(buffer)))
        answer = session.chat.respond(text, on_token=on_token)
        live.update(Markdown(answer), refresh=True)
    console.print()
    return answer


def _chat(console):
    cfg = load_config()
    llm = RoutingLLM(cfg)
    store = MemoryStore()
    session = CompanionSession(cfg, store, llm)

    _clear()
    _header(console, "Chat")
    console.print("[dim]/back untuk kembali[/]\n")

    while True:
        text = _input("› ", placeholder="Tulis pesan…").strip()
        if text.lower() in {"/back", "/exit", "/quit"}:
            return
        if not text:
            continue
        console.print(f"[bold bright_cyan]You[/]  {text}")
        try:
            with console.status("[bright_magenta]Memahami…[/]", spinner="dots"):
                intent = session.classify(text)

            if intent.mode == "device":
                allowed = _confirm(
                    "Furina perlu memakai layar untuk tugas ini. Izin berlaku untuk seluruh tugas yang kamu minta, "
                    "termasuk Send/Kirim/Post/Share yang memang eksplisit. Lanjut?",
                    default=False,
                )
                if not allowed:
                    console.print("[bright_magenta]Furina[/]  Baik. Aku tidak menyentuh layar.\n")
                    continue
                store.add_message("user", text)
                with console.status("[bright_magenta]Menggunakan layar…[/]", spinner="dots"):
                    reply = session.agent.run(
                        intent.goal,
                        lambda *_args: True,
                        task_authorized=True,
                    )
                store.add_message("assistant", reply)
                console.print(f"[bold bright_magenta]Furina[/]  {reply}\n")
            else:
                _stream_chat(console, session, text)
        except Exception as exc:
            console.print(f"[red]Gagal[/]  {exc}\n")


def _memory_list(console):
    store = MemoryStore()
    memories = store.list_memories(limit=30)
    _clear()
    _header(console, "Memory")
    if not memories:
        console.print("[dim]Belum ada long-term memory.[/]")
        return
    for m in memories:
        kind = str(m.kind).upper()[:11]
        console.print(f"[bright_cyan]{kind:<11}[/]  {m.text}")
    console.print(f"\n[dim]{len(memories)} memory terbaru ditampilkan.[/]")


def _reminders(console):
    store = MemoryStore()
    _clear()
    _header(console, "Reminder")
    try:
        due = store.due_prospectives(time.time() + 365 * 86400, 30)
    except Exception:
        due = []
    if not due:
        console.print("[dim]Belum ada reminder aktif.[/]")
        return
    for item in due:
        due_at = float(item.get("due_at", 0) or 0)
        when = time.strftime("%d %b · %H:%M", time.localtime(due_at)) if due_at else "tanpa waktu"
        console.print(f"[bright_cyan]{when}[/]  {item.get('text', '')}")


def _screen(console):
    _clear()
    _header(console, "Screen")
    try:
        data = AndroidBridge(load_config()).screen()
    except Exception as exc:
        console.print(f"[red]Bridge tidak dapat membaca layar[/]  {exc}")
        return
    nodes = data.get("nodes") or []
    package = data.get("package") or "?"
    console.print(f"[dim]{package} · {len(nodes)} node[/]\n")
    shown = 0
    for node in nodes:
        label = node.get("text") or node.get("desc") or node.get("view_id") or ""
        if not label:
            continue
        flags = "".join([
            "C" if node.get("clickable") else "",
            "E" if node.get("editable") else "",
            "S" if node.get("scrollable") else "",
        ])
        console.print(f"[cyan]{str(node.get('id', '')):>3}[/]  {str(label)[:64]} [dim]{flags}[/]")
        shown += 1
        if shown >= 35:
            break


def _memory_menu(console):
    while True:
        _clear()
        _header(console, "Memory")
        choice = _choose("", ["Long-term memory", "Reminder", "Screen tree", "Back"], height=6)
        if choice in {"", "Back"}:
            return
        if choice == "Long-term memory":
            _memory_list(console)
        elif choice == "Reminder":
            _reminders(console)
        elif choice == "Screen tree":
            _screen(console)
        _pause()


def _provider_name() -> str:
    names = list(PROVIDER_LABELS)
    selected = _choose("Provider", [PROVIDER_LABELS[n] for n in names] + ["Back"], height=7)
    if selected in {"", "Back"}:
        return ""
    for name in names:
        if PROVIDER_LABELS[name] == selected:
            return name
    return ""


def _providers(console):
    secrets = ProviderSecrets()
    while True:
        cfg = load_config()
        _clear()
        _header(console, "Provider")
        for name, label in PROVIDER_LABELS.items():
            console.print(f"[bright_cyan]{label:<12}[/]  [dim]{secrets.masked(name) or 'belum diatur'}[/]")
        console.print(f"\n[dim]Routing[/]  [bold]{cfg.routing_mode.upper()}[/]")
        if "openrouter" in PROVIDER_LABELS:
            console.print(f"[dim]OpenRouter free-only[/]  {'ON' if cfg.provider_prefer_free else 'OFF'}")

        choice = _choose(
            "",
            ["Add / update key", "Remove key", "Test provider", "Routing", "Toggle OpenRouter free-only", "Back"],
            height=8,
        )
        if choice in {"", "Back"}:
            return

        if choice in {"Add / update key", "Remove key", "Test provider"}:
            name = _provider_name()
            if not name:
                continue
            if choice == "Add / update key":
                key = _input("API key › ", password=True).strip()
                if key:
                    secrets.set(name, key)
                    console.print("[green]Tersimpan lokal.[/]")
                    if cfg.routing_mode == "local" and _confirm("Aktifkan AUTO?", default=True):
                        cfg.routing_mode = "auto"
                        save_config(cfg)
            elif choice == "Remove key":
                if _confirm(f"Hapus key {PROVIDER_LABELS[name]}?", default=False):
                    secrets.remove(name)
            else:
                key = secrets.get(name)
                if not key:
                    console.print("[yellow]Key belum diatur.[/]")
                else:
                    try:
                        with console.status(f"[bright_magenta]Menguji {PROVIDER_LABELS[name]}…[/]", spinner="dots"):
                            ok, detail = OpenAICompatibleProvider(name, key, cfg).test()
                        console.print(("[green]OK[/]  " if ok else "[red]FAIL[/]  ") + detail)
                    except Exception as exc:
                        console.print(f"[red]FAIL[/]  {exc}")
            _pause()
        elif choice == "Routing":
            picked = _choose("Routing", ["LOCAL", "AUTO", "ONLINE", "Back"], height=6)
            if picked in {"LOCAL", "AUTO", "ONLINE"}:
                cfg.routing_mode = {"LOCAL": "local", "AUTO": "auto", "ONLINE": "online"}[picked]
                save_config(cfg)
        elif choice == "Toggle OpenRouter free-only":
            cfg.provider_prefer_free = not cfg.provider_prefer_free
            save_config(cfg)


def _settings(console):
    while True:
        cfg = load_config()
        _clear()
        _header(console, "Settings")
        console.print(f"[dim]Panggilan[/]   {cfg.user_nickname or '—'}")
        console.print(f"[dim]Nama[/]       {cfg.persona_name}")
        console.print(f"[dim]Local start[/] {'ON' if cfg.auto_start else 'OFF'}")
        console.print(f"[dim]Context[/]    {cfg.context_size}\n")

        choice = _choose("", ["Nama panggilan", "Nama Furina", "Toggle local auto-start", "Back"], height=6)
        if choice in {"", "Back"}:
            return
        if choice == "Nama panggilan":
            cfg.user_nickname = _input("Panggilan › ", value=cfg.user_nickname).strip()[:48]
        elif choice == "Nama Furina":
            cfg.persona_name = _input("Nama › ", value=cfg.persona_name).strip()[:48] or "Furina"
        elif choice == "Toggle local auto-start":
            cfg.auto_start = not cfg.auto_start
        cfg.local_reasoning = False
        save_config(cfg)


def _doctor(console):
    from .cli import collect_doctor_checks

    _clear()
    _header(console, "System")
    for name, detail, ok in collect_doctor_checks():
        mark = "[green]●[/]" if ok else "[red]●[/]"
        console.print(f"{mark} [bold]{name}[/]  [dim]{detail}[/]")


def _system(console):
    while True:
        _doctor(console)
        choice = _choose("", ["Optimize local", "Start local", "Stop local", "Back"], height=6)
        if choice in {"", "Back"}:
            return
        if choice == "Optimize local":
            if _confirm("Benchmark dapat membuat HP hangat. Lanjut?", default=False):
                from .cli import cmd_optimize
                try:
                    cmd_optimize(None)
                except Exception as exc:
                    console.print(f"[red]Optimize gagal[/]  {exc}")
                _pause()
        elif choice == "Start local":
            from .cli import cmd_start
            try:
                with console.status("[bright_magenta]Menyalakan local model…[/]", spinner="dots"):
                    cmd_start(None)
            except Exception as exc:
                console.print(f"[red]Start gagal[/]  {exc}")
            _pause()
        elif choice == "Stop local":
            from .cli import cmd_stop
            cmd_stop(None)


def _setup(console):
    cfg = load_config()
    _clear()
    _header(console, "Setup")
    console.print("Satu kali setup. Setelah ini cukup ketik [bright_cyan]furina[/].\n")

    cfg.user_nickname = _input("Furina memanggilmu › ", value=cfg.user_nickname).strip()[:48]
    cfg.local_reasoning = False
    save_config(cfg)

    bridge = AndroidBridge(cfg)
    try:
        health = bridge.health()
        ok = bridge.ensure_paired()
        console.print(f"[green]●[/] Bridge {health.get('version', '?')}" if ok else "[yellow]●[/] Bridge perlu Repair")
    except Exception:
        console.print("[yellow]●[/] Buka Furina Bridge dan aktifkan Accessibility.")

    mode = _choose("Model", ["LOCAL", "AUTO", "ONLINE"], height=5)
    if mode:
        cfg.routing_mode = {"LOCAL": "local", "AUTO": "auto", "ONLINE": "online"}[mode]
    save_config(cfg)
    if cfg.routing_mode in {"auto", "online"} and _confirm("Tambahkan API key sekarang?", default=True):
        _providers(console)
    cfg = load_config()
    cfg.onboarding_complete = True
    cfg.local_reasoning = False
    save_config(cfg)


def _update_repair(console):
    while True:
        _clear()
        _header(console, "Update")
        choice = _choose("", ["Update Core", "Repair Bridge", "Setup ulang", "Back"], height=6)
        if choice in {"", "Back"}:
            return
        if choice == "Update Core":
            if _confirm("Pasang update Core? Memory dan model tetap disimpan.", default=True):
                from .cli import cmd_update
                try:
                    cmd_update(None)
                except Exception as exc:
                    console.print(f"[red]Update gagal[/]  {exc}")
                _pause()
        elif choice == "Repair Bridge":
            from .cli import cmd_repair
            try:
                cmd_repair(None)
            except SystemExit as exc:
                console.print(f"[yellow]{exc}[/]")
            _pause()
        elif choice == "Setup ulang":
            _setup(console)


def _show_due(console):
    try:
        due = MemoryStore().due_prospectives(time.time(), 3)
    except Exception:
        due = []
    if not due:
        return
    console.print()
    for item in due:
        console.print(f"[yellow]Reminder[/]  {item.get('text', '')}")


def _auto_start_local(console):
    cfg = load_config()
    if not cfg.auto_start or cfg.routing_mode != "local" or not cfg.model_path or LocalLLM(cfg).health():
        return
    try:
        from .cli import cmd_start
        with console.status("[bright_magenta]Menyalakan local model…[/]", spinner="dots"):
            cmd_start(None)
    except Exception:
        pass


def run_tui():
    Console, _, _, _, _, _, _ = _rich()
    console = Console(highlight=False)
    cfg = load_config()
    if not cfg.onboarding_complete:
        _setup(console)
    _auto_start_local(console)

    while True:
        _clear()
        _header(console)
        _show_due(console)
        choice = _main_menu(console)
        if choice in {"", "Exit"}:
            return
        if choice == "Chat":
            _chat(console)
        elif choice == "Memory":
            _memory_menu(console)
        elif choice == "Provider":
            _providers(console)
        elif choice == "Settings":
            _settings(console)
        elif choice == "System":
            _system(console)
        elif choice == "Update":
            _update_repair(console)
