from __future__ import annotations

import os
import select
import sys
import termios
import time
import tty


def _horizontal_key() -> str:
    if not sys.stdin.isatty():
        try:
            return input("←/→/Enter/ESC › ").strip().casefold()
        except EOFError:
            return "escape"
    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        first = os.read(fd, 1)
        if first in {b"\r", b"\n"}:
            return "enter"
        if first != b"\x1b":
            value = first.decode(errors="ignore").casefold()
            return {"a": "a", "b": "b", "s": "skip", "r": "reroll", "q": "escape"}.get(value, "noop")
        sequence = bytearray()
        deadline = time.monotonic() + .16
        while len(sequence) < 16:
            timeout = deadline - time.monotonic()
            if timeout <= 0 or not select.select([fd], [], [], timeout)[0]:
                break
            part = os.read(fd, 1)
            if not part:
                break
            sequence.extend(part)
            if part == b"D":
                return "left"
            if part == b"C":
                return "right"
        return "escape" if not sequence else "noop"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def install_tui_v125(ns: dict) -> None:
    console_helpers = {key: ns[key] for key in ("_clear", "_header", "_choose", "_pause", "_confirm")}
    clear = console_helpers["_clear"]
    header = console_helpers["_header"]
    choose_menu = console_helpers["_choose"]
    pause = console_helpers["_pause"]
    confirm = console_helpers["_confirm"]
    load_config = ns["load_config"]

    def training_room(console):
        from .hub_settings import load_hub_settings
        from .routing import RoutingLLM
        from .training_room import CATEGORIES, REROLL_REASONS_123, TrainingSession, training_progress

        labels = [item["label"] for item in CATEGORIES.values()]
        by_label = {item["label"]: key for key, item in CATEGORIES.items()}
        reason_labels = list(REROLL_REASONS_123.values())
        reason_by_label = {label: key for key, label in REROLL_REASONS_123.items()}
        while True:
            progress = training_progress()
            clear(); header(console, "Training Room")
            console.print(
                f"[dim]Preferensi tersimpan[/]  {progress['total']} pilihan  ·  "
                f"{progress.get('retired_prompts', 0)} prompt dipensiunkan"
            )
            console.print(
                f"[dim]{progress.get('corpus_size', 0)} percakapan netral tersedia. "
                "Dijawab atau dilewati berarti tidak akan muncul lagi.[/]\n"
            )
            category_label = choose_menu("", labels + ["Kembali"], height=12)
            if category_label in {"", "Kembali"}:
                return
            category_id = by_label.get(category_label)
            if not category_id:
                continue
            cfg = load_config()
            session = TrainingSession(category_id, RoutingLLM(cfg))
            pair = None
            notice = ""
            selected = 0
            actions = ("Respons A", "Respons B", "Lewati", "R · Buat ulang", "Selesai")
            while True:
                if pair is None:
                    try:
                        clear(); header(console, "Training Room")
                        console.print(f"[#5de4c7]{category_label}[/]  [dim]Memilih percakapan netral dan membuat kandidat…[/]")
                        pair = session.generate()
                        selected = 0
                    except Exception as exc:
                        console.print(f"\n[red]Tidak dapat membuat respons[/]  {str(exc)[:220]}")
                        console.print("[dim]Periksa Provider & Model, lalu coba lagi.[/]")
                        pause(); break

                clear(); header(console, "Training Room")
                partner = bool(load_hub_settings().get("partner_mode"))
                console.print(f"[#5de4c7]{category_label}[/]  [dim]Percakapan nyata · Mode pasangan {'aktif' if partner else 'nonaktif'}[/]")
                context = str(getattr(pair, "context_text", "") or "").strip()
                if context and context != "(tanpa konteks tambahan)":
                    console.print("\n[dim]Konteks sebelumnya[/]")
                    console.print(context, markup=False)
                console.print("\n[bold]Pesan user[/]")
                console.print(pair.user_text, markup=False)

                console.print("\n[bold cyan]Respons A[/]")
                console.print(pair.response_a, markup=False)
                console.print("\n[bold cyan]Respons B[/]")
                console.print(pair.response_b, markup=False)

                if selected == 2:
                    console.print("\n[yellow]Lewati[/]")
                    console.print("Prompt ini dipensiunkan permanen tanpa menyimpan preferensi.")
                elif selected == 3:
                    console.print("\n[cyan]Buat ulang[/]")
                    console.print("Buat A/B baru untuk prompt yang sama dan simpan alasan penolakannya.")
                else:
                    console.print("\n[dim]Selesai[/]")
                    console.print("Kembali ke daftar materi.")

                if notice:
                    console.print(f"\n[green]{notice}[/]")
                rendered = []
                for index, label in enumerate(("A", "B", "Lewati", "R", "Selesai")):
                    rendered.append(f"[bold #9efce7]› {label} ‹[/]" if index == selected else f"[#3d6b5e]{label}[/]")
                console.print("\n" + "  [#1f6e5a]│[/]  ".join(rendered))
                key = _horizontal_key()
                if key == "left":
                    selected = (selected - 1) % len(actions); continue
                if key == "right":
                    selected = (selected + 1) % len(actions); continue
                if key == "a":
                    selected = 0; key = "enter"
                elif key == "b":
                    selected = 1; key = "enter"
                elif key == "skip":
                    selected = 2; key = "enter"
                elif key == "reroll":
                    selected = 3; key = "enter"
                if key == "escape":
                    selected = 4; key = "enter"
                if key != "enter":
                    continue

                action = actions[selected]
                if action == "Selesai":
                    summary = session.summary()
                    clear(); header(console, "Training Room")
                    console.print(f"[green]Sesi selesai.[/] {summary['choices']} pilihan baru tersimpan.")
                    pause(); break
                if action == "Lewati":
                    session.skip()
                    pair = None
                    notice = "Prompt dilewati dan dipensiunkan permanen. Menyiapkan prompt baru."
                    continue
                if action == "R · Buat ulang":
                    reason_label = choose_menu("Kenapa keduanya tidak cocok?", reason_labels + ["Batal"], height=10)
                    if reason_label in {"", "Batal"}:
                        continue
                    result = session.reject_pair(reason_by_label[reason_label])
                    pair = None
                    notice = f"Alasan dipelajari: {result['label']}. Prompt tetap sama."
                    continue
                choice_key = "a" if action == "Respons A" else "b"
                session.choose(choice_key)
                pair = None
                notice = f"{action} tersimpan. Prompt dipensiunkan permanen."

    def advanced_settings(console):
        from .hub_settings import load_hub_settings, save_hub_settings
        from .training_room import training_progress

        while True:
            state = load_hub_settings()
            partner = bool(state.get("partner_mode"))
            full = bool(state.get("full_local_memory"))
            suggestions = bool(state.get("training_suggestions"))
            progress = training_progress()
            clear(); header(console, "Lanjutan")
            console.print("[dim]Semua fitur dapat dimatikan. Saran latihan memakai batas otomatis agar tidak mengganggu chat.[/]\n")
            training_label = f"Training Room · {progress['total']} pilihan"
            suggestion_label = f"Saran latihan di chat · {'Aktif' if suggestions else 'Nonaktif'}"
            partner_label = f"Mode pasangan · {'Aktif' if partner else 'Nonaktif'}"
            memory_label = f"Memori penuh lokal · {'Aktif' if full else 'Nonaktif'}"
            action = choose_menu("", [training_label, suggestion_label, partner_label, memory_label, "Kembali"], height=8)
            if action in {"", "Kembali"}:
                return
            if action == training_label:
                training_room(console)
            elif action == suggestion_label:
                state["training_suggestions"] = not suggestions
                save_hub_settings(state)
                console.print(
                    f"[green]Saran latihan di chat {'diaktifkan' if not suggestions else 'dinonaktifkan'}.[/] "
                    + ("Sistem memilih momen bernilai tinggi dan membatasi maksimal dua tawaran per sesi." if not suggestions else "Chat kembali menjawab langsung seperti biasa.")
                )
                pause()
            elif action == partner_label:
                state["partner_mode"] = not partner
                save_hub_settings(state)
                console.print(f"[green]Mode pasangan {'diaktifkan' if not partner else 'dinonaktifkan'}.[/]")
                pause()
            elif action == memory_label:
                if not full and not confirm("Semua teks percakapan baru akan diarsipkan di perangkat dan dicari saat relevan. Aktifkan?", default=False):
                    continue
                state["full_local_memory"] = not full
                save_hub_settings(state)
                note = "Arsip lama tetap tersimpan dan tidak dihapus otomatis." if full else "Mulai sekarang seluruh teks baru disimpan di arsip lokal."
                console.print(f"[green]Memori penuh lokal {'dinonaktifkan' if full else 'diaktifkan'}.[/] {note}")
                pause()

    ns["_training_room_125"] = training_room
    ns["_training_room_121"] = training_room
    ns["_advanced_settings_125"] = advanced_settings
    ns["_advanced_settings_121"] = advanced_settings
    ns["_advanced_settings_119"] = advanced_settings
