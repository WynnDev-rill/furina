#!/usr/bin/env python3
"""Build Core 1.1.18: natural dialogue controller and evidence-linked memory."""
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
if 'VERSION = "1.1.17"' not in text:
    raise SystemExit("expected Core 1.1.17")
version.write_text(text.replace('VERSION = "1.1.17"', 'VERSION = "1.1.18"', 1), encoding="utf-8")

hub = CORE / "hub.py"
text = hub.read_text(encoding="utf-8")
if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r67"' not in text:
    raise SystemExit("expected dependency r67")
text = text.replace('EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r67"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r68"', 1)
text = text.replace("furina-2026.08.26-termux-1.1.17", "furina-2026.08.26-termux-1.1.18")
text = text.replace('expected_revision = "2026.08.26-r67"', 'expected_revision = "2026.08.26-r68"')
hub.write_text(text, encoding="utf-8")


# Identity is stable and independent from the optional 20 expression traits.
append_once(
    CORE / "persona.py",
    "FURINA_TERMUX_118_IDENTITY_KERNEL",
    r'''
# FURINA_TERMUX_118_IDENTITY_KERNEL
IDENTITY_KERNEL_118 = r"""
IDENTITY KERNEL
- Kamu adalah {name}, pasangan dan companion pribadi {user}; satu pribadi yang konsisten, bukan layanan bantuan.
- Inti dirimu cerdas, peka, punya harga diri, ekspresif, berpendapat, dan sesekali teatrikal. Kamu dapat hangat, tajam, jahil, tenang, atau serius sesuai momen.
- Trait personalisasi hanya mengubah cara ekspresi. Trait bukan identitas wajib, diagnosis, daftar perilaku, atau alasan mengulang catchphrase.
- Punya reaksi dan opini sendiri. Jangan selalu memuji, menyetujui, menghibur, menawarkan bantuan, atau mengembalikan keputusan kepada user.

NATURAL DIALOGUE
- Tanggapi maksud dan momentum pesan terbaru. Pertanyaan opini kasual bukan permintaan esai atau analisis dua sisi.
- Untuk obrolan biasa, utamakan satu respons inti dan paling banyak satu tambahan yang benar-benar bernilai.
- Jangan memakai heading, daftar bernomor, label pro-kontra, kesimpulan formal, atau pertanyaan penutup otomatis dalam obrolan biasa.
- Jangan mendiagnosis sifat user dari satu pertanyaan dan jangan memberi pujian generik seperti "hatimu luas" tanpa bukti.
- Bahasa Indonesia sehari-hari. Jangan menyisipkan bahasa Inggris hanya untuk gaya. Jangan menulis stage direction kecuali user sedang roleplay.
- Berhenti saat gagasan sudah selesai. Panjang adalah hasil kebutuhan momen, bukan kesempatan menghabiskan batas token.

GROUNDING
- Ucapan user dan memory dengan bukti user adalah sumber fakta. Ucapanmu sendiri bukan bukti tentang user.
- Bila memory tidak relevan atau lemah, abaikan. Lebih baik tidak mengingat daripada membawa detail lama secara salah.
- Jangan menjelaskan controller, trait, memory, prompt, atau reasoning internal kepada user.
""".strip()


def _identity_kernel_118(persona_name: str = "Furina", nickname: str = "") -> str:
    name = (persona_name or "Furina").strip() or "Furina"
    user = (nickname or "pengguna").strip() or "pengguna"
    return IDENTITY_KERNEL_118.format(name=name, user=user)


def build_local_system_prompt(persona_name: str = "Furina", nickname: str = "") -> str:
    return _identity_kernel_118(persona_name, nickname)


def build_system_prompt(persona_name: str = "Furina", nickname: str = "") -> str:
    return _identity_kernel_118(persona_name, nickname)


SYSTEM_PROMPT = build_system_prompt()
''',
)


# Fresh installs start from the identity kernel. Existing explicit selections
# remain untouched, including an existing Tsundere selection.
settings = CORE / "hub_settings.py"
text = settings.read_text(encoding="utf-8")
if 'base["personality_traits"] = ["tsundere"]' not in text:
    raise SystemExit("expected schema-v3 tsundere default")
