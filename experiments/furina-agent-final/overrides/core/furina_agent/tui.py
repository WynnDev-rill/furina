from __future__ import annotations

import json
import os
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


def _rich():
    try:
        from rich import box
        from rich.console import Console
        from rich.live import Live
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.prompt import Confirm, Prompt
        from rich.table import Table
        from rich.text import Text
        return box, Console, Live, Markdown, Panel, Confirm, Prompt, Table, Text
    except ImportError as exc:
        raise SystemExit("UI membutuhkan Rich. Jalankan: pkg install python-pip -y && python -m pip install rich") from exc


def _status_snapshot():
    cfg = load_config()
    local = LocalLLM(cfg)
    bridge = AndroidBridge(cfg)
    store = MemoryStore()
    secrets = ProviderSecrets()
    bridge_data = None
    bridge_error = None
    try:
        bridge_data = bridge.health()
    except Exception as exc:
        bridge_error = str(exc)
    return cfg, local.health(), bridge_data, bridge_error, len(store.list_memories(limit=999)), secrets.configured()


def _header(console):
    box, _, _, _, Panel, _, _, _, Text = _rich()
    cfg = load_config()
    title = Text("FURINA", style="bold bright_cyan")
    title.append("  COMPANION", style="bold bright_magenta")
    title.append("   By Wynn", style="bold white")
    subtitle = f"v{VERSION}  •  local-first  •  Android bridge  •  private by default"
    if cfg.user_nickname:
        subtitle += f"  •  user: {cfg.user_nickname}"
    console.print(Panel(Text.assemble(title, "\n", (subtitle, "dim")), border_style="bright_blue", box=box.ROUNDED, padding=(1, 2)))


def _dashboard(console):
    box, _, _, _, Panel, _, _, Table, _ = _rich()
    cfg, local_ok, bridge, bridge_error, memory_count, providers = _status_snapshot()
    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(ratio=1)
    table.add_column(ratio=1)

    model_name = Path(cfg.model_path).name if cfg.model_path else "belum dipilih"
    local_state = "[bold green]READY[/]" if local_ok else "[yellow]SLEEP[/]"
    if cfg.routing_mode == "auto" and not local_ok:
        local_state = "[cyan]STANDBY[/]"
    if bridge:
        fg = bool(bridge.get("foreground"))
        acc = bool(bridge.get("accessibility"))
        bridge_state = "[bold green]LIVE[/]" if fg else "[red]OFF[/]"
        access_state = "[bold green]BOUND[/]" if acc else "[yellow]UNBOUND[/]"
        bridge_detail = f"Bridge {bridge_state}   Accessibility {access_state}"
    else:
        bridge_detail = "[red]UNREACHABLE[/]"

    provider_names = ", ".join(PROVIDER_LABELS[p] for p in providers) if providers else "belum ada"
    route_label = {"local": "LOCAL", "auto": "AUTO → local fallback", "online": "ONLINE ONLY"}.get(cfg.routing_mode, cfg.routing_mode)
    perf = f"{cfg.threads} threads" + (f" • mask {cfg.cpu_mask}" if cfg.cpu_mask else "") + (" • tuned" if cfg.performance_tuned else " • default")
    table.add_row(
        f"[dim]LOCAL MODEL[/]\n{local_state}  {model_name}\n[dim]{perf}[/]",
        f"[dim]ANDROID[/]\n{bridge_detail}",
    )
    table.add_row(
        f"[dim]AI ROUTER[/]\n[bold cyan]{route_label}[/]\n[dim]{provider_names}[/]",
        f"[dim]MEMORY / RESPONSE[/]\n[bold cyan]{memory_count}[/] long-term  •  adaptive • berhenti saat selesai",
    )
    console.print(Panel(table, title="SYSTEM", border_style="blue", box=box.ROUNDED))
    if bridge_error:
        console.print(f"[yellow]Bridge:[/] {bridge_error}")


