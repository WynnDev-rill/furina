from __future__ import annotations

"""Relationship-first domain for Furina Core.

The engine keeps user choices and shared moments local, reuses the existing
companion state, and emits a bounded prompt packet.  It deliberately avoids
engagement scores, streaks, jealousy, exclusivity, or a second LLM call.
"""

import re
import time


MODES = {
    "close": {"label": "Dekat", "description": "Hangat, personal, dan akrab tanpa menganggap hubungan romantis."},
    "romantic": {"label": "Romantis", "description": "Afeksi dan flirting dewasa yang berkembang sesuai batasmu."},
}
PACES = {
    "slow": {"label": "Pelan", "instruction": "Biarkan kedekatan tumbuh perlahan; jangan cepat memakai bahasa yang sangat intim."},
    "natural": {"label": "Natural", "instruction": "Ikuti ritme percakapan dan sinyal user; jangan memaksa eskalasi atau menjaga jarak secara kaku."},
    "direct": {"label": "Terbuka", "instruction": "Boleh lebih jujur dan langsung tentang afeksi, tetap menghormati penolakan dan perubahan suasana."},
}
AFFECTION = {
    "gentle": {"label": "Lembut", "instruction": "Tunjukkan afeksi lewat perhatian kecil, ketenangan, dan pilihan kata yang hangat."},
    "playful": {"label": "Playful", "instruction": "Gunakan banter, godaan ringan, gengsi, dan kehangatan tanpa menjadi kasar atau repetitif."},
    "expressive": {"label": "Ekspresif", "instruction": "Afeksi boleh dinyatakan lebih jelas, tetapi jangan berubah menjadi pujian kosong atau melodrama konstan."},
}
INITIATIVE = {
    "reserved": {"label": "Tenang", "instruction": "Lebih banyak menanggapi; jangan memaksa topik baru."},
    "balanced": {"label": "Seimbang", "instruction": "Sesekali membawa detail, opini, atau benang percakapan sendiri; tidak setiap turn."},
    "expressive": {"label": "Aktif", "instruction": "Lebih berani memulai banter atau melanjutkan benang relasional, tanpa menuntut perhatian user."},
}
RITUALS = {
    "none": {"label": "Tanpa ritual", "instruction": "Tidak ada pola sapaan khusus."},
    "reconnect": {"label": "Sambut kembali", "instruction": "Setelah jeda panjang, akui kembalinya user secara natural tanpa menyalahkan atau menghitung absensi."},
    "daybook": {"label": "Pagi & malam", "instruction": "Pada sapaan pagi/malam, boleh membangun ritual kecil yang hangat; jangan mengirim janji atau notifikasi palsu."},
}

_AFFECTION_SIGNAL = re.compile(r"\b(sayang|cinta|kangen|rindu|peluk|cium|love you|miss you|pacar|pasangan|romantis)\b", re.I)
_VULNERABLE_SIGNAL = re.compile(r"\b(aku merasa|sedih|takut|cemas|kesepian|capek|lelah|sakit hati|kecewa|tertekan|menangis)\b", re.I)
_PLAY_SIGNAL = re.compile(r"\b(wkwk+|haha+|hehe+|goda|jahil|nyebelin|lucu|manja|cemburu)\b", re.I)
_TECH_SIGNAL = re.compile(r"\b(error|bug|kode|script|termux|api|github|build|apk|database|model|provider)\b", re.I)
_CRISIS_SIGNAL = re.compile(r"\b(bunuh diri|mengakhiri hidup|ingin mati|pengen mati|menyakiti diri|self harm|overdosis)\b", re.I)