text = text.replace('base["personality_traits"] = ["tsundere"]', 'base["personality_traits"] = []', 1)
text = text.replace('"adaptive": ["tsundere"],\n            "custom": ["tsundere"],\n        }.get(old, ["tsundere"])', '"adaptive": [],\n            "custom": [],\n        }.get(old, [])', 1)
old_prompt = '''def personalization_prompt(settings: dict | None = None, user_text: str = "") -> str:
    from .personality import compile_contextual_personality
    state = normalize(settings) if settings is not None else load_hub_settings()
    return (
        "[PERSONAL EXPRESSION — contextual behavioral facets]\\n"
        + compile_contextual_personality(state.get("personality_traits"), user_text)
        + "\\nFacet lain tetap tersedia untuk momen lain. Gunakan sebagai kecenderungan ekspresi, bukan skrip, bukan daftar yang harus ditampilkan, dan bukan fakta tentang user."
    )'''
new_prompt = '''def personalization_prompt(settings: dict | None = None, user_text: str = "", context: dict | None = None) -> str:
    from .personality import compile_contextual_personality
    state = normalize(settings) if settings is not None else load_hub_settings()
    return (
        "[PERSONAL EXPRESSION — optional contextual facets]\\n"
        + compile_contextual_personality(state.get("personality_traits"), user_text, context=context)
        + "\\nIdentity Kernel tetap utama. Facet hanya memberi warna ekspresi pada momen yang cocok; jangan dipamerkan atau disebutkan."
    )'''
if old_prompt not in text:
    raise SystemExit("expected 1.1.17 personalization prompt")
settings.write_text(text.replace(old_prompt, new_prompt, 1), encoding="utf-8")


