#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker)) if start >= 0 else -1
    if start < 0 or end < 0:
        if replacement.strip() in text:
            return text
        raise SystemExit(f"RC21 block marker missing: {label}")
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC21 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-reactive-core-rc21.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    agent = core / "agent.py"
    chat = core / "chat_surface.py"
    version = core / "version.py"
    for path in (agent, chat, version):
        if not path.is_file():
            raise SystemExit(f"missing RC21 source: {path}")

    a = agent.read_text(encoding="utf-8")
    compiler = r'''    def _compile_ui_sequence(self, goal: str, contract: TaskContract, apps: list[dict]) -> list[dict]:
        # Side effects stay on the guarded step-by-step agent path. Read-only
        # browsing/search is allowed to use the continuous local executor.
        blocked = re.compile(
            r"\b(?:kirim|send|submit|post|publish|share|bagikan|hapus|delete|remove|uninstall|reset|bayar|pay|purchase|beli|transfer|subscribe|berlangganan|login|logout|factory reset)\b",
            re.I,
        )
        if DESTRUCTIVE_WORDS.search(goal) or blocked.search(goal):
            return []
        packages = {str(x.get("package") or "") for x in apps if isinstance(x, dict) and x.get("package")}
        prompt = f"""
Kompilasi tujuan Android menjadi PREFIX aksi UI yang dapat dijalankan terus-menerus di Android Bridge tanpa memanggil model di antara langkah.
TUJUAN: {goal}
APLIKASI: {json.dumps(apps, ensure_ascii=False)[:9000]}
Output JSON saja: {{"confidence":0.0,"steps":[{{"type":"..."}}]}}

Tipe aksi: open_app, tap_text, set_text_best, ime_best, scroll_best, wait_text, wait_package, back, home, recents.
Maksimal 18 langkah.

Aturan selector:
- tap_text/wait_text boleh memakai target, targets, atau role.
- role yang tersedia: search, settings, battery, battery_usage, details, latest, menu, notes.
- Gunakan role daripada menebak label tombol jika role tersedia.
- tap_text boleh memakai max_scrolls 0..6. Gunakan max_scrolls untuk menu/list yang mungkin belum terlihat.
- wait_* timeout maksimal 5000 ms.
- set_text_best mengisi field editable terbaik yang sedang tersedia.
- ime_best menjalankan Search/Enter dan punya fallback tombol Search lokal.

Pola penting:
- "buka aplikasi lalu cari X": open_app -> tap_text role=search -> set_text_best X -> ime_best.
- Jika app membuka langsung dengan field pencarian aktif, boleh open_app -> set_text_best -> ime_best.
- Untuk Pengaturan, gunakan role battery/battery_usage dan max_scrolls jika diperlukan.
- Browsing/search READ-ONLY boleh dijalankan kontinu.
- Jangan menghasilkan Send/Kirim/Post/Share/Delete/Pay/Transfer/Login atau tindakan eksternal/destruktif.
- Jangan gunakan koordinat, shell, screenshot, atau kontrol privileged.
- Jika tujuan akhirnya membutuhkan penilaian atas konten yang belum terlihat (misalnya memilih hasil "paling relevan"), buat PREFIX deterministik terpanjang sampai tepat sebelum keputusan ambigu itu. Jangan buang prefix yang aman.
- Jika tidak ada minimal satu langkah yang cukup pasti, steps=[].
""".strip()
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": "Kamu compiler aksi UI Android internal. Output JSON valid saja."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=900,
                temperature=0.0,
                json_mode=True,
            )
            obj = _first_json_object(str(raw)) or {}
            if float(obj.get("confidence", 0.0) or 0.0) < 0.68:
                return []
            items = obj.get("steps")
            if not isinstance(items, list) or not items or len(items) > 18:
                return []
            allowed = {"open_app", "tap_text", "set_text_best", "ime_best", "scroll_best", "wait_text", "wait_package", "back", "home", "recents"}
            roles = {"search", "settings", "battery", "battery_usage", "details", "latest", "menu", "notes"}
            out: list[dict] = []
            for item in items:
                if not isinstance(item, dict):
                    return []
                typ = str(item.get("type") or "")
                if typ not in allowed:
                    return []
                step = {"type": typ}
                if typ in {"open_app", "wait_package"}:
                    pkg = str(item.get("package") or "")
                    if pkg not in packages:
                        return []
                    step["package"] = pkg
                if typ in {"tap_text", "wait_text"}:
                    target = sanitize(str(item.get("target") or "")).strip()[:100]
                    role = str(item.get("role") or "").strip().lower()
                    targets = []
                    if isinstance(item.get("targets"), list):
                        targets = [sanitize(str(x)).strip()[:80] for x in item["targets"][:5] if str(x).strip()]
                    targets = [x for x in targets if not blocked.search(x) and not DESTRUCTIVE_WORDS.search(x)]
                    if target and not blocked.search(target) and not DESTRUCTIVE_WORDS.search(target):
                        step["target"] = target
                    if targets:
                        step["targets"] = targets
                    if role in roles:
                        step["role"] = role
                    if not step.get("target") and not step.get("targets") and not step.get("role"):
                        return []
                    if typ == "tap_text":
                        try:
                            scrolls = int(item.get("max_scrolls", 0) or 0)
                        except Exception:
                            scrolls = 0
                        step["max_scrolls"] = max(0, min(scrolls, 6))
                if typ == "set_text_best":
                    value = str(item.get("text") or "")
                    if len(value) > 4000:
                        return []
                    step["text"] = value
                if typ == "scroll_best":
                    step["direction"] = "backward" if str(item.get("direction") or "forward").lower() == "backward" else "forward"
                if typ in {"wait_text", "wait_package"}:
                    try:
                        timeout = int(item.get("timeout_ms", 2200) or 2200)
                    except Exception:
                        timeout = 2200
                    step["timeout_ms"] = max(120, min(timeout, 5000))
                out.append(step)
            return out
        except Exception as exc:
            self.store.log_event("ui_sequence_compile_error", {"error": str(exc)[:240]})
            return []
'''
    a = replace_block(
        a,
        "    def _compile_ui_sequence(self, goal: str, contract: TaskContract, apps: list[dict]) -> list[dict]:\n",
        "    def _try_ui_sequence(",
        compiler,
        "semantic sequence compiler",
    )
    agent.write_text(a, encoding="utf-8")

    c = chat.read_text(encoding="utf-8")
    confirm = r'''    class ConfirmScreen(ModalScreen[bool]):
        CSS = """
        ConfirmScreen {
            align: center middle;
            background: rgba(0, 0, 0, 0.72);
        }
        #confirm-box {
            width: 88%;
            max-width: 62;
            height: auto;
            padding: 1 2;
            background: #080f0d;
            color: #e7eee9;
            border: solid #1f6e5a;
        }
        """
        BINDINGS = [
            Binding("left", "choose_allow", "", show=False, priority=True),
            Binding("right", "choose_cancel", "", show=False, priority=True),
            Binding("enter", "confirm", "", show=False, priority=True),
            Binding("escape", "cancel", "", show=False, priority=True),
        ]
        def __init__(self) -> None:
            super().__init__()
            self._allow_selected = True
        def _body(self) -> str:
            allow = "[bold #9efce7]› Izinkan[/]" if self._allow_selected else "[#3d6b5e]  Izinkan[/]"
            cancel = "[bold #e8b86d]› Batal[/]" if not self._allow_selected else "[#3d6b5e]  Batal[/]"
            return (
                "[bold #9efce7]Furina[/] [#5de4c7]By Wynn[/]  [#1f6e5a]·[/]  [bold]Agent[/]\n"
                "[#1f6e5a]────────────────────────────────[/]\n\n"
                "Izin menggunakan layar untuk menyelesaikan tugas ini.\n\n"
                + allow + "        " + cancel
                + "\n\n[#3d6b5e]← → pilih  ·  Enter konfirmasi  ·  Esc batal[/]"
            )
        def compose(self) -> ComposeResult:
            yield Static(self._body(), id="confirm-box", markup=True)
        def _refresh_choice(self) -> None:
            self.query_one("#confirm-box", Static).update(self._body())
        def action_choose_allow(self) -> None:
            self._allow_selected = True
            self._refresh_choice()
        def action_choose_cancel(self) -> None:
            self._allow_selected = False
            self._refresh_choice()
        def action_confirm(self) -> None:
            self.dismiss(bool(self._allow_selected))
        def action_cancel(self) -> None:
            self.dismiss(False)
'''
    c = replace_block(
        c,
        "    class ConfirmScreen(ModalScreen[bool]):\n",
        "    class ChatApp(App[None]):\n",
        confirm,
        "Furina agent confirmation",
    )
    chat.write_text(c, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = rep(v, 'VERSION = "1.0.0-rc20"', 'VERSION = "1.0.0-rc21"', "Core version")
    version.write_text(v, encoding="utf-8")

    for path in (agent, chat, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    checks = [
        (agent, 'roles = {"search", "settings", "battery"'),
        (agent, 'step["max_scrolls"]'),
        (agent, "PREFIX deterministik terpanjang"),
        (chat, "background: #080f0d"),
        (chat, "[bold #9efce7]Furina[/]"),
        (version, 'VERSION = "1.0.0-rc21"'),
    ]
    missing = [needle for path, needle in checks if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("Core RC21 incomplete: " + ", ".join(missing))
    print("Furina Core RC21 semantic reactive planner + themed approval: OK")


if __name__ == "__main__":
    main()