def _menu(console):
    box, _, _, _, Panel, _, Prompt, Table, _ = _rich()
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold bright_cyan", width=5)
    table.add_column()
    table.add_row("1", "Percakapan + tindakan Android")
    table.add_row("2", "Memori & layar")
    table.add_row("3", "AI Provider / API key")
    table.add_row("4", "Pengaturan Furina")
    table.add_row("5", "Health / optimize Poco")
    table.add_row("6", "Update / repair")
    table.add_row("r", "Refresh")
    table.add_row("q", "Keluar")
    console.print(Panel(table, title="ACTIONS", border_style="magenta", box=box.ROUNDED))
    return Prompt.ask("[bold]Pilih[/]", default="1").strip().lower()


def _approval_callback(console):
    box, _, _, _, Panel, Confirm, _, _, _ = _rich()

    def approve(summary, action, risk, detail):
        label = {
            "external": "AKSI EKSTERNAL",
            "uncertain": "TARGET TIDAK PASTI",
            "navigate": "NAVIGASI",
            "write": "INPUT",
        }.get(risk, risk.upper())
        body = (
            f"[bold]{summary or 'Aksi berikutnya'}[/]\n\n"
            f"Risk: [yellow]{label}[/]\nTarget: {detail}\n\n"
            f"[cyan]{json.dumps(action, ensure_ascii=False, indent=2)}[/]"
        )
        console.print(Panel(body, title="CONFIRM", border_style="yellow", box=box.ROUNDED))
        return Confirm.ask("Izinkan aksi ini?", default=False)

    return approve


def _stream_chat(console, session, text: str):
    _, _, Live, Markdown, Panel, _, _, _, _ = _rich()
    buffer: list[str] = []
    last_draw = [0.0]
    panel = Panel("[dim]Menyiapkan respons…[/]", title="Furina", border_style="bright_magenta", padding=(1, 2))
    with Live(panel, console=console, refresh_per_second=10, transient=False) as live:
        def on_token(piece: str):
            buffer.append(piece)
            now = time.monotonic()
            if now - last_draw[0] < 0.06 and len(piece) < 24:
                return
            last_draw[0] = now
            live.update(Panel(Markdown("".join(buffer)), title="Furina", border_style="bright_magenta", padding=(1, 2)))

        answer = session.chat.respond(text, on_token=on_token)
        live.update(Panel(Markdown(answer), title="Furina", border_style="bright_magenta", padding=(1, 2)), refresh=True)
    return answer


def _chat(console):
    _, _, _, Markdown, Panel, Confirm, Prompt, _, _ = _rich()
    cfg = load_config()
    llm = RoutingLLM(cfg)
    store = MemoryStore()
    session = CompanionSession(cfg, store, llm)
    approve = _approval_callback(console)
    console.print("[dim]Ketik apa saja secara natural. Furina akan memakai Android Bridge sendiri jika memang perlu. /back untuk kembali.[/]")

    while True:
        text = Prompt.ask("[bold bright_cyan]You[/]").strip()
        if text.lower() in {"/back", "/exit", "/quit"}:
            return
        if not text:
            continue
        try:
            with console.status("[bright_magenta]Memahami…[/]", spinner="dots"):
                intent = session.classify(text)

            if intent.mode == "device":
                if not Confirm.ask(
                    "Perintah ini membutuhkan kontrol layar. Izinkan Furina menavigasi/mengetik? Send/aksi eksternal tetap dikonfirmasi tepat sebelum dilakukan",
                    default=False,
                ):
                    console.print(Panel("Baik. Aku tidak akan menyentuh layar.", title="Furina", border_style="bright_magenta", padding=(1, 2)))
                    continue

                # Device actions are part of the same conversation history, not
                # a separate Agent mode. This preserves conversational continuity.
                store.add_message("user", text)
                with console.status("[bright_magenta]Menggunakan layar…[/]", spinner="dots"):
                    reply = session.agent.run(intent.goal, approve, task_authorized=True)
                store.add_message("assistant", reply)
                console.print(Panel(Markdown(reply), title="Furina", border_style="bright_magenta", padding=(1, 2)))
            else:
                _stream_chat(console, session, text)

            if llm.last.backend:
                console.print(f"[dim]AI: {llm.last.backend} / {llm.last.model}[/]")
        except Exception as exc:
            console.print(f"[red]Gagal:[/] {exc}")