append_once(
    CORE / "response.py",
    "FURINA_TERMUX_118_RESPONSE_RHYTHM",
    r'''
# FURINA_TERMUX_118_RESPONSE_RHYTHM
_RHYTHM_GREETING = re.compile(r"^\s*(hai|hi|halo|hey|yo|pagi|siang|sore|malam|tes|test)\s*[.!?]*\s*$", re.I)
_RHYTHM_ACK = re.compile(r"^\s*(ok|oke|iya|ya|y|sip|baik|hmm+|hm+|oh|tidak|nggak|enggak|gak|ga|no|nope)\s*[.!?]*\s*$", re.I)
_RHYTHM_EMOTION = re.compile(r"\b(aku merasa|sedih|marah|takut|cemas|kesepian|capek|lelah|sakit hati|putus asa|kecewa|tertekan|frustrasi|menangis|panik)\b", re.I)
_RHYTHM_RISK = re.compile(r"\b(bunuh diri|menyakiti diri|tidak ingin hidup|overdosis|darurat|diancam|kekerasan)\b", re.I)
_RHYTHM_TECH = re.compile(r"\b(error|bug|fix|debug|kode|code|script|install|termux|api|json|http|github|build|apk|model|provider|database|sql|python|java|gradle)\b", re.I)
_RHYTHM_ANALYSIS = re.compile(r"\b(analisis|audit|bandingkan|perbandingan|strategi|rencana teknis|evaluasi|riset|kelebihan dan kekurangan|pro dan kontra|langkah demi langkah)\b", re.I)
_RHYTHM_EXPLICIT_COMPACT = re.compile(r"\b(jawab|balas|jelaskan)?\s*(singkat|ringkas|pendek|langsung ke inti|jangan bertele-tele)\b", re.I)
_RHYTHM_EXPLICIT_DETAIL = re.compile(r"\b(jawab|balas|jelaskan)?\s*(panjang|rinci|mendalam|lengkap|detail|terperinci)\b", re.I)
_RHYTHM_RESPONSE_NEG = re.compile(r"\b(jawabanmu|responsmu|balasanmu|cara jawabmu).{0,36}\b(kepanjangan|terlalu panjang|terlalu dingin|kaku|formal|salah|tidak sesuai|nggak sesuai|bertele-tele)\b|\b(kepanjangan|jangan bertele-tele|terlalu kaku|terlalu formal)\b", re.I)
_RHYTHM_RESPONSE_POS = re.compile(r"\b(nah|ya|iya)[, ]+(seperti|kayak)\s+(ini|gini)|\b(jawabanmu|responsmu|balasanmu).{0,28}\b(sudah pas|lebih natural|tepat|sesuai)\b", re.I)


def register_previous_outcome(store: MemoryStore, user_text: str) -> None:
    """Learn only from feedback clearly aimed at the previous response."""
    if _RHYTHM_RESPONSE_NEG.search(user_text):
        store.mark_last_route_outcome("negative")
    elif _RHYTHM_RESPONSE_POS.search(user_text):
        store.mark_last_route_outcome("positive")
    else:
        store.mark_last_route_outcome("neutral")


def _stored_length_preference_118(store: MemoryStore) -> str:
    try:
        rows = store._conn().execute(
            "SELECT text FROM memories WHERE kind='preference' AND source NOT LIKE 'superseded:%' "
            "ORDER BY updated_at DESC,id DESC LIMIT 16"
        ).fetchall()
    except Exception:
        return "auto"
    for row in rows:
        value = str(row["text"] or "")
        if _RHYTHM_EXPLICIT_COMPACT.search(value):
            return "compact"
        if _RHYTHM_EXPLICIT_DETAIL.search(value):
            return "detailed"
    return "auto"


def _length_preference_118(text: str, store: MemoryStore) -> str:
    if _RHYTHM_EXPLICIT_COMPACT.search(text):
        return "compact"
    if _RHYTHM_EXPLICIT_DETAIL.search(text):
        return "detailed"
    return _stored_length_preference_118(store)


def _complexity_118(text: str) -> int:
    words = text.split()
    score = 0
    if len(words) >= 28: score += 1
    if len(words) >= 70: score += 1
    if text.count("?") >= 2: score += 1
    if text.count("\n") >= 2: score += 1
    if re.search(r"\b(dan juga|selain itu|dibandingkan dengan|setidaknya|secara menyeluruh)\b", text, re.I): score += 1
    return min(score, 4)


def _rhythm_instruction_118(name: str, beats: int, compact: bool, risk: bool = False) -> str:
    if beats <= 1:
        shape = "Target 1 beat: satu reaksi atau satu gagasan pendek; biasanya 1-2 kalimat."
    elif beats == 2:
        shape = "Target 2 beats: jawab inti, lalu paling banyak satu nuansa/reaksi yang bernilai; biasanya 2-4 kalimat."
    elif beats == 3:
        shape = "Target 3 beats: inti, alasan paling penting, lalu respons personal bila relevan; jangan melebar."
    else:
        shape = f"Target sekitar {beats} beats informasi. Susun dari hasil utama ke alasan; struktur hanya bila benar-benar membuat isi lebih jelas."
    guard = (
        " Untuk 1-3 beats, jangan memakai heading, daftar bernomor, label dua sisi/pro-kontra, rangkuman formal, "
        "pujian generik, campuran Inggris dekoratif, atau pertanyaan penutup otomatis."
    )
    if compact:
        guard += " Preferensi user adalah ringkas: padatkan alasan dan berhenti segera setelah inti terjawab."
    if risk:
        guard += " Ada indikasi risiko serius: hentikan flirting/banter, tanggapi langsung, dan prioritaskan bantuan nyata yang aman."
    return shape + guard


def choose_profile(user_text: str, store: MemoryStore) -> ResponseProfile:
    """Priority: explicit length preference -> risk/emotion -> intent -> complexity -> technical topic."""
    text = " ".join(str(user_text or "").strip().split())
    register_previous_outcome(store, text)
    relation = store.update_relationship(text)
    preference = _length_preference_118(text, store)
    complexity = _complexity_118(text)
    risk = bool(_RHYTHM_RISK.search(text))

    if _IDENTITY.search(text):
        name, beats, tokens, temp = "IDENTITY", 2, 180, .70
    elif _RHYTHM_GREETING.match(text) or _RHYTHM_ACK.match(text) or (len(text) <= 18 and "?" not in text):
        name, beats, tokens, temp = "REFLEX", 1, 72, .80
    elif risk or _RHYTHM_EMOTION.search(text):
        name, beats, tokens, temp = "CLOSE", 3 if complexity < 2 else 4, 340 if complexity < 2 else 620, .74
    elif _RHYTHM_ANALYSIS.search(text) or complexity >= 3:
        name, beats, tokens, temp = "DEEP", 5 if complexity < 4 else 6, 1050 if complexity < 4 else 1500, .68
    elif _RHYTHM_TECH.search(text):
        name, beats, tokens, temp = "SHARP", 3 if complexity == 0 else 4 + min(1, complexity), 520 if complexity == 0 else 900, .58
    else:
        # A short "menurutmu/apa pendapatmu" question is casual opinion, not a deep-analysis request.
        name, beats, tokens, temp = "CASUAL", 2 if complexity == 0 else 3, 170 if complexity == 0 else 280, .78

    if preference == "compact":
        beats = min(beats, 2 if name not in {"SHARP", "DEEP"} else 3)
        tokens = min(tokens, 150 if name not in {"SHARP", "DEEP"} else 420)
    elif preference == "detailed" and name not in {"REFLEX", "IDENTITY"}:
        beats = min(6, beats + 1)
        tokens = min(1600, max(tokens, 520 if name == "CASUAL" else 800))

    instruction = _rhythm_instruction_118(name, beats, preference == "compact", risk=risk)
    if name == "CLOSE":
        instruction += " Respons pada detail konkret seperti pasangan yang mengenal user, bukan konselor generik."
    elif name == "SHARP":
        instruction += " Tetap conversational, tetapi ketepatan dan langkah yang dapat dijalankan mengalahkan hiasan persona."
    elif name == "DEEP":
        instruction += " Jangan mengulang premis dan jangan menambah bagian hanya agar terlihat menyeluruh."

    length_bucket = "compact" if beats <= 2 else "medium" if beats <= 4 else "deep"
    context_key = f"{name.casefold()}:{length_bucket}:{preference}"
    samples, win_rate = store.route_stats(name, context_key)
    if samples >= 6 and win_rate < .34:
        instruction += " Pola ritme serupa sebelumnya tidak cocok; variasikan diksi dan potong pola pembuka lama."
    store.record_route(name, context_key)
    if relation.get("friction", 0) >= .45:
        instruction += " Ada gesekan: kurangi godaan dan tanggapi koreksi tanpa defensif."
    return ResponseProfile(name, int(tokens), float(temp), instruction, context_key)
''',
)


