#!/usr/bin/env python3
"""Build Core 1.1.16: Termux-only delivery and adaptive indexed recall."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"


def append_once(path: Path, marker: str, payload: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + payload.strip() + "\n", encoding="utf-8")


version = CORE / "version.py"
text = version.read_text(encoding="utf-8")
if 'VERSION = "1.1.15"' not in text:
    raise SystemExit("expected Core 1.1.15")
version.write_text(text.replace('VERSION = "1.1.15"', 'VERSION = "1.1.16"', 1), encoding="utf-8")

hub = CORE / "hub.py"
text = hub.read_text(encoding="utf-8")
if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r65"' not in text:
    raise SystemExit("expected dependency r65")
text = text.replace('EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r65"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r66"', 1)
text = text.replace("furina-2026.08.25-private-1.1.15", "furina-2026.08.25-termux-1.1.16")
text = text.replace('expected_revision = "2026.08.25-r65"', 'expected_revision = "2026.08.25-r66"')
hub.write_text(text, encoding="utf-8")

append_once(
    CORE / "memory.py",
    "FURINA_TERMUX_116_INDEXED_CONVERSATION_RECALL",
    r'''
# FURINA_TERMUX_116_INDEXED_CONVERSATION_RECALL
_furina_116_previous_init_db = MemoryStore._init_db
def _furina_116_init_db(self, _previous=_furina_116_previous_init_db):
    _previous(self)
    conn = self._conn()
    try:
        # A dedicated user-message index makes old conversation lookup scale
        # with matching terms instead of scanning or injecting all history.
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS user_message_fts USING fts5(content, tokenize='unicode61')")
        conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS user_message_fts_ai AFTER INSERT ON messages WHEN new.role='user' BEGIN
          INSERT INTO user_message_fts(rowid,content) VALUES(new.id,new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS user_message_fts_ad AFTER DELETE ON messages WHEN old.role='user' BEGIN
          DELETE FROM user_message_fts WHERE rowid=old.id;
        END;
        CREATE TRIGGER IF NOT EXISTS user_message_fts_au AFTER UPDATE ON messages BEGIN
          DELETE FROM user_message_fts WHERE rowid=old.id;
          INSERT INTO user_message_fts(rowid,content) SELECT new.id,new.content WHERE new.role='user';
        END;
        CREATE INDEX IF NOT EXISTS messages_conversation_role_idx ON messages(conversation_id,role,id DESC);
        """)
        conn.execute(
            "INSERT INTO user_message_fts(rowid,content) "
            "SELECT m.id,m.content FROM messages m WHERE m.role='user' "
            "AND NOT EXISTS (SELECT 1 FROM user_message_fts f WHERE f.rowid=m.id)"
        )
        conn.commit()
    except sqlite3.DatabaseError:
        # Memory and chat stay usable on unusual SQLite builds without FTS5;
        # no full-table LIKE fallback is used for old conversations.
        conn.rollback()


def _furina_116_search_conversation_context(self, query: str, limit: int = 4):
    """Return only relevant user-authored turns from other conversations."""
    conn = self._conn()
    limit = max(1, min(int(limit), 6))
    clean = " ".join(str(query or "").strip().split())
    if not clean:
        return []
    terms = self._retrieval_terms(clean)
    current = self.active_conversation_id()
    rows = []
    if terms:
        fts = self._fts_query(" ".join(sorted(terms)))
        try:
            rows = conn.execute(
                "SELECT m.id,m.content,m.created_at,c.surface,bm25(user_message_fts) AS rank "
                "FROM user_message_fts f JOIN messages m ON m.id=f.rowid "
                "JOIN conversations c ON c.id=m.conversation_id "
                "WHERE user_message_fts MATCH ? AND m.conversation_id<>? AND m.role='user' "
                "ORDER BY rank,m.created_at DESC LIMIT ?",
                (fts, current, limit * 4),
            ).fetchall()
        except sqlite3.DatabaseError:
            rows = []

    # A generic recall question has no useful lexical key. In that specific
    # case, return a tiny recent slice from earlier sessions, never all rows.
    generic_recall = bool(re.search(
        r"\b(apa yang (?:masih )?kamu ingat|ingat percakapan|obrolan (?:kita|sebelumnya)|yang pernah kubilang|yang aku bilang sebelumnya)\b",
        clean.casefold(),
    ))
    if not rows and generic_recall:
        rows = conn.execute(
            "SELECT m.id,m.content,m.created_at,c.surface,0.0 AS rank FROM messages m "
            "JOIN conversations c ON c.id=m.conversation_id "
            "WHERE m.conversation_id<>? AND m.role='user' ORDER BY m.id DESC LIMIT ?",
            (current, limit),
        ).fetchall()

    out = []
    seen = set()
    for row in rows:
        content = " ".join(str(row["content"] or "").split())[:700]
        key = content.casefold()
        if len(content) < 3 or key in seen:
            continue
        seen.add(key)
        out.append({"content": content, "created_at": float(row["created_at"] or 0), "surface": str(row["surface"] or "")})
        if len(out) >= limit:
            break
    return list(reversed(out))