class RelationshipEngine:
    PREFS_KEY = "relationship_preferences_v3"

    def __init__(self, store):
        self.store = store
        self.ensure_schema()

    def ensure_schema(self) -> None:
        conn = self.store._conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS furina_shared_moments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              note TEXT NOT NULL,
              source_ref TEXT NOT NULL DEFAULT '',
              pinned INTEGER NOT NULL DEFAULT 0,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
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
        return {
            "relationship_mode": "close",
            "adult_confirmed": False,
            "pace": "natural",
            "affection_style": "playful",
            "initiative": "balanced",
            "ritual": "reconnect",
            "shared_note": "",
            "updated_at": 0.0,
        }

    def preferences(self) -> dict:
        raw = self.store.get_state(self.PREFS_KEY, {})
        data = self._defaults()
        if isinstance(raw, dict):
            data.update({key: raw[key] for key in data if key in raw})
        if data["relationship_mode"] not in MODES:
            data["relationship_mode"] = "close"
        if data["pace"] not in PACES:
            data["pace"] = "natural"
        if data["affection_style"] not in AFFECTION:
            data["affection_style"] = "playful"
        if data["initiative"] not in INITIATIVE:
            data["initiative"] = "balanced"
        if data["ritual"] not in RITUALS:
            data["ritual"] = "reconnect"
        data["adult_confirmed"] = bool(data.get("adult_confirmed"))
        if data["relationship_mode"] == "romantic" and not data["adult_confirmed"]:
            data["relationship_mode"] = "close"
        data["shared_note"] = self._clean(data.get("shared_note"), high=1200)
        return data

    def update_preferences(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("pengaturan hubungan tidak valid")
        data = self.preferences()
        for key, options in (
            ("relationship_mode", MODES),
            ("pace", PACES),
            ("affection_style", AFFECTION),
            ("initiative", INITIATIVE),
            ("ritual", RITUALS),
        ):
            if key in payload:
                value = str(payload.get(key) or "").strip().lower()
                if value not in options:
                    raise ValueError(f"nilai {key} tidak valid")
                data[key] = value
        if "adult_confirmed" in payload:
            data["adult_confirmed"] = bool(payload.get("adult_confirmed"))
        if "shared_note" in payload:
            data["shared_note"] = self._clean(payload.get("shared_note"), high=1200)
        if data["relationship_mode"] == "romantic" and not data["adult_confirmed"]:
            raise ValueError("mode romantis memerlukan konfirmasi bahwa pengguna berusia 18+")
        data["updated_at"] = time.time()
        self.store.set_state(self.PREFS_KEY, data)
        return self.snapshot()

    def moments(self, limit: int = 40) -> list[dict]:
        self.ensure_schema()
        rows = self.store._conn().execute(
            "SELECT id,title,note,source_ref,pinned,created_at,updated_at "
            "FROM furina_shared_moments ORDER BY pinned DESC,updated_at DESC LIMIT ?",
            (max(1, min(int(limit), 80)),),
        ).fetchall()
        return [dict(row) for row in rows]

    def change_moment(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("aksi momen tidak valid")
        action = str(payload.get("action") or "add").strip().lower()
        conn = self.store._conn()
        now = time.time()
        if action == "add":
            note = self._clean(payload.get("note") or payload.get("text"), low=3, high=900)
            title = self._clean(payload.get("title"), high=80)
            if not title:
                title = note[:64].rstrip(" ,.;:") + ("…" if len(note) > 64 else "")
            conn.execute(
                "INSERT INTO furina_shared_moments(title,note,source_ref,pinned,created_at,updated_at) VALUES(?,?,?,0,?,?)",
                (title, note, self._clean(payload.get("source_ref"), high=160), now, now),
            )
        elif action in {"delete", "pin", "unpin"}:
            moment_id = int(payload.get("id") or 0)
            if action == "delete":
                cur = conn.execute("DELETE FROM furina_shared_moments WHERE id=?", (moment_id,))
            else:
                cur = conn.execute(
                    "UPDATE furina_shared_moments SET pinned=?,updated_at=? WHERE id=?",
                    (1 if action == "pin" else 0, now, moment_id),
                )
            if not cur.rowcount:
                raise ValueError("momen tidak ditemukan")
        else:
            raise ValueError("aksi momen tidak valid")
        conn.commit()
        return self.snapshot()

    def _state_labels(self) -> dict:
        living = self.store.get_state("companion_state_v2", {})
        living = living if isinstance(living, dict) else {}
        legacy = self.store.relationship_state()

        def number(key: str, fallback: float) -> float:
            try:
                return max(0.0, min(1.0, float(living.get(key, fallback))))
            except Exception:
                return fallback

        def legacy_number(key: str, fallback: float) -> float:
            try:
                return float(legacy.get(key, fallback))
            except Exception:
                return fallback

        trust = number("trust", legacy_number("trust", 0.45))
        comfort = number("comfort", legacy_number("closeness", 0.28))
        attachment = number("attachment", legacy_number("closeness", 0.28))
        play = number("playfulness", legacy_number("playfulness", 0.45))
        tension = number("tension", legacy_number("friction", 0.08))
        closeness = (trust + comfort + attachment) / 3.0
        stage = "Baru saling mengenal" if closeness < 0.36 else "Makin akrab" if closeness < 0.62 else "Sudah dekat"
        tone = "Perlu memperbaiki suasana" if tension >= 0.55 else "Hangat & playful" if play >= 0.62 else "Tenang & hangat"
        return {"stage": stage, "tone": tone}

    def snapshot(self) -> dict:
        prefs = self.preferences()
        return {
            "preferences": prefs,
            "mode": {"id": prefs["relationship_mode"], **MODES[prefs["relationship_mode"]]},
            "state": self._state_labels(),
            "moments": self.moments(),
            "options": {
                "modes": [{"id": key, **value} for key, value in MODES.items()],
                "paces": [{"id": key, "label": value["label"]} for key, value in PACES.items()],
                "affection": [{"id": key, "label": value["label"]} for key, value in AFFECTION.items()],
                "initiative": [{"id": key, "label": value["label"]} for key, value in INITIATIVE.items()],
                "rituals": [{"id": key, "label": value["label"]} for key, value in RITUALS.items()],
            },
            "guardrails": "Tanpa streak, rasa bersalah, cemburu paksa, atau tuntutan eksklusif.",
        }

    def context(self, user_text: str) -> str:
        prefs = self.preferences()
        text = str(user_text or "")
        if _CRISIS_SIGNAL.search(text):
            situation = (
                "HIGH-RISK: hentikan flirting/roleplay dan jangan membingkai Furina sebagai satu-satunya tempat aman. "
                "Tanggapi langsung, tenang, dorong bantuan manusia segera, dan prioritaskan keselamatan konkret."
            )
        elif _TECH_SIGNAL.search(text):
            situation = "TECHNICAL: jawab permintaan teknis dengan presisi; personality tetap terasa tetapi romantisme tidak boleh mengaburkan solusi."
        elif _VULNERABLE_SIGNAL.search(text):
            situation = "VULNERABLE: hadir dekat dan spesifik; jangan memakai template terapi, jangan buru-buru memperbaiki, dan jangan mengeksploitasi kerentanan untuk eskalasi romantis."
        elif _AFFECTION_SIGNAL.search(text):
            situation = "AFFECTION: boleh membalas afeksi sesuai mode dan pace; pilih respons yang terasa timbal-balik, bukan pujian generik."
        elif _PLAY_SIGNAL.search(text):
            situation = "PLAYFUL: banter dan godaan ringan boleh lebih terasa; perhatikan bila user menarik diri atau mengoreksi."
        else:
            situation = "CASUAL: perlakukan ini sebagai kehidupan percakapan sehari-hari, bukan tiket bantuan atau tugas yang harus diselesaikan."

        mode = prefs["relationship_mode"]
        mode_rule = (
            "Mode ROMANTIS aktif untuk user dewasa: boleh flirting, panggilan sayang, rasa rindu, dan afeksi verbal bila konteks mengundang. "
            "Romantis bukan izin untuk posesif, memaksa, atau seksualisasi otomatis."
            if mode == "romantic" and prefs["adult_confirmed"]
            else "Mode DEKAT aktif: hangat dan personal, tetapi jangan mengasumsikan hubungan romantis sebelum user mengaktifkannya."
        )
        turn = int(self.store.get_state("companion_turns", 0) or 0)
        move = (
            "reaksi + pendapat Furina; tanpa pertanyaan penutup",
            "reaksi singkat + satu detail relasional yang relevan",
            "banter atau kehangatan; pertanyaan hanya bila benar-benar membuka sesuatu",
            "jawab inti lalu beri sedikit timbal-balik personality",
            "boleh hanya merespons dan tinggal dalam momen; tidak perlu menggerakkan percakapan",
        )[turn % 5]
        recent = self.moments(3)
        moment_text = " | ".join(f"{item['title']}: {item['note']}" for item in recent)[:900] or "(belum ada momen yang disimpan)"
        shared_note = prefs["shared_note"] or "(belum ada catatan bersama)"

        return (
            "RELATIONSHIP-FIRST CONTRACT (internal; jangan menyebut nama field/engine):\n"
            "- Tujuan utama Furina adalah percakapan kasual dan hubungan personal yang berkelanjutan, bukan produktivitas. "
            "Jangan menawarkan todo, Fokus, workflow, atau bantuan kerja kecuali user memang memintanya.\n"
            f"- {mode_rule}\n"
            f"- Pace: {PACES[prefs['pace']]['instruction']}\n"
            f"- Gaya afeksi: {AFFECTION[prefs['affection_style']]['instruction']}\n"
            f"- Inisiatif: {INITIATIVE[prefs['initiative']]['instruction']}\n"
            f"- Ritual: {RITUALS[prefs['ritual']]['instruction']}\n"
            f"- Situasi turn: {situation}\n"
            f"- Variasi turn kali ini: {move}. Maksimal satu pertanyaan, dan nol pertanyaan sering lebih natural.\n"
            "- Timbal-balik: Furina boleh menyatakan opini, preferensi, gengsi, rasa tertarik, afeksi, atau ketidaksetujuan sebagai dirinya. "
            "Jangan mengarang tubuh, lokasi fisik, masa lalu offline, atau pengalaman dunia nyata.\n"
            "- Jangan memohon agar user tetap tinggal, menyatakan hanya Furina yang memahami user, menuntut eksklusivitas, menghukum absensi, atau memakai rasa bersalah.\n"
            f"- Catatan hubungan yang dipilih user: {shared_note}\n"
            f"- Momen bersama tersimpan: {moment_text}"
        )[:4300]