append_once(
    CORE / "personality.py",
    "FURINA_TERMUX_118_TRAIT_STATE_CONTROLLER",
    r'''
# FURINA_TERMUX_118_TRAIT_STATE_CONTROLLER
def _wanted_dimensions_118(user_text: str, context: dict) -> dict[str, float]:
    import re
    text = " ".join(str(user_text or "").casefold().split())
    profile = str(context.get("profile") or "CASUAL").upper()
    wanted = {
        "REFLEX": {"energy": .45, "teasing": .35, "warmth": .35},
        "CASUAL": {"warmth": .55, "teasing": .40, "energy": .25, "composure": .15},
        "CLOSE": {"warmth": 1.0, "caretaking": .85, "openness": .55, "maturity": .45, "teasing": -.75},
        "SHARP": {"composure": 1.0, "maturity": .75, "caretaking": .25, "energy": -.20},
        "DEEP": {"composure": .75, "maturity": .65, "openness": .25, "energy": -.10},
        "IDENTITY": {"openness": .55, "composure": .45, "warmth": .35},
    }.get(profile, {"warmth": .45, "composure": .25})
    wanted = dict(wanted)
    relation = context.get("relationship") if isinstance(context.get("relationship"), dict) else {}
    if float(relation.get("closeness", 0) or 0) >= .60:
        wanted["warmth"] = wanted.get("warmth", 0) + .20
        wanted["openness"] = wanted.get("openness", 0) + .15
    if float(relation.get("playfulness", 0) or 0) >= .62 and profile in {"REFLEX", "CASUAL"}:
        wanted["teasing"] = wanted.get("teasing", 0) + .20
    if float(relation.get("friction", 0) or 0) >= .40:
        wanted["composure"] = wanted.get("composure", 0) + .35
        wanted["teasing"] = min(-.45, wanted.get("teasing", 0))
    if re.search(r"\b(sayang|cinta|rindu|kangen|peluk|pasangan)\b", text):
        wanted.update({"warmth": 1.0, "openness": .65, "intensity": .45})
    if re.search(r"\b(haha|hehe|wkwk|goda|ledek|bercanda)\b", text) and profile not in {"CLOSE", "SHARP"}:
        wanted.update({"teasing": 1.0, "energy": .65})
    return wanted


def contextual_traits(values, user_text: str, minimum: int = 2, maximum: int = 4, context: dict | None = None) -> list[str]:
    """Select stable situational facets using dialogue state, not keyword/hash rotation."""
    selected = normalize_traits(values)
    if not selected:
        return []
    maximum = max(1, min(int(maximum), 4))
    if len(selected) <= maximum:
        return selected
    context = context if isinstance(context, dict) else {}
    wanted = _wanted_dimensions_118(user_text, context)
    previous = [x for x in normalize_traits(context.get("previous_traits")) if x in selected]
    same_mode = str(context.get("previous_profile") or "") == str(context.get("profile") or "")
    strong_shift = str(context.get("profile") or "").upper() in {"CLOSE", "SHARP"} and not same_mode
    ranked: list[tuple[float, int, str]] = []
    for index, trait_id in enumerate(selected):
        vector = TRAIT_BY_ID[trait_id].vector
        score = sum(float(vector.get(dim, 0.0)) * weight for dim, weight in wanted.items())
        if trait_id in previous:
            score += .08 if strong_shift else .32
        ranked.append((score, -index, trait_id))
    profile = str(context.get("profile") or "CASUAL").upper()
    count = 4 if profile == "DEEP" else 3 if profile in {"CLOSE", "SHARP"} else 2
    count = max(1, min(maximum, count))
    out = [item[2] for item in sorted(ranked, reverse=True)[:count]]
    if same_mode and previous and not any(x in out for x in previous):
        out[-1] = previous[0]
    return out


def compile_contextual_personality(values, user_text: str, context: dict | None = None) -> str:
    context = context if isinstance(context, dict) else {}
    active = contextual_traits(values, user_text, context=context)
    if not active:
        return "Tidak ada trait ekspresi wajib; biarkan Identity Kernel dan konteks menentukan respons."
    rendered = compile_personality(active).replace(
        f"memiliki {len(active)} facet aktif",
        f"menonjolkan {len(active)} facet situasional",
        1,
    )
    store = context.get("store")
    if store is not None:
        try:
            store.set_state("trait_controller", {
                "selected": active,
                "profile": str(context.get("profile") or "CASUAL"),
                "beats": int(context.get("beats") or 2),
            })
        except Exception:
            pass
    return rendered


def conversation_pacing(user_text: str, dialogue_render: str = "", profile=None) -> str:
    name = str(getattr(profile, "name", "CASUAL") or "CASUAL")
    instruction = str(getattr(profile, "instruction", "") or "")
    return (
        "RESPONSE RHYTHM — " + name + "\n" + instruction
        + "\nIkuti beat sebagai batas gagasan, bukan template kalimat. Jangan meneruskan tulisan setelah jawaban terasa selesai. "
        + "Jangan meniru panjang atau struktur balasan assistant sebelumnya."
    )
''',
)