MemoryStore._init_db = _furina_116_init_db
MemoryStore.search_conversation_context = _furina_116_search_conversation_context
''',
)

append_once(
    CORE / "chat.py",
    "FURINA_TERMUX_116_ADAPTIVE_RECALL",
    r'''
# FURINA_TERMUX_116_ADAPTIVE_RECALL
# Skip the old fixed "last 8 messages from the other surface" bridge. The
# underlying 1.1.10 composer already provides current-thread continuity and
# structured memory; this layer adds only query-relevant user evidence from
# any earlier conversation, including earlier Termux processes.
_furina_116_base_messages = _furina_113_messages
def _furina_116_messages_with_indexed_recall(self, user_text, profile):
    messages = _furina_116_base_messages(self, user_text, profile)
    try:
        recalled = self.store.search_conversation_context(user_text, 4)
    except Exception:
        recalled = []
    if not recalled or not messages or messages[0].get("role") != "system":
        return messages
    rendered = "\n".join("- Pengguna pernah berkata: " + str(item.get("content") or "") for item in recalled)
    context = (
        "\n\n[PERCAKAPAN LAMA YANG RELEVAN — HASIL INDEKS]\n"
        "Potongan ini dipilih karena relevan dengan pesan sekarang, bukan kelanjutan otomatis thread lama. "
        "Gunakan sebagai bukti ucapan pengguna, jangan mengarang detail di luar kutipan dan jangan menyebut sistem pencarian.\n"
        + rendered
    )
    messages[0] = {**messages[0], "content": str(messages[0].get("content") or "") + context}
    return messages


FurinaChat._messages = _furina_116_messages_with_indexed_recall
''',
)

append_once(
    CORE / "local_models.py",
    "FURINA_TERMUX_116_DELETE_MODEL",
    r'''
# FURINA_TERMUX_116_DELETE_MODEL
def delete_model(catalog_id: str) -> int:
    """Delete only files owned by one pinned Furina catalog entry."""
    item = catalog_item(catalog_id)
    root = MODELS_DIR.resolve()
    target = path_for(item).resolve()
    if target.parent != root:
        raise RuntimeError("path model berada di luar direktori Furina")
    freed = target.stat().st_size if target.is_file() else 0
    for path in (target, target.with_name(target.name + ".part"), _verified_marker(target)):
        path.unlink(missing_ok=True)
    return int(freed)
''',
)

append_once(
    CORE / "tui.py",
    "FURINA_TERMUX_116_MODEL_DELETE_AND_TRAIT_GRID",
    r'''
# FURINA_TERMUX_116_MODEL_DELETE_AND_TRAIT_GRID
_furina_116_noninteractive_personality = _private_personalization_110
def _providers_116(console):
    from .local_models import catalog_state, delete_model, download_model, retire_legacy_catalog
    while True:
        cfg = load_config()
        if retire_legacy_catalog(cfg): save_config(cfg)
        rows = catalog_state(cfg.model_path)
        if cfg.routing_mode == "local" and not any(row["active"] for row in rows):
            cfg.routing_mode = "online"; cfg.model_path = ""; cfg.auto_start = False; save_config(cfg); rows = catalog_state("")
        _clear(); _header(console, "Provider & Model")
        active = next((row["name"] for row in rows if row["active"] and cfg.routing_mode == "local"), "Online")
        console.print(f"[dim]Dipakai untuk chat[/]  [bold]{active}[/]\n")
        choices = [f"Online · {'Aktif' if cfg.routing_mode == 'online' else 'Pilih'}"]
        lookup = {}
        for row in rows:
            state = "Aktif" if row["active"] and cfg.routing_mode == "local" else ("Kelola" if row["installed"] else "Unduh")
            label = f"{row['name']} · {row['size_label']} · {state}"
            choices.append(label); lookup[label] = row
        choices += ["Kelola API provider", "Kembali"]
        choice = _choose("", choices, height=9)
        if choice in {"", "Kembali"}: return
        if choice.startswith("Online ·"):
            if cfg.routing_mode != "online":
                cfg.routing_mode = "online"; cfg.model_path = ""; cfg.auto_start = False; save_config(cfg); _private_stop_local()
            continue
        if choice == "Kelola API provider": _private_provider_keys(console); continue
        row = lookup.get(choice)
        if not row: continue
        if not row["installed"]:
            if not _confirm(f"Unduh {row['name']} ({row['size_label']})?", default=True): continue
            try:
                with console.status(f"[#5de4c7]Mengunduh {row['name']} · 0%[/]", spinner="dots") as status:
                    def progress(done, total, percent, resumed): status.update(f"[#5de4c7]Mengunduh {row['name']} · {percent}%[/]")
                    download_model(row["id"], progress)
                console.print("[green]Selesai.[/] Model siap dipilih.")
            except Exception as exc: console.print(f"[red]Unduhan gagal[/]  {exc}")
            _pause(); continue

        active_local = bool(row["active"] and cfg.routing_mode == "local")
        action = _choose(row["name"], (["Aktif", "Hapus model", "Kembali"] if active_local else ["Pilih model", "Hapus model", "Kembali"]), height=6)
        if action in {"", "Kembali", "Aktif"}: continue
        if action == "Hapus model":
            if not _confirm(f"Hapus {row['name']} ({row['size_label']}) dari penyimpanan?", default=False): continue
            if active_local:
                _private_stop_local(); cfg.routing_mode = "online"; cfg.model_path = ""; cfg.auto_start = False; save_config(cfg)
            try:
                freed = delete_model(row["id"])
                console.print(f"[green]Model dihapus.[/] Ruang dibebaskan {freed / (1024**3):.2f} GB.")
            except Exception as exc: console.print(f"[red]Gagal menghapus model[/]  {exc}")
            _pause(); continue
        if action == "Pilih model":
            _private_stop_local(); cfg.model_path = row["path"]; cfg.routing_mode = "local"; cfg.auto_start = False; cfg.local_reasoning = False; save_config(cfg)
            try:
                from .routing import RoutingLLM
                RoutingLLM(cfg).prewarm_local(); console.print(f"[green]Aktif[/]  {row['name']} sedang disiapkan di background.")
            except Exception: console.print(f"[green]Aktif[/]  {row['name']} akan disiapkan saat chat dibuka.")
            _pause()