def _screen(console):
    box, _, _, _, Panel, _, _, Table, _ = _rich()
    try:
        data = AndroidBridge(load_config()).screen()
    except Exception as exc:
        console.print(f"[red]Tidak dapat membaca layar:[/] {exc}")
        return
    nodes = data.get("nodes") or []
    table = Table(box=box.SIMPLE_HEAVY, expand=True)
    table.add_column("ID", style="cyan", width=5)
    table.add_column("Type", width=15)
    table.add_column("Text / Description", overflow="fold")
    table.add_column("Flags", width=16)
    for node in nodes[:45]:
        label = node.get("text") or node.get("desc") or node.get("view_id") or ""
        flags = ",".join(k for k in ("clickable", "editable", "scrollable") if node.get(k))
        table.add_row(str(node.get("id", "")), str(node.get("class", "")).split(".")[-1], str(label), flags)
    console.print(Panel(table, title="ANDROID SCREEN", border_style="blue"))


def _memories(console):
    box, _, _, _, Panel, _, _, Table, _ = _rich()
    memories = MemoryStore().list_memories(limit=30)
    if not memories:
        console.print("[dim]Belum ada long-term memory.[/]")
        return
    table = Table(box=box.SIMPLE, expand=True)
    table.add_column("Type", style="cyan", width=13)
    table.add_column("Importance", justify="right", width=10)
    table.add_column("Memory", overflow="fold")
    for m in memories:
        table.add_row(m.kind, f"{m.importance:.2f}", m.text)
    console.print(Panel(table, title="MEMORY", border_style="magenta"))


def _memory_screen_menu(console):
    _, _, _, _, _, _, Prompt, _, _ = _rich()
    console.print("[dim]1 Memory  2 Lihat layar/accessibility tree  b Back[/]")
    c = Prompt.ask("Pilih", default="1").strip().lower()
    if c == "1":
        _memories(console)
    elif c == "2":
        _screen(console)


def _providers(console):
    box, _, _, _, Panel, Confirm, Prompt, Table, _ = _rich()
    secrets = ProviderSecrets()
    while True:
        cfg = load_config()
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Provider", style="cyan")
        table.add_column("API key")
        for name, label in PROVIDER_LABELS.items():
            table.add_row(label, secrets.masked(name))
        table.add_row("Routing", cfg.routing_mode.upper())
        table.add_row("OpenRouter free-only", "ON" if cfg.provider_prefer_free else "OFF")
        console.print(Panel(table, title="AI PROVIDERS", border_style="bright_blue"))
        console.print("[dim]1 Add/update key  2 Remove  3 Test  4 Routing  5 Toggle OpenRouter free-only  b Back[/]")
        choice = Prompt.ask("Pilih", default="1").strip().lower()
        if choice in {"b", "back", "q"}:
            return
        if choice in {"1", "2", "3"}:
            names = list(PROVIDER_LABELS)
            for i, n in enumerate(names, 1):
                console.print(f"  [cyan]{i}[/] {PROVIDER_LABELS[n]}")
            try:
                name = names[int(Prompt.ask("Provider")) - 1]
            except Exception:
                console.print("[yellow]Provider tidak valid.[/]")
                continue
            if choice == "1":
                key = Prompt.ask(f"API key {PROVIDER_LABELS[name]}", password=True).strip()
                if key:
                    secrets.set(name, key)
                    console.print("[green]Key tersimpan lokal.[/]")
                    if cfg.routing_mode == "local" and Confirm.ask("Aktifkan AUTO (online → local fallback)?", default=True):
                        cfg.routing_mode = "auto"
                        save_config(cfg)
            elif choice == "2":
                if Confirm.ask(f"Hapus key {PROVIDER_LABELS[name]}?", default=False):
                    secrets.remove(name)
            else:
                key = secrets.get(name)
                if not key:
                    console.print("[yellow]Key belum diatur.[/]")
                    continue
                try:
                    with console.status(f"Menguji {PROVIDER_LABELS[name]}…", spinner="dots"):
                        ok, detail = OpenAICompatibleProvider(name, key, cfg).test()
                    console.print(("[green]OK[/] " if ok else "[red]FAIL[/] ") + detail)
                except Exception as exc:
                    console.print(f"[red]FAIL[/] {exc}")
        elif choice == "4":
            console.print("1 LOCAL   2 AUTO (online → local)   3 ONLINE ONLY")
            cfg.routing_mode = {"1": "local", "2": "auto", "3": "online"}.get(
                Prompt.ask("Mode", default="2").strip(), cfg.routing_mode
            )
            save_config(cfg)
        elif choice == "5":
            cfg.provider_prefer_free = not cfg.provider_prefer_free
            save_config(cfg)
        console.input("\n[dim]Enter…[/]")
        os.system("clear")
        _header(console)


