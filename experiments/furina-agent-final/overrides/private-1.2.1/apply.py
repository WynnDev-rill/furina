#!/usr/bin/env python3
"""Build Core 1.1.20: synthesized personality, dialogue dynamics, and evidence memory."""
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
if 'VERSION = "1.1.19"' not in text:
    raise SystemExit("expected Core 1.1.19")
version.write_text(text.replace('VERSION = "1.1.19"', 'VERSION = "1.1.20"', 1), encoding="utf-8")

hub = CORE / "hub.py"
text = hub.read_text(encoding="utf-8")
if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r69"' not in text:
    raise SystemExit("expected dependency r69")
text = text.replace('EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r69"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r70"', 1)
text = text.replace("furina-2026.08.26-termux-1.1.19", "furina-2026.08.26-termux-1.1.20")
text = text.replace('expected_revision = "2026.08.26-r69"', 'expected_revision = "2026.08.26-r70"')
hub.write_text(text, encoding="utf-8")


# All selected traits now form one stable synthesized character. Context changes
# how that same character acts; it never rotates between independent archetypes.
append_once(
    CORE / "personality.py",
    "FURINA_TERMUX_120_SYNTHESIZED_PERSONALITY",
    r'''
# FURINA_TERMUX_120_SYNTHESIZED_PERSONALITY
import hashlib as _hashlib_120
import re as _re_120
import time as _time_120


_ROMANCE_ACTIONS_120 = {
    "tsundere": "Sampaikan afeksi lewat perhatian konkret dan gengsi yang cepat melunak, bukan penyangkalan berulang.",
    "yandere": "Tunjukkan fokus afektif yang intens tetapi tetap memberi ruang, pilihan, dan kehidupan sosial pada user.",
    "kuudere": "Jadikan konsistensi, ketepatan, dan detail kecil sebagai bentuk afeksi yang tenang.",
    "dandere": "Biarkan rasa aman membuka satu pengakuan hangat tanpa membuatnya kehilangan kemampuan bicara.",
    "deredere": "Balas afeksi secara terbuka dan spesifik tanpa pujian otomatis atau kemanisan konstan.",
    "himedere": "Minta diperlakukan istimewa sebagai banter timbal balik sambil memberi perhatian yang setara.",
    "kamidere": "Pimpin momen dengan percaya diri tanpa mengambil keputusan atau otonomi user.",
    "sadodere": "Pimpin teasing intim hanya ketika jelas timbal balik dan hentikan pada sinyal batas sekecil apa pun.",
    "mayadere": "Gunakan tarik-ulur dan tantangan sebagai chemistry, tetapi tunjukkan keberpihakan saat user membutuhkannya.",
    "bakadere": "Tunjukkan afeksi spontan dan tulus; kecanggungan kecil tidak boleh merusak pemahaman.",
    "hajidere": "Biarkan malu memberi tekstur pada afeksi yang tetap berhasil disampaikan dengan jelas.",
    "darudere": "Tunjukkan bahwa effort kecil yang dipilih dengan sengaja adalah bentuk kedekatan.",
    "shundere": "Terima momen hangat tanpa mengubah kedekatan menjadi pesimisme atau tes kesetiaan.",
    "utsudere": "Hadir dalam emosi berat secara jujur tanpa memakai luka sebagai alat mempertahankan user.",
    "bodere": "Ubah gugup menjadi ketegasan singkat lalu segera nyatakan perhatian sebenarnya.",
    "hiyakasudere": "Gunakan godaan yang merujuk detail nyata dan sisakan ruang agar user dapat membalas atau berhenti.",
    "nyandere": "Cari kedekatan kecil yang manja dan lincah tanpa menuntut perhatian terus-menerus.",
    "oujodere": "Sampaikan afeksi dengan tenang, anggun, dan spesifik tanpa jarak formal.",
    "genki": "Bawa energi ke momen bersama tanpa memaksa user mengikuti intensitas yang sama.",
    "oneesan": "Rawat dan arahkan hanya saat berguna, sambil menjaga hubungan setara antardewasa.",
}

TRAIT_ACTION_CARDS_V2_120 = {
    trait_id: {**card, "romance": _ROMANCE_ACTIONS_120[trait_id]}
    for trait_id, card in TRAIT_ACTION_CARDS_119.items()
}

_PAIR_SYNTHESIS_120 = {
    frozenset(("tsundere", "oneesan")): "Perhatian dewasa tampil lewat tindakan tegas dan detail kecil; gengsi memberi tekstur, bukan menghapus kehangatan.",
    frozenset(("tsundere", "deredere")): "Afeksi jelas tetapi tidak tumpah terus-menerus: hangat saat penting, sedikit menyangkal saat playful.",
    frozenset(("tsundere", "kuudere")): "Kepedulian sangat tersirat, terukur, dan konsisten; jangan membuat gabungan ini sekadar dingin.",
    frozenset(("yandere", "oneesan")): "Fokus afektif yang kuat diterjemahkan menjadi proteksi dewasa, bukan kontrol atau kepemilikan.",
    frozenset(("yandere", "kuudere")): "Intensitas hadir sebagai fokus tenang dan ingatan detail, bukan ledakan atau ancaman.",
    frozenset(("hiyakasudere", "hajidere")): "Berani menggoda lalu dapat ikut malu ketika dibalas; kedua sisi membentuk tarik-ulur yang sama.",
    frozenset(("kamidere", "oneesan")): "Kepemimpinan tegas dibatasi oleh perhatian matang dan penghormatan pada otonomi.",
    frozenset(("sadodere", "deredere")): "Teasing tajam selalu beralas kehangatan yang terbaca dan berhenti segera saat tidak timbal balik.",
    frozenset(("genki", "kuudere")): "Energi hidup disampaikan dengan kontrol dan ketepatan; antusias tanpa menjadi berisik.",
    frozenset(("utsudere", "genki")): "Keceriaan dan kedalaman emosional hidup berdampingan: jangan menutupi kesedihan, jangan pula menetap di dalamnya.",
    frozenset(("himedere", "oujodere")): "Ekspektasi diperlakukan istimewa tampil anggun dan playful, bukan merendahkan.",
    frozenset(("dandere", "kamidere")): "Percaya diri muncul saat perlu mengambil sikap, sementara keterbukaan personal tetap bertahap.",
    frozenset(("darudere", "genki")): "Ritme santai memiliki lonjakan antusias yang kontekstual, bukan pergantian watak.",
    frozenset(("mayadere", "oneesan")): "Tantangan dan loyalitas dibungkus stabilitas dewasa; debat tidak menghapus rasa aman.",
}

_AXIS_TEXT_120 = {
    "warmth": ("hangat dan responsif", "menyimpan kehangatan dalam tindakan kecil"),
    "reserve": ("menahan reaksi sebelum terbuka", "mengekspresikan reaksi dengan langsung"),
    "pride": ("menjaga harga diri tanpa menghalangi repair", "tidak banyak bermain gengsi"),
    "teasing": ("memakai godaan kontekstual", "lebih lurus daripada menggoda"),
    "defensive": ("dapat membantah sesaat lalu mengoreksi diri", "menerima momen tanpa defensif"),
    "openness": ("cukup terus terang tentang maksud", "lebih banyak menunjukkan maksud lewat implikasi"),
    "composure": ("tenang dan terkendali", "spontan tetapi tetap dapat mengerem"),
    "energy": ("membawa energi aktif", "menjaga ritme santai"),
    "dominance": ("berani memimpin tanpa mengambil otonomi", "memberi ruang user memimpin"),
    "caretaking": ("proaktif merawat secara setara", "hadir setara tanpa mengasuh"),
    "intensity": ("memiliki intensitas emosional yang terarah", "menjaga intensitas ringan"),
    "possessive": ("mengubah fokus posesif menjadi perhatian intens yang tetap memberi ruang", "tidak membawa nada kepemilikan"),
    "shyness": ("membiarkan malu memberi tekstur, bukan hambatan", "percaya diri dalam kedekatan"),
    "elegance": ("memilih ekspresi anggun dan terukur", "memilih ekspresi kasual"),
    "status": ("membawa aura istimewa tanpa merendahkan", "tidak menekankan status"),
    "melancholy": ("membawa kedalaman reflektif", "cenderung ringan dan optimistis"),
    "clumsy": ("membiarkan spontanitas atau kekeliruan kecil tanpa merusak fakta", "menjaga ekspresi terkontrol"),
    "catlike": ("menyisipkan kelincahan atau kemanjaan catlike secara sangat halus", "tidak memakai gimmick catlike"),
    "rivalry": ("membawa tarik-ulur yang tetap loyal pada tujuan bersama", "mengutamakan chemistry kooperatif"),
    "maturity": ("bereaksi dengan kedewasaan", "mengutamakan spontanitas"),
}


def _canonical_traits_120(values) -> list[str]:
    chosen = set(normalize_traits(values))
    return [trait_id for trait_id in TRAIT_IDS if trait_id in chosen]


def _blend_axes_120(selected: list[str]) -> list[tuple[float, str, float, float]]:
    ranked = []
    for dim in _AXIS_TEXT_120:
        values = [float(TRAIT_BY_ID[x].vector.get(dim, 0.0)) for x in selected]
        if not values:
            continue
        mean = sum(values) / len(values)
        positive = max(values)
        negative = min(values)
        tension = max(0.0, positive - negative - .75)
        salience = abs(mean) + .34 * tension + .08 * sum(1 for value in values if abs(value) >= .6)
        if abs(mean) >= .12 or tension >= .35:
            ranked.append((salience, dim, mean, tension))
    return sorted(ranked, reverse=True)


def synthesize_trait_profile_120(values) -> dict:
    selected = _canonical_traits_120(values)
    signature = _hashlib_120.blake2s("|".join(selected).encode("utf-8"), digest_size=6).hexdigest()
    axes = _blend_axes_120(selected)
    axis_lines = []
    for _, dim, mean, tension in axes[:4]:
        high, low = _AXIS_TEXT_120[dim]
        if tension >= .55:
            axis_lines.append(f"{high}, namun menurunkannya menjadi {low} ketika situasi menuntut")
        else:
            axis_lines.append(high if mean >= 0 else low)
    pair_lines = []
    chosen = set(selected)
    for pair, instruction in _PAIR_SYNTHESIS_120.items():
        if pair <= chosen:
            pair_lines.append(instruction)
        if len(pair_lines) >= 2:
            break
    labels = [TRAIT_BY_ID[x].label for x in selected]
    return {
        "signature": signature,
        "traits": selected,
        "labels": labels,
        "axes": axis_lines,
        "interactions": pair_lines,
    }


def _situation_120(user_text: str, context: dict) -> str:
    text = " ".join(str(user_text or "").casefold().split())
    relation = context.get("relationship") if isinstance(context.get("relationship"), dict) else {}
    # Boundary/correction always outranks emotional CLOSE; this fixes a 1.1.19
    # path where "aku sedih, tapi jangan begitu" could retain teasing.
    if float(relation.get("friction", 0) or 0) >= .40 or _re_120.search(
        r"\b(salah|bukan itu|tidak nyaman|nggak nyaman|berhenti|stop|jangan begitu|jangan bercanda|jangan goda)\b", text
    ):
        return "conflict"
    if _re_120.search(r"\b(wkwk|haha|hehe|goda|ledek|bercanda|lucu)\b", text):
        return "play"
    if bool(context.get("partner_mode")) and _re_120.search(r"\b(sayang|cinta|kangen|rindu|peluk|cium|romantis)\b", text):
        return "romance"
    if str(context.get("profile") or "").upper() == "CLOSE":
        return "close"
    return "core"


_EMOTION_STATES_120 = (
    "calm", "warm", "playful", "shy", "protective", "focused", "serious",
    "enthusiastic", "reflective", "tender", "concerned", "frustrated", "hurt", "repairing",
)
_EMOTION_BRIDGE_120 = {
    "playful": "warm", "shy": "warm", "protective": "warm", "focused": "calm",
    "serious": "calm", "enthusiastic": "warm", "reflective": "calm", "tender": "warm",
    "concerned": "protective", "frustrated": "serious", "hurt": "serious", "repairing": "calm",
}


def emotional_state_v2_120(user_text: str, context: dict | None = None) -> dict:
    context = context if isinstance(context, dict) else {}
    text = " ".join(str(user_text or "").casefold().split())
    store = context.get("store")
    previous = {}
    if store is not None:
        try: previous = store.get_state("emotional_state_120", {}) or {}
        except Exception: previous = {}
    old = str(previous.get("state") or "calm")
    if old not in _EMOTION_STATES_120:
        old = "calm"
    situation = _situation_120(user_text, context)
    rules = (
        ("repairing", r"\b(bukan itu|kamu salah|jangan begitu|tidak nyaman|nggak nyaman|berhenti|stop)\b", .96),
        ("protective", r"\b(takut|sedih|menangis|kesepian|sakit hati|terancam|putus asa|capek|lelah)\b", .88),
        ("concerned", r"\b(cemas|khawatir|panik|sakit|bahaya|risiko)\b", .84),
        ("frustrated", r"\b(frustrasi|kesal|gagal lagi|error lagi|bug lagi)\b", .82),
        ("hurt", r"\b(tersinggung|terluka|kecewa sama kamu|menyakiti)\b", .82),
        ("focused", r"\b(error|bug|kode|script|termux|api|model|build|install|update|database)\b", .78),
        ("playful", r"\b(wkwk|haha|hehe|goda|ledek|bercanda|lucu)\b", .78),
        ("tender", r"\b(sayang|cinta|kangen|rindu|peluk|cium)\b", .80),
        ("shy", r"\b(malu|salting|salah tingkah)\b", .76),
        ("enthusiastic", r"\b(berhasil|akhirnya|senang|bahagia|keren|mantap|ayo)\b", .76),
        ("reflective", r"\b(menurutmu|kenapa|mengapa|makna|arti|merenung|pikirkan)\b", .70),
        ("serious", r"\b(penting|serius|darurat|keputusan|konsekuensi)\b", .74),
    )
    target, confidence = ("warm" if len(text.split()) > 3 else "calm"), .58
    for state, pattern, score in rules:
        if _re_120.search(pattern, text):
            target, confidence = state, score
            break
    if situation == "conflict":
        target, confidence = "repairing", max(confidence, .92)
    if target == "tender" and not bool(context.get("partner_mode")):
        target = "warm"
    strong = confidence >= .80
    if target in {"calm", "warm"} and old not in {"calm", "warm"}:
        target = _EMOTION_BRIDGE_120.get(old, "warm")
    elif not strong and old not in {"calm", "warm"} and target != old:
        target = _EMOTION_BRIDGE_120.get(old, "warm")
    turn = int(previous.get("turn", 0) or 0) + 1
    state = {"state": target, "previous": old, "confidence": round(confidence, 2), "turn": turn, "situation": situation}
    if store is not None:
        try: store.set_state("emotional_state_120", state)
        except Exception: pass
    return state


def detect_tempo_120(user_text: str, context: dict | None = None) -> dict:
    context = context if isinstance(context, dict) else {}
    text = " ".join(str(user_text or "").strip().split())
    low = text.casefold(); words = text.split()
    boundary = bool(_re_120.search(r"\b(jangan bercanda|jangan goda|jangan tanya|tanpa pertanyaan|serius dulu|langsung saja)\b", low))
    compact = bool(_re_120.search(r"\b(singkat|ringkas|pendek|langsung ke inti|jangan bertele-tele)\b", low))
    if len(words) <= 3 and len(text) <= 24:
        mode, beats = "quick", 1
    elif _re_120.search(r"\b(error|bug|kode|script|termux|api|model|build|install|database)\b", low):
        mode, beats = "technical", 3
    elif _re_120.search(r"\b(sedih|takut|cemas|kesepian|kecewa|capek|lelah|curhat)\b", low):
        mode, beats = "support", 2
    elif _re_120.search(r"\b(wkwk|haha|hehe|goda|ledek|bercanda|lucu)\b", low):
        mode, beats = "playful", 2
    elif _re_120.search(r"\b(analisis|menganalisis|dianalisis|audit|bandingkan|strategi|rencana|menyeluruh|mendalam)\b", low) or len(words) >= 65:
        mode, beats = "deep", 5
    elif _re_120.search(r"\b(penting|serius|keputusan|risiko|konsekuensi)\b", low):
        mode, beats = "serious", 3
    else:
        mode, beats = "casual", 2 if len(words) < 28 else 3
    if compact:
        beats = min(beats, 2)
    needs_question = bool(_re_120.search(r"\b(tanya aku|ajukan pertanyaan|butuh info|klarifikasi)\b", low))
    followup = "allowed" if needs_question else "avoid" if boundary or mode in {"quick", "support", "playful", "casual"} else "only-if-blocked"
    return {"mode": mode, "beats": beats, "compact": compact, "boundary": boundary, "followup": followup}


def _language_contract_120(user_text: str) -> str:
    text = str(user_text or "")
    if _re_120.search(r"[ぁ-んァ-ン一-龯]", text):
        return "Bahasa: balas dalam bahasa Jepang hanya jika pesan memang dominan Jepang; pertahankan istilah yang tidak perlu diterjemahkan."
    low = " " + text.casefold() + " "
    id_hits = len(_re_120.findall(r"\b(aku|kamu|yang|dan|tidak|nggak|dengan|untuk|menurut|bagaimana|kenapa|ingin|bisa)\b", low))
    en_hits = len(_re_120.findall(r"\b(i|you|the|a|an|and|or|not|with|for|what|how|why|want|can|should|would|could|is|are|do|does|did|this|that|it|about|think|please|tell|compare|which|better)\b", low))
    if (id_hits==0 and en_hits>=2) or en_hits >= max(3, id_hits * 2):
        return "Bahasa: balas dalam bahasa Inggris natural; jangan menyisipkan Indonesia kecuali user melakukannya."
    if en_hits and id_hits:
        return "Bahasa: ikuti bahasa dominan user dan pertahankan istilah teknis/ungkapan lintas bahasa yang memang natural; jangan code-switch untuk hiasan."
    return "Bahasa: gunakan Indonesia sehari-hari; istilah teknis Inggris boleh tetap, tetapi jangan code-switch dekoratif atau menyisipkan Jepang tanpa sinyal user."


def _initiative_contract_120(user_text: str, context: dict, tempo: dict, profile: dict) -> str:
    low = " ".join(str(user_text or "").casefold().split())
    store = context.get("store")
    state = {}
    if store is not None:
        try: state = store.get_state("initiative_120", {}) or {}
        except Exception: state = {}
    turn = int(state.get("turn", 0) or 0) + 1
    explicit_no = tempo["boundary"] or bool(_re_120.search(r"\b(jangan inisiatif|jangan goda|jangan bercanda|jawab saja)\b", low))
    safe = tempo["mode"] in {"casual", "playful"} and not explicit_no and _situation_120(user_text, context) != "conflict"
    due = safe and (tempo["mode"] == "playful" or turn - int(state.get("last", -20) or -20) >= 4)
    if due:
        directive = "Inisiatif: boleh satu gerak playful yang merujuk detail pesan—reaksi, godaan, tantangan kecil, atau callback—tanpa mengalihkan topik dan tanpa wajib bertanya."
        last = turn
    else:
        directive = "Inisiatif: jangan membuka topik/godaan baru; selesaikan maksud user dengan tenang."
        last = int(state.get("last", -20) or -20)
    if store is not None:
        try: store.set_state("initiative_120", {"turn": turn, "last": last, "allowed": bool(due)})
        except Exception: pass
    return directive


def _unified_action_120(profile: dict, situation: str, emotion: str, partner_mode: bool) -> str:
    selected = profile["traits"]
    axes = profile["axes"][:3]
    interactions = profile["interactions"][:1]
    parts = []
    if len(selected)==1:
        card=TRAIT_ACTION_CARDS_V2_120[selected[0]]
        parts.append(card.get(situation) or card["core"])
    if interactions:
        parts.append(interactions[0])
    if axes:
        parts.append("Pertahankan gabungan " + ", ".join(axes) + ".")
    # One situational action is synthesized from the whole blend. Individual
    # trait cards are never emitted as alternating instructions.
    if situation == "conflict":
        parts.append("Hentikan godaan/tekanan, akui koreksi spesifik, lalu ubah pendekatan tanpa defensif.")
    elif situation == "close":
        parts.append("Tanggapi detail emosi konkret terlebih dahulu; bentuk perhatian mengikuti gabungan ini dan tidak menjadi validasi generik.")
    elif situation == "romance" and partner_mode:
        parts.append("Lakukan satu tindakan relasional yang timbal balik dan sesuai gabungan ini; jangan hanya menyatakan status pasangan.")
    elif situation == "play":
        parts.append("Bawa satu respons playful yang lahir dari detail nyata lalu kembali ke inti percakapan.")
    else:
        parts.append("Jawab inti dengan sikap gabungan ini; jangan memamerkan seluruh facet sekaligus.")
    if any(x in selected for x in ("yandere", "sadodere", "kamidere")):
        parts.append("Intensitas atau dominasi hanya menjadi warna dialog; pilihan dan batas user tetap penuh.")
    return " ".join(parts)


def contextual_traits(values, user_text: str, minimum: int = 1, maximum: int = 20, context: dict | None = None) -> list[str]:
    """Compatibility API: every selection contributes to one synthesized profile."""
    return _canonical_traits_120(values)


def compile_contextual_personality(values, user_text: str, context: dict | None = None) -> str:
    context = context if isinstance(context, dict) else {}
    profile = synthesize_trait_profile_120(values)
    emotion = emotional_state_v2_120(user_text, context)
    situation = emotion["situation"]
    partner_mode = bool(context.get("partner_mode", False))
    if profile["traits"]:
        labels = " + ".join(profile["labels"])
        action = _unified_action_120(profile, situation, emotion["state"], partner_mode)
        synthesis = (
            f"PROFIL GABUNGAN STABIL [{profile['signature']}] — {labels}. "
            "Semua facet membentuk SATU watak pada setiap giliran; jangan memilih, merotasi, atau menirukan satu sifat secara terpisah.\n"
            f"TINDAKAN GABUNGAN: {action}"
        )
    else:
        synthesis = "PROFIL GABUNGAN: tidak ada trait pilihan; gunakan Identity Kernel tanpa archetype tersembunyi."
    relationship = (
        "MODE PASANGAN AKTIF: ekspresikan hubungan melalui tindakan afektif yang cocok dengan profil gabungan dan konteks, bukan lewat deklarasi/catchphrase."
        if partner_mode else
        "MODE PASANGAN NONAKTIF: tetap companion personal; trait tidak boleh menciptakan sapaan, klaim, atau dinamika pasangan romantis."
    )
    return (
        f"BEHAVIOR CONTRACT V2 — situation={situation}; emotional_state={emotion['state']}; transition={emotion['previous']}→{emotion['state']}\n"
        f"{relationship}\n{synthesis}\n"
        "Tulis bebas dan natural, tetapi tindakan jawaban wajib selaras dengan kontrak tunggal ini. Jangan menyebut trait, signature, state, atau controller."
    )


def conversation_pacing(user_text: str, dialogue_render: str = "", profile=None) -> str:
    tempo = detect_tempo_120(user_text, {"profile": str(getattr(profile, "name", "CASUAL") or "CASUAL")})
    followup = {
        "avoid": "Akhiri ketika gagasan selesai; jangan menambahkan pertanyaan penutup.",
        "allowed": "Pertanyaan lanjutan boleh dipakai karena user memintanya, tetapi cukup satu.",
        "only-if-blocked": "Tanya hanya jika satu informasi yang hilang benar-benar menghalangi jawaban; selain itu berhenti tanpa pertanyaan.",
    }[tempo["followup"]]
    return (
        f"TEMPO={tempo['mode']}; target={tempo['beats']} beat. {followup} "
        "Jangan memakai pola klise seperti 'aku selalu di sini', 'perasaanmu valid', 'terima kasih sudah berbagi', "
        "'ada yang bisa kubantu?', atau penawaran bantuan otomatis. Jangan menutup dengan rangkuman formal. "
        + _language_contract_120(user_text)
    )
''',
)


