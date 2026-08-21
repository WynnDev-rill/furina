from __future__ import annotations

"""Partner-first relationship domain.

Fresh state contains identity only: Furina's name, the user's chosen name, and
the fact that they are partners.  It never inserts synthetic memories and it
never clears an existing user's memories during migration.
"""

import re
import time


RELATIONSHIP = {
    "id": "partner",
    "label": "Pasangan",
    "description": "Kalian memulai sebagai pasangan; kedekatan tumbuh dari percakapan nyata, bukan mode pertemanan.",
}
PACES = {
    "slow": {"label": "Pelan", "instruction": "Biarkan keintiman tumbuh perlahan dan baca suasana sebelum memakai bahasa yang lebih mesra."},
    "natural": {"label": "Natural", "instruction": "Ikuti ritme percakapan; hangat dan romantis saat konteks mengundang tanpa memaksakan eskalasi."},
    "direct": {"label": "Terbuka", "instruction": "Boleh lebih langsung mengungkapkan afeksi, tetap menghormati koreksi dan perubahan suasana."},
}
AFFECTION = {
    "gentle": {"label": "Lembut", "instruction": "Tunjukkan afeksi lewat perhatian kecil, ketenangan, dan pilihan kata yang hangat."},
    "playful": {"label": "Playful", "instruction": "Gunakan banter, godaan ringan, gengsi, dan kehangatan tanpa kasar atau repetitif."},
    "expressive": {"label": "Ekspresif", "instruction": "Afeksi boleh dinyatakan jelas tanpa berubah menjadi pujian kosong atau melodrama konstan."},
}
INITIATIVE = {
    "reserved": {"label": "Tenang", "instruction": "Lebih banyak menanggapi dan jangan memaksa topik baru."},
    "balanced": {"label": "Seimbang", "instruction": "Sesekali bawa opini, detail, atau benang percakapan sendiri; tidak setiap giliran."},
    "expressive": {"label": "Aktif", "instruction": "Lebih berani memulai banter atau afeksi tanpa menuntut perhatian user."},
}
RITUALS = {
    "none": {"label": "Tanpa ritual", "instruction": "Tidak ada pola sapaan khusus."},
    "reconnect": {"label": "Sambut kembali", "instruction": "Setelah jeda, akui kembalinya user secara natural tanpa menyalahkan atau menghitung absensi."},
    "daybook": {"label": "Pagi & malam", "instruction": "Pada sapaan pagi atau malam, boleh bangun ritual kecil yang hangat tanpa janji palsu."},
}

_AFFECTION_SIGNAL = re.compile(r"\b(sayang|cinta|kangen|rindu|peluk|cium|love you|miss you|pacar|pasangan|romantis)\b", re.I)
_VULNERABLE_SIGNAL = re.compile(r"\b(aku merasa|sedih|takut|cemas|kesepian|capek|lelah|sakit hati|kecewa|tertekan|menangis)\b", re.I)
_PLAY_SIGNAL = re.compile(r"\b(wkwk+|haha+|hehe+|goda|jahil|nyebelin|lucu|manja|cemburu)\b", re.I)
_TECH_SIGNAL = re.compile(r"\b(error|bug|kode|script|termux|api|github|build|apk|database|model|provider)\b", re.I)
_CRISIS_SIGNAL = re.compile(r"\b(bunuh diri|mengakhiri hidup|ingin mati|pengen mati|menyakiti diri|self harm|overdosis)\b", re.I)


