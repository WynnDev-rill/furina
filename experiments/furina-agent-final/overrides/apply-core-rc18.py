#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC18 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def replace_block(text: str, start: str, end: str, new: str, label: str) -> str:
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if new.strip() in text:
            return text
        raise SystemExit(f"RC18 block marker mismatch {label}")
    return text[:a] + new.rstrip() + "\n\n" + text[b:]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc18.py <termux-root>")

    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    events = core / "events.py"
    chat = core / "chat.py"
    version = core / "version.py"
    for path in (events, chat, version):
        if not path.is_file():
            raise SystemExit(f"missing RC18 source: {path}")

    e = events.read_text(encoding="utf-8")
    sync_method = '''    def _sync_termux_session(self, session) -> None:
        if not isinstance(session, dict):
            return
        try:
            clean = {
                "source": str(session.get("source") or "")[:80],
                "authoritative": bool(session.get("authoritative", False)),
                "foreground_package": str(session.get("foreground_package") or "")[:160],
                "currently_away": bool(session.get("currently_away", False)),
                "active_left_at": float(session.get("active_left_at", 0) or 0),
                "last_left_at": float(session.get("last_left_at", 0) or 0),
                "last_returned_at": float(session.get("last_returned_at", 0) or 0),
                "last_absence_seconds": max(0.0, float(session.get("last_absence_seconds", 0) or 0)),
                "last_outside_package": str(session.get("last_outside_package") or "")[:160],
            }
            history = session.get("history")
            if isinstance(history, list):
                clean["history"] = [x for x in history[-8:] if isinstance(x, dict)]
            self.store.set_state("termux_session", clean)
            if clean["foreground_package"]:
                self.store.set_state("device_foreground_package", clean["foreground_package"])
        except Exception:
            return

'''
    if sync_method.strip() not in e:
        marker = "    def _seed_from_bridge(self) -> None:\n"
        if marker not in e:
            raise SystemExit("RC18 events seed marker missing")
        e = e.replace(marker, sync_method + marker, 1)

    seed_old = '''        try:
            screen = self.bridge.screen()
        except Exception:
            return
        for event in (screen.get("recent_events") or [])[-12:]:
'''
    seed_new = '''        try:
            screen = self.bridge.screen()
        except Exception:
            return
        self._sync_termux_session(screen.get("termux_session"))
        for event in (screen.get("recent_events") or [])[-12:]:
'''
    e = replace_once(e, seed_old, seed_new, "seed Bridge session")

    e = replace_once(
        e,
        "        self._recent.append(compact)\n",
        '''        session = event.get("termux_session")
        if isinstance(session, dict):
            self._sync_termux_session(session)
        self._recent.append(compact)
''',
        "event session sync",
    )

    package_start = '        package = compact["package"]\n'
    package_end = '        if compact["type"] == "notification" and compact["text"]:\n'
    package_new = '''        package = compact["package"]
        # Only a real Android window-state transition may redefine foreground.
        # Notification/text/click events are not evidence that the user changed apps.
        if package and compact["type"] == "window":
            self.store.set_state("device_foreground_package", package)
            usage = self.store.get_state("device_usage_counts", {})
            if not isinstance(usage, dict):
                usage = {}
            hour_bucket = time.localtime(compact["at"]).tm_hour // 4
            key = f"{package}|{hour_bucket}"
            usage[key] = min(100000, int(usage.get(key, 0) or 0) + 1)
            if len(usage) > 160:
                usage = dict(sorted(usage.items(), key=lambda kv: kv[1], reverse=True)[:120])
            self.store.set_state("device_usage_counts", usage)
'''
    e = replace_block(e, package_start, package_end, package_new, "foreground evidence")
    e = replace_once(
        e,
        '        package = str(last.get("package") or self.store.get_state("device_foreground_package", "") or "")\n',
        '        package = str(self.store.get_state("device_foreground_package", "") or last.get("package") or "")\n',
        "stable foreground context",
    )
    events.write_text(e, encoding="utf-8")

    ch = chat.read_text(encoding="utf-8")
    temporal = '''    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        total = max(0, int(round(float(seconds or 0))))
        hours, rest = divmod(total, 3600)
        minutes, secs = divmod(rest, 60)
        parts: list[str] = []
        if hours:
            parts.append(f"{hours} jam")
        if minutes:
            parts.append(f"{minutes} menit")
        if secs or not parts:
            parts.append(f"{secs} detik")
        return " ".join(parts)

    def _termux_absence_query(self, user_text: str) -> bool:
        low = " ".join(str(user_text or "").casefold().split())
        asks_amount = any(x in low for x in ("berapa lama", "berapa menit", "berapa jam", "berapa detik", "how long"))
        refers_away = any(x in low for x in ("tadi keluar", "keluar termux", "meninggalkan termux", "pergi dari termux", "away from termux"))
        return asks_amount and refers_away

    def _direct_termux_absence_answer(self, user_text: str) -> str | None:
        if not self._termux_absence_query(user_text):
            return None
        session = self.store.get_state("termux_session", {})
        if not isinstance(session, dict) or not session.get("authoritative"):
            return "Aku tidak punya timestamp Android yang cukup untuk memastikan berapa lama kamu keluar tadi, jadi aku tidak akan menebaknya."
        returned = float(session.get("last_returned_at", 0) or 0)
        duration = float(session.get("last_absence_seconds", 0) or 0)
        if returned <= 0:
            return "Aku belum punya satu sesi keluar-masuk Termux yang lengkap untuk dihitung dengan pasti."
        return f"Sekitar {self._format_elapsed(duration)}. Itu durasi keluar Termux terakhir yang tercatat oleh Android."

    def _temporal_context(self) -> str:
        now = time.time()
        lines = [time.strftime("waktu lokal: %Y-%m-%d %H:%M:%S %Z", time.localtime(now))]
        last_user = float(self.store.get_state("companion_last_user_at", 0) or 0)
        if last_user > 0:
            gap = max(0.0, now - last_user)
            lines.append(f"jeda sejak pesan pengguna sebelumnya: {self._format_elapsed(gap)}")

        session = self.store.get_state("termux_session", {})
        if isinstance(session, dict) and session.get("authoritative"):
            if bool(session.get("currently_away", False)):
                left = float(session.get("active_left_at", 0) or 0)
                if left > 0:
                    lines.append(f"status Termux: sedang di luar sejak {self._format_elapsed(now-left)} lalu")
            returned = float(session.get("last_returned_at", 0) or 0)
            duration = float(session.get("last_absence_seconds", 0) or 0)
            if returned > 0:
                lines.append(f"durasi keluar Termux TERAKHIR: {self._format_elapsed(duration)}")
                lines.append(f"kembali ke Termux: {self._format_elapsed(max(0.0, now-returned))} lalu")
            lines.append("sumber durasi Termux: Bridge Android; ini lebih otoritatif daripada jeda percakapan")
        else:
            lines.append("durasi keluar Termux: tidak tersedia secara pasti; JANGAN menebak dari jeda percakapan")
        return "\\n".join(lines)
'''
    ch = replace_block(
        ch,
        "    def _temporal_context(self) -> str:\n",
        "    @staticmethod\n    def _bounded_recent(",
        temporal,
        "authoritative temporal context",
    )

    answer_marker = "        answer = self.llm.chat(\n"
    direct_block = '''        direct_temporal = self._direct_termux_absence_answer(user_text)
        if direct_temporal is not None:
            self.store.add_message("assistant", direct_temporal)
            turn = self.store.increment_state("companion_turns", 1)
            self._schedule_background(prepared.model_text if prepared.chunked else user_text, direct_temporal, turn)
            return direct_temporal

'''
    if direct_block.strip() not in ch:
        if ch.count(answer_marker) != 1:
            raise SystemExit(f"RC18 direct temporal answer marker mismatch: {ch.count(answer_marker)}")
        ch = ch.replace(answer_marker, direct_block + answer_marker, 1)
    chat.write_text(ch, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = replace_once(v, 'VERSION = "1.0.0-rc17"', 'VERSION = "1.0.0-rc18"', "core version")
    version.write_text(v, encoding="utf-8")

    for path in (events, chat, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    checks = [
        (events, "def _sync_termux_session"),
        (events, 'compact["type"] == "window"'),
        (events, 'screen.get("termux_session")'),
        (chat, "durasi keluar Termux TERAKHIR"),
        (chat, "JANGAN menebak dari jeda percakapan"),
        (chat, "def _direct_termux_absence_answer"),
        (version, 'VERSION = "1.0.0-rc18"'),
    ]
    missing = [needle for path, needle in checks if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC18 temporal contract incomplete: " + ", ".join(missing))
    print("Furina Core RC18 authoritative Termux time + no-guess temporal answers: OK")


if __name__ == "__main__":
    main()