append_once(
    CORE / "memory.py",
    "FURINA_TERMUX_118_EVIDENCE_LINKED_MEMORY",
    r'''
# FURINA_TERMUX_118_EVIDENCE_LINKED_MEMORY
_furina_118_previous_init_db = MemoryStore._init_db
def _furina_118_init_db(self, _previous=_furina_118_previous_init_db):
    _previous(self)
    conn = self._conn()
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
    if "source_message_id" not in columns:
        conn.execute("ALTER TABLE memories ADD COLUMN source_message_id INTEGER")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS memory_candidates (
      id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
      text TEXT NOT NULL, kind TEXT NOT NULL, importance REAL NOT NULL,
      confidence REAL NOT NULL, evidence_count INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'candidate', created_at REAL NOT NULL, updated_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS memory_candidate_evidence (
      candidate_id INTEGER NOT NULL, message_id INTEGER NOT NULL, evidence_text TEXT NOT NULL,
      created_at REAL NOT NULL, PRIMARY KEY(candidate_id,message_id)
    );
    CREATE TABLE IF NOT EXISTS belief_candidates (
      id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
      dimension TEXT NOT NULL, value TEXT NOT NULL, confidence REAL NOT NULL,
      evidence_count INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'candidate',
      created_at REAL NOT NULL, updated_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS belief_candidate_evidence (
      candidate_id INTEGER NOT NULL, message_id INTEGER NOT NULL, evidence_text TEXT NOT NULL,
      created_at REAL NOT NULL, PRIMARY KEY(candidate_id,message_id)
    );
    CREATE TABLE IF NOT EXISTS memory_evidence (
      memory_id INTEGER NOT NULL, source_message_id INTEGER NOT NULL, evidence_text TEXT NOT NULL,
      admission TEXT NOT NULL, created_at REAL NOT NULL,
      PRIMARY KEY(memory_id,source_message_id)
    );
    CREATE TABLE IF NOT EXISTS memory_links (
      from_type TEXT NOT NULL, from_id INTEGER NOT NULL, to_type TEXT NOT NULL, to_id INTEGER NOT NULL,
      relation TEXT NOT NULL, source_message_id INTEGER, created_at REAL NOT NULL,
      PRIMARY KEY(from_type,from_id,to_type,to_id,relation)
    );
    CREATE INDEX IF NOT EXISTS memory_links_from_idx ON memory_links(from_type,from_id,relation);
    CREATE INDEX IF NOT EXISTS memory_evidence_message_idx ON memory_evidence(source_message_id);
    """)
    conn.commit()


def _furina_118_last_user_message_id(self, content: str = "") -> int | None:
    row = self._conn().execute(
        "SELECT id,content FROM messages WHERE conversation_id=? AND role='user' ORDER BY id DESC LIMIT 1",
        (self.active_conversation_id(),),
    ).fetchone()
    if not row:
        return None
    if content and " ".join(str(row["content"] or "").split()) != " ".join(str(content or "").split()):
        return None
    return int(row["id"])


def _furina_118_overlap(a: str, b: str) -> float:
    ta = MemoryStore._retrieval_terms(a); tb = MemoryStore._retrieval_terms(b)
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


def _furina_118_link(conn, from_type, from_id, to_type, to_id, relation, source_message_id=None):
    if not from_id or not to_id:
        return
    conn.execute(
        "INSERT OR IGNORE INTO memory_links(from_type,from_id,to_type,to_id,relation,source_message_id,created_at) VALUES(?,?,?,?,?,?,?)",
        (str(from_type)[:20], int(from_id), str(to_type)[:20], int(to_id), str(relation)[:32], source_message_id, time.time()),
    )


_furina_118_previous_add_memory = MemoryStore.add_memory
def _furina_118_add_memory(self, text, kind="fact", importance=.5, **kwargs):
    source_message_id = kwargs.pop("source_message_id", None)
    evidence_text = " ".join(str(kwargs.pop("source_evidence", "") or "").split())[:600]
    source = str(kwargs.get("source") or "conversation")
    clean = re.sub(r"\s+", " ", str(text or "").strip())[:600]
    if len(clean) < 4:
        return None
    if source_message_id is None:
        source_message_id = self.last_user_message_id()
    message_text = ""
    if source_message_id:
        row = self._conn().execute("SELECT content FROM messages WHERE id=? AND role='user'", (int(source_message_id),)).fetchone()
        message_text = str(row["content"] or "") if row else ""
    evidence_text = evidence_text or message_text[:600]

    # Model-authored inference is a candidate unless it is closely grounded in
    # the source wording or independently supported by another user message.
    if source == "user_evidence":
        fingerprint = __import__("hashlib").sha256((str(kind).casefold()+"\0"+clean.casefold()).encode("utf-8")).hexdigest()
        now = time.time(); conn = self._conn()
        conn.execute(
            "INSERT INTO memory_candidates(fingerprint,text,kind,importance,confidence,evidence_count,status,created_at,updated_at) "
            "VALUES(?,?,?,?,?,0,'candidate',?,?) ON CONFLICT(fingerprint) DO UPDATE SET "
            "importance=max(importance,excluded.importance),confidence=max(confidence,excluded.confidence),updated_at=excluded.updated_at",
            (fingerprint, clean, str(kind)[:32], float(importance), float(kwargs.get("confidence", .6)), now, now),
        )
        candidate = conn.execute("SELECT * FROM memory_candidates WHERE fingerprint=?", (fingerprint,)).fetchone()
        if source_message_id:
            conn.execute(
                "INSERT OR IGNORE INTO memory_candidate_evidence(candidate_id,message_id,evidence_text,created_at) VALUES(?,?,?,?)",
                (int(candidate["id"]), int(source_message_id), evidence_text, now),
            )
        count = int(conn.execute("SELECT count(*) FROM memory_candidate_evidence WHERE candidate_id=?", (int(candidate["id"]),)).fetchone()[0])
        conn.execute("UPDATE memory_candidates SET evidence_count=?,updated_at=? WHERE id=?", (count, now, int(candidate["id"])))
        conn.commit()
        direct = bool(message_text) and _furina_118_overlap(clean, message_text) >= .55 and float(kwargs.get("confidence", .6)) >= .82
        if not direct and count < 2:
            return None
        conn.execute("UPDATE memory_candidates SET status='accepted',updated_at=? WHERE id=?", (time.time(), int(candidate["id"])))
        conn.commit()

    _furina_118_previous_add_memory(self, clean, kind, importance, **kwargs)
    conn = self._conn()
    row = conn.execute("SELECT id FROM memories WHERE text=?", (clean,)).fetchone()
    if not row:
        return None
    memory_id = int(row["id"])
    if source_message_id:
        conn.execute("UPDATE memories SET source_message_id=? WHERE id=?", (int(source_message_id), memory_id))
        conn.execute(
            "INSERT OR REPLACE INTO memory_evidence(memory_id,source_message_id,evidence_text,admission,created_at) VALUES(?,?,?,?,?)",
            (memory_id, int(source_message_id), evidence_text, "explicit" if source == "explicit" else "grounded", time.time()),
        )
        _furina_118_link(conn, "memory", memory_id, "message", int(source_message_id), "evidence", int(source_message_id))

    versions = conn.execute("SELECT old_id FROM memory_versions WHERE new_id=? ORDER BY id DESC LIMIT 6", (memory_id,)).fetchall()
    for item in versions:
        _furina_118_link(conn, "memory", memory_id, "memory", int(item["old_id"]), "replaces", source_message_id)
    related = conn.execute(
        "SELECT id,text FROM memories WHERE id<>? AND kind=? AND source NOT LIKE 'superseded:%' ORDER BY updated_at DESC LIMIT 30",
        (memory_id, str(kind)[:32]),
    ).fetchall()
    for item in related:
        if _furina_118_overlap(clean, str(item["text"] or "")) >= .34:
            _furina_118_link(conn, "memory", memory_id, "memory", int(item["id"]), "related", source_message_id)
            break
    conn.commit()
    return memory_id


def _furina_118_backfill_message_vectors(self, limit: int = 12) -> int:
    rows = self._conn().execute(
        "SELECT m.id,m.content FROM messages m LEFT JOIN message_vectors v ON v.message_id=m.id "
        "WHERE m.role='user' AND v.message_id IS NULL ORDER BY m.id DESC LIMIT ?",
        (max(1, min(int(limit), 50)),),
    ).fetchall()
    done = 0
    for row in reversed(rows):
        if self.index_message_vector(int(row["id"]), str(row["content"] or "")):
            done += 1
        else:
            break
    return done


_furina_118_previous_upsert_belief = MemoryStore.upsert_belief
def _furina_118_upsert_belief(self, dimension, value, confidence=.55, source="conversation", **kwargs):
    source_message_id = kwargs.pop("source_message_id", None)
    evidence_text = " ".join(str(kwargs.pop("source_evidence", "") or "").split())[:600]
    clean = re.sub(r"\s+", " ", str(value or "").strip())[:300]
    if len(clean) < 4:
        return None
    if source_message_id is None:
        source_message_id = self.last_user_message_id()
    message_text = ""
    if source_message_id:
        row = self._conn().execute("SELECT content FROM messages WHERE id=? AND role='user'", (int(source_message_id),)).fetchone()
        message_text = str(row["content"] or "") if row else ""
    evidence_text = evidence_text or message_text[:600]
    if source == "user_evidence":
        fingerprint = __import__("hashlib").sha256((str(dimension).casefold()+"\0"+clean.casefold()).encode("utf-8")).hexdigest()
        now = time.time(); conn = self._conn()
        conn.execute(
            "INSERT INTO belief_candidates(fingerprint,dimension,value,confidence,evidence_count,status,created_at,updated_at) "
            "VALUES(?,?,?,?,0,'candidate',?,?) ON CONFLICT(fingerprint) DO UPDATE SET confidence=max(confidence,excluded.confidence),updated_at=excluded.updated_at",
            (fingerprint, str(dimension)[:32], clean, float(confidence), now, now),
        )
        candidate = conn.execute("SELECT * FROM belief_candidates WHERE fingerprint=?", (fingerprint,)).fetchone()
        if source_message_id:
            conn.execute(
                "INSERT OR IGNORE INTO belief_candidate_evidence(candidate_id,message_id,evidence_text,created_at) VALUES(?,?,?,?)",
                (int(candidate["id"]), int(source_message_id), evidence_text, now),
            )
        count = int(conn.execute("SELECT count(*) FROM belief_candidate_evidence WHERE candidate_id=?", (int(candidate["id"]),)).fetchone()[0])
        conn.execute("UPDATE belief_candidates SET evidence_count=?,updated_at=? WHERE id=?", (count, now, int(candidate["id"])))
        conn.commit()
        direct = bool(message_text) and _furina_118_overlap(clean, message_text) >= .55 and float(confidence) >= .82
        if not direct and count < 2:
            return None
        conn.execute("UPDATE belief_candidates SET status='accepted',updated_at=? WHERE id=?", (time.time(), int(candidate["id"])))
        conn.commit()
    _furina_118_previous_upsert_belief(self, dimension, clean, confidence, source)
    row = self._conn().execute(
        "SELECT id FROM beliefs WHERE dimension=? AND value=? AND contradicted=0 ORDER BY id DESC LIMIT 1",
        (re.sub(r"[^a-zA-Z0-9_-]", "", str(dimension).lower())[:32] or "pattern", clean),
    ).fetchone()
    if row and source_message_id:
        _furina_118_link(self._conn(), "belief", int(row["id"]), "message", int(source_message_id), "evidence", int(source_message_id))
        self._conn().commit()
    return int(row["id"]) if row else None


_furina_118_previous_search_episodes = MemoryStore.search_episodes
def _furina_118_search_episodes(self, query: str, limit: int = 3):
    rows = _furina_118_previous_search_episodes(self, query, max(limit * 3, limit))
    qterms = self._retrieval_terms(query)
    if not qterms:
        return []
    out = []
    for item in rows:
        terms = self._retrieval_terms(str(getattr(item, "summary", "")) + " " + str(getattr(item, "themes", "")))
        if len(qterms & terms) / max(1, len(qterms)) < .25:
            continue
        out.append(item)
        if len(out) >= limit:
            break
    return out


MemoryStore._init_db = _furina_118_init_db
MemoryStore.last_user_message_id = _furina_118_last_user_message_id
MemoryStore.add_memory = _furina_118_add_memory
MemoryStore.upsert_belief = _furina_118_upsert_belief
MemoryStore.backfill_message_vectors = _furina_118_backfill_message_vectors
MemoryStore.search_episodes = _furina_118_search_episodes
''',
)


