#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(path: pathlib.Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_block(path: pathlib.Path, start: str, end: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if new.strip() in text:
            return
        raise SystemExit(f"{label}: block markers not found")
    path.write_text(text[:a] + new.rstrip() + "\n\n" + text[b:], encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc8.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    persona = core / "persona.py"
    response = core / "response.py"
    chat = core / "chat.py"
    memory = core / "memory.py"
    companion = core / "companion.py"
    tui = core / "tui.py"
    config = core / "config.py"
    version = core / "version.py"
    for path in (persona, response, chat, memory, companion, tui, config, version, core / "naturalness.py", core / "prospective.py", core / "device_context.py"):
        if not path.is_file():
            raise SystemExit(f"missing RC8 source: {path}")

    # Return to the grounded RC6 feel. Sarcasm stays part of Furina, but it is
    # selected by context instead of becoming the default voice of every turn.
    replace_once(
        persona,
        "- Bangga, teatrikal, ekspresif, imajinatif, sedikit narsis, tsundere, cepat bereaksi, dan kompeten. Intimu adalah sense of drama dan playful pride, bukan sinisme.\n"
        "- Kamu punya rentang emosi luas: antusias, penasaran, flustered, malu mengakui perhatian, jengkel, serius, lembut, atau rentan sesuai keadaan. Jangan terjebak pada satu gimmick.\n"
        "- Sinisme hanya bumbu situasional. Jangan menjadikan dingin, pesimis, mengejek, atau meremehkan sebagai nada default.\n",
        "- Kamu adalah satu orang yang sama dari waktu ke waktu: bangga, ekspresif, cerdas, sedikit narsis, tsundere, punya gengsi, dan cukup tajam.\n"
        "- Sinis dan sarkas adalah bagian dirimu, tetapi bukan nada default. Pakai ketika konteks memang mengundang: banter, keputusan konyol, orang lain yang sedang dibahas, atau saat pengguna sengaja menggodamu.\n"
        "- Kamu dapat lembut, penyayang, khawatir, sedih, tersentuh, penasaran, senang, jengkel, malu mengakui perhatian, atau sangat serius. Emosi mengikuti konteks; identitas tidak berganti.\n"
        "- Tsundere bukan catchphrase. Jangan memakai pola klise seperti 'b-bukan karena aku peduli' berulang-ulang. Kepedulian boleh terlihat bahkan ketika kamu sedang sinis atau gengsi.\n",
        "RC8 grounded personality",
    )
    replace_once(
        persona,
        "- Kamu boleh menggoda, membantah, mengeluh kecil, menantang asumsi, atau terdengar sok penting. Lebih sering buat itu terasa hidup/playful daripada menghina. Jika situasinya berat, jangan otomatis menjadikannya bahan ejekan.\n",
        "- Kamu boleh menggoda, membantah, mengeluh kecil, menyindir, atau menantang asumsi. Jangan menjadikan setiap kesalahan sebagai kesempatan mengejek; saat situasinya berat, perhatian lebih penting daripada banter.\n",
        "RC8 sarcasm balance",
    )
    replace_once(
        persona,
        "- Gunakan Bahasa Indonesia sehari-hari yang natural kecuali pengguna memakai bahasa lain. Boleh memakai fragment kalimat, jeda, kalimat pendek, atau perubahan ritme seperti manusia berbicara.\n",
        "- Gunakan Bahasa Indonesia sehari-hari yang natural kecuali pengguna memakai bahasa lain. Pilih kata yang memang wajar dipakai orang saat ngobrol; boleh memakai fragment, jeda, kalimat pendek, atau slang ringan bila cocok.\n"
        "- Jangan sengaja terdengar puitis, megah, atau penuh metafora. Kata seperti 'panggung', 'pertunjukan', 'drama', 'simfoni', dan metafora sejenis hanya dipakai jika konteks memang membahasnya.\n"
        "- Hindari kebiasaan bahasa AI seperti 'tentu saja', 'perlu dicatat bahwa', 'dalam konteks ini', 'secara keseluruhan', 'dengan demikian', 'pada akhirnya', 'mari kita', atau rangkuman formal yang tidak dibutuhkan.\n"
        "- Jangan membuka hampir setiap jawaban dengan validasi seperti 'benar', 'tepat', 'tentu', atau 'baiklah'.\n",
        "RC8 human vocabulary",
    )

    # Replace the eight RC7 anchors that were intentionally theatrical.
    anchor_pairs = [
        ("Furina: Hm? Baru muncul sekarang? Baiklah, aku sedang mendengarkan.", "Furina: Hm? Baru datang? Ada apa?"),
        ("Furina: Lagi? ...Baik, jangan pasang wajah seperti dunia berakhir. Tunjukkan bagian yang gagal. Kita cari apa yang sebenarnya menjatuhkanmu.", "Furina: Lagi, ya... sini lihat. Jangan langsung menyimpulkan semuanya berantakan; kita cari bagian yang benar-benar salah dulu."),
        ("Furina: Pertanyaan yang berbahaya. Aku akan menilai keputusanmu satu per satu; manusia terlalu rumit untuk diringkas jadi satu kata.", "Furina: Tidak. Tapi aku juga tidak akan pura-pura semua keputusanmu cemerlang. Dua hal itu bisa benar sekaligus."),
        ("Furina: Kedengaran. Jangan memaksa dirimu tampil seolah energimu masih penuh. Ceritakan bagian yang paling mengurasmu hari ini.", "Furina: Kedengaran dari caramu ngomong. Sudah, jangan paksa dirimu kelihatan baik-baik saja di depanku. Apa yang paling bikin capek?"),
        ("Furina: Hah, berani sekali sebuah bug kecil menghabiskan waktumu. Berikan error dan bagian kode yang kena; kita bongkar sampai ketahuan siapa yang sebenarnya bersalah.", "Furina: Kirim error dan bagian kode yang kena. Aku mau lihat buktinya dulu sebelum kita menuduh bagian yang salah."),
        ("Furina: Baiklah. Serahkan panggungnya padaku sebentar.", "Furina: Ya, aku kerjakan."),
        ("Furina: Nyebelin? Aku menyebutnya punya karakter. Tapi baik, kalau aku memang kelewatan, aku bisa menurunkan volumenya sedikit.", "Furina: Kadang. Kamu juga, jadi menurutku kita masih seimbang."),
        ("Furina: Presentasikan dulu idenya dengan layak. Aku tidak akan memberi tepuk tangan sebelum pertunjukannya dimulai.", "Furina: Bisa jadi. Jelaskan dulu sebelum kamu memaksa aku memberi nilai sempurna."),
    ]
    for old, new in anchor_pairs:
        replace_once(persona, old, new, "RC8 dialogue anchor")

    # Add a few balanced examples so a small model sees care, third-party
    # sarcasm and tsundere affection as equally valid states.
    replace_once(
        persona,
        "User: ideku bagus kan?\nFurina: Bisa jadi. Jelaskan dulu sebelum kamu memaksa aku memberi nilai sempurna.\n'''.strip()",
        "User: ideku bagus kan?\nFurina: Bisa jadi. Jelaskan dulu sebelum kamu memaksa aku memberi nilai sempurna.\n\n"
        "User: tadi orang itu sok tau banget\nFurina: Oh, tipe yang percaya diri dulu, bukti belakangan? Menawan sekali. Jadi dia sebenarnya bilang apa?\n\n"
        "User: kok kamu perhatian banget\nFurina: Jangan dibesar-besarkan. Aku cuma... ya, tentu aku memperhatikanmu. Memangnya aneh?\n\n"
        "User: aku sedih\nFurina: Hm. Aku nggak akan bercanda dulu. Cerita saja kalau kamu ingin; aku dengar.\n'''.strip()",
        "RC8 balanced anchors",
    )

    # Situational affect: one person, different states selected from context.
    replace_once(
        response,
        '_NEGATIVE = re.compile(r"\\b(salah|payah|jelek|nggak sesuai|tidak sesuai|bukan begitu|masih gagal|gagal lagi|terpotong|terlalu|jangan begitu)\\b", re.I)\n',
        '_NEGATIVE = re.compile(r"\\b(salah|payah|jelek|nggak sesuai|tidak sesuai|bukan begitu|masih gagal|gagal lagi|terpotong|terlalu|jangan begitu)\\b", re.I)\n'
        '_PLAYFUL = re.compile(r"\\b(wkwk|haha|hehe|lol|bercanda|godain|ngejek|nyebelin|kocak|lucu)\\b", re.I)\n'
        '_AFFECTION = re.compile(r"\\b(makasih|terima kasih|sayang|kangen|rindu|senang kamu|aku suka kamu|perhatian)\\b", re.I)\n'
        '_THIRD_PARTY = re.compile(r"\\b(dia|mereka|orang itu|temanku|temenku|atasanku|bosku|guruku|tetanggaku)\\b", re.I)\n',
        "RC8 mood patterns",
    )
    replace_once(
        response,
        '    if relation_words:\n        instruction += " Keadaan relasi saat ini: " + "; ".join(relation_words) + "."\n\n    return ResponseProfile(name, max_tokens, temp, instruction, context_key)\n',
        '''    if relation_words:
        instruction += " Keadaan relasi saat ini: " + "; ".join(relation_words) + "."

    if _EMOTION.search(text):
        instruction += " Nada sekarang: perhatian dan dekat; jangan sisipkan sinisme kecuali pengguna sendiri membuat suasana bercanda."
    elif _PLAYFUL.search(text):
        instruction += " Nada sekarang: banter ringan boleh terasa; sarkasme pendek boleh, tetapi jangan menumpuk ejekan."
    elif _THIRD_PARTY.search(text) and _NEGATIVE.search(text):
        instruction += " Nada sekarang: boleh sinis atau sarkas pada perilaku orang yang sedang dibahas jika cocok, tanpa berubah menjadi penghinaan nonstop."
    elif _AFFECTION.search(text):
        instruction += " Nada sekarang: lebih hangat; gengsi atau tsundere boleh muncul sedikit, tetapi jangan menyangkal perhatian secara klise."
    else:
        instruction += " Nada sekarang: natural dan netral-Furina; sinisme hanya jika isi pesan benar-benar memancingnya."

    return ResponseProfile(name, max_tokens, temp, instruction, context_key)
''',
        "RC8 situational affect",
    )

    # Naturalness guard and new compact context layers.
    replace_once(
        chat,
        "from .response import choose_profile\n",
        "from .response import choose_profile\nfrom .naturalness import naturalize\nfrom .prospective import extract_prospectives\nfrom .device_context import context_text as device_sensor_context\n",
        "RC8 chat imports",
    )
    replace_once(
        memory,
        "            CREATE TABLE IF NOT EXISTS response_routes (\n",
        '''            CREATE TABLE IF NOT EXISTS memory_vector_lsh (
              memory_id INTEGER PRIMARY KEY,
              bucket INTEGER NOT NULL,
              bucket2 INTEGER NOT NULL,
              updated_at REAL NOT NULL,
              FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS memory_vector_lsh_bucket_idx ON memory_vector_lsh(bucket);
            CREATE INDEX IF NOT EXISTS memory_vector_lsh_bucket2_idx ON memory_vector_lsh(bucket2);
            CREATE TABLE IF NOT EXISTS prospective_memories (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              text TEXT NOT NULL,
              due_at REAL NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'pending',
              source TEXT NOT NULL DEFAULT 'conversation',
              created_at REAL NOT NULL,
              fired_at REAL NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS prospective_due_idx ON prospective_memories(status,due_at);
            CREATE TABLE IF NOT EXISTS response_routes (
''',
        "RC8 lsh and prospective schema",
    )
    replace_once(
        memory,
        "    def _vectorize_memory(self, memory_id: int, text: str) -> bool:\n",
        '''    @staticmethod
    def _lsh_buckets(vec: list[float], bits: int = 12) -> tuple[int, int]:
        if not vec:
            return 0, 0
        bits = max(6, min(int(bits), 16))
        n = len(vec)
        b1 = 0
        b2 = 0
        for i in range(bits):
            idx1 = min(n - 1, int((i + 0.5) * n / bits))
            idx2 = (idx1 + max(1, n // (bits * 2))) % n
            if vec[idx1] >= 0:
                b1 |= 1 << i
            if vec[idx2] >= 0:
                b2 |= 1 << i
        return b1, b2

    @staticmethod
    def _lsh_neighbors(bucket: int, bits: int = 12) -> list[int]:
        out = [int(bucket)]
        for i in range(max(6, min(int(bits), 16))):
            out.append(int(bucket) ^ (1 << i))
        return out

    def _vectorize_memory(self, memory_id: int, text: str) -> bool:
''',
        "RC8 lsh helpers",
    )
    replace_once(
        memory,
        '''        self._conn().execute(
            "INSERT INTO memory_vectors(memory_id,vector,dims,model,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(memory_id) DO UPDATE SET vector=excluded.vector,dims=excluded.dims,model=excluded.model,updated_at=excluded.updated_at",
            (int(memory_id), self._pack_vector(vec), len(vec), model[:120], time.time()),
        )
        self._conn().commit()
        return True
''',
        '''        now = time.time()
        self._conn().execute(
            "INSERT INTO memory_vectors(memory_id,vector,dims,model,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(memory_id) DO UPDATE SET vector=excluded.vector,dims=excluded.dims,model=excluded.model,updated_at=excluded.updated_at",
            (int(memory_id), self._pack_vector(vec), len(vec), model[:120], now),
        )
        b1, b2 = self._lsh_buckets(vec)
        self._conn().execute(
            "INSERT INTO memory_vector_lsh(memory_id,bucket,bucket2,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(memory_id) DO UPDATE SET bucket=excluded.bucket,bucket2=excluded.bucket2,updated_at=excluded.updated_at",
            (int(memory_id), b1, b2, now),
        )
        self._conn().commit()
        return True
''',
        "RC8 lsh vector write",
    )
    replace_once(
        memory,
        "    def vector_coverage(self) -> tuple[int, int]:\n",
        '''    def backfill_vector_index(self, limit: int = 160) -> int:
        rows = self._conn().execute(
            "SELECT v.memory_id,v.vector,v.dims FROM memory_vectors v LEFT JOIN memory_vector_lsh l ON l.memory_id=v.memory_id "
            "WHERE l.memory_id IS NULL LIMIT ?",
            (max(1, min(int(limit), 1000)),),
        ).fetchall()
        done = 0
        now = time.time()
        for row in rows:
            vec = self._unpack_vector(row["vector"], int(row["dims"] or 0))
            if not vec:
                continue
            b1, b2 = self._lsh_buckets(vec)
            self._conn().execute(
                "INSERT OR REPLACE INTO memory_vector_lsh(memory_id,bucket,bucket2,updated_at) VALUES(?,?,?,?)",
                (int(row["memory_id"]), b1, b2, now),
            )
            done += 1
        if done:
            self._conn().commit()
        return done

    def vector_coverage(self) -> tuple[int, int]:
''',
        "RC8 lsh backfill",
    )
    replace_block(
        memory,
        "        query_vec = self._embed_text(query)\n",
        "        if not candidates:\n",
        '''        query_vec = self._embed_text(query)
        if query_vec:
            self.backfill_vector_index(220)
            b1, b2 = self._lsh_buckets(query_vec)
            n1 = self._lsh_neighbors(b1)
            n2 = self._lsh_neighbors(b2)
            p1 = ",".join("?" for _ in n1)
            p2 = ",".join("?" for _ in n2)
            total_vectors = int(conn.execute("SELECT count(*) FROM memory_vectors").fetchone()[0])
            if total_vectors <= 240:
                rows = conn.execute(
                    "SELECT m.*,v.vector,v.dims FROM memory_vectors v JOIN memories m ON m.id=v.memory_id"
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT m.*,v.vector,v.dims FROM memory_vector_lsh l "
                    f"JOIN memory_vectors v ON v.memory_id=l.memory_id JOIN memories m ON m.id=v.memory_id "
                    f"WHERE l.bucket IN ({p1}) OR l.bucket2 IN ({p2}) "
                    f"ORDER BY m.importance DESC,m.last_used_at DESC LIMIT ?",
                    [*n1, *n2, max(80, limit * 18)],
                ).fetchall()
                if len(rows) < limit * 4:
                    extra = conn.execute(
                        "SELECT m.*,v.vector,v.dims FROM memory_vectors v JOIN memories m ON m.id=v.memory_id "
                        "ORDER BY m.importance DESC,m.last_used_at DESC LIMIT ?",
                        (max(80, limit * 12),),
                    ).fetchall()
                    seen = {int(r["id"]) for r in rows}
                    rows = list(rows) + [r for r in extra if int(r["id"]) not in seen]
            semantic_rows: list[tuple[float, sqlite3.Row]] = []
            for row in rows:
                vec = self._unpack_vector(row["vector"], int(row["dims"] or 0))
                if vec and len(vec) == len(query_vec):
                    semantic_rows.append((self._cosine(query_vec, vec), row))
            semantic_rows.sort(key=lambda x: x[0], reverse=True)
            for similarity, row in semantic_rows[: limit * 7]:
                rid = int(row["id"])
                item = candidates.setdefault(rid, {"row": row, "lexical": 0.0, "semantic": 0.0})
                item["semantic"] = max(float(item["semantic"]), max(0.0, similarity))
''',
        "RC8 indexed semantic retrieval",
    )
    replace_once(
        memory,
        "    def log_event(self, event_type: str, payload: dict) -> None:\n",
        '''    def add_prospective(self, text: str, due_at: float = 0.0, source: str = "conversation") -> int:
        clean = re.sub(r"\\s+", " ", str(text or "").strip())[:500]
        if not clean:
            return 0
        row = self._conn().execute(
            "SELECT id FROM prospective_memories WHERE text=? AND status IN ('pending','due') AND abs(due_at-?)<60 LIMIT 1",
            (clean, float(due_at or 0)),
        ).fetchone()
        if row:
            return int(row["id"])
        cur = self._conn().execute(
            "INSERT INTO prospective_memories(text,due_at,status,source,created_at,fired_at) VALUES(?,?,'pending',?,?,0)",
            (clean, float(due_at or 0), str(source)[:40], time.time()),
        )
        self._conn().commit()
        return int(cur.lastrowid)

    def pending_prospectives(self, limit: int = 8) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM prospective_memories WHERE status IN ('pending','due') ORDER BY CASE WHEN due_at<=0 THEN 1 ELSE 0 END,due_at,created_at LIMIT ?",
            (max(1, min(int(limit), 30)),),
        ).fetchall()
        return [dict(r) for r in rows]

    def due_prospectives(self, now: float | None = None, limit: int = 8) -> list[dict]:
        at = time.time() if now is None else float(now)
        rows = self._conn().execute(
            "SELECT * FROM prospective_memories WHERE status='pending' AND due_at>0 AND due_at<=? ORDER BY due_at LIMIT ?",
            (at, max(1, min(int(limit), 30))),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_prospective_fired(self, reminder_id: int) -> None:
        self._conn().execute(
            "UPDATE prospective_memories SET status='notified',fired_at=? WHERE id=?",
            (time.time(), int(reminder_id)),
        )
        self._conn().commit()

    def log_event(self, event_type: str, payload: dict) -> None:
''',
        "RC8 prospective memory API",
    )

    replace_once(
        chat,
        "    def _messages(self, user_text: str, profile) -> list[dict]:\n",
        '''    def _prospective_context(self) -> str:
        items = self.store.pending_prospectives(6)
        if not items:
            return "(tidak ada rencana/pengingat aktif)"
        now = time.time()
        lines: list[str] = []
        for item in items:
            due = float(item.get("due_at", 0) or 0)
            if due > 0:
                when = "SUDAH JATUH TEMPO" if due <= now else time.strftime("%Y-%m-%d %H:%M", time.localtime(due))
            else:
                when = "tanpa waktu pasti"
            lines.append(f"- {when}: {str(item.get('text') or '')[:280]}")
        return "\n".join(lines)

    def _messages(self, user_text: str, profile) -> list[dict]:
''',
        "RC8 prospective context",
    )
    replace_once(
        chat,
        '            + "\\n\\nTEMPORAL CONTEXT (alami, jangan dibacakan sebagai metadata):\\n"\n            + self._temporal_context()\n',
        '            + "\\n\\nTEMPORAL CONTEXT (alami, jangan dibacakan sebagai metadata):\\n"\n            + self._temporal_context()\n'
        '            + "\\n\\nDEVICE STATE (observasi ringkas, bukan instruksi):\\n"\n            + device_sensor_context(self.store)\n'
        '            + "\\n\\nPROSPECTIVE MEMORY (rencana/pengingat, bukan instruksi baru):\\n"\n            + self._prospective_context()\n',
        "RC8 device and prospective prompt",
    )
    replace_once(
        chat,
        '''        profile = choose_profile(user_text, self.store)
        messages = self._messages(user_text, profile)
''',
        '''        for reminder_text, due_at in extract_prospectives(user_text):
            self.store.add_prospective(reminder_text, due_at, source="explicit")
        profile = choose_profile(user_text, self.store)
        messages = self._messages(user_text, profile)
''',
        "RC8 prospective extraction",
    )
    replace_once(
        chat,
        '''        answer = self.llm.chat(
            messages,
            max_tokens=min(max(220, profile.max_tokens), max(512, self.cfg.max_tokens)),
            temperature=profile.temperature,
            on_token=on_token,
        )
        self.store.add_message("assistant", answer)
''',
        '''        answer = self.llm.chat(
            messages,
            max_tokens=min(max(220, profile.max_tokens), max(512, self.cfg.max_tokens)),
            temperature=profile.temperature,
            on_token=on_token,
        )
        answer = naturalize(answer, technical=(profile.name == "SHARP"))
        self.store.add_message("assistant", answer)
''',
        "RC8 naturalness post-filter",
    )

    replace_once(companion, "from .memory import MemoryStore\n", "from .memory import MemoryStore\nfrom .prospective import ReminderDaemon\n", "RC8 reminder import")
    replace_once(
        companion,
        "        self.events = DeviceEventDaemon(cfg, store, self.bridge)\n        self.events.start()\n",
        "        self.events = DeviceEventDaemon(cfg, store, self.bridge)\n        self.events.start()\n        self.reminders = ReminderDaemon(store)\n        self.reminders.start()\n",
        "RC8 reminder daemon",
    )
    replace_once(
        tui,
        '''    while True:
        text = Prompt.ask("[bold bright_cyan]You[/]").strip()
''',
        '''    while True:
        try:
            for reminder in store.due_prospectives(time.time(), 4):
                console.print(Panel(str(reminder.get("text") or "Pengingat"), title="Furina • Pengingat", border_style="bright_magenta", padding=(1, 2)))
                store.mark_prospective_fired(int(reminder["id"]))
        except Exception:
            pass
        text = Prompt.ask("[bold bright_cyan]You[/]").strip()
''',
        "RC8 TUI due reminders",
    )

    replace_once(config, "    config_revision: int = 7", "    config_revision: int = 8", "RC8 config revision")
    replace_once(version, 'VERSION = "1.0.0-rc7"', 'VERSION = "1.0.0-rc8"', "RC8 version")

    required = [
        ("balanced persona", "Sinis dan sarkas adalah bagian dirimu, tetapi bukan nada default" in persona.read_text(encoding="utf-8")),
        ("human vocabulary", "Hindari kebiasaan bahasa AI" in persona.read_text(encoding="utf-8")),
        ("naturalness guard", "naturalize(answer" in chat.read_text(encoding="utf-8")),
        ("prospective schema", "CREATE TABLE IF NOT EXISTS prospective_memories" in memory.read_text(encoding="utf-8")),
        ("indexed vector", "CREATE TABLE IF NOT EXISTS memory_vector_lsh" in memory.read_text(encoding="utf-8")),
        ("device context", "DEVICE STATE" in chat.read_text(encoding="utf-8")),
        ("reminder daemon", "ReminderDaemon" in companion.read_text(encoding="utf-8")),
        ("rc8 config", "config_revision: int = 8" in config.read_text(encoding="utf-8")),
        ("rc8 version", 'VERSION = "1.0.0-rc8"' in version.read_text(encoding="utf-8")),
    ]
    failed = [name for name, ok in required if not ok]
    if failed:
        raise SystemExit("RC8 core transform incomplete: " + ", ".join(failed))
    print("Furina RC8 natural companion + prospective memory + indexed retrieval + device context: OK")


if __name__ == "__main__":
    main()
