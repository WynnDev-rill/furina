#!/usr/bin/env python3
from __future__ import annotations
import pathlib, sys


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-semantic-guard-rc23.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    tui = root / "core/furina_agent/tui.py"
    if not tui.is_file():
        raise SystemExit("missing RC23 TUI source")
    text = tui.read_text(encoding="utf-8")

    done_marker = "def approve_agent_action(summary, action, risk, detail):"
    if done_marker in text and "semantic_steps=intent.steps" in text:
        compile(text, str(tui), "exec")
        print("Furina RC23 fallback TUI semantic safety: already applied")
        return

    start_marker = '            if intent.mode == "device":\n'
    end_marker = '            else:\n                _stream_chat(console, session, text)\n'
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker)) if start >= 0 else -1
    if start < 0 or end < 0:
        raise SystemExit(f"RC23 guard marker range missing: start={start} end={end}")
    end += len(end_marker)

    replacement = r'''            semantic_direct = session.try_direct_intent(intent)
            if semantic_direct.handled:
                store.add_message("user", text)
                store.add_message("assistant", semantic_direct.reply)
                console.print(f"[bold bright_magenta]{_display_name()}[/]  {semantic_direct.reply}\n")
                continue

            if intent.mode == "device":
                allowed = _confirm(
                    "Furina perlu memakai layar untuk menyelesaikan tugas ini. Navigasi dan input biasa tercakup; "
                    "aksi eksternal atau target yang belum pasti akan meminta konfirmasi lagi. Lanjut?",
                    default=True,
                )
                if not allowed:
                    console.print(f"[bright_magenta]{_display_name()}[/]  Baik. Aku tidak menyentuh layar.\n")
                    continue

                def approve_agent_action(summary, action, risk, detail):
                    if risk not in {"external", "uncertain"}:
                        return True
                    prefix = (
                        "Aksi berikut dapat memberi efek ke luar aplikasi."
                        if risk == "external"
                        else "Target tindakan berikut belum cukup pasti."
                    )
                    label = str(summary or detail or "Tindakan berikutnya").strip()
                    if len(label) > 180:
                        label = label[:177] + "..."
                    return _confirm(prefix + (f"\n\n{label}" if label else "") + "\n\nLanjut?", default=False)

                store.add_message("user", text)
                with console.status("[#5de4c7]Menggunakan layar…[/]", spinner="dots"):
                    reply = session.agent.run(
                        intent.goal,
                        approve_agent_action,
                        task_authorized=True,
                        semantic_steps=intent.steps,
                    )
                store.add_message("assistant", reply)
                console.print(f"[bold bright_magenta]{_display_name()}[/]  {reply}\n")
            else:
                _stream_chat(console, session, text)
'''
    text = text[:start] + replacement + text[end:]
    tui.write_text(text, encoding="utf-8")
    compile(text, str(tui), "exec")
    checks = [
        "semantic_direct = session.try_direct_intent(intent)",
        done_marker,
        'risk not in {"external", "uncertain"}',
        "default=False",
        "semantic_steps=intent.steps",
    ]
    missing = [x for x in checks if x not in text]
    if missing:
        raise SystemExit("RC23 fallback guard incomplete: " + ", ".join(missing))
    print("Furina RC23 fallback TUI semantic safety: OK")


if __name__ == "__main__":
    main()