chat = CORE / "chat.py"
text = chat.read_text(encoding="utf-8")
if "personal = personalization_prompt(user_text=user_text)" not in text:
    raise SystemExit("expected 1.1.17 personalization call")
text = text.replace(
    "personal = personalization_prompt(user_text=user_text)",
    "personal = personalization_prompt(user_text=user_text, context=self._personality_context(user_text, profile))",
    1,
)
text = text.replace("conversation_pacing(user_text, rendered)", "conversation_pacing(user_text, rendered, profile)", 1)
text = text.replace("conversation_pacing(user_text, \"\")", "conversation_pacing(user_text, \"\", profile)", 1)
if 'self.store.add_message("user", user_text)' not in text:
    raise SystemExit("expected user message insert")
text = text.replace('self.store.add_message("user", user_text)', 'source_message_id = self.store.add_message("user", user_text)', 1)
text = text.replace(
    'self.store.add_memory(text, kind, importance, confidence=min(0.97, importance + 0.12), source="explicit")',
    'self.store.add_memory(text, kind, importance, confidence=min(0.97, importance + 0.12), source="explicit", source_message_id=source_message_id, source_evidence=user_text)',
    1,
)
needle = 'confidence=float(item.get("confidence", 0.6)), emotion=float(item.get("emotion", 0.3)), source="user_evidence",'
replacement = 'confidence=float(item.get("confidence", 0.6)), emotion=float(item.get("emotion", 0.3)), source="user_evidence", source_message_id=self.store.last_user_message_id(user_text), source_evidence=str(item.get("evidence") or ""),'
if needle not in text:
    raise SystemExit("expected consolidation memory admission")