def _settings(console):
    box, _, _, _, Panel, _, Prompt, Table, _ = _rich()
    while True:
        cfg = load_config()
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value")
        table.add_row("Nama panggilan", cfg.user_nickname or "belum diatur")
        table.add_row("Nama AI", cfg.persona_name)
        table.add_row("Jawaban", "Adaptive — berhenti saat selesai")
        table.add_row("Reasoning tampilan", "HIDDEN")
        table.add_row("Context", str(cfg.context_size))
        table.add_row("Threads", str(cfg.threads))
        table.add_row("Auto start local", "ON" if cfg.auto_start else "OFF")
        console.print(Panel(table, title="SETTINGS", border_style="bright_blue"))
        console.print("[dim]1 Nama panggilan  2 Nama AI  3 Toggle auto-start  b Back[/]")
        c = Prompt.ask("Pilih", default="1").strip().lower()
        if c in {"b", "q", "back"}:
            return
        if c == "1":
            cfg.user_nickname = Prompt.ask("Furina sebaiknya memanggilmu apa?", default=cfg.user_nickname or "").strip()[:48]
        elif c == "2":
            cfg.persona_name = Prompt.ask("Nama AI", default=cfg.persona_name).strip()[:48] or "Furina"
        elif c == "3":
            cfg.auto_start = not cfg.auto_start
        # Reasoning is always hidden/non-thinking for daily companion use.
        cfg.local_reasoning = False
        save_config(cfg)
        console.print("[green]Tersimpan.[/]")


def _doctor(console):
    from .cli import collect_doctor_checks

    box, _, _, _, Panel, _, _, Table, _ = _rich()
    table = Table(box=box.SIMPLE, expand=True)
    table.add_column("State", width=8)
    table.add_column("Check", width=16)
    table.add_column("Detail", overflow="fold")
    for name, detail, ok in collect_doctor_checks():
        table.add_row("[green]OK[/]" if ok else "[red]FAIL[/]", name, str(detail))
    console.print(Panel(table, title="DOCTOR", border_style="bright_blue"))


def _health_optimize(console):
    _, _, _, _, _, Confirm, Prompt, _, _ = _rich()
    _doctor(console)
    console.print("[dim]1 Optimize CPU lokal (thread + affinity benchmark aktual)  2 Start local  3 Stop local  b Back[/]")
    c = Prompt.ask("Pilih", default="b").strip().lower()
    if c == "1":
        if Confirm.ask("Benchmark memuat model beberapa kali dan dapat membuat HP hangat. Lanjutkan?", default=False):
            from .cli import cmd_optimize
            try:
                cmd_optimize(None)
            except Exception as exc:
                console.print(f"[red]Optimize gagal:[/] {exc}")
    elif c == "2":
        from .cli import cmd_start
        try:
            cmd_start(None)
        except Exception as exc:
            console.print(f"[red]Start gagal:[/] {exc}")
    elif c == "3":
        from .cli import cmd_stop
        cmd_stop(None)