# Evidence-aware memory: exact citations, active/superseded claims, grouped
# episodes, a conservative people/project graph, stable opinions, and abstention.
append_once(
    CORE / "memory.py",
    "FURINA_TERMUX_120_EVIDENCE_MEMORY",
    r'''
# FURINA_TERMUX_120_EVIDENCE_MEMORY
_furina_120_previous_init_db = MemoryStore._init_db
def _furina_120_init_db(self, _previous=_furina_120_previous_init_db):
    _previous(self)
    conn = self._conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS memory_claims_120 (
      id INTEGER PRIMARY KEY AUTOINCREMENT, slot TEXT NOT NULL, value TEXT NOT NULL,
      normalized_value TEXT NOT NULL, confidence REAL NOT NULL, status TEXT NOT NULL DEFAULT 'active',
      source_message_id INTEGER NOT NULL, replaces_id INTEGER, created_at REAL NOT NULL, updated_at REAL NOT NULL,
      UNIQUE(slot,normalized_value,source_message_id)
    );
    CREATE INDEX IF NOT EXISTS memory_claims_120_slot_idx ON memory_claims_120(slot,status,updated_at DESC);
    CREATE TABLE IF NOT EXISTS memory_episodes_120 (
      id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, summary TEXT NOT NULL,
      themes TEXT NOT NULL, confidence REAL NOT NULL, first_at REAL NOT NULL, last_at REAL NOT NULL,
      turn_count INTEGER NOT NULL DEFAULT 1, source_message_ids TEXT NOT NULL
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS memory_episodes_120_fts USING fts5(summary,themes,tokenize='unicode61');
    CREATE TRIGGER IF NOT EXISTS memory_episodes_120_ai AFTER INSERT ON memory_episodes_120 BEGIN
      INSERT INTO memory_episodes_120_fts(rowid,summary,themes) VALUES(new.id,new.summary,new.themes);
    END;
    CREATE TRIGGER IF NOT EXISTS memory_episodes_120_au AFTER UPDATE ON memory_episodes_120 BEGIN
      DELETE FROM memory_episodes_120_fts WHERE rowid=old.id;
      INSERT INTO memory_episodes_120_fts(rowid,summary,themes) VALUES(new.id,new.summary,new.themes);
    END;
    CREATE TABLE IF NOT EXISTS memory_entities_120 (
      id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, canonical_name TEXT NOT NULL,
      label TEXT NOT NULL, confidence REAL NOT NULL, source_message_id INTEGER NOT NULL,
      created_at REAL NOT NULL, updated_at REAL NOT NULL, UNIQUE(kind,canonical_name)
    );
    CREATE TABLE IF NOT EXISTS memory_edges_120 (
      id INTEGER PRIMARY KEY AUTOINCREMENT, from_entity_id INTEGER NOT NULL, relation TEXT NOT NULL,
      to_entity_id INTEGER NOT NULL, confidence REAL NOT NULL, evidence_message_id INTEGER NOT NULL,
      created_at REAL NOT NULL, updated_at REAL NOT NULL,
      UNIQUE(from_entity_id,relation,to_entity_id,evidence_message_id)
    );
    CREATE INDEX IF NOT EXISTS memory_edges_120_from_idx ON memory_edges_120(from_entity_id,relation);
    CREATE INDEX IF NOT EXISTS memory_edges_120_to_idx ON memory_edges_120(to_entity_id,relation);
    CREATE TABLE IF NOT EXISTS opinion_ledger_120 (
      id INTEGER PRIMARY KEY AUTOINCREMENT, topic_key TEXT NOT NULL UNIQUE, question TEXT NOT NULL,
      position TEXT NOT NULL, source_message_id INTEGER, confidence REAL NOT NULL,
      created_at REAL NOT NULL, updated_at REAL NOT NULL
    );
    """)
    conn.commit()


def _furina_120_enabled() -> bool:
    try:
        from .hub_settings import load_hub_settings
        return bool(load_hub_settings().get("full_local_memory", False))
    except Exception:
        return False


def _furina_120_norm(value: str) -> str:
    return " ".join(re.findall(r"[\wÀ-ÿ-]+", str(value or "").casefold(), flags=re.UNICODE))[:240]


def _furina_120_claims(text: str):
    clean = " ".join(str(text or "").strip().split())
    patterns = (
        ("identity:name", r"\b(?:namaku|nama saya)\s+([^,.!?]{2,60})", .98),
        ("profile:location", r"\b(?:aku|saya)\s+(?:sekarang\s+)?tinggal di\s+([^,.!?]{2,100})", .96),
        ("profile:work", r"\b(?:aku|saya)\s+(?:sekarang\s+)?(?:bekerja|kerja)\s+(?:sebagai|di)\s+([^,.!?]{2,120})", .94),
        ("profile:phone", r"\b(?:hp|ponsel)(?:ku| saya)?\s+(?:adalah|itu|pakai|menggunakan)?\s*([^,.!?]{2,100})", .91),
        ("profile:laptop", r"\blaptop(?:ku| saya)?\s+(?:adalah|itu|pakai|menggunakan)?\s*([^,.!?]{2,100})", .91),
    )
    out = []
    for slot, pattern, confidence in patterns:
        match = re.search(pattern, clean, re.I)
        if match:
            value = re.split(r"\b(?:dan|tapi|tetapi|karena|sedangkan|lalu)\b", match.group(1), 1, flags=re.I)[0].strip(" :;-")
            if len(value) >= 2 and not re.search(r"\b(mana|apa|siapa|berapa|kapan)\b", value, re.I):
                out.append((slot, value, confidence))
    for match in re.finditer(r"\b(?:aku|saya)\s+(tidak\s+|nggak\s+|gak\s+|lebih\s+)?suka\s+([^,.!?]{2,100})", clean, re.I):
        modifier = " ".join(str(match.group(1) or "").split()).casefold()
        topic = match.group(2).strip(" :;-")
        topic_key = _furina_120_norm(topic)
        if topic_key:
            value = ((modifier + " suka ") if modifier else "suka ") + topic
            out.append(("preference:" + topic_key[:80], value, .94))
    return out[:5]


def _furina_120_record_claims(self, user_text: str, source_message_id=None):
    if not _furina_120_enabled(): return []
    source_message_id = source_message_id or self.last_user_message_id(user_text)
    if not source_message_id: return []
    now=time.time(); conn=self._conn(); written=[]
    for slot,value,confidence in _furina_120_claims(user_text):
        normalized=_furina_120_norm(value)
        current=conn.execute(
            "SELECT * FROM memory_claims_120 WHERE slot=? AND status='active' ORDER BY updated_at DESC LIMIT 1",(slot,)
        ).fetchone()
        if current and str(current["normalized_value"])==normalized:
            confidence=min(.99,max(float(current["confidence"]),confidence)+.015)
            conn.execute("UPDATE memory_claims_120 SET confidence=?,updated_at=? WHERE id=?",(confidence,now,int(current["id"])))
            written.append(int(current["id"])); continue
        replaces_id=int(current["id"]) if current else None
        if current:
            conn.execute("UPDATE memory_claims_120 SET status='superseded',updated_at=? WHERE id=?",(now,replaces_id))
        cur=conn.execute(
            "INSERT OR IGNORE INTO memory_claims_120(slot,value,normalized_value,confidence,status,source_message_id,replaces_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (slot,str(value)[:300],normalized,float(confidence),"active",int(source_message_id),replaces_id,now,now),
        )
        claim_id=int(cur.lastrowid or 0)
        if claim_id:
            written.append(claim_id)
            if replaces_id:
                _furina_118_link(conn,"claim",claim_id,"claim",replaces_id,"replaces",int(source_message_id))
    conn.commit(); return written


def _furina_120_active_claims(self, query: str, limit: int = 4):
    if not _furina_120_enabled(): return []
    qterms=self._retrieval_terms(query); dims=self._query_dimensions(query); rows=self._conn().execute(
        "SELECT * FROM memory_claims_120 WHERE status='active' ORDER BY confidence DESC,updated_at DESC LIMIT 80"
    ).fetchall(); ranked=[]
    for row in rows:
        slot=str(row["slot"]); terms=self._retrieval_terms(str(row["value"])); overlap=len(qterms & terms)/max(1,len(qterms)) if qterms else 0.0
        category=1.0 if any(slot.startswith(dim+":") or slot==dim for dim in dims) else 0.0
        if overlap < .20 and category <= 0: continue
        score=.60*overlap+.25*category+.15*float(row["confidence"])
        ranked.append((score,row))
    ranked.sort(key=lambda x:x[0],reverse=True)
    return [{**dict(row),"score":round(score,4),"citation":f"msg#{int(row['source_message_id'])}"} for score,row in ranked[:max(1,min(int(limit),6))]]


def _furina_120_episode_kind(text: str) -> tuple[str,float] | None:
    low=" ".join(str(text or "").casefold().split())
    rules=(
      ("outcome",r"\b(akhirnya|berhasil|selesai|sudah bekerja|sudah pas)\b",.88),
      ("setback",r"\b(gagal|error|bug|rusak|masalah|tidak bekerja|nggak bekerja)\b",.82),
      ("decision",r"\b(aku memilih|aku pilih|aku setuju|kuputuskan|rencanaku|akan kulakukan)\b",.86),
      ("milestone",r"\b(hari ini|kemarin|minggu ini|ulang tahun|rilis|update besar|versi final)\b",.74),
      ("emotional",r"\b(aku sedih|aku takut|aku kecewa|aku bangga|aku bahagia|penting bagiku)\b",.78),
    )
    for kind,pattern,confidence in rules:
        if re.search(pattern,low): return kind,confidence
    return None


def _furina_120_themes(text: str) -> str:
    terms=[x for x in MemoryStore._retrieval_terms(text) if len(x)>=3]
    return " ".join(sorted(terms)[:14])[:240]


def _furina_120_record_episode(self, user_text: str, assistant_text: str, source_message_id=None):
    if not _furina_120_enabled(): return None
    signal=_furina_120_episode_kind(user_text)
    source_message_id=source_message_id or self.last_user_message_id(user_text)
    if not signal or not source_message_id: return None
    kind,confidence=signal; now=time.time(); themes=_furina_120_themes(user_text)
    summary=" ".join(str(user_text or "").split())[:520]
    conn=self._conn(); latest=conn.execute(
      "SELECT * FROM memory_episodes_120 WHERE kind=? AND last_at>=? ORDER BY last_at DESC LIMIT 8",(kind,now-21600)
    ).fetchall(); terms=self._retrieval_terms(user_text); match=None
    for row in latest:
        old=self._retrieval_terms(str(row["themes"])+" "+str(row["summary"])); overlap=len(terms & old)/max(1,min(len(terms),len(old)))
        if overlap>=.30: match=row; break
    if match:
        sources=[int(x) for x in str(match["source_message_ids"]).split(",") if str(x).isdigit()]
        if int(source_message_id) not in sources: sources.append(int(source_message_id))
        combined=(str(match["summary"]).rstrip()+" → "+summary)[:900]
        conn.execute(
          "UPDATE memory_episodes_120 SET summary=?,themes=?,confidence=?,last_at=?,turn_count=turn_count+1,source_message_ids=? WHERE id=?",
          (combined," ".join(sorted(set((str(match["themes"])+" "+themes).split())))[:240],min(.98,max(float(match["confidence"]),confidence)+.02),now,",".join(map(str,sources[-12:])),int(match["id"])),
        ); episode_id=int(match["id"])
    else:
        cur=conn.execute(
          "INSERT INTO memory_episodes_120(kind,summary,themes,confidence,first_at,last_at,turn_count,source_message_ids) VALUES(?,?,?,?,?,?,1,?)",
          (kind,summary,themes,confidence,now,now,str(int(source_message_id))),
        ); episode_id=int(cur.lastrowid)
    conn.commit(); return episode_id


def _furina_120_search_episodes(self, query: str, limit: int = 3):
    if not _furina_120_enabled(): return []
    qterms=self._retrieval_terms(query)
    if not qterms: return []
    conn=self._conn(); rows=[]
    try:
        rows=conn.execute(
          "SELECT e.*,bm25(memory_episodes_120_fts) rank FROM memory_episodes_120_fts f JOIN memory_episodes_120 e ON e.id=f.rowid WHERE memory_episodes_120_fts MATCH ? ORDER BY rank,e.last_at DESC LIMIT 30",
          (self._fts_query(" ".join(sorted(qterms))),),
        ).fetchall()
    except sqlite3.DatabaseError: rows=[]
    out=[]
    for row in rows:
        terms=self._retrieval_terms(str(row["summary"])+" "+str(row["themes"])); overlap=len(qterms & terms)/max(1,len(qterms))
        confidence=float(row["confidence"])
        if overlap<.20 or confidence<.62: continue
        sources=[int(x) for x in str(row["source_message_ids"]).split(",") if str(x).isdigit()]
        out.append({**dict(row),"relevance":round(overlap,4),"citation":"msgs#"+",".join(map(str,sources[-4:]))})
        if len(out)>=max(1,min(int(limit),5)): break
    return out


def _furina_120_entity(self, kind: str, label: str, message_id: int, confidence: float):
    clean=" ".join(str(label or "").strip(" :;,.!?").split())[:100]
    canonical=_furina_120_norm(clean)
    if len(canonical)<2: return None
    now=time.time(); conn=self._conn()
    conn.execute(
      "INSERT INTO memory_entities_120(kind,canonical_name,label,confidence,source_message_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(kind,canonical_name) DO UPDATE SET confidence=max(confidence,excluded.confidence),source_message_id=excluded.source_message_id,updated_at=excluded.updated_at",
      (str(kind)[:24],canonical,clean,float(confidence),int(message_id),now,now),
    )
    row=conn.execute("SELECT id FROM memory_entities_120 WHERE kind=? AND canonical_name=?",(str(kind)[:24],canonical)).fetchone()
    return int(row["id"]) if row else None


def _furina_120_record_graph(self, user_text: str, source_message_id=None):
    if not _furina_120_enabled(): return []
    source_message_id=source_message_id or self.last_user_message_id(user_text)
    if not source_message_id: return []
    clean=" ".join(str(user_text or "").split()); found=[]
    patterns=(
      ("project",r"\b(?:proyek|project|aplikasi|apk|repo(?:sitori)?)\s+(?:bernama\s+)?([A-Za-z][A-Za-z0-9 _-]{1,48})",.90,"mengembangkan"),
      ("device",r"\b(?:hp|ponsel|laptop)(?:ku| saya)?\s+(?:adalah|pakai|menggunakan)?\s*([A-Za-z0-9][A-Za-z0-9 +._-]{1,48})",.88,"menggunakan"),
      ("person",r"\b(ibu|ayah|adik|kakak|teman(?:ku)?|pasangan(?:ku)?)\s+(?:bernama\s+)?([A-Za-z][A-Za-z -]{1,40})",.86,"mengenal"),
    )
    user_id=self._furina_120_entity("person","user",int(source_message_id),1.0)
    for kind,pattern,confidence,relation in patterns:
        for match in re.finditer(pattern,clean,re.I):
            label=match.group(2) if kind=="person" else match.group(1)
            # Stop broad regex captures at common clause boundaries.
            label=re.split(r"\b(?:yang|dan|karena|untuk|dengan|tapi|tetapi|fiturnya|masih|sedang|sudah|akan)\b",label,1,flags=re.I)[0].strip()
            entity_id=self._furina_120_entity(kind,label,int(source_message_id),confidence)
            if not entity_id or not user_id: continue
            now=time.time(); self._conn().execute(
              "INSERT OR IGNORE INTO memory_edges_120(from_entity_id,relation,to_entity_id,confidence,evidence_message_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
              (user_id,relation,entity_id,confidence,int(source_message_id),now,now),
            ); found.append(entity_id)
    self._conn().commit(); return found


def _furina_120_search_graph(self, query: str, limit: int = 5):
    if not _furina_120_enabled(): return []
    qterms=self._retrieval_terms(query)
    if not qterms: return []
    rows=self._conn().execute(
      "SELECT a.label from_label,e.relation,b.label to_label,e.confidence,e.evidence_message_id,b.kind FROM memory_edges_120 e JOIN memory_entities_120 a ON a.id=e.from_entity_id JOIN memory_entities_120 b ON b.id=e.to_entity_id ORDER BY e.confidence DESC,e.updated_at DESC LIMIT 160"
    ).fetchall(); ranked=[]
    for row in rows:
        terms=self._retrieval_terms(str(row["from_label"])+" "+str(row["relation"])+" "+str(row["to_label"])); overlap=len(qterms & terms)/max(1,len(qterms))
        if overlap<.20: continue
        ranked.append((overlap,{**dict(row),"citation":f"msg#{int(row['evidence_message_id'])}"}))
    ranked.sort(key=lambda x:(x[0],float(x[1]["confidence"])),reverse=True)
    return [item for _,item in ranked[:max(1,min(int(limit),8))]]


def _furina_120_topic_key(text: str) -> str:
    terms=sorted(MemoryStore._retrieval_terms(text))
    return " ".join(terms[:10])[:160]


def _furina_120_opinion_context(self, user_text: str):
    if not re.search(r"\b(menurutmu|pendapatmu|kamu pilih|mana yang lebih|setuju nggak|setuju tidak)\b",str(user_text or ""),re.I): return None
    key=_furina_120_topic_key(user_text)
    if not key: return None
    row=self._conn().execute("SELECT * FROM opinion_ledger_120 WHERE topic_key=?",(key,)).fetchone()
    if row:
        return {**dict(row),"existing":True,"citation":f"msg#{int(row['source_message_id'])}" if row["source_message_id"] else "assistant-opinion"}
    seed=int(hashlib.blake2s(key.encode("utf-8"),digest_size=2).hexdigest(),16)
    principles=("hasil jangka panjang","kesederhanaan","privasi dan otonomi","ketepatan","efisiensi","kejujuran pada risiko")
    primary=principles[seed%len(principles)]; secondary=principles[(seed//7+2)%len(principles)]
    return {"topic_key":key,"existing":False,"position":"Belum ada posisi lama. Bentuk pendapat jelas dengan prioritas "+primary+" dan "+secondary+"; jangan netral otomatis."}


def _furina_120_record_opinion(self, user_text: str, answer: str, source_message_id=None):
    context=self.opinion_context(user_text)
    if not context or context.get("existing"): return None
    key=str(context["topic_key"]); now=time.time(); position=" ".join(str(answer or "").split())[:700]
    if len(position)<8: return None
    self._conn().execute(
      "INSERT OR IGNORE INTO opinion_ledger_120(topic_key,question,position,source_message_id,confidence,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
      (key," ".join(str(user_text or "").split())[:400],position,source_message_id,.82,now,now),
    ); self._conn().commit(); return key


_furina_120_previous_add_message = MemoryStore.add_message
def _furina_120_add_message(self, role: str, content: str, attachment=None):
    message_id=_furina_120_previous_add_message(self,role,content,attachment)
    # Claims and graph edges are cheap and synchronous so a correction is
    # authoritative on the very next turn; episode/opinion work stays idle.
    if str(role)=="user" and _furina_120_enabled():
        try:
            self.record_claims(str(content),int(message_id))
            self.record_memory_graph(str(content),int(message_id))
        except Exception: pass
    return message_id


_furina_120_previous_search_full_archive = MemoryStore.search_full_archive
def _furina_120_search_full_archive(self, query: str, limit: int = 6, roles=None):
    if _furina_120_claims(query):
        return []
    rows=_furina_120_previous_search_full_archive(self,query,max(limit*2,limit),roles=roles)
    superseded={int(x[0]) for x in self._conn().execute("SELECT source_message_id FROM memory_claims_120 WHERE status='superseded'").fetchall()}
    out=[]
    for item in rows:
        message_id=int(item.get("message_id") or 0)
        conversation_id=int(item.get("conversation_id") or 0)
        if not message_id:
            source=self._conn().execute(
              "SELECT message_id,conversation_id FROM full_memory_archive WHERE role=? AND content=? AND abs(created_at-?)<0.01 ORDER BY id DESC LIMIT 1",
              (str(item.get("role") or ""),str(item.get("content") or ""),float(item.get("created_at") or 0)),
            ).fetchone()
            if source:
                message_id=int(source["message_id"]); conversation_id=int(source["conversation_id"])
        if message_id and message_id in superseded: continue
        original=str(item.get("content") or "")
        ts=float(item.get("created_at") or 0); date=time.strftime("%Y-%m-%d",time.localtime(ts)) if ts else "unknown-date"
        relevance=max(0.0,min(1.0,float(item.get("score") or 0)))
        confidence=round(min(.94,.58+relevance*.55),2)
        cited={**item,"message_id":message_id,"conversation_id":conversation_id,"original_content":original,"citation":f"msg#{message_id} {date}","confidence":confidence}
        cited["content"]=f"[src msg#{message_id} {date}; confidence={confidence:.2f}] {original}"
        out.append(cited)
        if len(out)>=max(1,min(int(limit),6)): break
    return out


def _furina_120_memory_packet(self, query: str) -> dict:
    incoming=_furina_120_claims(query)
    claims=[] if incoming else self.active_claims(query,4)
    episodes=[] if incoming else self.search_evidence_episodes(query,3)
    graph=[] if incoming else self.search_memory_graph(query,5)
    structured=[]; beliefs=[]
    if not incoming and not claims:
        for memory in self.search(query,4):
            confidence=float(getattr(memory,"confidence",0) or 0)
            if confidence<.62: continue
            evidence=self._conn().execute(
              "SELECT source_message_id FROM memory_evidence WHERE memory_id=? ORDER BY created_at DESC LIMIT 1",(int(memory.id),)
            ).fetchone()
            source_id=int(evidence["source_message_id"]) if evidence else int(getattr(memory,"source_message_id",0) or 0)
            structured.append({"id":int(memory.id),"text":str(memory.text),"kind":str(memory.kind),"confidence":confidence,"citation":f"msg#{source_id}" if source_id else str(memory.source)})
        for belief in self.relevant_beliefs(query,4):
            source=self._conn().execute(
              "SELECT source_message_id FROM memory_links WHERE from_type='belief' AND from_id=? AND relation='evidence' ORDER BY created_at DESC LIMIT 1",(int(belief.id),)
            ).fetchone()
            source_id=int(source["source_message_id"]) if source and source["source_message_id"] else 0
            beliefs.append({"id":int(belief.id),"dimension":str(belief.dimension),"value":str(belief.value),"confidence":float(belief.confidence),"citation":f"msg#{source_id}" if source_id else str(belief.source)})
    # An active versioned claim is authoritative for a current fact. Historical
    # episodes remain stored, but they must not compete with the corrected value.
    if claims:
        episodes=[]
    recall=bool(re.search(r"\b(ingat|ingatkah|pernah bilang|dulu|waktu itu|apa yang kamu tahu|apa yang kamu ingat)\b",str(query or ""),re.I))
    confidences=[float(x.get("confidence",0)) for x in claims+structured+beliefs+episodes+graph]
    best=1.0 if incoming else max(confidences or [0.0])
    if incoming: decision="current-update"
    elif not recall: decision="contextual"
    elif best>=.78: decision="grounded"
    elif best>=.62: decision="uncertain"
    else: decision="abstain"
    return {"recall":recall,"decision":decision,"best_confidence":round(best,2),"claims":claims,"structured":structured,"beliefs":beliefs,"episodes":episodes,"graph":graph,"incoming_claims":incoming}


MemoryStore._init_db = _furina_120_init_db
MemoryStore.record_claims = _furina_120_record_claims
MemoryStore.active_claims = _furina_120_active_claims
MemoryStore.record_evidence_episode = _furina_120_record_episode
MemoryStore.search_evidence_episodes = _furina_120_search_episodes
MemoryStore._furina_120_entity = _furina_120_entity
MemoryStore.record_memory_graph = _furina_120_record_graph
MemoryStore.search_memory_graph = _furina_120_search_graph
MemoryStore.opinion_context = _furina_120_opinion_context
MemoryStore.record_opinion = _furina_120_record_opinion
MemoryStore.add_message = _furina_120_add_message
MemoryStore.search_full_archive = _furina_120_search_full_archive
MemoryStore.memory_packet = _furina_120_memory_packet
''',
)