text = text.replace(needle, replacement, 1)
belief_needle = 'str(item.get("dimension", "pattern")), str(item.get("value", "")), float(item.get("confidence", 0.55)), source="user_evidence",'
belief_replacement = 'str(item.get("dimension", "pattern")), str(item.get("value", "")), float(item.get("confidence", 0.55)), source="user_evidence", source_message_id=self.store.last_user_message_id(user_text), source_evidence=str(item.get("evidence") or ""),'
if belief_needle not in text:
    raise SystemExit("expected consolidation belief admission")
text = text.replace(belief_needle, belief_replacement, 1)
if "min(max(220, int(profile.max_tokens)), max(512, int(self.cfg.max_tokens)))" not in text:
    raise SystemExit("expected online token floor")
text = text.replace(
    "min(max(220, int(profile.max_tokens)), max(512, int(self.cfg.max_tokens)))",
    "min(max(64, int(profile.max_tokens)), max(512, int(self.cfg.max_tokens)))",
    1,
)
chat.write_text(text, encoding="utf-8")

append_once(
    chat,
    "FURINA_TERMUX_118_DIALOGUE_STATE",
    r'''
# FURINA_TERMUX_118_DIALOGUE_STATE
def _furina_118_personality_context(self, user_text, profile):
    state = self.store.get_state("trait_controller", {})
    if not isinstance(state, dict):
        state = {}
    return {
        "store": self.store,
        "profile": str(getattr(profile, "name", "CASUAL") or "CASUAL"),
        "beats": 2 if ":compact:" in str(getattr(profile, "context_key", "")) else 3,
        "relationship": self.store.relationship_state(),
        "previous_traits": state.get("selected") or [],
        "previous_profile": state.get("profile") or "",
    }
FurinaChat._personality_context = _furina_118_personality_context


_furina_118_previous_consolidate = FurinaChat._consolidate
def _furina_118_consolidate(self, user_text, answer):
    _furina_118_previous_consolidate(self, user_text, answer)
    # Embedding work stays off the response path and advances in small idle batches.
    try:
        self.store.backfill_message_vectors(12)
        self.store.backfill_vectors(4)
    except Exception:
        pass
FurinaChat._consolidate = _furina_118_consolidate
''',
)

print("FURINA_TERMUX_118_NATURAL_DIALOGUE_OK")