def _update_repair(console):
    _, _, _, _, _, Confirm, Prompt, _, _ = _rich()
    console.print("[dim]1 Update Furina Core  2 Repair/auto-connect Bridge  3 Setup ulang  b Back[/]")
    c = Prompt.ask("Pilih", default="b").strip().lower()
    if c == "1":
        if Confirm.ask("Cek dan pasang update Core sekarang? Model/memory tidak dihapus.", default=True):
            from .cli import cmd_update
            cmd_update(None)
    elif c == "2":
        from .cli import cmd_repair
        try:
            cmd_repair(None)
        except SystemExit as exc:
            console.print(f"[yellow]{exc}[/]")
    elif c == "3":
        _setup(console)


def _setup(console):
    _, _, _, _, Panel, Confirm, Prompt, _, _ = _rich()
    cfg = load_config()
    console.print(Panel(
        "[bold]Setup final[/]\n\nTidak perlu memindahkan ZIP atau menyalin pairing code. Setelah setup, pemakaian harian cukup [cyan]furina[/].",
        title="START HERE",
        border_style="bright_cyan",
    ))

    nickname = Prompt.ask("Furina sebaiknya memanggilmu apa? (boleh dikosongkan)", default=cfg.user_nickname or "").strip()
    cfg.user_nickname = nickname[:48]
    cfg.local_reasoning = False
    save_config(cfg)

    bridge = AndroidBridge(cfg)
    try:
        health = bridge.health()
        console.print(f"[green]✓[/] Furina Bridge v{health.get('version', '?')} terdeteksi")
        if bridge.ensure_paired():
            console.print("[green]✓[/] Auto-connect Termux ↔ Bridge berhasil")
        else:
            console.print("[yellow]![/] Buka aplikasi Furina Bridge selama beberapa detik lalu pilih Update/Repair → Repair.")
    except Exception:
        console.print("[yellow]! Bridge belum aktif.[/] Install/buka Furina Bridge, aktifkan Persistent Bridge + Accessibility. Tidak ada kode pairing.")

    console.print("\n[bold]Cara AI bekerja[/]\n1 LOCAL — privat, model HP\n2 AUTO — online jika tersedia, local baru bangun saat fallback\n3 ONLINE ONLY")
    mode = Prompt.ask("Mode", default={"local": "1", "auto": "2", "online": "3"}.get(cfg.routing_mode, "1")).strip()
    cfg.routing_mode = {"1": "local", "2": "auto", "3": "online"}.get(mode, cfg.routing_mode)
    save_config(cfg)
    if cfg.routing_mode in {"auto", "online"} and Confirm.ask("Tambahkan API key sekarang?", default=True):
        _providers(console)
    cfg = load_config()
    cfg.onboarding_complete = True
    cfg.local_reasoning = False
    save_config(cfg)
    console.print("\n[green]Setup selesai.[/] Berikutnya cukup buka Termux → ketik [cyan]furina[/].")


def _auto_start_local(console):
    cfg = load_config()
    if not cfg.auto_start or cfg.routing_mode != "local" or not cfg.model_path or LocalLLM(cfg).health():
        return
    try:
        from .cli import cmd_start
        with console.status("[bright_magenta]Menyalakan model lokal…[/]", spinner="dots"):
            cmd_start(None)
    except Exception as exc:
        console.print(f"[yellow]Local runtime belum dapat start otomatis:[/] {exc}")


def run_tui():
    _, Console, _, _, _, _, _, _, _ = _rich()
    console = Console()
    cfg = load_config()
    if not cfg.onboarding_complete:
        _header(console)
        _setup(console)
        console.input("\n[dim]Enter untuk membuka Furina…[/]")
    _auto_start_local(console)
    while True:
        os.system("clear")
        _header(console)
        _dashboard(console)
        choice = _menu(console)
        if choice == "q":
            return
        if choice == "1":
            _chat(console)
        elif choice == "2":
            _memory_screen_menu(console)
        elif choice == "3":
            _providers(console)
        elif choice == "4":
            _settings(console)
        elif choice == "5":
            _health_optimize(console)
        elif choice == "6":
            _update_repair(console)
        elif choice == "r":
            continue
        else:
            console.print("[yellow]Pilihan tidak dikenal.[/]")
        console.input("\n[dim]Enter untuk kembali…[/]")