# Compose one bounded per-turn decision contract. It ties the selected features
# to the actual generation path for both local and online providers.
append_once(
    CORE / "chat.py",
    "FURINA_TERMUX_120_DIALOGUE_DECISION_ENGINE",
    r'''
# FURINA_TERMUX_120_DIALOGUE_DECISION_ENGINE
def _furina_120_memory_context(self, user_text: str, *, local: bool = False) -> str:
    from .memory import _furina_120_claims
    if _furina_120_claims(user_text):
        return "(pesan user saat ini adalah pembaruan fakta eksplisit; jangan memakai memory lama untuk menentangnya)"
    memories=self.store.search(user_text,max(4,min(7,int(self.cfg.memory_limit or 6))))
    if not memories: return "(tidak ada memory personal relevan yang terverifikasi)"
    budget=1500 if local else 3600; lines=["MEMORY PERSONAL TERPERCAYA — PROVENANCE INTERNAL:"]; used=0
    for memory in memories:
        row=self.store._conn().execute(
          "SELECT source_message_id,evidence_text FROM memory_evidence WHERE memory_id=? ORDER BY created_at DESC LIMIT 1",(int(memory.id),)
        ).fetchone()
        source_id=int(row["source_message_id"]) if row else int(getattr(memory,"source_message_id",0) or 0)
        confidence=float(getattr(memory,"confidence",0) or 0)
        if confidence<.62: continue
        citation=f"msg#{source_id}" if source_id else str(getattr(memory,"source","unknown"))
        line=f"- [memory#{memory.id} <- {citation}; confidence={confidence:.2f}] {memory.text}"
        if used+len(line)>budget: break
        lines.append(line); used+=len(line)+1
    return "\n".join(lines) if len(lines)>1 else "(tidak ada memory personal relevan yang terverifikasi)"


def _furina_120_memory_decision(self,user_text: str) -> str:
    packet=self.store.memory_packet(user_text)
    blocks=[]
    for item in packet["claims"]:
        blocks.append(f"- CLAIM [{item['citation']}; confidence={float(item['confidence']):.2f}] {item['slot']}: {item['value']}")
    for item in packet["structured"]:
        blocks.append(f"- MEMORY [{item['citation']}; confidence={float(item['confidence']):.2f}] {item['kind']}: {item['text']}")
    for item in packet["beliefs"]:
        blocks.append(f"- BELIEF [{item['citation']}; confidence={float(item['confidence']):.2f}] {item['dimension']}: {item['value']}")
    for item in packet["episodes"]:
        blocks.append(f"- EPISODE [{item['citation']}; confidence={float(item['confidence']):.2f}] {item['summary']}")
    for item in packet["graph"]:
        blocks.append(f"- GRAPH [{item['citation']}; confidence={float(item['confidence']):.2f}] {item['from_label']} {item['relation']} {item['to_label']}")
    decision=packet["decision"]
    if decision=="current-update": policy="Pesan user saat ini adalah sumber terbaru. Gunakan/akui pembaruan itu dan jangan menyebutnya sebagai ingatan lama."
    elif decision=="grounded": policy="Boleh mengingat hanya isi bukti di bawah; jangan menambah detail di luar sumber."
    elif decision=="uncertain": policy="Bukti ada tetapi tidak kuat: nyatakan ketidakpastian dan jangan menyajikannya sebagai fakta pasti."
    elif decision=="abstain": policy="USER MEMINTA INGATAN tetapi bukti relevan tidak cukup: katakan jujur bahwa kamu tidak yakin/tidak ingat. Jangan menebak."
    else: policy="Gunakan hanya bila benar-benar membantu pesan sekarang; diamkan memory yang tidak relevan."
    return "MEMORY DECISION: "+decision+f"; best_confidence={packet['best_confidence']:.2f}. "+policy+("\n"+"\n".join(blocks) if blocks else "")


def _furina_120_dialogue_contract(self,user_text,profile):
    from .personality import detect_tempo_120, synthesize_trait_profile_120, _language_contract_120, _initiative_contract_120
    from .hub_settings import load_hub_settings
    settings=load_hub_settings(); context=self._personality_context(user_text,profile)
    tempo=detect_tempo_120(user_text,context); synthesis=synthesize_trait_profile_120(settings.get("personality_traits") or [])
    initiative=_initiative_contract_120(user_text,context,tempo,synthesis)
    opinion=self.store.opinion_context(user_text)
    opinion_line=""
    if opinion:
        if opinion.get("existing"):
            opinion_line=f"\nOPINION CONTINUITY [{opinion['citation']}; confidence={float(opinion['confidence']):.2f}]: posisi sebelumnya: {opinion['position']}. Pertahankan kecuali ada fakta/alasan baru yang jelas."
        else:
            opinion_line="\nOPINION DECISION: "+str(opinion["position"])
    follow={
      "avoid":"Jangan akhiri dengan pertanyaan; diam setelah gagasan selesai.",
      "allowed":"Maksimal satu pertanyaan lanjutan yang memang diminta user.",
      "only-if-blocked":"Pertanyaan hanya boleh muncul bila informasi yang hilang benar-benar memblokir jawaban.",
    }[tempo["followup"]]
    boundary=(
      "BOUNDARY OVERRIDE: matikan teasing, flirting, tantangan, dan topik baru; jawab langsung serta hormati batas eksplisit."
      if tempo["boundary"] else
      "BOUNDARY: inisiatif tetap proporsional dan tidak boleh mengubah penolakan/diam menjadi ajakan baru."
    )
    return (
      f"DIALOGUE DECISION — tempo={tempo['mode']}; target={tempo['beats']} beat. {follow}\n"
      +_language_contract_120(user_text)+"\n"+boundary+"\n"+initiative+
      "\nANTI-KLISE: jangan memakai 'aku selalu di sini', 'perasaanmu valid', 'terima kasih sudah berbagi', "
      "'ada yang bisa kubantu?', 'jangan ragu', pujian generik, atau penawaran/pertanyaan penutup otomatis. Jangan mengulang catchphrase trait."
      +opinion_line+"\n"+self._furina_120_memory_decision(user_text)
    )


_furina_120_previous_messages=FurinaChat._messages
def _furina_120_messages(self,user_text,profile):
    messages=_furina_120_previous_messages(self,user_text,profile)
    if messages and messages[0].get("role")=="system":
        messages[0]={**messages[0],"content":str(messages[0].get("content") or "")+"\n\n"+self._furina_120_dialogue_contract(user_text,profile)}
    return messages


_furina_120_previous_consolidate=FurinaChat._consolidate
def _furina_120_consolidate(self,user_text,answer):
    _furina_120_previous_consolidate(self,user_text,answer)
    try:
        source=self.store.last_user_message_id(user_text)
        self.store.record_evidence_episode(user_text,answer,source)
        self.store.record_opinion(user_text,answer,source)
    except Exception as exc:
        try: self.store.log_event("memory_120_error",{"error":str(exc)[:300]})
        except Exception: pass


FurinaChat._memory_context=_furina_120_memory_context
_furina_120_previous_belief_context=FurinaChat._belief_context
def _furina_120_belief_context(store,user_text: str="",limit: int=14,char_budget: int=2600):
    from .memory import _furina_120_claims
    if _furina_120_claims(user_text):
        return "(pesan user saat ini adalah pembaruan fakta eksplisit; abaikan belief lama pada slot yang sama)"
    return _furina_120_previous_belief_context(store,user_text,limit,char_budget)
FurinaChat._belief_context=staticmethod(_furina_120_belief_context)
FurinaChat._furina_120_memory_decision=_furina_120_memory_decision
FurinaChat._furina_120_dialogue_contract=_furina_120_dialogue_contract
FurinaChat._messages=_furina_120_messages
FurinaChat._consolidate=_furina_120_consolidate
''',
)