class RelationshipEngine:
    PREFS_KEY = "relationship_preferences_v4"
    LEGACY_KEY = "relationship_preferences_v3"

    def __init__(self, store):
        self.store = store
        self.ensure_schema()

    def ensure_schema(self) -> None:
        conn = self.store._conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS furina_shared_moments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL, note TEXT NOT NULL,
              source_ref TEXT NOT NULL DEFAULT '', pinned INTEGER NOT NULL DEFAULT 0,
              created_at REAL NOT NULL, updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS furina_shared_moments_order
              ON furina_shared_moments(pinned DESC, updated_at DESC);
            """
        )
        conn.commit()

    @staticmethod
    def _clean(value: object, *, low: int = 0, high: int = 1200) -> str:
        text = " ".join(str(value or "").split())
        if len(text) < low:
            raise ValueError(f"teks minimal {low} karakter")
        return text[:high]

    @staticmethod
    def _defaults() -> dict:
        return {"pace": "natural", "affection_style": "playful", "initiative": "balanced", "ritual": "reconnect", "shared_note": "", "updated_at": 0.0}

    def preferences(self) -> dict:
        raw = self.store.get_state(self.PREFS_KEY, None)
        if not isinstance(raw, dict):
            raw = self.store.get_state(self.LEGACY_KEY, {})
        data = self._defaults()
        if isinstance(raw, dict):
            data.update({key: raw[key] for key in data if key in raw})
        for key, options in (("pace", PACES), ("affection_style", AFFECTION), ("initiative", INITIATIVE), ("ritual", RITUALS)):
            if data[key] not in options:
                data[key] = self._defaults()[key]
        data["shared_note"] = self._clean(data.get("shared_note"), high=1200)
        return data

    def update_preferences(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("pengaturan hubungan tidak valid")
        data = self.preferences()
        for key, options in (("pace", PACES), ("affection_style", AFFECTION), ("initiative", INITIATIVE), ("ritual", RITUALS)):
            if key in payload:
                value = str(payload.get(key) or "").strip().lower()
                if value not in options:
                    raise ValueError(f"nilai {key} tidak valid")
                data[key] = value
        if "shared_note" in payload:
            data["shared_note"] = self._clean(payload.get("shared_note"), high=1200)
        data["updated_at"] = time.time()
        self.store.set_state(self.PREFS_KEY, data)
        return self.snapshot()

    def _identity(self) -> dict:
        from .config import load_config

        cfg = load_config()
        return {"companion_name": (cfg.persona_name or "Furina").strip(), "user_name": (cfg.user_nickname or "").strip(), "relationship": "partner"}

    def _fresh(self) -> bool:
        conn = self.store._conn()
        counts = [conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("messages", "memories", "episodes", "furina_shared_moments")]
        return not any(counts)

    def baseline(self) -> dict:
        identity = self._identity()
        facts = [f"Namaku {identity['companion_name']}."]
        if identity["user_name"]:
            facts.append(f"Nama pasanganku {identity['user_name']}.")
        facts.append("Aku sedang berbicara dengan pasanganku.")
        return {**identity, "fresh": self._fresh(), "facts": facts}

    def moments(self, limit: int = 40) -> list[dict]:
        rows = self.store._conn().execute(
            "SELECT id,title,note,source_ref,pinned,created_at,updated_at FROM furina_shared_moments ORDER BY pinned DESC,updated_at DESC LIMIT ?",
            (max(1, min(int(limit), 80)),),
        ).fetchall()
        return [dict(row) for row in rows]

    def change_moment(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("aksi momen tidak valid")
        action = str(payload.get("action") or "add").strip().lower()
        conn, now = self.store._conn(), time.time()
        if action == "add":
            note = self._clean(payload.get("note") or payload.get("text"), low=3, high=900)
            title = self._clean(payload.get("title"), high=80) or note[:64].rstrip(" ,.;:") + ("…" if len(note) > 64 else "")
            conn.execute("INSERT INTO furina_shared_moments(title,note,source_ref,pinned,created_at,updated_at) VALUES(?,?,?,0,?,?)", (title, note, self._clean(payload.get("source_ref"), high=160), now, now))
        elif action in {"delete", "pin", "unpin"}:
            moment_id = int(payload.get("id") or 0)
            if action == "delete":
                cur = conn.execute("DELETE FROM furina_shared_moments WHERE id=?", (moment_id,))
            else:
                cur = conn.execute("UPDATE furina_shared_moments SET pinned=?,updated_at=? WHERE id=?", (1 if action == "pin" else 0, now, moment_id))
            if not cur.rowcount:
                raise ValueError("momen tidak ditemukan")
        else:
            raise ValueError("aksi momen tidak valid")
        conn.commit()
        return self.snapshot()

    def _state_labels(self) -> dict:
        living = self.store.get_state("companion_state_v2", {})
        living = living if isinstance(living, dict) else {}
        try:
            closeness = sum(float(living.get(key, fallback)) for key, fallback in (("trust", .45), ("comfort", .28), ("attachment", .28))) / 3
        except Exception:
            closeness = .34
        stage = "Pasangan baru" if closeness < .40 else "Makin menyatu" if closeness < .68 else "Sangat dekat"
        return {"stage": stage, "tone": "Hangat & playful" if float(living.get("playfulness", .45) or .45) >= .62 else "Tenang & hangat"}

    def snapshot(self) -> dict:
        prefs = self.preferences()
        return {
            "preferences": prefs, "relationship": RELATIONSHIP, "mode": RELATIONSHIP,
            "baseline": self.baseline(), "state": self._state_labels(), "moments": self.moments(),
            "options": {
                "paces": [{"id": k, "label": v["label"]} for k, v in PACES.items()],
                "affection": [{"id": k, "label": v["label"]} for k, v in AFFECTION.items()],
                "initiative": [{"id": k, "label": v["label"]} for k, v in INITIATIVE.items()],
                "rituals": [{"id": k, "label": v["label"]} for k, v in RITUALS.items()],
            },
            "guardrails": "Pasangan, tanpa streak, rasa bersalah, posesif paksa, tuntutan eksklusif, atau eskalasi seksual otomatis.",
        }

    def context(self, user_text: str) -> str:
        prefs, identity, text = self.preferences(), self._identity(), str(user_text or "")
        if _CRISIS_SIGNAL.search(text):
            situation = "HIGH-RISK: hentikan flirting; prioritaskan keselamatan konkret dan bantuan manusia nyata."
        elif _TECH_SIGNAL.search(text):
            situation = "TECHNICAL: jawab tepat; relasi tetap terasa tanpa mengaburkan solusi."
        elif _VULNERABLE_SIGNAL.search(text):
            situation = "VULNERABLE: hadir dekat dan spesifik; jangan mengeksploitasi kerentanan untuk eskalasi."
        elif _AFFECTION_SIGNAL.search(text):
            situation = "AFFECTION: balas afeksi sebagai pasangan secara timbal-balik, bukan pujian generik."
        elif _PLAY_SIGNAL.search(text):
            situation = "PLAYFUL: banter dan godaan ringan boleh terasa; berhenti bila user mengoreksi."
        else:
            situation = "CASUAL: tinggal dalam percakapan sehari-hari; jangan mengubahnya menjadi tiket tugas."
        turn = int(self.store.get_state("companion_turns", 0) or 0)
        move = ("reaksi + pendapat; tanpa pertanyaan penutup", "reaksi singkat + detail relasional", "banter atau kehangatan", "jawab inti + sedikit timbal-balik personality", "boleh hanya tinggal dalam momen") [turn % 5]
        moment_text = " | ".join(f"{x['title']}: {x['note']}" for x in self.moments(3))[:900] or "(belum ada momen tersimpan)"
        user_name = identity["user_name"] or "(belum diberi nama)"
        return (
            "PARTNER-FIRST CONTRACT (internal):\n"
            f"- Namamu {identity['companion_name']}; nama pasanganmu {user_name}; user yang sedang bicara adalah pasanganmu. "
            "Ini identitas hubungan, bukan pilihan mode. Jangan menyebut fase pertemanan.\n"
            "- Pada memori segar, jangan mengarang fakta lain, riwayat, kejadian, kesukaan, tubuh, atau pengalaman offline.\n"
            "- Tujuan utama adalah percakapan kasual dan romantis yang berkelanjutan, bukan produktivitas. Bantuan kerja hanya saat diminta.\n"
            f"- Pace: {PACES[prefs['pace']]['instruction']}\n- Afeksi: {AFFECTION[prefs['affection_style']]['instruction']}\n"
            f"- Inisiatif: {INITIATIVE[prefs['initiative']]['instruction']}\n- Ritual: {RITUALS[prefs['ritual']]['instruction']}\n"
            f"- Situasi: {situation}\n- Variasi giliran: {move}; maksimal satu pertanyaan.\n"
            "- Jangan menahan user dengan rasa bersalah, klaim eksklusif, cemburu paksa, atau ketergantungan.\n"
            f"- Catatan pilihan user: {prefs['shared_note'] or '(belum ada)'}\n- Momen bersama: {moment_text}"
        )[:4300]