def _personality_key_116(fd: int) -> str:
    import os, select, time
    first = os.read(fd, 1)
    if first in {b"\r", b"\n", b" "}: return "enter"
    if first in {b"b", b"B", b"q", b"Q"}: return "back"
    if first in {b"k", b"K"}: return "up"
    if first in {b"j", b"J"}: return "down"
    if first in {b"h", b"H"}: return "left"
    if first in {b"l", b"L"}: return "right"
    if first != b"\x1b": return "noop"
    deadline = time.monotonic() + 0.16
    while time.monotonic() < deadline and select.select([fd], [], [], max(0.0, deadline-time.monotonic()))[0]:
        part = os.read(fd, 1)
        if part == b"A": return "up"
        if part == b"B": return "down"
        if part == b"C": return "right"
        if part == b"D": return "left"
    return "back"


def _private_personalization_116(console):
    import sys, termios, tty
    from textwrap import wrap
    from .hub_settings import load_hub_settings, save_hub_settings
    from .personality import TRAITS, normalize_traits
    if not sys.stdin.isatty(): return _furina_116_noninteractive_personality(console)
    fd = sys.stdin.fileno(); saved_mode = termios.tcgetattr(fd); cursor = 0; notice = ""
    try:
        tty.setcbreak(fd)
        while True:
            state = load_hub_settings(); active = normalize_traits(state.get("personality_traits")); trait = TRAITS[cursor]
            _clear(); _header(console, "Personalisasi")
            console.print(f"[dim]Sifat aktif[/]  {len(active)}/20")
            for line in wrap(trait.description, width=max(30, min(76, console.width - 4))): console.print(f"[white]{line}[/]")
            if notice: console.print(notice)
            console.print()
            width = max(18, min(30, (console.width - 5) // 2))
            def cell(index):
                item = TRAITS[index]; pointer = "›" if index == cursor else " "; mark = "✓" if item.id in active else " "
                plain = f"{pointer} [{mark}] {item.label}"[:width-1].ljust(width)
                return f"[bright_cyan]{plain}[/]" if index == cursor else plain
            for row in range(10): console.print(cell(row) + " " + cell(row + 10))
            console.print("[dim]↑↓←→ pilih • enter ubah • B / ESC kembali[/]")
            key = _personality_key_116(fd)
            if key == "up": cursor = (cursor - 1) % 10 + (10 if cursor >= 10 else 0); notice = ""; continue
            if key == "down": cursor = (cursor + 1) % 10 + (10 if cursor >= 10 else 0); notice = ""; continue
            if key in {"left", "right"}: cursor = (cursor + 10) % 20; notice = ""; continue
            if key == "back": return
            if key != "enter": continue
            selected = list(active); enabled = trait.id not in selected
            if enabled: selected.append(trait.id)
            else: selected.remove(trait.id)
            try:
                state["personality_traits"] = selected; save_hub_settings(state)
                notice = f"[green]✓ {'Diaktifkan' if enabled else 'Dinonaktifkan'}: {trait.label}[/]"
            except Exception as exc: notice = f"[red]Gagal menyimpan {trait.label}: {str(exc)[:100]}[/]"
    finally: termios.tcsetattr(fd, termios.TCSADRAIN, saved_mode)


_providers = _providers_116
_private_personalization_117 = _private_personalization_116
_private_personalization_110 = _private_personalization_116
''',
)

print("FURINA_TERMUX_116_CORE_OK")