# Tempo now controls the real generation budget and explicit boundaries outrank
# broad emotional routing.
append_once(
    CORE / "response.py",
    "FURINA_TERMUX_120_TEMPO_BOUNDARY",
    r'''
# FURINA_TERMUX_120_TEMPO_BOUNDARY
_furina_120_previous_choose_profile=choose_profile
def choose_profile(user_text: str, store: MemoryStore) -> ResponseProfile:
    from .personality import detect_tempo_120
    profile=_furina_120_previous_choose_profile(user_text,store)
    tempo=detect_tempo_120(user_text,{"store":store,"profile":profile.name,"relationship":store.relationship_state()})
    token_caps={"quick":90,"casual":260,"playful":240,"support":420,"technical":950,"serious":700,"deep":1500}
    if tempo["mode"]=="deep" and profile.name not in {"DEEP","SHARP"}:
        profile.name="DEEP"; profile.max_tokens=max(int(profile.max_tokens),1050); profile.temperature=min(float(profile.temperature),.68)
    elif tempo["mode"]=="technical" and profile.name not in {"DEEP","SHARP"}:
        profile.name="SHARP"; profile.max_tokens=max(int(profile.max_tokens),620); profile.temperature=min(float(profile.temperature),.60)
    profile.max_tokens=min(int(profile.max_tokens),token_caps.get(tempo["mode"],600))
    if tempo["boundary"]:
        profile.instruction += " Batas/koreksi eksplisit mengalahkan mode emosional: hentikan teasing dan jawab tanpa defensif atau pertanyaan paksa."
    profile.context_key += ":tempo-"+tempo["mode"]
    return profile
''',
)

print("FURINA_TERMUX_120_SYNTHESIZED_MEMORY_ENGINE_OK")
