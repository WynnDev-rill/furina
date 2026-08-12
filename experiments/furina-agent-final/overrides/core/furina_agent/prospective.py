from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
import threading
import time


_REMINDER = re.compile(r"\b(ingatkan|remind|jangan lupa(?:kan)?|ingatkan aku)\b", re.I)
_IN = re.compile(r"\bdalam\s+(\d{1,4})\s*(menit|minute|minutes|jam|hour|hours|hari|day|days)\b", re.I)
_CLOCK = re.compile(r"\b(?:jam|pukul)\s*(\d{1,2})(?:[.:](\d{2}))?\b", re.I)
_DATE = re.compile(r"\b(?:tanggal\s*)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
_DAYPART = {"pagi": 8, "siang": 13, "sore": 16, "malam": 20}


def _next_clock(now: dt.datetime, hour: int, minute: int, *, tomorrow: bool = False) -> dt.datetime:
    hour = max(0, min(hour, 23))
    minute = max(0, min(minute, 59))
    base = now + dt.timedelta(days=1 if tomorrow else 0)
    target = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if not tomorrow and target <= now:
        target += dt.timedelta(days=1)
    return target


def extract_prospectives(text: str, now: float | None = None) -> list[tuple[str, float]]:
    raw = " ".join(str(text or "").split())
    if not raw or not _REMINDER.search(raw):
        return []
    current = dt.datetime.fromtimestamp(now or time.time())
    low = raw.lower()
    due: dt.datetime | None = None

    relative = _IN.search(low)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2).lower()
        if unit.startswith(("menit", "minute")):
            seconds = amount * 60
        elif unit.startswith(("jam", "hour")):
            seconds = amount * 3600
        else:
            seconds = amount * 86400
        due = current + dt.timedelta(seconds=seconds)
    else:
        date_match = _DATE.search(low)
        clock_match = _CLOCK.search(low)
        tomorrow = "besok" in low
        hour = int(clock_match.group(1)) if clock_match else None
        minute = int(clock_match.group(2) or 0) if clock_match else 0
        if hour is None:
            for name, day_hour in _DAYPART.items():
                if re.search(rf"\b{name}\b", low):
                    hour = day_hour
                    minute = 0
                    break
        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            year_raw = date_match.group(3)
            year = int(year_raw) if year_raw else current.year
            if year < 100:
                year += 2000
            try:
                due = current.replace(
                    year=year,
                    month=month,
                    day=day,
                    hour=hour if hour is not None else 9,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )
                if due <= current and not year_raw:
                    due = due.replace(year=year + 1)
            except ValueError:
                due = None
        elif tomorrow or hour is not None:
            due = _next_clock(current, hour if hour is not None else 9, minute, tomorrow=tomorrow)

    # due_at=0 preserves a future intention whose exact clock time is unknown.
    return [(raw[:500], due.timestamp() if due else 0.0)]


class ReminderDaemon:
    """Low-power reminder notifier.

    If Termux:API's notification command is available, due reminders become an
    Android notification. Otherwise they remain pending and the TUI surfaces
    them on the next interaction instead of silently discarding them.
    """

    def __init__(self, store):
        self.store = store
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="furina-reminders", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @staticmethod
    def _notify(item: dict) -> bool:
        command = shutil.which("termux-notification")
        if not command:
            return False
        try:
            result = subprocess.run(
                [command, "--title", "Furina", "--content", str(item.get("text") or "Pengingat")[:500]],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _loop(self) -> None:
        while not self._stop.wait(20):
            try:
                for item in self.store.due_prospectives(time.time(), 4):
                    if self._notify(item):
                        self.store.mark_prospective_fired(int(item["id"]))
            except Exception:
                continue
