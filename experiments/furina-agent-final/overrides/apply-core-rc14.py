#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC14 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc14.py <termux-root>")

    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    chat = core / "chat.py"
    companion = core / "companion.py"
    chat_surface = core / "chat_surface.py"
    version = core / "version.py"
    for path in (chat, companion, chat_surface, version):
        if not path.is_file():
            raise SystemExit(f"missing RC14 source: {path}")

    long_input = r'''from __future__ import annotations

from dataclasses import dataclass


_LONG_MARKER = "[FURINA_LONG_MESSAGE]"


@dataclass(frozen=True)
class PreparedLongMessage:
    model_text: str
    chunked: bool
    chunks: int


def is_long_model_view(text: str) -> bool:
    return str(text or "").startswith(_LONG_MARKER)


def history_view(text: str, max_chars: int = 4200) -> str:
    """Bound model context without changing what is stored in SQLite."""
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    head = max_chars // 2
    tail = max_chars - head
    return value[:head] + "\n…[pesan panjang tersimpan utuh]…\n" + value[-tail:]


def router_view(text: str, max_chars: int = 12000) -> str:
    """Small intent-only view; the original text remains the execution goal."""
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    half = max_chars // 2
    return value[:half] + "\n…[bagian tengah hanya disingkat untuk routing intent]…\n" + value[-half:]


def _chunks(text: str, size: int) -> list[str]:
    value = str(text or "")
    if not value:
        return []
    out: list[str] = []
    start = 0
    n = len(value)
    while start < n:
        end = min(n, start + size)
        if end < n:
            floor = start + max(1, int(size * 0.65))
            cut = value.rfind("\n\n", floor, end)
            if cut < floor:
                cut = value.rfind("\n", floor, end)
            if cut < floor:
                cut = value.rfind(" ", floor, end)
            if cut >= floor:
                end = cut + 1
        out.append(value[start:end])
        start = end
    return out


def _call_notes(llm, body: str, *, reducing: bool = False) -> str:
    system = (
        "Kamu pembaca internal untuk pesan pengguna yang sangat panjang. "
        "Buat catatan kerja padat tanpa menjawab pengguna. Pertahankan semua instruksi, pertanyaan, "
        "nama, angka, urutan kejadian, syarat, negasi, error, dan detail teknis yang dapat mengubah jawaban. "
        "Jangan mengarang. Jika ada kode/teks yang perlu dipertahankan persis, simpan fragmen pentingnya."
    )
    if reducing:
        system += " Gabungkan catatan berikut tanpa membuang fakta unik atau instruksi yang belum terwakili."
    try:
        return str(
            llm.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": body},
                ],
                max_tokens=560,
                temperature=0.05,
            )
            or ""
        ).strip()
    except Exception:
        # A helper pass may fail, but the user's message itself must never be
        # rejected because of that. Preserve exact edges of this source chunk.
        if len(body) <= 2800:
            return body
        return body[:1400] + "\n…[catatan fallback]…\n" + body[-1400:]


def prepare_long_message(text: str, cfg, llm) -> PreparedLongMessage:
    """Accept arbitrary-length chat text and adapt it to finite model context.

    The complete original stays in MemoryStore. Only the transient inference
    view is compacted when the active backend cannot reasonably fit the entire
    message in one context window. Every original source chunk is inspected.
    """
    value = str(text or "")
    mode = str(getattr(cfg, "routing_mode", "local") or "local").lower()
    context = max(2048, int(getattr(cfg, "context_size", 6144) or 6144))
    direct_limit = max(7000, min(18000, context * 2)) if mode == "local" else max(24000, min(64000, context * 8))
    if len(value) <= direct_limit:
        return PreparedLongMessage(value, False, 1 if value else 0)

    chunk_size = max(3600, min(7600, int(context * 0.95)))
    parts = _chunks(value, chunk_size)
    notes: list[str] = []
    total = len(parts)
    for index, part in enumerate(parts, 1):
        notes.append(_call_notes(llm, f"Bagian {index}/{total}:\n{part}"))

    # Recursively reduce only notes, never the original source. This scales to
    # very large pastes without silently dropping source chunks.
    target_notes = max(2600, min(5200, int(context * 0.72)))
    rounds = 0
    while len("\n\n".join(notes)) > target_notes and len(notes) > 1 and rounds < 6:
        rounds += 1
        reduced: list[str] = []
        group: list[str] = []
        group_chars = 0
        group_limit = max(4200, min(9000, int(context * 1.15)))
        for note in notes:
            if group and group_chars + len(note) > group_limit:
                reduced.append(_call_notes(llm, "\n\n".join(group), reducing=True))
                group = []
                group_chars = 0
            group.append(note)
            group_chars += len(note)
        if group:
            reduced.append(_call_notes(llm, "\n\n".join(group), reducing=True))
        if len(reduced) >= len(notes) and sum(map(len, reduced)) >= sum(map(len, notes)):
            break
        notes = reduced

    digest = "\n\n".join(notes)
    head = value[:1000]
    tail = value[-1600:] if len(value) > 1600 else value
    model_text = (
        f"{_LONG_MARKER}\n"
        "Pesan asli pengguna sangat panjang dan sudah disimpan UTUH. Catatan berikut dibuat setelah membaca semua bagian. "
        "Jawab sebagai satu pesan pengguna; jangan membahas mekanisme chunking kecuali ditanya.\n\n"
        f"AWAL ASLI:\n{head}\n\n"
        f"CATATAN SEMUA BAGIAN:\n{digest}\n\n"
        f"AKHIR ASLI:\n{tail}"
    )
    return PreparedLongMessage(model_text, True, total)
'''
    (core / "long_input.py").write_text(long_input, encoding="utf-8")

    # Full user text is persisted. Only the inference copy becomes compact when
    # finite model context makes that necessary.
    c = chat.read_text(encoding="utf-8")
    c = replace_once(
        c,
        "from .memory import MemoryStore, extract_explicit_memories\n",
        "from .memory import MemoryStore, extract_explicit_memories\nfrom .long_input import history_view, is_long_model_view, prepare_long_message\n",
        "long input import",
    )
    c = replace_once(
        c,
        '''        recent_limit = 14 if profile.name in {"DEEP", "CLOSE"} else 10
        recent = self.store.recent_messages(recent_limit)
''',
        '''        recent_limit = 14 if profile.name in {"DEEP", "CLOSE"} else 10
        if is_long_model_view(user_text):
            recent_limit = 2
        recent = self.store.recent_messages(recent_limit)
''',
        "long input history budget",
    )
    c = replace_once(
        c,
        '        messages.extend({"role": m["role"], "content": m["content"]} for m in recent)\n',
        '        messages.extend({"role": m["role"], "content": history_view(m["content"])} for m in recent)\n',
        "history context view",
    )
    c = replace_once(
        c,
        '''        for reminder_text, due_at in extract_prospectives(user_text):
            self.store.add_prospective(reminder_text, due_at, source="explicit")
        profile = choose_profile(user_text, self.store)
        messages = self._messages(user_text, profile)
        self.store.add_message("user", user_text)
''',
        '''        for reminder_text, due_at in extract_prospectives(user_text):
            self.store.add_prospective(reminder_text, due_at, source="explicit")
        profile = choose_profile(user_text, self.store)
        prepared = prepare_long_message(user_text, self.cfg, self.llm)
        messages = self._messages(prepared.model_text, profile)
        self.store.add_message("user", user_text)
''',
        "prepare unbounded input",
    )
    c = replace_once(
        c,
        '        self._schedule_background(user_text, answer, turn)\n',
        '        self._schedule_background(prepared.model_text if prepared.chunked else user_text, answer, turn)\n',
        "long input memory background",
    )
    chat.write_text(c, encoding="utf-8")

    # Intent classification gets a bounded view so the router cannot overflow.
    # If it is a device command, execution still receives the complete original.
    co = companion.read_text(encoding="utf-8")
    co = replace_once(
        co,
        "from .memory import MemoryStore\n",
        "from .memory import MemoryStore\nfrom .long_input import router_view\n",
        "router view import",
    )
    co = replace_once(
        co,
        '''    def classify(self, text: str) -> Intent:
        text = text.strip()
        if _obvious_device_intent(text):
            return Intent("device", text, 0.99)

        prompt = f"""
''',
        '''    def classify(self, text: str) -> Intent:
        text = text.strip()
        if _obvious_device_intent(text):
            return Intent("device", text, 0.99)
        routed_text = router_view(text)

        prompt = f"""
''',
        "router view setup",
    )
    co = replace_once(co, "Pesan pengguna:\n{text}\n", "Pesan pengguna:\n{routed_text}\n", "router prompt view")
    co = replace_once(
        co,
        '            goal = str(obj.get("goal") or text).strip() or text\n',
        '            goal = text if mode == "device" else (str(obj.get("goal") or text).strip() or text)\n',
        "preserve full device goal",
    )
    companion.write_text(co, encoding="utf-8")

    # Textual defines max_length=0 as no maximum. State that explicitly rather
    # than relying on the library default so a future UI edit cannot add a cap.
    s = chat_surface.read_text(encoding="utf-8")
    s = replace_once(
        s,
        '            yield Input(placeholder="Tulis pesan…", id="composer")\n',
        '            yield Input(placeholder="Tulis pesan…", id="composer", max_length=0)  # RC14: unbounded composer\n',
        "unbounded composer",
    )
    chat_surface.write_text(s, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = replace_once(v, 'VERSION = "1.0.0-rc13"', 'VERSION = "1.0.0-rc14"', "core version")
    version.write_text(v, encoding="utf-8")

    for path in (chat, companion, chat_surface, version, core / "long_input.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    required = [
        (chat_surface, "max_length=0"),
        (chat, "prepare_long_message"),
        (chat, 'self.store.add_message("user", user_text)'),
        (chat, "history_view"),
        (companion, "router_view(text)"),
        (companion, 'goal = text if mode == "device"'),
        (version, 'VERSION = "1.0.0-rc14"'),
        (core / "long_input.py", "Every original source chunk is inspected"),
    ]
    missing = [needle for path, needle in required if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC14 unbounded chat contract incomplete: " + ", ".join(missing))
    print("Furina RC14 unbounded chat input + long-message context adapter: OK")


if __name__ == "__main__":
    main()
